import auth
import pytest
import utils
from _pytest.monkeypatch import MonkeyPatch

from google.oauth2 import service_account


def test_get_credentials_invalid(test_env: MonkeyPatch) -> None:
    # Delete any of keys raises an error.
    for key in ("ACCOUNT_USERNAME", "PASSWORD", "GOOGLE_SHEETS_CREDENTIALS"):
        with test_env.context() as m, pytest.raises(utils.ScraperError):
            m.delenv(key)
            auth.GetCredentials()


def test_credentials_success(
    test_env: MonkeyPatch, test_creds: service_account.Credentials
) -> None:
    assert auth.GetCredentials() == auth.Credentials(
        username="TEST_USERNAME",
        password="TEST_PASSWORD",
        sheets=test_creds,
    )
