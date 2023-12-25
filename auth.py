import json
import os
import utils

from google.oauth2 import service_account  # type: ignore

from typing import Dict, NamedTuple


class Credentials(NamedTuple):
    """Holds credential information needed to successfully run the scraper.

    Properties:
      username: The username associated with the PC account.
      password: The password for the PC account.
      emailPassword: The password for the email account.
      sheets: The credentials for the service account for Google Sheets.

    """

    username: str
    password: str
    emailPassword: str
    sheets: service_account.Credentials


def _getGoogleCredentials() -> service_account.Credentials:
    """Loads the Google Account Service Credentials to access sheets."""
    credentials_string = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    if not credentials_string:
        raise utils.ScraperError(
            f"Invalid Google credentials. Got {credentials_string}"
        )
    service_info: Dict[str, str] = json.loads(credentials_string)
    _SCOPES = (
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    )
    return service_account.Credentials.from_service_account_info(
        service_info, scopes=_SCOPES
    )


def GetCredentials() -> Credentials:
    """Retrieves the crendentials for logging into PC from the environment.

    This is necessary because they do not currently provide an API.

    Returns:
      The retrieved crendentials.
    """
    username = os.getenv("ACCOUNT_USERNAME")
    if not username:
        raise utils.ScraperError(
            "Unable to find username from var %s!" % "ACCOUNT_USERNAME"
        )
    password = os.getenv("PASSWORD")
    if not password:
        raise utils.ScraperError("Unable to find password from var %s!" % "PASSWORD")
    emailPassword = os.getenv("EMAIL_PASSWORD")
    if not emailPassword:
        raise utils.ScraperError("Unable to find pass from var %s!" % "EMAIL_PASSWORD")
    sheets_creds = _getGoogleCredentials()
    return Credentials(
        username=username,
        password=password,
        emailPassword=emailPassword,
        sheets=sheets_creds,
    )
