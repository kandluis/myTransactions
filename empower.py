import requests
import getpass
import json
import re
import os
from typing import Mapping, Optional
import logging


logger = logging.getLogger(__name__)


class PersonalCapitalSessionExpiredException(RuntimeError):
    pass


class PersonalCapital:
    _ROOT_URL: str = "https://home.personalcapital.com"
    _USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"

    _csrf: Optional[str]
    session: requests.Session

    def __init__(self) -> None:
        self._csrf = None
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
                f"Request for {path} {data} failed: {response.status_code} {response.headers}"
            )

        json_res = json.loads(resp_txt)

        if json_res.get("spHeader", {}).get("success", False) is False:
            if (
                json_res.get("spHeader", {}).get("errors", [{}])[0].get("code", None)
                == 201
            ):
                self._csrf = None
                raise PersonalCapitalSessionExpiredException(
                    f'Login session expired {json_res["spHeader"]}'
                )
            raise RuntimeError(
                f'API request seems to have failed: {json_res["spHeader"]}'
            )

        return json_res

    def is_logged_in(self) -> bool:
        if self._csrf is None:
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

    def login(
        self,
        email: str,
        password: str,
        auth_method: str = "sms",
        get_two_factor_code_func=lambda: getpass.getpass("Enter 2 factor code: "),
    ) -> "PersonalCapital":
        """
        Login using API calls. If this doesn't work, try login_via_browser().

        You should run this function interactively at least once so you can supply the 2 factor authentication
        code interactively.
        """
        if auth_method not in ("sms", "email"):
            raise ValueError(f"Auth method {auth_method} is not supported")

        self._csrf = re.search(
            "csrf *= *'([-a-z0-9]+)'", self.session.get(PersonalCapital._ROOT_URL).text
        ).groups()[0]

        resp = self.api_request("post", "/api/login/identifyUser", {"username": email})

        # update to the new csrf
        self._csrf = resp.get("spHeader", {}).get("csrf")

        if resp.get("spHeader", {}).get("authLevel") != "USER_REMEMBERED":
            self.api_request(
                "post",
                "/api/credential/challenge"
                + ("Sms" if auth_method == "sms" else "Email"),
                {
                    "challengeReason": "DEVICE_AUTH",
                    "challengeMethod": "OP",
                    "bindDevice": "false",
                    "challengeType": "challengeSMS"
                    if auth_method == "sms"
                    else "challengeEmail",
                },
            )

            two_factor_code = get_two_factor_code_func()

            self.api_request(
                "post",
                "/api/credential/authenticateSms"
                if auth_method == "sms"
                else "/api/credential/authenticateEmailByCode",
                {
                    "challengeReason": "DEVICE_AUTH",
                    "challengeMethod": "OP",
                    "bindDevice": "false",
                    "code": two_factor_code,
                },
            )

        self.api_request(
            "post",
            "/api/credential/authenticatePassword",
            {
                "bindDevice": "true",
                "deviceName": "API script",
                "passwd": password,
            },
        )

        self._email = email

        return self
