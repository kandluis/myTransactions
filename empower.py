import mintotp
import requests
import getpass
import json
import re
import os

from dateutil.relativedelta import relativedelta
from datetime import datetime, date

from typing import cast, Mapping, get_args, Self
import logging

from empower_types import (
    AccountsData,
    Response,
    TChallengeMethod,
    TransactionData,
)


logger = logging.getLogger(__name__)


class PersonalCapitalSessionExpiredException(RuntimeError):
    pass


class PersonalCapital:
    _ROOT_URL: str = "https://pc-api.empower-retirement.com"
    _USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
    )

    _csrf: str | None
    _email: str | None  # Only set on successful login.
    session: requests.Session

    def __init__(self) -> None:
        self._csrf = None
        self._email = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": PersonalCapital._USER_AGENT})

    def _api_request(
        self,
        method: str,
        path: str,
        data: Mapping[str, str] = {},
        check_success: bool = True,
    ) -> Response:
        response = self.session.request(
            method=method,
            url=os.path.join(PersonalCapital._ROOT_URL, path.lstrip("/")),
            data={**data, "csrf": self._csrf, "apiClient": "WEB"},
        )
        resp_txt = response.text

        is_json_resp = re.match(
            "text/json|application/json", response.headers.get("content-type", "")
        )

        if response.status_code != requests.codes.ok or not is_json_resp:
            logger.error(f"__api_request failed response: {resp_txt}")
            raise RuntimeError(
                f"Request for {path} {data} failed: \
                {response.status_code} {response.headers}"
            )

        json_res: Response = json.loads(resp_txt)

        if (
            check_success
            and json_res.get("spHeader", {}).get("success", False) is False
        ):
            resp_code = (
                json_res.get("spHeader", {}).get("errors", [{}])[0].get("code", None)
            )
            if resp_code == 201:
                self._csrf = None
                raise PersonalCapitalSessionExpiredException(
                    f'Login session expired {json_res["spHeader"]}'
                )
            raise RuntimeError(
                f'API request seems to have failed: {json_res["spHeader"]}'
            )

        return json_res

    def is_logged_in(self) -> bool:
        """Returns true if logged in."""
        if self._email is None:
            return False

        try:
            self.get_account_data()
            return True
        except PersonalCapitalSessionExpiredException:
            return False

    def get_transaction_data(
        self,
        start_date: date | None,
        end_date: date = datetime.now() + relativedelta(months=1),
    ) -> TransactionData:
        resp = self._api_request(
            "post",
            path="/api/transaction/getUserTransactions",
            data={
                "startDate": start_date.strftime("%Y-%m-%d") if start_date else "",
                "endDate": end_date.strftime("%Y-%m-%d"),
            },
        )
        return cast(TransactionData, resp["spData"])

    def get_account_data(self) -> AccountsData:
        resp = self._api_request("post", "/api/newaccount/getAccounts2")
        return cast(AccountsData, resp["spData"])

    def login(
        self,
        email: str,
        password: str,
    ) -> Self:
        """
        Login using API calls.

        Args:
            email: The email (username) to use for logging in.
            password: The password for the account. Unencrypted.

        Returns:
            Instance of class after logging in.
        """
        # Step 1: Initial Authentication
        auth_url = "https://pc-api.empower-retirement.com/api/auth/multiauth/noauth/authenticate"
        auth_payload = {
            "deviceFingerPrint": "f48762cc9379ddfb9bcd07c8d3cce772",
            "userAgent": PersonalCapital._USER_AGENT,
            "language": "en-US",
            "hasLiedLanguages": False,
            "hasLiedResolution": False,
            "hasLiedOs": False,
            "hasLiedBrowser": False,
            "userName": email,
            "password": password,
            "flowName": "mfa",
            "accu": "MYERIRA",
        }
        response = self.session.post(auth_url, json=auth_payload)
        response.raise_for_status()
        auth_response = response.json()

        if not auth_response.get("success"):
            raise RuntimeError(f"Initial authentication failed: {auth_response}")

        id_token = auth_response.get("idToken")
        if not id_token:
            raise RuntimeError(
                f"Could not get idToken from auth response: {auth_response}"
            )

        # Step 2: Token Authentication
        token_auth_endpoint = "/api/credential/authenticateToken"
        # This request is expected to fail with "Authorization required"
        resp = self._api_request(
            "post",
            token_auth_endpoint,
            data={"idToken": id_token},
            check_success=False,
        )

        sp_header = resp.get("spHeader", {})
        if sp_header.get("success") is True:
            # It means 2FA is not needed, which is unlikely but possible.
            self._email = email
            self._csrf = sp_header.get("csrf")
            return self

        errors = sp_header.get("errors", [])
        auth_required = any(
            e.get("code") == 200 and "Authorization required" in e.get("message", "")
            for e in errors
        )

        if not auth_required:
            raise RuntimeError(
                f"Token authentication failed for an unexpected reason: {sp_header}"
            )

        self._csrf = sp_header.get("csrf")
        if not self._csrf:
            raise RuntimeError(
                f"Could not get CSRF token from token auth response: {sp_header}"
            )

        # Step 3: Challenge SMS
        challenge_endpoint = "/api/credential/challengeSmsFreemium"
        challenge_data = {
            "challengeReason": "DEVICE_AUTH",
            "challengeMethod": "OP",
            "bindDevice": "false",
        }
        self._api_request("post", challenge_endpoint, challenge_data)

        # Step 4: Authenticate SMS
        sms_code = os.getenv("SMS_CODE") or input("Enter SMS code: ")
        auth_sms_endpoint = "/api/credential/authenticateSmsFreemium"
        auth_sms_data = {
            "code": sms_code,
            "challengeReason": "DEVICE_AUTH",
            "challengeMethod": "OP",
            "bindDevice": "false",
        }
        self._api_request("post", auth_sms_endpoint, auth_sms_data)

        self._email = email

        return self
