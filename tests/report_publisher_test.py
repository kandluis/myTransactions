from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

import report_publisher
from scripts import publish_spend_report


def test_build_report_urls_include_token() -> None:
    report_url, outlier_url = report_publisher.build_report_urls(
        "https://example.test/", "secret token"
    )

    assert report_url == (
        "https://example.test/reports/spend_profile.html?token=secret+token"
    )
    assert outlier_url == "https://example.test/reports/outliers.csv?token=secret+token"


def test_write_report_status_writes_expected_settings_block() -> None:
    sheet = MagicMock()
    settings_ws = MagicMock()
    sheet.worksheet_by_title.return_value = settings_ws
    result = report_publisher.SpendReportResult(
        report_url="https://example.test/report",
        outlier_url="https://example.test/outliers",
        generated_at="2026-06-09T12:00:00+00:00",
        status="success",
        source="sheets",
    )

    report_publisher.write_report_status(sheet, result)

    settings_ws.update_values.assert_called_once_with(
        "D5",
        [
            ["https://example.test/report"],
            ["https://example.test/outliers"],
            ["2026-06-09T12:00:00+00:00"],
            ["success"],
            ["sheets"],
            [""],
        ],
    )


def test_write_report_status_preserves_urls_on_failure() -> None:
    sheet = MagicMock()
    settings_ws = MagicMock()
    settings_ws.get_value.side_effect = [
        "https://example.test/old-report",
        "https://example.test/old-outliers",
    ]
    sheet.worksheet_by_title.return_value = settings_ws
    result = report_publisher.SpendReportResult(
        report_url="",
        outlier_url="",
        generated_at="2026-06-09T12:00:00+00:00",
        status="failed",
        source="sheets",
        error="boom",
    )

    report_publisher.write_report_status(sheet, result)

    written_values = settings_ws.update_values.call_args.args[1]
    assert written_values[0] == ["https://example.test/old-report"]
    assert written_values[1] == ["https://example.test/old-outliers"]
    assert written_values[3] == ["failed"]
    assert written_values[5] == ["boom"]


def test_publish_spend_report_calls_loader_writer_and_sheet_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    sheet = MagicMock()

    def load_csv(path: Path):
        calls.append(f"load:{path}")
        return MagicMock()

    def generate_files(
        txns,
        output_dir: Path,
        *,
        window: int = 31,
        include_heatmap: bool = True,
        include_total_spend: bool = True,
        include_category_share: bool = True,
        include_customdata: bool = True,
        job_id=None,
    ):
        calls.append(f"generate:{output_dir}:{window}")
        assert include_heatmap is True
        assert include_total_spend is True
        assert include_category_share is True
        assert include_customdata is True
        return output_dir / "spend_profile.html", output_dir / "outliers.csv"

    def write_status(status_sheet, result, *, job_id=None):
        calls.append(f"status:{result.status}:{result.report_url}")
        assert status_sheet is sheet

    monkeypatch.setattr(
        report_publisher.generate_spend_charts,
        "load_transactions_from_csv",
        load_csv,
    )
    monkeypatch.setattr(report_publisher, "generate_report_files", generate_files)
    monkeypatch.setattr(report_publisher, "open_configured_spreadsheet", lambda: sheet)
    monkeypatch.setattr(report_publisher, "write_report_status", write_status)

    result = report_publisher.publish_spend_report(
        source="csv",
        input_path=Path("txns.csv"),
        output_dir=Path("/tmp/reports"),
        base_url="https://example.test",
        token="secret",
        update_sheet=True,
        window=7,
    )

    assert result.status == "success"
    assert calls == [
        "load:txns.csv",
        "generate:/tmp/reports:7",
        "status:success:https://example.test/reports/spend_profile.html?token=secret",
    ]


def test_publish_spend_report_records_failure_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sheet = MagicMock()
    written_results: list[report_publisher.SpendReportResult] = []

    def fail_load(path: Path):
        raise ValueError("bad csv")

    monkeypatch.setattr(
        report_publisher.generate_spend_charts,
        "load_transactions_from_csv",
        fail_load,
    )
    monkeypatch.setattr(report_publisher, "open_configured_spreadsheet", lambda: sheet)
    monkeypatch.setattr(
        report_publisher,
        "write_report_status",
        lambda status_sheet, result, *, job_id=None: written_results.append(result),
    )

    result = report_publisher.publish_spend_report(
        source="csv",
        input_path=Path("txns.csv"),
        update_sheet=True,
    )

    assert result.status == "failed"
    assert "bad csv" in result.error
    assert written_results == [result]


def test_publish_spend_report_logs_stage_progress(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sheet = MagicMock()

    monkeypatch.setattr(
        report_publisher.generate_spend_charts,
        "load_transactions_from_csv",
        lambda path: pd.DataFrame([{"id": 1}]),
    )
    monkeypatch.setattr(
        report_publisher,
        "generate_report_files",
        lambda txns, output_dir, *, window=31, include_heatmap=True, include_total_spend=True, include_category_share=True, include_customdata=True, job_id=None: (
            output_dir / "spend_profile.html",
            output_dir / "outliers.csv",
        ),
    )
    monkeypatch.setattr(report_publisher, "open_configured_spreadsheet", lambda: sheet)
    monkeypatch.setattr(
        report_publisher,
        "write_report_status",
        lambda status_sheet, result, *, job_id=None: None,
    )

    with caplog.at_level("INFO"):
        report_publisher.publish_spend_report(
            source="csv",
            input_path=Path("txns.csv"),
            output_dir=Path("/tmp/reports"),
            base_url="https://example.test",
            token="secret",
            update_sheet=True,
            job_id="job-1",
        )

    messages = "\n".join(record.message for record in caplog.records)
    assert "[report job job-1]" in messages
    assert "Loaded 1 transactions from CSV" in messages
    assert "Report generation finished" in messages
    assert "Status write finished" in messages


def test_generate_report_files_logs_each_stage(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    txns = pd.DataFrame(
        [
            {
                "Date": "2026-06-01",
                "Merchant": "Coffee Shop",
                "Amount": 12.34,
                "Category": "Food",
                "Account": "Checking",
                "ID": "txn-1",
                "Description": "Morning coffee",
            },
            {
                "Date": "2026-06-02",
                "Merchant": "Book Store",
                "Amount": 45.67,
                "Category": "Books",
                "Account": "Checking",
                "ID": "txn-2",
                "Description": "Books",
            },
        ]
    )
    calls: list[str] = []

    monkeypatch.setattr(
        report_publisher.generate_spend_charts,
        "write_spend_chart",
        lambda spend_data, output_path, *, window, include_heatmap=True, include_total_spend=True, include_category_share=True, include_customdata=True: calls.append(
            f"chart:{output_path}:{len(spend_data)}:{window}:{include_heatmap}:{include_total_spend}:{include_category_share}:{include_customdata}"
        ),
    )
    monkeypatch.setattr(
        report_publisher.generate_spend_charts,
        "write_outlier_report",
        lambda outlier_report, output_path: calls.append(
            f"outliers:{output_path}:{len(outlier_report)}"
        ),
    )

    with caplog.at_level("INFO"):
        report_publisher.generate_report_files(
            txns,
            Path("/tmp/reports"),
            job_id="job-1",
        )

    messages = "\n".join(record.message for record in caplog.records)
    assert "[report job job-1]" in messages
    assert "Preparing report files from 2 transactions" in messages
    assert "Prepared 2 transactions" in messages
    assert "Grouped transactions into" in messages
    assert "Built spend grid with" in messages
    assert "Wrote spend chart HTML" in messages
    assert "Built outlier report with" in messages
    assert "Wrote outlier CSV" in messages
    assert calls[0].startswith("chart:/tmp/reports/spend_profile.html:")
    assert calls[1].startswith("outliers:/tmp/reports/outliers.csv:")


def test_cli_publish_exits_nonzero_on_failed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed = report_publisher.SpendReportResult(
        report_url="",
        outlier_url="",
        generated_at="2026-06-09T12:00:00+00:00",
        status="failed",
        source="sheets",
        error="boom",
    )
    monkeypatch.setattr(
        publish_spend_report.report_publisher,
        "publish_spend_report",
        lambda **kwargs: failed,
    )

    with pytest.raises(SystemExit, match="boom"):
        publish_spend_report.main([])
