import auth
import empower
import pandas as pd
import pickle
import pytest

from _pytest.monkeypatch import MonkeyPatch

from google.oauth2 import service_account
from unittest.mock import MagicMock

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
def test_creds(monkeypatch: MonkeyPatch, mocker) -> service_account.Credentials:
    google_creds = service_account.Credentials(
        "signer", "service_account_email", "token_uri"
    )
    monkeypatch.setattr(
        auth.service_account.Credentials,
        "from_service_account_info",
        lambda *args, **kwargs: google_creds,
    )
    mocker.patch.object(
        empower.PersonalCapital, "_api_request", return_value=mocker.MagicMock()
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


@pytest.fixture()
def mockApi(mocker) -> MagicMock:
    with open("tests/txns.out", "rb") as f:
        txn_response = pickle.load(f)
        _MOCK_ACCOUNTS = {
            "accounts": [
                {
                    "name": "Amazon Store Card",
                    "balance": 0.0,
                    "closedDate": "",
                    "accountType": "Credit",
                },
                {
                    "name": "Amazon Store",
                    "balance": 40723.74,
                    "closedDate": "",
                    "accountType": "Credit",
                },
                {
                    "name": "Investment_101",
                    "balance": 17950.9,
                    "closedDate": "",
                    "accountType": "Stock",
                },
                {
                    "name": "Roth IRA",
                    "balance": 32873.9,
                    "closedDate": "",
                    "accountType": "Roth",
                },
                {
                    "name": "LendingClub",
                    "balance": 957.39,
                    "closedDate": "",
                    "accountType": "Loan",
                },
                # Will be dropped because it's not active.
                {
                    "name": "GOOGLE INC.",
                    "balance": 58447.76,
                    "closedDate": "2022-10-01",
                    "accountType": "Stock",
                },
                {
                    "name": "Brokerage Account",
                    "balance": 0.0,
                    "closedDate": "",
                    "accountType": "Stock",
                },
                {
                    "name": "Brokerage Account - Luis",
                    "balance": 0.0,
                    "closedDate": "",
                    "accountType": "Stock",
                },
                {
                    "name": "Traditional IRA",
                    "balance": 0.0,
                    "closedDate": "",
                    "accountType": "IRA",
                },
            ]
        }

    mockApi = mocker.MagicMock()
    mockApi.get_transaction_data.return_value = txn_response
    mockApi.get_account_data.return_value = _MOCK_ACCOUNTS

    return mockApi


@pytest.fixture()
def mockSheet(mocker) -> MagicMock:
    old_txns = pd.read_csv("tests/old_txns.csv")
    mockWs = mocker.MagicMock()
    mockWs.get_as_df.return_value = old_txns
    mockSheet = mocker.MagicMock()
    mockSheet.worksheet_by_title.return_value = mockWs
    return mockSheet
