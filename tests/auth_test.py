import auth
import pytest
import utils
from _pytest.monkeypatch import MonkeyPatch

from typing import Dict, Iterator

_REQUIRED_ENV_KEYS: Dict[str, str] = {
    "MINT_EMAIL": "TEST_MINT_EMAIL",
    "MINT_PASSWORD": "TEST_MINT_PASSWORD",
    "EMAIL_PASSWORD": "TEST_EMAIL_PASSWORD",
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
    env.setattr(
        auth.service_account.Credentials,
        "from_service_account_info",
        lambda *args, **kwargs: None,
    )
    assert auth.GetCredentials() == auth.Credentials(
        email="TEST_MINT_EMAIL",
        mintPassword="TEST_MINT_PASSWORD",
        emailPassword="TEST_EMAIL_PASSWORD",
        sheets=None,
    )
