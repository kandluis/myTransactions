import auth
import pytest
import utils
from _pytest.monkeypatch import MonkeyPatch

from typing import Dict, Iterator

_REQUIRED_ENV_KEYS: Dict[str, str] = {
    "ACCOUNT_USERNAME": "TEST_USERNAME",
    "PASSWORD": "TEST_PASSWORD",
    # This needs to be valued JSON.
    "GOOGLE_SHEETS_CREDENTIALS": """{
      "key" : "value",
      "key2" : "value2"
    }""",
}


@pytest.fixture()
def env(monkeypatch: MonkeyPatch) -> Iterator[MonkeyPatch]:
    """Mocks out a default environment and yields the monkeypatch."""
    for key, value in _REQUIRED_ENV_KEYS.items():
        monkeypatch.setenv(key, value)

    yield monkeypatch


def test_get_credentials_invalid(env: MonkeyPatch) -> None:
    # Delete any of keys raises an error.
    for key in _REQUIRED_ENV_KEYS:
        with env.context() as m, pytest.raises(utils.ScraperError):
            m.delenv(key)
            auth.GetCredentials()


def test_credentials_success(env: MonkeyPatch) -> None:
    google_creds = auth.service_account.Credentials(
        "signer", "service_account_email", "token_uri"
    )
    env.setattr(
        auth.service_account.Credentials,
        "from_service_account_info",
        lambda *args, **kwargs: google_creds,
    )
    assert auth.GetCredentials() == auth.Credentials(
        username="TEST_USERNAME",
        password="TEST_PASSWORD",
        sheets=google_creds,
    )
