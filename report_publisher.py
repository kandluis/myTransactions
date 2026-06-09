"""Publish the spend report to disk and optionally update Google Sheets status."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import pandas as pd
import pygsheets

import auth
import config
from scripts import generate_spend_charts

logger = logging.getLogger(__name__)

DEFAULT_REPORT_DIR = Path(os.getenv("REPORT_OUTPUT_DIR", "/data/reports"))
SPEND_REPORT_FILENAME = "spend_profile.html"
OUTLIER_REPORT_FILENAME = "outliers.csv"
STATUS_RANGE_START = "F1"
STATUS_URL_VALUE_CELLS = ("G1", "G2")
STATUS_LABELS = [
    "Latest spend report URL",
    "Latest outlier report URL",
    "Report generated at",
    "Report generation status",
    "Report generation source",
    "Report generation error",
]


def _job_prefix(job_id: Optional[str]) -> str:
    return f"[report job {job_id}] " if job_id else ""


def _log(job_id: Optional[str], message: str, *args: object) -> None:
    if args:
        logger.info("%s" + message, _job_prefix(job_id), *args)
    else:
        logger.info("%s%s", _job_prefix(job_id), message)


def _elapsed(start: float) -> str:
    return f"{time.perf_counter() - start:.2f}s"


@dataclass(frozen=True)
class SpendReportResult:
    """Result metadata for a report publication attempt."""

    report_url: str
    outlier_url: str
    generated_at: str
    status: str
    source: str
    error: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "report_url": self.report_url,
            "outlier_url": self.outlier_url,
            "generated_at": self.generated_at,
            "status": self.status,
            "source": self.source,
            "error": self.error,
        }


def build_report_url(base_url: str, filename: str, token: str) -> str:
    """Build a tokenized report URL."""
    clean_base = base_url.rstrip("/")
    query = urlencode({"token": token})
    return f"{clean_base}/reports/{filename}?{query}"


def build_report_urls(base_url: str, token: str) -> tuple[str, str]:
    """Return tokenized URLs for the HTML report and outlier CSV."""
    return (
        build_report_url(base_url, SPEND_REPORT_FILENAME, token),
        build_report_url(base_url, OUTLIER_REPORT_FILENAME, token),
    )


def open_configured_spreadsheet() -> pygsheets.Spreadsheet:
    """Open the configured Google Sheet using the repo's auth helper."""
    creds = auth.GetCredentials()
    client = pygsheets.authorize(custom_credentials=creds.sheets)
    return client.open(config.GLOBAL.WORKSHEET_TITLE)


def load_transactions_from_sheet(sheet: pygsheets.Spreadsheet) -> pd.DataFrame:
    """Load transactions from an already-open Google Sheet."""
    worksheet = sheet.worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
    return generate_spend_charts._normalize_transaction_columns(
        worksheet.get_as_df(numerize=False)
    )


def _existing_url_values(settings_ws: pygsheets.Worksheet) -> tuple[str, str]:
    values: list[str] = []
    for cell in STATUS_URL_VALUE_CELLS:
        try:
            values.append(str(settings_ws.get_value(cell) or ""))
        except Exception:
            values.append("")
    return values[0], values[1]


def write_report_status(
    sheet: pygsheets.Spreadsheet,
    result: SpendReportResult,
    *,
    job_id: Optional[str] = None,
) -> None:
    """Write report publication status to Settings!F1:G6."""
    settings_ws = sheet.worksheet_by_title(title=config.GLOBAL.SETTINGS_SHEET_TITLE)
    report_url = result.report_url
    outlier_url = result.outlier_url
    if result.status != "success":
        existing_report_url, existing_outlier_url = _existing_url_values(settings_ws)
        report_url = report_url or existing_report_url
        outlier_url = outlier_url or existing_outlier_url

    values = [
        [STATUS_LABELS[0], report_url],
        [STATUS_LABELS[1], outlier_url],
        [STATUS_LABELS[2], result.generated_at],
        [STATUS_LABELS[3], result.status],
        [STATUS_LABELS[4], result.source],
        [STATUS_LABELS[5], result.error],
    ]
    settings_ws.update_values(STATUS_RANGE_START, values)
    _log(job_id, "Updated Settings!F1:G6 with status=%s", result.status)


def generate_report_files(
    txns: pd.DataFrame,
    output_dir: Path,
    *,
    window: int = 31,
    top_n_categories: Optional[int] = generate_spend_charts.DEFAULT_TOP_N_CATEGORIES,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    cap_daily_spend: Optional[float] = None,
    auto_cap: bool = True,
    include_heatmap: bool = True,
    include_total_spend: bool = True,
    include_customdata: bool = True,
    job_id: Optional[str] = None,
) -> tuple[Path, Path]:
    """Generate the HTML spend report and outlier CSV under output_dir."""
    stage_start = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / SPEND_REPORT_FILENAME
    outlier_path = output_dir / OUTLIER_REPORT_FILENAME

    _log(
        job_id,
        "Preparing report files from %d transactions into %s",
        len(txns),
        output_dir,
    )
    prep_start = time.perf_counter()
    prepared_txns = generate_spend_charts._prepare_transactions(
        txns,
        start_date=start_date,
        end_date=end_date,
        job_id=job_id,
    )
    _log(
        job_id,
        "Prepared %d transactions in %s",
        len(prepared_txns),
        _elapsed(prep_start),
    )
    group_start = time.perf_counter()
    grouped_txns = generate_spend_charts._apply_top_n_category_grouping(
        prepared_txns, top_n_categories
    )
    _log(
        job_id,
        "Grouped transactions into %d rows across %d categories in %s",
        len(grouped_txns),
        grouped_txns["Category"].nunique() if not grouped_txns.empty else 0,
        _elapsed(group_start),
    )
    spend_start = time.perf_counter()
    spend_data = generate_spend_charts.prepare_spend_data(
        grouped_txns,
        window=window,
        top_n_categories=None,
        skip_cleanup=True,
        cap_daily_spend=cap_daily_spend,
        auto_cap=auto_cap,
        job_id=job_id,
    )
    _log(
        job_id,
        "Built spend grid with %d rows across %d dates in %s",
        len(spend_data),
        spend_data["Date"].nunique() if not spend_data.empty else 0,
        _elapsed(spend_start),
    )
    chart_start = time.perf_counter()
    generate_spend_charts.write_spend_chart(
        spend_data,
        report_path,
        window=window,
        include_heatmap=include_heatmap,
        include_total_spend=include_total_spend,
        include_customdata=include_customdata,
    )
    _log(
        job_id, "Wrote spend chart HTML to %s in %s", report_path, _elapsed(chart_start)
    )
    outlier_start = time.perf_counter()
    outlier_report = generate_spend_charts.build_outlier_report(
        grouped_txns,
        spend_data,
        cap_daily_spend=cap_daily_spend,
    )
    _log(
        job_id,
        "Built outlier report with %d rows in %s",
        len(outlier_report),
        _elapsed(outlier_start),
    )
    outlier_write_start = time.perf_counter()
    generate_spend_charts.write_outlier_report(outlier_report, outlier_path)
    _log(
        job_id,
        "Wrote outlier CSV to %s in %s",
        outlier_path,
        _elapsed(outlier_write_start),
    )
    _log(
        job_id,
        "Generated report files in %s (txns=%d, spend_rows=%d, report=%s, outliers=%s)",
        _elapsed(stage_start),
        len(txns),
        len(spend_data),
        report_path,
        outlier_path,
    )
    return report_path, outlier_path


def publish_spend_report(
    *,
    source: str = "sheets",
    output_dir: Path = DEFAULT_REPORT_DIR,
    base_url: str = "",
    token: str = "",
    update_sheet: bool = False,
    input_path: Optional[Path] = None,
    window: int = 31,
    include_heatmap: bool = True,
    include_total_spend: bool = True,
    include_customdata: bool = True,
    job_id: Optional[str] = None,
) -> SpendReportResult:
    """Generate report files, build tokenized URLs, and update Sheets status."""
    generated_at = datetime.now(timezone.utc).isoformat()
    sheet: Optional[pygsheets.Spreadsheet] = None
    job_start = time.perf_counter()
    _log(
        job_id,
        "Starting spend report publish (source=%s, update_sheet=%s, output_dir=%s)",
        source,
        update_sheet,
        output_dir,
    )

    try:
        if source == "sheets":
            stage_start = time.perf_counter()
            sheet = open_configured_spreadsheet()
            _log(job_id, "Opened configured spreadsheet in %s", _elapsed(stage_start))
            stage_start = time.perf_counter()
            txns = load_transactions_from_sheet(sheet)
            _log(
                job_id,
                "Loaded %d transactions from Sheets in %s",
                len(txns),
                _elapsed(stage_start),
            )
        elif source == "csv":
            if input_path is None:
                input_path = generate_spend_charts.DEFAULT_INPUT
            stage_start = time.perf_counter()
            txns = generate_spend_charts.load_transactions_from_csv(input_path)
            _log(
                job_id,
                "Loaded %d transactions from CSV %s in %s",
                len(txns),
                input_path,
                _elapsed(stage_start),
            )
        else:
            raise ValueError(f"Unsupported report source: {source}")

        stage_start = time.perf_counter()
        generate_report_files(
            txns,
            output_dir,
            window=window,
            include_heatmap=include_heatmap,
            include_total_spend=include_total_spend,
            include_customdata=include_customdata,
            job_id=job_id,
        )
        _log(job_id, "Report generation finished in %s", _elapsed(stage_start))
        report_url = ""
        outlier_url = ""
        if base_url and token:
            report_url, outlier_url = build_report_urls(base_url, token)
            _log(job_id, "Built tokenized report URLs for %s", base_url)
        result = SpendReportResult(
            report_url=report_url,
            outlier_url=outlier_url,
            generated_at=generated_at,
            status="success",
            source=source,
        )
    except Exception as exc:
        logger.exception("Spend report generation failed.")
        result = SpendReportResult(
            report_url="",
            outlier_url="",
            generated_at=generated_at,
            status="failed",
            source=source,
            error=str(exc),
        )

    if update_sheet:
        stage_start = time.perf_counter()
        if sheet is None:
            _log(job_id, "Opening spreadsheet for status write")
            sheet = open_configured_spreadsheet()
        write_report_status(sheet, result, job_id=job_id)
        _log(job_id, "Status write finished in %s", _elapsed(stage_start))

    _log(
        job_id,
        "Spend report publish completed with status=%s in %s",
        result.status,
        _elapsed(job_start),
    )
    return result
