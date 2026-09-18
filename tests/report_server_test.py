from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
import time

import pytest
import pandas as pd

import config
import plaid_source
import report_publisher
import report_server


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("REPORT_TOKEN", "test-token")
    monkeypatch.setenv("REPORT_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path))
    return report_server.app.test_client()


@pytest.fixture(autouse=True)
def reset_job_registry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(report_server, "_current_job", None)
    monkeypatch.setattr(report_server, "_last_terminal_job", None)
    monkeypatch.setattr(report_server, "_current_scrape_job", None)
    monkeypatch.setattr(report_server, "_last_terminal_scrape_job", None)
    monkeypatch.setattr(report_server, "_plaid_approval_lock", threading.Lock())
    monkeypatch.setattr(report_server, "_load_durable_scrape_job", lambda: None)
    monkeypatch.setattr(report_server, "_save_durable_scrape_job", lambda _job: None)
    monkeypatch.setattr(report_server.fly_machine, "is_configured", lambda: True)
    monkeypatch.setattr(
        report_server.fly_machine, "start_scraper_machine", lambda: None
    )


def test_token_validation_accepts_correct_token_and_rejects_missing_or_wrong(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPORT_TOKEN", "test-token")

    assert report_server.is_authorized_token("test-token")
    assert not report_server.is_authorized_token(None)
    assert not report_server.is_authorized_token("wrong")


def test_health_is_public(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_review_accounts_displays_official_name_and_last_four() -> None:
    accounts = report_server._review_accounts(
        {
            "selected_account_ids": ["card"],
            "account_mappings": {"card": "Freedom Unlimited Belinda"},
            "account_original_names": {"card": "CREDIT CARD"},
            "account_details": {
                "card": {
                    "name": "CREDIT CARD",
                    "official_name": "Freedom Unlimited®",
                    "mask": "0940",
                    "type": "credit",
                    "subtype": "credit card",
                }
            },
        }
    )

    assert accounts == [
        {
            "id": "card",
            "plaid_name": "Freedom Unlimited®",
            "mask": "0940",
            "type": "credit",
            "subtype": "credit card",
            "canonical_name": "Freedom Unlimited Belinda",
            "selected": True,
        }
    ]


def test_review_context_explains_candidates_and_transfer_exclusions() -> None:
    item = {
        "selected_account_ids": ["account"],
        "account_mappings": {"account": "Card"},
        "pending_transactions": [
            {
                "account_id": "account",
                "transaction_id": "purchase",
                "date": "2026-08-01",
                "amount": 12.5,
                "merchant_name": "Coffee Shop",
                "name": "Coffee Shop",
            },
            {
                "account_id": "account",
                "transaction_id": "transfer",
                "date": "2026-08-02",
                "amount": -20.0,
                "merchant_name": "Incoming Transfer",
                "name": "Incoming Transfer",
                "personal_finance_category": {"primary": "TRANSFER_IN"},
            },
        ],
    }
    context = report_server._review_context(
        pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES),
        {"items": {"pending": item}},
        "pending",
        item,
    )

    assert context["review"]["plaid_only_candidates"] == 1
    assert context["candidates"][0]["merchant"] == "Coffee Shop"
    assert context["excluded"][0]["reason"] == "Incoming transfer"
    assert context["safety"]["candidate_debit_total"] == 12.5


def test_mapping_conflicts_detects_active_duplicate_account() -> None:
    state = {
        "items": {
            "active": {
                "status": "active",
                "selected_account_ids": ["old"],
                "account_mappings": {"old": "Chase Joint Checking"},
            },
            "pending": {
                "status": "pending_review",
                "selected_account_ids": ["new"],
                "account_mappings": {"new": "Chase Joint Checking"},
            },
        }
    }

    assert report_server._mapping_conflicts(
        state, "pending", state["items"]["pending"]
    ) == ["Chase Joint Checking"]


class _ApprovalStore:
    def __init__(self, state):
        self.state = state
        self.saves = 0

    def load(self):
        return self.state

    def save(self, state) -> None:
        self.state = state
        self.saves += 1


class _ApprovalWorksheet:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def get_as_df(self, numerize=False) -> pd.DataFrame:
        return self.frame.copy()


class _ApprovalSheet:
    def __init__(self, frame: pd.DataFrame):
        self.raw = _ApprovalWorksheet(frame)

    def worksheet_by_title(self, title: str) -> _ApprovalWorksheet:
        assert title == config.GLOBAL.RAW_TRANSACTIONS_TITLE
        return self.raw


def _pending_approval_state(status: str = "pending_review") -> dict:
    return {
        "items": {
            "item": {
                "status": status,
                "access_token": "access-token",
                "selected_account_ids": ["account"],
                "account_mappings": {"account": "Amex"},
                "pending_transactions": [
                    {
                        "account_id": "account",
                        "transaction_id": "transaction",
                        "date": "2026-08-01",
                        "amount": 12.5,
                        "merchant_name": "Coffee Shop",
                        "name": "Coffee Shop",
                    }
                ],
            }
        }
    }


def test_plaid_approval_is_single_flight_and_idempotent(client, monkeypatch) -> None:
    store = _ApprovalStore(_pending_approval_state())
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    writes = []
    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(
        report_server.remote,
        "UpdateGoogleSheet",
        lambda _sheet, transactions, _accounts: writes.append(transactions),
    )

    first = client.post("/plaid/approve/item?token=test-token")
    second = client.post("/plaid/approve/item?token=test-token")

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(writes) == 1
    assert store.state["items"]["item"]["status"] == "active"
    assert store.state["items"]["item"]["pending_transactions"] == []


def test_plaid_approval_resumes_a_persisted_merge(client, monkeypatch) -> None:
    store = _ApprovalStore(_pending_approval_state("merging"))
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(report_server.remote, "UpdateGoogleSheet", lambda *_: None)

    response = client.post("/plaid/approve/item?token=test-token")
    status = client.get("/plaid/approve/item/status?token=test-token")

    assert response.status_code == 200
    assert status.get_json()["state"] == "active"


def test_plaid_approval_rejects_a_second_in_flight_request(client, monkeypatch) -> None:
    store = _ApprovalStore(_pending_approval_state())
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    assert report_server._plaid_approval_lock.acquire(blocking=False)

    response = client.post("/plaid/approve/item?token=test-token")

    report_server._plaid_approval_lock.release()
    assert response.status_code == 409
    assert response.get_json()["error_code"] == "approval_in_progress"


def test_plaid_approval_blocks_duplicate_active_account_mapping(
    client, monkeypatch
) -> None:
    state = _pending_approval_state()
    state["items"]["existing"] = {
        "status": "active",
        "selected_account_ids": ["other-account"],
        "account_mappings": {"other-account": "Amex"},
    }
    store = _ApprovalStore(state)
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    writes = []
    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(
        report_server.remote,
        "UpdateGoogleSheet",
        lambda *_: writes.append(True),
    )

    response = client.post("/plaid/approve/item?token=test-token")

    assert response.status_code == 409
    assert response.get_json()["error_code"] == "duplicate_account_mapping"
    assert writes == []
    assert store.state["items"]["item"]["status"] == "pending_review"


def test_plaid_review_renders_safety_summary_and_row_details(
    client, monkeypatch
) -> None:
    state = _pending_approval_state()
    state["items"]["item"]["pending_transactions"].append(
        {
            "account_id": "account",
            "transaction_id": "transfer",
            "date": "2026-08-02",
            "amount": -20.0,
            "merchant_name": "Incoming Transfer",
            "name": "Incoming Transfer",
            "personal_finance_category": {"primary": "TRANSFER_IN"},
        }
    )
    store = _ApprovalStore(state)
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)

    response = client.get("/plaid/review?token=test-token")

    assert response.status_code == 200
    assert b"Pre-merge safety summary" in response.data
    assert b"New candidates" in response.data
    assert b"Excluded (not added)" in response.data
    assert b"Incoming transfer" in response.data


def test_plaid_connections_lists_and_removes_an_item(client, monkeypatch) -> None:
    store = _ApprovalStore(_pending_approval_state("active"))
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    revoked = []

    class FakePlaidClient:
        def remove_item(self, access_token: str) -> None:
            revoked.append(access_token)

    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(plaid_source, "PlaidClient", FakePlaidClient)

    page = client.get("/plaid/connections?token=test-token")
    response = client.post(
        "/plaid/connections/item/remove?token=test-token",
        json={"remove_transactions": False},
    )

    assert page.status_code == 200
    assert b"Manage Plaid connections" in page.data
    assert response.status_code == 200
    assert response.get_json()["removed_transactions"] == 0
    assert revoked == ["access-token"]
    assert store.state["items"] == {}


def test_plaid_removal_only_deletes_rows_owned_by_the_item(client, monkeypatch) -> None:
    state = _pending_approval_state("active")
    state["items"]["item"]["imported_transaction_ids"] = ["plaid:owned"]
    store = _ApprovalStore(state)
    existing = pd.DataFrame(
        [
            ["2026-08-01", "Owned", -10, "Food", "Amex", "plaid:owned", "Owned"],
            ["2026-08-01", "Other", -20, "Food", "Amex", "plaid:other", "Other"],
            ["2026-08-01", "Manual", -30, "Food", "Amex", "manual", "Manual"],
        ],
        columns=config.GLOBAL.COLUMN_NAMES,
    )
    sheet = _ApprovalSheet(existing)
    writes = []

    class FakePlaidClient:
        def remove_item(self, _access_token: str) -> None:
            return None

    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(plaid_source, "PlaidClient", FakePlaidClient)
    monkeypatch.setattr(
        report_server.remote,
        "UpdateGoogleSheet",
        lambda _sheet, transactions, _accounts: writes.append(transactions),
    )

    response = client.post(
        "/plaid/connections/item/remove?token=test-token",
        json={"remove_transactions": True},
    )

    assert response.status_code == 200
    assert response.get_json()["removed_transactions"] == 1
    assert set(writes[0]["ID"]) == {"plaid:other", "manual"}


def test_plaid_removal_preserves_untracked_rows_for_safety(client, monkeypatch) -> None:
    store = _ApprovalStore(_pending_approval_state("active"))
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    revoked = []

    class FakePlaidClient:
        def remove_item(self, access_token: str) -> None:
            revoked.append(access_token)

    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(plaid_source, "PlaidClient", FakePlaidClient)

    response = client.post(
        "/plaid/connections/item/remove?token=test-token",
        json={"remove_transactions": True},
    )

    assert response.status_code == 409
    assert response.get_json()["error_code"] == "transaction_ownership_unknown"
    assert revoked == []
    assert "item" in store.state["items"]


def test_toyota_backfill_recovers_only_the_missing_debit(client, monkeypatch) -> None:
    state = _pending_approval_state("active")
    state["items"]["item"]["account_mappings"] = {"account": "Starone Savings"}
    store = _ApprovalStore(state)
    existing = pd.DataFrame(
        [
            [
                "2026-08-06",
                "Toyota",
                -511.46,
                "Transportation",
                "Starone Savings",
                "manual-august",
                "Toyota",
            ]
        ],
        columns=config.GLOBAL.COLUMN_NAMES,
    )
    sheet = _ApprovalSheet(existing)
    writes = []

    class FakePlaidClient:
        def transactions(self, _access_token: str, _start_date: str, _end_date: str):
            return [
                {
                    "account_id": "account",
                    "transaction_id": "september-toyota",
                    "date": "2026-09-06",
                    "amount": 511.46,
                    "merchant_name": "Toyota",
                    "name": "TOYOTA ACH RTL WEB",
                    "personal_finance_category": {"primary": "TRANSFER_IN"},
                },
                {
                    "account_id": "account",
                    "transaction_id": "credit",
                    "date": "2026-09-06",
                    "amount": -511.46,
                    "merchant_name": "Toyota ACH RTL WEB",
                    "name": "TOYOTA ACH RTL WEB",
                    "personal_finance_category": {"primary": "TRANSFER_IN"},
                },
                {
                    "account_id": "account",
                    "transaction_id": "unrelated",
                    "date": "2026-09-06",
                    "amount": 9.99,
                    "merchant_name": "Coffee Shop",
                    "name": "Coffee Shop",
                },
            ]

    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(plaid_source, "PlaidClient", FakePlaidClient)
    monkeypatch.setattr(
        report_server.remote,
        "UpdateGoogleSheet",
        lambda _sheet, transactions, _accounts: writes.append(transactions),
    )

    response = client.post("/plaid/backfill/toyota?token=test-token")

    assert response.status_code == 200
    assert response.get_json()["added"] == 1
    assert list(writes[0]["ID"]) == ["manual-august", "plaid:september-toyota"]
    assert store.state["items"]["item"]["imported_transaction_ids"] == [
        "plaid:september-toyota"
    ]


def test_toyota_backfill_uses_staged_unconnected_starone_debit(
    client, monkeypatch
) -> None:
    state = _pending_approval_state("active")
    state["items"]["review"] = {
        "status": "pending_review",
        "selected_account_ids": ["savings"],
        "account_mappings": {"savings": "Starone Savings"},
        "pending_transactions": [
            {
                "account_id": "savings",
                "transaction_id": "staged-toyota",
                "date": "2026-09-06",
                "amount": 511.46,
                "merchant_name": "Toyota",
                "name": "TOYOTA ACH RTL WEB",
                "personal_finance_category": {"primary": "TRANSFER_IN"},
            }
        ],
    }
    store = _ApprovalStore(state)
    sheet = _ApprovalSheet(pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES))
    writes = []

    class FakePlaidClient:
        def transactions(self, _access_token: str, _start_date: str, _end_date: str):
            return []

    monkeypatch.setattr(report_server, "_open_plaid_sheet", lambda: sheet)
    monkeypatch.setattr(plaid_source, "SheetStateStore", lambda _: store)
    monkeypatch.setattr(plaid_source, "PlaidClient", FakePlaidClient)
    monkeypatch.setattr(
        report_server.remote,
        "UpdateGoogleSheet",
        lambda _sheet, transactions, _accounts: writes.append(transactions),
    )

    response = client.post("/plaid/backfill/toyota?token=test-token")

    assert response.get_json()["added"] == 1
    assert list(writes[0]["ID"]) == ["plaid:staged-toyota"]
    assert store.state["items"]["review"]["status"] == "pending_review"


def test_report_file_requires_valid_token(client, tmp_path: Path) -> None:
    report_path = tmp_path / report_publisher.SPEND_REPORT_FILENAME
    report_path.write_text("<html>report</html>")

    missing = client.get("/reports/spend_profile.html")
    wrong = client.get("/reports/spend_profile.html?token=wrong")
    valid = client.get("/reports/spend_profile.html?token=test-token")

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert valid.status_code == 200
    assert b"<html>report</html>" in valid.data


def test_outlier_file_requires_valid_token(client, tmp_path: Path) -> None:
    outlier_path = tmp_path / report_publisher.OUTLIER_REPORT_FILENAME
    outlier_path.write_text("Date,Amount\n2026-01-01,10\n")

    response = client.get("/reports/outliers.csv?token=test-token")

    assert response.status_code == 200
    assert b"Date,Amount" in response.data


def test_generate_requires_valid_token(client) -> None:
    response = client.post("/generate")

    assert response.status_code == 403


def _wait_for_generate_status(
    client, expected_state: str, timeout: float = 5.0
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get("/generate/status?token=test-token").get_json()
        if payload["state"] == expected_state:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for state {expected_state}")


def _wait_for_scrape_status(client, expected_state: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get("/scrape/status?token=test-token").get_json()
        if payload["state"] == expected_state:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for state {expected_state}")


def test_generate_starts_background_job_and_returns_accepted(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    started = threading.Event()
    result = report_publisher.SpendReportResult(
        report_url="http://localhost:8080/reports/spend_profile.html?token=test-token",
        outlier_url="http://localhost:8080/reports/outliers.csv?token=test-token",
        generated_at="2026-06-09T12:00:00+00:00",
        status="success",
        source="sheets",
    )

    def publish(
        *,
        include_heatmap: bool = True,
        include_total_spend: bool = True,
        include_customdata: bool = True,
        **kwargs,
    ):
        started.set()
        assert include_heatmap is True
        assert include_total_spend is True
        assert include_customdata is True
        release.wait(timeout=5)
        return result

    monkeypatch.setattr(report_server.report_publisher, "publish_spend_report", publish)

    response = client.post("/generate?token=test-token")

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["state"] in {"queued", "running"}
    assert payload["active"] is True
    assert payload["job_id"]
    assert payload["status_url"] == "/generate/status?token=test-token"
    assert started.wait(timeout=5)

    running = _wait_for_generate_status(client, "running")
    assert running["job_id"] == payload["job_id"]

    release.set()
    finished = _wait_for_generate_status(client, "succeeded")
    assert finished["job_id"] == payload["job_id"]
    assert finished["report_url"] == result.report_url
    assert finished["outlier_url"] == result.outlier_url
    assert finished["error"] == ""


def test_generate_rejects_concurrent_request(client) -> None:
    release = threading.Event()
    started = threading.Event()

    def publish(
        *,
        include_heatmap: bool = True,
        include_total_spend: bool = True,
        include_customdata: bool = True,
        **kwargs,
    ):
        started.set()
        assert include_heatmap is True
        assert include_total_spend is True
        assert include_customdata is True
        release.wait(timeout=5)
        return report_publisher.SpendReportResult(
            report_url="",
            outlier_url="",
            generated_at="2026-06-09T12:00:00+00:00",
            status="success",
            source="sheets",
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(report_server.report_publisher, "publish_spend_report", publish)
    try:
        first = client.post("/generate?token=test-token")
        assert first.status_code == 202
        assert started.wait(timeout=5)

        response = client.post("/generate?token=test-token")

        assert response.status_code == 409
        assert response.get_json()["error"] == "generation already running"
    finally:
        release.set()
        _wait_for_generate_status(client, "succeeded")
        monkeypatch.undo()


def test_generate_failure_returns_500(client, monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    result = report_publisher.SpendReportResult(
        report_url="",
        outlier_url="",
        generated_at="2026-06-09T12:00:00+00:00",
        status="failed",
        source="sheets",
        error="boom",
    )

    def publish(
        *,
        include_heatmap: bool = True,
        include_total_spend: bool = True,
        include_customdata: bool = True,
        **kwargs,
    ):
        started.set()
        assert include_heatmap is True
        assert include_total_spend is True
        assert include_customdata is True
        return result

    monkeypatch.setattr(
        report_server.report_publisher,
        "publish_spend_report",
        publish,
    )

    response = client.post("/generate?token=test-token")

    assert response.status_code == 202
    assert started.wait(timeout=5)
    finished = _wait_for_generate_status(client, "failed")
    assert finished["error"] == "boom"
    assert finished["state"] == "failed"


def test_generate_status_is_idle_before_any_job(client) -> None:
    response = client.get("/generate/status?token=test-token")

    assert response.status_code == 200
    assert response.get_json() == {"state": "idle", "active": False}


def test_scrape_requires_valid_token(client) -> None:
    response = client.post("/scrape")

    assert response.status_code == 403


def test_scrape_skips_when_recent(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    last_scrape_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    monkeypatch.setattr(report_server, "_load_last_scrape_at", lambda: last_scrape_at)
    monkeypatch.setattr(report_server.scraper, "scrape_lock_available", lambda: True)

    response = client.post("/scrape?token=test-token")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["state"] == "skipped"
    assert payload["active"] is False
    assert payload["skip_reason"]
    assert payload["last_successful_at"] == last_scrape_at.isoformat()
    assert payload["age_seconds"] is not None


def test_scrape_queues_durable_worker_and_returns_accepted(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[report_server.ScrapeJob] = []
    monkeypatch.setattr(report_server, "_load_last_scrape_at", lambda: None)
    monkeypatch.setattr(report_server, "_save_durable_scrape_job", saved.append)

    response = client.post("/scrape?token=test-token")

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["state"] in {"queued", "running"}
    assert payload["active"] is True
    assert payload["job_id"]
    assert payload["status_url"] == "/scrape/status?token=test-token"
    assert saved[0].state == "queued"
    assert saved[0].job_id == payload["job_id"]


def test_scrape_reports_worker_dispatch_failure(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[report_server.ScrapeJob] = []
    monkeypatch.setattr(report_server, "_load_last_scrape_at", lambda: None)
    monkeypatch.setattr(report_server, "_save_durable_scrape_job", saved.append)

    def fail_start() -> None:
        raise report_server.fly_machine.FlyMachineError("Fly API unavailable")

    monkeypatch.setattr(report_server.fly_machine, "start_scraper_machine", fail_start)

    response = client.post("/scrape?token=test-token")

    assert response.status_code == 503
    assert response.get_json()["error_code"] == "scrape_worker_unavailable"
    assert saved[-1].state == "failed"


def test_scrape_rejects_active_durable_job(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = report_server.ScrapeJob(
        job_id="active-job",
        state="running",
        created_at=datetime.now(timezone.utc).isoformat(),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    monkeypatch.setattr(report_server, "_load_last_scrape_at", lambda: None)
    monkeypatch.setattr(report_server, "_load_durable_scrape_job", lambda: running)

    response = client.post("/scrape?token=test-token")

    assert response.status_code == 409
    assert response.get_json()["job_id"] == "active-job"


def test_scrape_status_uses_durable_worker_result(client, monkeypatch) -> None:
    completed = report_server.ScrapeJob(
        job_id="durable-job",
        state="succeeded",
        created_at="2026-08-24T00:00:00+00:00",
        started_at="2026-08-24T00:00:01+00:00",
        finished_at="2026-08-24T00:01:00+00:00",
        last_successful_at="2026-08-24T00:01:00+00:00",
        source="plaid",
    )
    monkeypatch.setattr(report_server, "_load_durable_scrape_job", lambda: completed)

    response = client.get("/scrape/status?token=test-token")

    assert response.status_code == 200
    assert response.get_json()["job_id"] == "durable-job"
    assert response.get_json()["state"] == "succeeded"


def test_stopped_worker_marks_running_durable_job_failed(monkeypatch) -> None:
    saved: list[report_server.ScrapeJob] = []
    running = report_server.ScrapeJob(
        job_id="interrupted-job",
        state="running",
        created_at="2026-08-24T00:00:00+00:00",
        started_at="2026-08-24T00:00:00+00:00",
    )
    monkeypatch.setattr(report_server, "_save_durable_scrape_job", saved.append)
    monkeypatch.setattr(
        report_server.fly_machine, "scraper_machine_state", lambda: "stopped"
    )

    report_server._terminalize_stale_scrape_job(running)

    assert running.state == "failed"
    assert running.error_code == "worker_interrupted"
    assert saved == [running]


def test_scrape_status_is_idle_before_any_job(client) -> None:
    response = client.get("/scrape/status?token=test-token")

    assert response.status_code == 200
    assert response.get_json() == {"state": "idle", "active": False}
