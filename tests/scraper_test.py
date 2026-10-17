import pandas as pd
import pytest
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


def _plaid_options(*, transactions=True, accounts=True, dry_run=False):
    options = scraper.utils.ScraperOptions()
    options.scrape_transactions = transactions
    options.scrape_accounts = accounts
    options.dry_run = dry_run
    return options


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


def test_plaid_accounts_only_does_not_consume_transaction_cursor(mocker) -> None:
    state = {
        "items": {
            "item-1": {
                "status": "active",
                "access_token": "token-1",
                "cursor": "old-cursor",
                "imported_transaction_ids": ["plaid:old"],
            }
        }
    }
    store = _StateStore(state)
    sheet = mocker.MagicMock()
    client = mocker.MagicMock()
    client.accounts.return_value = [
        {
            "account_id": "account-1",
            "name": "Checking",
            "type": "depository",
            "subtype": "checking",
            "balances": {"current": 10},
        }
    ]
    mocker.patch.object(scraper, "_open_sheet", return_value=sheet)
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)
    mocker.patch.object(scraper.plaid_source, "PlaidClient", return_value=client)
    update = mocker.patch.object(scraper.remote, "UpdateGoogleSheet")

    scraper.scrape_plaid_and_push(_plaid_options(transactions=False, accounts=True))

    client.sync.assert_not_called()
    assert state["items"]["item-1"]["cursor"] == "old-cursor"
    assert state["items"]["item-1"]["imported_transaction_ids"] == ["plaid:old"]
    assert update.call_args.kwargs["mark_scrape_success"] is False
    assert update.call_args.args[1] is None


def test_plaid_partial_failure_commits_successful_cursor(
    mocker,
) -> None:
    state = {
        "items": {
            "good": {"status": "active", "access_token": "good", "cursor": "old"},
            "bad": {"status": "active", "access_token": "bad", "cursor": "keep"},
        }
    }
    store = _StateStore(state)
    sheet = mocker.MagicMock()
    sheet.worksheet_by_title.return_value.get_as_df.return_value = pd.DataFrame(
        columns=scraper.config.GLOBAL.COLUMN_NAMES
    )
    client = mocker.MagicMock()
    client.sync.side_effect = [
        ([], [], [], "new"),
        scraper.plaid_source.PlaidError("reauthentication_required", "reconnect"),
    ]
    client.accounts.return_value = []
    mocker.patch.object(scraper, "_open_sheet", return_value=sheet)
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)
    mocker.patch.object(scraper.plaid_source, "PlaidClient", return_value=client)
    update = mocker.patch.object(scraper.remote, "UpdateGoogleSheet")

    with pytest.raises(scraper.plaid_source.PlaidError, match="could not be") as exc:
        scraper.scrape_plaid_and_push(_plaid_options())

    assert exc.value.code == "partial_sync_failed"
    assert state["items"]["good"]["cursor"] == "new"
    assert state["items"]["bad"]["cursor"] == "keep"
    assert state["items"]["bad"]["last_error"] == "reauthentication_required"
    assert update.call_args.kwargs["mark_scrape_success"] is False


def test_plaid_dry_run_does_not_write_failed_item_state(mocker) -> None:
    state = {
        "items": {"bad": {"status": "active", "access_token": "bad", "cursor": "keep"}}
    }
    store = mocker.Mock(wraps=_StateStore(state))
    sheet = mocker.MagicMock()
    client = mocker.MagicMock()
    client.sync.side_effect = scraper.plaid_source.PlaidError("sync_failed", "nope")
    client.accounts.side_effect = scraper.plaid_source.PlaidError("sync_failed", "nope")
    mocker.patch.object(scraper, "_open_sheet", return_value=sheet)
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)
    mocker.patch.object(scraper.plaid_source, "PlaidClient", return_value=client)
    update = mocker.patch.object(scraper.remote, "UpdateGoogleSheet")

    with pytest.raises(scraper.plaid_source.PlaidError) as exc:
        scraper.scrape_plaid_and_push(_plaid_options(dry_run=True))

    assert exc.value.code == "sync_failed"
    store.save.assert_not_called()
    update.assert_not_called()


def test_durable_finish_retries_full_state_reload_and_save(mocker) -> None:
    state = {"scrape_job": {"job_id": "job-1", "state": "running"}}
    store = _StateStore(state)
    load = mocker.patch.object(
        store, "load", side_effect=[RuntimeError("503"), RuntimeError("500"), state]
    )
    mocker.patch.object(scraper, "_open_sheet", return_value=object())
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)
    sleep = mocker.patch.object(scraper.time, "sleep")

    scraper._finish_durable_scrape_job("job-1")

    assert load.call_count == 3
    sleep.assert_has_calls([mocker.call(1), mocker.call(2)])
    assert state["scrape_job"]["state"] == "succeeded"


def test_durable_finish_propagates_after_bounded_retries(mocker) -> None:
    store = mocker.Mock()
    store.load.side_effect = RuntimeError("503")
    mocker.patch.object(scraper, "_open_sheet", return_value=object())
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)
    sleep = mocker.patch.object(scraper.time, "sleep")

    with pytest.raises(RuntimeError, match="503"):
        scraper._finish_durable_scrape_job("job-1")

    assert store.load.call_count == scraper.DURABLE_STATUS_MAX_ATTEMPTS
    sleep.assert_has_calls([mocker.call(1), mocker.call(2)])


def test_main_plaid_does_not_load_legacy_empower_credentials(mocker) -> None:
    mocker.patch.object(scraper.plaid_source, "is_configured", return_value=True)
    mocker.patch.object(scraper, "_claim_durable_scrape_job", return_value=None)
    scrape = mocker.patch.object(scraper, "scrape_and_push")
    legacy_creds = mocker.patch.object(scraper.auth, "GetCredentials")

    scraper.main([])

    legacy_creds.assert_not_called()
    scrape.assert_called_once_with(mocker.ANY, None)


def test_partial_accounts_failure_preserves_prior_accounts_snapshot(mocker) -> None:
    state = {
        "items": {
            "good": {"status": "active", "access_token": "good", "cursor": "old"},
            "bad": {"status": "active", "access_token": "bad", "cursor": "old"},
        }
    }
    store = _StateStore(state)
    sheet = mocker.MagicMock()
    sheet.worksheet_by_title.return_value.get_as_df.return_value = pd.DataFrame(
        columns=scraper.config.GLOBAL.COLUMN_NAMES
    )
    client = mocker.MagicMock()
    client.sync.side_effect = [([], [], [], "new-good"), ([], [], [], "new-bad")]
    client.accounts.side_effect = [
        [
            {
                "account_id": "account-1",
                "name": "Checking",
                "type": "depository",
                "subtype": "checking",
                "balances": {"current": 10},
            }
        ],
        scraper.plaid_source.PlaidError("sync_failed", "accounts unavailable"),
    ]
    mocker.patch.object(scraper, "_open_sheet", return_value=sheet)
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)
    mocker.patch.object(scraper.plaid_source, "PlaidClient", return_value=client)
    update = mocker.patch.object(scraper.remote, "UpdateGoogleSheet")

    with pytest.raises(scraper.plaid_source.PlaidError) as exc:
        scraper.scrape_plaid_and_push(_plaid_options())

    assert exc.value.code == "partial_sync_failed"
    assert update.call_args.args[1] is not None
    assert update.call_args.args[2] is None


def test_durable_finish_retries_after_transient_save_failure(mocker) -> None:
    state = {"scrape_job": {"job_id": "job-1", "state": "running"}}
    store = _StateStore(state)
    save = mocker.patch.object(store, "save", side_effect=[RuntimeError("503"), None])
    mocker.patch.object(scraper, "_open_sheet", return_value=object())
    mocker.patch.object(scraper.auth, "GetGoogleCredentials", return_value=object())
    mocker.patch.object(scraper.plaid_source, "SheetStateStore", return_value=store)
    sleep = mocker.patch.object(scraper.time, "sleep")

    scraper._finish_durable_scrape_job("job-1")

    assert save.call_count == 2
    sleep.assert_called_once_with(1)


def test_main_dry_run_skips_durable_job_writes(mocker) -> None:
    mocker.patch.object(scraper.plaid_source, "is_configured", return_value=True)
    claim = mocker.patch.object(scraper, "_claim_durable_scrape_job")
    finish = mocker.patch.object(scraper, "_finish_durable_scrape_job")
    scrape = mocker.patch.object(scraper, "scrape_and_push")

    scraper.main(["--dry_run"])

    claim.assert_not_called()
    finish.assert_not_called()
    scrape.assert_called_once_with(mocker.ANY, None)


def test_main_preserves_scrape_error_if_failure_status_save_fails(mocker) -> None:
    original = scraper.plaid_source.PlaidError("sync_failed", "original failure")
    mocker.patch.object(scraper.plaid_source, "is_configured", return_value=True)
    mocker.patch.object(scraper, "_claim_durable_scrape_job", return_value="job-1")
    mocker.patch.object(scraper, "scrape_and_push", side_effect=original)
    finish = mocker.patch.object(
        scraper, "_finish_durable_scrape_job", side_effect=RuntimeError("503")
    )

    with pytest.raises(scraper.plaid_source.PlaidError) as exc:
        scraper.main([])

    assert exc.value is original
    finish.assert_called_once_with("job-1", error=original)
