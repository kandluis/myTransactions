from pathlib import Path
import threading
import time

import pytest

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


def _wait_for_status(client, expected_state: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get("/generate/status?token=test-token").get_json()
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

    def publish(**kwargs):
        started.set()
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

    running = _wait_for_status(client, "running")
    assert running["job_id"] == payload["job_id"]

    release.set()
    finished = _wait_for_status(client, "succeeded")
    assert finished["job_id"] == payload["job_id"]
    assert finished["report_url"] == result.report_url
    assert finished["outlier_url"] == result.outlier_url
    assert finished["error"] == ""


def test_generate_rejects_concurrent_request(client) -> None:
    release = threading.Event()
    started = threading.Event()

    def publish(**kwargs):
        started.set()
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
        _wait_for_status(client, "succeeded")
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

    def publish(**kwargs):
        started.set()
        return result

    monkeypatch.setattr(
        report_server.report_publisher,
        "publish_spend_report",
        publish,
    )

    response = client.post("/generate?token=test-token")

    assert response.status_code == 202
    assert started.wait(timeout=5)
    finished = _wait_for_status(client, "failed")
    assert finished["error"] == "boom"
    assert finished["state"] == "failed"


def test_generate_status_is_idle_before_any_job(client) -> None:
    response = client.get("/generate/status?token=test-token")

    assert response.status_code == 200
    assert response.get_json() == {"state": "idle", "active": False}
