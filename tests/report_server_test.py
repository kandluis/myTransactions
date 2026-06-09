from pathlib import Path

import pytest

import report_publisher
import report_server


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("REPORT_TOKEN", "test-token")
    monkeypatch.setenv("REPORT_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path))
    return report_server.app.test_client()


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


def test_generate_calls_publish_once_and_returns_json(
    client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []
    result = report_publisher.SpendReportResult(
        report_url="http://localhost:8080/reports/spend_profile.html?token=test-token",
        outlier_url="http://localhost:8080/reports/outliers.csv?token=test-token",
        generated_at="2026-06-09T12:00:00+00:00",
        status="success",
        source="sheets",
    )

    def publish(**kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr(report_server.report_publisher, "publish_spend_report", publish)

    response = client.post("/generate?token=test-token")

    assert response.status_code == 200
    assert response.get_json() == result.as_dict()
    assert len(calls) == 1
    assert calls[0]["source"] == "sheets"
    assert calls[0]["output_dir"] == tmp_path
    assert calls[0]["base_url"] == "http://localhost:8080"
    assert calls[0]["token"] == "test-token"
    assert calls[0]["update_sheet"] is True


def test_generate_rejects_concurrent_request(client) -> None:
    acquired = report_server._generate_lock.acquire(blocking=False)
    assert acquired
    try:
        response = client.post("/generate?token=test-token")
    finally:
        report_server._generate_lock.release()

    assert response.status_code == 409
    assert response.get_json() == {"error": "generation already running"}


def test_generate_failure_returns_500(client, monkeypatch: pytest.MonkeyPatch) -> None:
    result = report_publisher.SpendReportResult(
        report_url="",
        outlier_url="",
        generated_at="2026-06-09T12:00:00+00:00",
        status="failed",
        source="sheets",
        error="boom",
    )
    monkeypatch.setattr(
        report_server.report_publisher,
        "publish_spend_report",
        lambda **kwargs: result,
    )

    response = client.post("/generate?token=test-token")

    assert response.status_code == 500
    assert response.get_json() == result.as_dict()
