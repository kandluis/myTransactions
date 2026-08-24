import pandas as pd
import runpy
import scraper
import sys

from _pytest.monkeypatch import MonkeyPatch

from google.oauth2 import service_account
from unittest.mock import MagicMock


class _StateStore:
    def __init__(self, state):
        self.state = state

    def load(self):
        return self.state

    def save(self, state) -> None:
        self.state = state


def test_scraper(
    test_env: MonkeyPatch,
    test_creds: service_account.Credentials,
    mockApi: MagicMock,
    mockSheet: MagicMock,
    mocker,
) -> None:
    test_env.setenv("SMS_CODE", "123456")
    mocker.patch.object(scraper.remote, "Authenticate", return_value=mockApi)
    sheetsClient = mocker.MagicMock()
    sheetsClient.open.return_value = mockSheet
    mocker.patch.object(scraper.pygsheets, "authorize", return_value=sheetsClient)
    scraper.main([])

    del test_creds


def test_scraper_debug(
    test_env: MonkeyPatch,
    test_creds: service_account.Credentials,
    mockApi: MagicMock,
    mockSheet: MagicMock,
    mocker,
) -> None:
    test_env.setenv("SMS_CODE", "123456")
    mocker.patch.object(scraper.remote, "Authenticate", return_value=mockApi)
    sheetsClient = mocker.MagicMock()
    sheetsClient.open.return_value = mockSheet
    mocker.patch.object(scraper.pygsheets, "authorize", return_value=sheetsClient)
    scraper.main(["--debug"])

    del test_creds


def _setup_mocks(mocker):
    mocker.patch.object(scraper, "main")
    mock_creds = mocker.patch("auth.GetCredentials")
    mock_creds.return_value.username = "test_user"
    mock_creds.return_value.password = "test_pass"

    mock_pc = mocker.patch("empower.PersonalCapital")
    mock_pc.return_value.get_transaction_data.return_value = {
        "transactions": [
            {
                "transactionDate": "2025-01-01",
                "merchant": "Test Merchant",
                "amount": 123.45,
                "categoryName": "Test Category",
                "accountName": "Test Account",
                "userTransactionId": "Test ID",
                "description": "Test Description",
                "isCredit": False,
                "isSpending": True,
                "isCashOut": False,
                "investmentType": None,
            }
        ]
    }

    mock_pygsheets = mocker.patch("pygsheets.authorize")
    mock_worksheet = mocker.MagicMock()
    mock_worksheet.get_as_df.return_value = pd.DataFrame(
        {
            "Date": ["2025-01-01"],
            "Merchant": ["Test Merchant"],
            "Amount": [123.45],
            "Category": ["Test Category"],
            "Account": ["Test Account"],
            "ID": ["Test ID"],
            "Description": ["Test Description"],
        }
    )
    mock_pygsheets.return_value.open.return_value.worksheet_by_title.return_value = (
        mock_worksheet
    )


def test_main_entrypoint(mocker, test_env: MonkeyPatch):
    test_env.setenv("SMS_CODE", "123456")
    _setup_mocks(mocker)
    # Clear argv to avoid pytest args being passed to scraper
    sys.argv = ["scraper.py"]
    runpy.run_module("scraper", run_name="__main__")


def test_durable_scrape_worker_claims_and_finishes_requested_job(mocker) -> None:
    state = {
        "items": {},
        "scrape_job": {
            "job_id": "job-1",
            "state": "queued",
            "created_at": "2026-08-24T00:00:00+00:00",
        },
    }
    store = _StateStore(state)
    mocker.patch.object(scraper, "_open_sheet", return_value=object())
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)

    job_id = scraper._claim_durable_scrape_job()
    scraper._finish_durable_scrape_job(job_id)

    assert job_id == "job-1"
    assert store.state["scrape_job"]["state"] == "succeeded"
    assert store.state["scrape_job"]["started_at"]
    assert store.state["scrape_job"]["finished_at"]
