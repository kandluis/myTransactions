# We test several internal-only details. Its easier this way.
import remote
import pandas as pd
import pytest

from _pytest.monkeypatch import MonkeyPatch

from typing import Iterator


@pytest.fixture()
def config(monkeypatch: MonkeyPatch) -> Iterator[MonkeyPatch]:
    monkeypatch.setattr(remote.config.GLOBAL, "MERCHANT_NORMALIZATION", [])
    yield monkeypatch


def test_normalize() -> None:
    assert remote._Normalize("Title String 123") == "Title String 123"
    assert remote._Normalize("title string 123") == "Title String 123"
    assert remote._Normalize("T$it^&le str90/4ing 123") == "Title Str904Ing 123"


def test_normalize_merchant(config: MonkeyPatch) -> None:
    assert remote._NormalizeMerchant("Normal Merchant") == "Normal Merchant"
    assert remote._NormalizeMerchant("wEirD CasES") == "Weird Cases"
    assert remote._NormalizeMerchant("  Extra   Spaces ") == "Extra Spaces"
    assert remote._NormalizeMerchant("Non-#%23&@(%C%*@4)ha$#2%(s") == "Nonchas"

    with config.context() as c:
        assert remote._NormalizeMerchant("Normal Merchant") == "Normal Merchant"
        # Spaces don't count.
        assert remote._NormalizeMerchant("Nor mal Merchant") == "Nor Mal Merchant"
        # Neither do special chars.
        res = remote._NormalizeMerchant("N$%*@%*$or m$*%$a@$(%l Merchant")
        assert res == "Nor Mal Merchant"

    with config.context() as c:
        c.setattr(
            remote.config.GLOBAL, "MERCHANT_NORMALIZATION", ["Airbnb", "Chipotle"]
        )

        assert remote._NormalizeMerchant("Airbnb Long TxN 1234") == "Airbnb"
        assert remote._NormalizeMerchant("Chi#$%$#%124potle Tx14x435") == "Chipotle"


def test_retrieve_accounts(monkeypatch, mocker) -> None:
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
    # We should match more specific to least specific.
    monkeypatch.setattr(
        remote.config.GLOBAL,
        "ACCOUNT_NAME_TO_TYPE_MAP",
        [
            # Won't match anything.
            ("Amazon", "Savings"),
            ("Amazon Store Card", "Credit"),
            ("Amazon Store", "Checking"),
            ("Investment", "Investment"),
            # Case should not matter.
            ("roth", "Investment"),
            ("Lending", "Loan"),
            ("Brokerage", "Stock"),
            ("Brokerage account - luis", "Retirement"),
            # (Traditional, Other)
        ],
    )
    mockApi = mocker.MagicMock()
    mockApi.get_account_data.return_value = _MOCK_ACCOUNTS

    data = remote.RetrieveAccounts(mockApi)
    data.sort_values(by=["Name"], inplace=True, ignore_index=True)
    expected = pd.DataFrame(
        [
            # Sorted by name.
            {
                "Name": "Amazon Store",
                "Type": "Checking",
                "Balance": 40723.74,
                "inferredType": "Credit",
            },
            {
                "Name": "Amazon Store Card",
                "Type": "Credit",
                "Balance": 0.0,
                "inferredType": "Credit",
            },
            {
                "Name": "Brokerage Account",
                "Type": "Stock",
                "Balance": 0.0,
                "inferredType": "Stock",
            },
            {
                "Name": "Brokerage Account - Luis",
                "Type": "Retirement",
                "Balance": 0.0,
                "inferredType": "Stock",
            },
            {
                "Name": "Investment_101",
                "Type": "Investment",
                "Balance": 17950.9,
                "inferredType": "Stock",
            },
            {
                "Name": "LendingClub",
                "Type": "Loan",
                "Balance": 957.39,
                "inferredType": "Loan",
            },
            {
                "Name": "Roth IRA",
                "Type": "Investment",
                "Balance": 32873.9,
                "inferredType": "Roth",
            },
            {
                "Name": "Traditional IRA",
                "Type": "Unknown - Traditional IRA",
                "Balance": 0.0,
                "inferredType": "IRA",
            },
        ]
    )
    assert data.compare(expected).empty
