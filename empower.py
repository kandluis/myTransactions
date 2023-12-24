import mintotp  # type: ignore
import requests
import getpass
import json
import re
import os

from constants import TMFAMethod
from typing import Mapping, Optional, Literal, get_args
from typing_extensions import Self
import logging


logger = logging.getLogger(__name__)


TChallengeMethod = Literal["OP", "TP", "TOTP"]


class PersonalCapitalSessionExpiredException(RuntimeError):
    pass


class PersonalCapital:
    _ROOT_URL: str = "https://home.personalcapital.com"
    _USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
    )
    _CHALLENGE_METHOD: dict[TMFAMethod, TChallengeMethod] = {
        "email": "OP",
        "phone": "OP",
        "sms": "OP",
        "totp": "TP",
    }
    _AUTH_ENDPOINT: dict[TMFAMethod, str] = {
        "email": "authenticateEmailByCode",
        "phone": "authenticatePhone",
        "sms": "authenticateSms",
        "totp": "authenticateTotpCode",
    }
    _AUTH_METHOD: dict[TMFAMethod, TChallengeMethod] = {
        "email": "OP",
        "phone": "OP",
        "sms": "OP",
        "totp": "TOTP",
    }

    _csrf: Optional[str]
    _email: Optional[str]  # Only set on successful login.
    session: requests.Session

    def __init__(self) -> None:
        self._csrf = None
        self._email = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": PersonalCapital._USER_AGENT})

    def api_request(
        self, method: str, path: str, data: Mapping[str, str] = {}
    ) -> dict[str, str]:
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
            logger.error(f"_api_request failed response: {resp_txt}")
            raise RuntimeError(
                f"Request for {path} {data} failed: \
                {response.status_code} {response.headers}"
            )

        json_res = json.loads(resp_txt)

        if json_res.get("spHeader", {}).get("success", False) is False:
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
            self.get_accounts()
            return True
        except PersonalCapitalSessionExpiredException:
            return False

    def get_transactions(
        self, start_date: str = "2007-01-01", end_date: str = "2030-01-01"
    ) -> list[dict[str, str]]:
        resp = self.api_request(
            "post",
            path="/api/transaction/getUserTransactions",
            data={"startDate": start_date, "endDate": end_date},
        )

        return resp["spData"]["transactions"]

    def get_accounts(self) -> dict[str, str]:
        resp = self.api_request("post", "/api/newaccount/getAccounts2")

        return resp["spData"]

    def _handle_mfa(self, mfa_method: TMFAMethod, mfa_token: Optional[str]) -> None:
        """Handles MFA.

        Args:
            mfa_method: The method to use. Fully automated option is 'totp'.
                All other methods required some user input.
            mfa_token: The secret token to use. Required if mfa_method is 'totp',
                otherwise ignored.
        """
        challenge_endpoint = f"/api/credential/challenge{mfa_method.capitalize()}"
        challenge_data = {
            "challengeReason": "DEVICE_AUTH",
            "challengeMethod": PersonalCapital._CHALLENGE_METHOD[mfa_method],
            "bindDevice": "false",
        }
        self.api_request("post", challenge_endpoint, challenge_data)
        if mfa_method == "totp":
            if not mfa_token:
                raise ValueError(f"Specified mfa_method: {mfa_method} without token.")
            breakpoint()
            auth_data = {"totpCode": mintotp.totp(mfa_token, digest="sha512")}
        else:
            auth_data = {"code": getpass.getpass("Enter 2 factor code: ")}

        auth_endpoint = f"/api/credential/{PersonalCapital._AUTH_ENDPOINT[mfa_method]}"
        auth_data = {
            "challengeReason": "DEVICE_AUTH",
            "challengeMethod": PersonalCapital._AUTH_METHOD[mfa_method],
            "bindDevice": "false",
            **auth_data,
        }
        self.api_request("post", auth_endpoint, auth_data)

    def login(
        self,
        email: str,
        password: str,
        mfa_method: TMFAMethod = "totp",
        mfa_token: Optional[str] = None,
    ) -> Self:
        """
        Login using API calls.

        Args:
            email: The email (username) to use for logging in.
            password: The password for the account. Unencrypted.
            mfa_method: The MFA method to use for 2-factor. 'totp' is fully automated.
                The other methods required interactively inputting the generated code.
            mfa_token: Required if MFA method is 'totp'. This is the secret usd to
                generate the TOPT token.

        Returns:
            Instance of class after logging in.
        """
        if mfa_method not in get_args(TMFAMethod):
            raise ValueError(f"Auth method {mfa_method} is not supported")

        self._csrf = re.search(
            "csrf *= *'([-a-z0-9]+)'", self.session.get(PersonalCapital._ROOT_URL).text
        ).groups()[0]

        identify_endpoint = "/api/login/identifyUser"
        identify_data = {"username": email}
        resp = self.api_request("post", identify_endpoint, identify_data)
        self._csrf = resp.get("spHeader", {}).get("csrf")

        if resp.get("spHeader", {}).get("authLevel") != "USER_REMEMBERED":
            self._handle_mfa(mfa_method, mfa_token)

        password_endpoint = "/api/credential/authenticatePassword"
        password_data = {
            "bindDevice": "true",
            "deviceName": "API script",
            "passwd": password,
        }
        resp = self.api_request("post", password_endpoint, password_data)

        self._email = email

        return self
