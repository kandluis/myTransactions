import auth
import pytest

from _pytest.monkeypatch import MonkeyPatch

from google.oauth2 import service_account

from typing import Iterator

_ENV_VARS = [
    "MFA_TOKEN",
]

_REQUIRED_ENV_KEYS: dict[str, str] = {
    "ACCOUNT_USERNAME": "TEST_USERNAME",
    "PASSWORD": "TEST_PASSWORD",
    # This needs to be valued JSON.
    "GOOGLE_SHEETS_CREDENTIALS": """{
      "key" : "value",
      "key2" : "value2"
    }""",
}


@pytest.fixture()
def test_creds(monkeypatch: MonkeyPatch) -> service_account.Credentials:
    google_creds = service_account.Credentials(
        "signer", "service_account_email", "token_uri"
    )
    monkeypatch.setattr(
        auth.service_account.Credentials,
        "from_service_account_info",
        lambda *args, **kwargs: google_creds,
    )
    return google_creds


@pytest.fixture()
def test_env(monkeypatch: MonkeyPatch) -> Iterator[MonkeyPatch]:
    """Mocks out a default environment and yields the monkeypatch."""
    for key, value in _REQUIRED_ENV_KEYS.items():
        monkeypatch.setenv(key, value)

    for envName in _ENV_VARS:
        monkeypatch.delenv(envName, raising=False)

    yield monkeypatch
