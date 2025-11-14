# We test several internal-only details. Its easier this way.
import remote

import argparse
import auth
import pandas as pd
import pytest
import utils


from unittest.mock import call, MagicMock

from google.oauth2 import service_account

from _pytest.monkeypatch import MonkeyPatch


from typing import Iterator


@pytest.fixture()
def config(monkeypatch: MonkeyPatch) -> Iterator[MonkeyPatch]:
    monkeypatch.setattr(remote.config.GLOBAL, "MERCHANT_NORMALIZATION", [])
    yield monkeypatch


def test_normalize() -> None:
    assert remote._Normalize("Title String 123") == "Title String 123"
    assert remote._Normalize("title string 123") == "Title String 123"
    assert remote._Normalize("T$it^&le str90/4ing 123") == "Title Str90/4Ing 123"


def test_normalize_merchant(config: MonkeyPatch) -> None:
    assert remote._NormalizeMerchant("Normal Merchant") == "Normal Merchant"
    assert remote._NormalizeMerchant("wEirD CasES") == "Weird Cases"
    assert remote._NormalizeMerchant("  Extra   Spaces ") == "Extra Spaces"
    assert remote._NormalizeMerchant("Non-#%23&@(%C%*@4)ha$#2%(s") == "Nonchas"
    assert remote._NormalizeMerchant("aPLpay merchant xxxx") == "Merchant"
    assert remote._NormalizeMerchant("gGLpay merchant xxxx") == "Merchant"
    assert remote._NormalizeMerchant("Amzn Mktp MEr424cHant") == "Amazon Merchant"

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


def test_authenticate(
    mocker, test_env: MonkeyPatch, test_creds: service_account.Credentials
) -> None:
    parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
    args = parser.parse_args([])
    options = utils.ScraperOptions.fromArgsAndEnv(args)
    creds = auth.GetCredentials()

    mock_pc = mocker.patch("empower.PersonalCapital").return_value
    conn = remote.Authenticate(creds, options)

    mock_pc.login.assert_called_once_with(
        email=creds.username, password=creds.password
    )
    assert conn == mock_pc


def test_retrieve_accounts_txns(
    config: MonkeyPatch, mockApi: MagicMock, mockSheet: MagicMock
) -> None:
    # Only new txns.
    with config.context() as c:
        c.setattr(remote.config.GLOBAL, "PC_MIGRATION_DATE", "1970-01-01")
        data = remote.RetrieveTransactions(mockApi, mockSheet)
        compare = data.compare(
            pd.DataFrame(
                [
                    {
                        "Date": "2023-12-08",
                        "Merchant": "Alcatraz Cruises",
                        "Amount": -90.50,
                        "Category": "Travel",
                        "Account": "Citi Double Cash Card",
                        "ID": 13500164302,
                        "Description": "Alcatraz Cruises",
                    },
                    {
                        "Date": "2023-12-09",
                        "Merchant": "Waterbar",
                        "Amount": -64.46,
                        "Category": "Restaurants/Dining",
                        "Account": "Platinum Card Belinda",
                        "ID": 13500164328,
                        "Description": "Waterbar",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Disney Plus",
                        "Amount": 7.99,
                        "Category": "Entertainment",
                        "Account": "Platinum Card Luis",
                        "ID": 13500164304,
                        "Description": "Disney Plus",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Whole Foods Market",
                        "Amount": -65.28,
                        "Category": "Groceries",
                        "Account": "Chase Amazon Luis",
                        "ID": 13568745214,
                        "Description": "Whole Foods Market",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Taj Campton Psan Francisco",
                        "Amount": -34.88,
                        "Category": "Restaurants/Dining",
                        "Account": "Platinum Card Belinda",
                        "ID": 13500164330,
                        "Description": "Gglpay Taj Campton Psan Francisco Ca",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Chargepoint",
                        "Amount": -2.95,
                        "Category": "Gasoline/Fuel",
                        "Account": "Citi Double Cash Card",
                        "ID": 13507386301,
                        "Description": "Chargepoint",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Teaspoon",
                        "Amount": -6.25,
                        "Category": "Restaurants/Dining",
                        "Account": "Citi Double Cash Card",
                        "ID": 13500164298,
                        "Description": "Parteaspoon Saratoga San Jose Ca",
                    },
                    {
                        "Date": "2023-12-11",
                        "Merchant": "Walmart",
                        "Amount": -19.18,
                        "Category": "General Merchandise",
                        "Account": "Citi Double Cash Card",
                        "ID": 13507386299,
                        "Description": "Walmart",
                    },
                    {
                        "Date": "2023-12-11",
                        "Merchant": "Chickfila",
                        "Amount": -6.97,
                        "Category": "Restaurants/Dining",
                        "Account": "Citi Double Cash Card",
                        "ID": 13514522240,
                        "Description": "Chickfila",
                    },
                    {
                        "Date": "2023-12-11",
                        "Merchant": "Costco",
                        "Amount": -97.66,
                        "Category": "General Merchandise",
                        "Account": "Chase Amazon Luis",
                        "ID": 13568745207,
                        "Description": "Costco",
                    },
                ]
            )
        )
        assert compare.empty, compare


def test_retrieve_accounts_txns_old_and_new_cleanup(
    config: MonkeyPatch, mockApi: MagicMock, mockSheet: MagicMock
) -> None:
    # Include both new and old.
    with config.context() as c:
        c.setattr(remote.config.GLOBAL, "PC_MIGRATION_DATE", "1970-01-01")
        c.setattr(remote.config.GLOBAL, "NUM_TXN_FOR_CUTOFF", 0)
        c.setattr(remote.config.GLOBAL, "CLEAN_UP_OLD_TXNS", True)
        data = remote.RetrieveTransactions(mockApi, mockSheet)
        compare = data.compare(
            pd.DataFrame(
                [
                    {
                        "Date": "2015-09-30",
                        "Merchant": "Amazon",
                        "Amount": -9.07,
                        "Category": "Shopping",
                        "Account": "Amazon Store Card",
                        "ID": 799439640,
                        "Description": "Amazon",
                    },
                    {
                        "Date": "2015-10-04",
                        "Merchant": "Yogurt Land",
                        "Amount": -11.92,
                        "Category": "Business Services",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426716,
                        "Description": "Yogurt Land",
                    },
                    {
                        "Date": "2015-10-04",
                        "Merchant": "Crimson Services Ma",
                        "Amount": -10.00,
                        "Category": "Education",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426706,
                        "Description": "Crimson Services Ma",
                    },
                    {
                        "Date": "2015-10-04",
                        "Merchant": "Din Tai Fung",
                        "Amount": -37.00,
                        "Category": "Restaurants",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426710,
                        "Description": "Din Tai Fung",
                    },
                    {
                        "Date": "2015-10-05",
                        "Merchant": "Typhoon Streets Asia",
                        "Amount": -2.00,
                        "Category": "Restaurants",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426669,
                        "Description": "Typhoon Streets Asia",
                    },
                    {
                        "Date": "2015-10-05",
                        "Merchant": "Typhoon Streets Asia",
                        "Amount": -8.40,
                        "Category": "Restaurants",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426720,
                        "Description": "Typhoon Streets Asia",
                    },
                    {
                        "Date": "2015-10-13",
                        "Merchant": "Mbta Harvard",
                        "Amount": -10.00,
                        "Category": "Public Transportation",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426664,
                        "Description": "Mbta Harvard",
                    },
                    {
                        "Date": "2015-10-16",
                        "Merchant": "Mbta Harvard",
                        "Amount": -10.00,
                        "Category": "Public Transportation",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426691,
                        "Description": "Mbta Harvard",
                    },
                    {
                        "Date": "2015-10-16",
                        "Merchant": "Cvs",
                        "Amount": -19.08,
                        "Category": "Pharmacy",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426723,
                        "Description": "Cvs",
                    },
                    {
                        "Date": "2015-10-20",
                        "Merchant": "Campus Services",
                        "Amount": -3.95,
                        "Category": "Music",
                        "Account": "Citi Dividend Miles",
                        "ID": 799426671,
                        "Description": "Campus Services",
                    },
                    {
                        "Date": "2023-12-08",
                        "Merchant": "Alcatraz Cruises",
                        "Amount": -90.50,
                        "Category": "Travel",
                        "Account": "Citi Double Cash Card",
                        "ID": 13500164302,
                        "Description": "Alcatraz Cruises",
                    },
                    {
                        "Date": "2023-12-09",
                        "Merchant": "Waterbar",
                        "Amount": -64.46,
                        "Category": "Restaurants/Dining",
                        "Account": "Platinum Card Belinda",
                        "ID": 13500164328,
                        "Description": "Waterbar",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Disney Plus",
                        "Amount": 7.99,
                        "Category": "Entertainment",
                        "Account": "Platinum Card Luis",
                        "ID": 13500164304,
                        "Description": "Disney Plus",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Whole Foods Market",
                        "Amount": -65.28,
                        "Category": "Groceries",
                        "Account": "Chase Amazon Luis",
                        "ID": 13568745214,
                        "Description": "Whole Foods Market",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Taj Campton Psan Francisco",
                        "Amount": -34.88,
                        "Category": "Restaurants/Dining",
                        "Account": "Platinum Card Belinda",
                        "ID": 13500164330,
                        "Description": "Gglpay Taj Campton Psan Francisco Ca",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Chargepoint",
                        "Amount": -2.95,
                        "Category": "Gasoline/Fuel",
                        "Account": "Citi Double Cash Card",
                        "ID": 13507386301,
                        "Description": "Chargepoint",
                    },
                    {
                        "Date": "2023-12-10",
                        "Merchant": "Teaspoon",
                        "Amount": -6.25,
                        "Category": "Restaurants/Dining",
                        "Account": "Citi Double Cash Card",
                        "ID": 13500164298,
                        "Description": "Parteaspoon Saratoga San Jose Ca",
                    },
                    {
                        "Date": "2023-12-11",
                        "Merchant": "Walmart",
                        "Amount": -19.18,
                        "Category": "General Merchandise",
                        "Account": "Citi Double Cash Card",
                        "ID": 13507386299,
                        "Description": "Walmart",
                    },
                    {
                        "Date": "2023-12-11",
                        "Merchant": "Chickfila",
                        "Amount": -6.97,
                        "Category": "Restaurants/Dining",
                        "Account": "Citi Double Cash Card",
                        "ID": 13514522240,
                        "Description": "Chickfila",
                    },
                    {
                        "Date": "2023-12-11",
                        "Merchant": "Costco",
                        "Amount": -97.66,
                        "Category": "General Merchandise",
                        "Account": "Chase Amazon Luis",
                        "ID": 13568745207,
                        "Description": "Costco",
                    },
                ]
            )
        )
        assert compare.empty, compare

    pass


def test_retrieve_accounts(
    monkeypatch: MonkeyPatch, mockApi: MagicMock, mocker
) -> None:
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


def test_update_google_sheets(mocker) -> None:
    with mocker.MagicMock() as mockWs, mocker.MagicMock() as mockSheet:
        mockSheet.worksheet_by_title.return_value = mockWs
        remote.UpdateGoogleSheet(mockSheet, transactions=None, accounts=None)

        mockSheet.worksheet_by_title.assert_called_with(
            title=remote.config.GLOBAL.SETTINGS_SHEET_TITLE
        )
        mockWs.set_dataframe.assert_called_once()


def test_update_google_sheets_txns(mocker) -> None:
    with mocker.MagicMock() as mockWs, mocker.MagicMock() as mockSheet:
        mockSheet.worksheet_by_title.return_value = mockWs
        remote.UpdateGoogleSheet(
            mockSheet, transactions=pd.DataFrame(["test"]), accounts=None
        )
        mockSheet.worksheet_by_title.assert_has_calls(
            [
                call(title=remote.config.GLOBAL.RAW_TRANSACTIONS_TITLE),
                call(title=remote.config.GLOBAL.SETTINGS_SHEET_TITLE),
            ],
            any_order=True,
        )
        assert mockWs.set_dataframe.call_count == 2


def test_update_google_sheets_accounts(mocker) -> None:
    with mocker.MagicMock() as mockWs, mocker.MagicMock() as mockSheet:
        mockSheet.worksheet_by_title.return_value = mockWs
        remote.UpdateGoogleSheet(
            mockSheet, transactions=None, accounts=pd.DataFrame(["test"])
        )
        mockSheet.worksheet_by_title.assert_has_calls(
            [
                call(title=remote.config.GLOBAL.RAW_ACCOUNTS_TITLE),
                call(title=remote.config.GLOBAL.SETTINGS_SHEET_TITLE),
            ],
            any_order=True,
        )
        assert mockWs.set_dataframe.call_count == 2


def test_update_google_sheets_all(mocker) -> None:
    with mocker.MagicMock() as mockWs, mocker.MagicMock() as mockSheet:
        mockSheet.worksheet_by_title.return_value = mockWs
        remote.UpdateGoogleSheet(
            mockSheet,
            transactions=pd.DataFrame(["test2"]),
            accounts=pd.DataFrame(["test"]),
        )
        mockSheet.worksheet_by_title.assert_has_calls(
            [
                call(title=remote.config.GLOBAL.RAW_TRANSACTIONS_TITLE),
                call(title=remote.config.GLOBAL.RAW_ACCOUNTS_TITLE),
                call(title=remote.config.GLOBAL.SETTINGS_SHEET_TITLE),
            ],
            any_order=True,
        )
        assert mockWs.set_dataframe.call_count == 3


def test_normalize_merchant_cycle(config: MonkeyPatch, mocker) -> None:
    mocker.patch.object(remote, "_normalize", side_effect=lambda x: x + "a")
    remote._NormalizeMerchant("g")


def test_retrieve_accounts_unknown_type(
    monkeypatch: MonkeyPatch, mockApi: MagicMock, mocker
) -> None:
    monkeypatch.setattr(remote.config.GLOBAL, "ACCOUNT_NAME_TO_TYPE_MAP", [])
    remote.RetrieveAccounts(mockApi)


def test_retrieve_transactions_no_cleanup(
    config: MonkeyPatch, mockApi: MagicMock, mockSheet: MagicMock
) -> None:
    with config.context() as c:
        c.setattr(remote.config.GLOBAL, "CLEAN_UP_OLD_TXNS", False)
        remote.RetrieveTransactions(mockApi, mockSheet)
