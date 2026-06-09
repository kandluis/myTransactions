"""Generate and publish the spend report from CSV or Google Sheets."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import report_publisher  # noqa: E402

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the spend report and optionally publish its URL."
    )
    parser.add_argument("--source", choices=("csv", "sheets"), default="sheets")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="CSV input path when --source=csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=report_publisher.DEFAULT_REPORT_DIR,
        help="Directory for spend_profile.html and outliers.csv.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("REPORT_BASE_URL", ""),
        help="Base URL for tokenized report links.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("REPORT_TOKEN", ""),
        help="Report token used in generated links.",
    )
    parser.add_argument(
        "--update-sheet",
        action="store_true",
        help="Write latest report status to Settings!F1:G6.",
    )
    parser.add_argument("--window", type=int, default=31)
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    args = build_parser().parse_args(argv)
    result = report_publisher.publish_spend_report(
        source=args.source,
        output_dir=args.output_dir,
        base_url=args.base_url,
        token=args.token,
        update_sheet=args.update_sheet,
        input_path=args.input,
        window=args.window,
    )
    if result.status != "success":
        raise SystemExit(f"Spend report generation failed: {result.error}")

    logger.info("Wrote spend report to %s.", args.output_dir)
    if result.report_url:
        logger.info("Report URL: %s", result.report_url)


if __name__ == "__main__":
    main()
