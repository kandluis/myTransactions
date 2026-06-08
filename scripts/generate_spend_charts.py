"""Generate interactive historical spending charts."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import plotly.express as px  # type: ignore[import-untyped]
import pygsheets

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import auth  # noqa: E402
import config  # noqa: E402
import remote  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_INPUT = Path("transactions_updated.csv")
DEFAULT_OUTPUT = Path("spend_profile.html")
SPEND_COLUMN = "Spend"
ROLLING_SPEND_COLUMN = "RollingAverageSpend"


def _normalize_transaction_columns(txns: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of txns with the repo's canonical transaction columns."""
    column_names = list(config.GLOBAL.COLUMN_NAMES)
    raw_columns = list(config.GLOBAL.COLUMNS)
    normalized = txns.copy()

    if all(column in normalized.columns for column in column_names):
        normalized = normalized[column_names]
    elif all(column in normalized.columns for column in raw_columns):
        normalized = normalized[raw_columns]
        normalized.columns = pd.Index(column_names)
    else:
        missing = [
            column for column in column_names if column not in normalized.columns
        ]
        raise ValueError(
            "Input transactions must include canonical columns "
            f"{column_names}; missing {missing}."
        )

    normalized["Merchant"] = normalized["Merchant"].fillna(normalized["Description"])
    normalized["Description"] = normalized["Description"].fillna("")
    normalized["Amount"] = pd.to_numeric(normalized["Amount"], errors="raise")
    return normalized


def load_transactions_from_csv(input_path: Path) -> pd.DataFrame:
    """Load transactions from a local CSV file."""
    return _normalize_transaction_columns(pd.read_csv(input_path))


def load_transactions_from_sheets() -> pd.DataFrame:
    """Load transactions from the configured Google Sheet."""
    creds = auth.GetCredentials()
    client = pygsheets.authorize(custom_credentials=creds.sheets)
    sheet = client.open(config.GLOBAL.WORKSHEET_TITLE)
    worksheet = sheet.worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
    return _normalize_transaction_columns(worksheet.get_as_df(numerize=False))


def prepare_spend_data(
    txns: pd.DataFrame,
    *,
    window: int = 31,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exclude_categories: Optional[Iterable[str]] = None,
    top_n_categories: Optional[int] = None,
    skip_cleanup: bool = False,
) -> pd.DataFrame:
    """Apply category rules and build a daily category spend grid."""
    if window < 1:
        raise ValueError("--window must be at least 1.")
    if top_n_categories is not None and top_n_categories < 1:
        raise ValueError("--top-n-categories must be at least 1 when provided.")

    prepared = _normalize_transaction_columns(txns)
    prepared = remote.ApplyCategoryRules(prepared)
    if not skip_cleanup:
        prepared = remote._cleanTxns(prepared)

    prepared = prepared.copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="raise").dt.normalize()
    if start_date is not None:
        prepared = prepared[prepared["Date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        prepared = prepared[prepared["Date"] <= pd.Timestamp(end_date)]

    if exclude_categories:
        excluded = set(exclude_categories)
        prepared = prepared[~prepared["Category"].isin(excluded)]

    if prepared.empty:
        return pd.DataFrame(
            columns=["Date", "Category", SPEND_COLUMN, ROLLING_SPEND_COLUMN]
        )

    prepared[SPEND_COLUMN] = prepared["Amount"].abs()

    if top_n_categories is not None:
        totals = prepared.groupby("Category", sort=False)[SPEND_COLUMN].sum()
        top_categories = set(
            totals.sort_values(ascending=False).head(top_n_categories).index
        )
        prepared["Category"] = prepared["Category"].where(
            prepared["Category"].isin(top_categories), "Other"
        )

    daily = (
        prepared.groupby(["Date", "Category"], as_index=True)[SPEND_COLUMN]
        .sum()
        .sort_index()
    )
    dates = pd.date_range(prepared["Date"].min(), prepared["Date"].max(), freq="D")
    categories = pd.Index(sorted(prepared["Category"].unique()), name="Category")
    complete_index = pd.MultiIndex.from_product(
        [dates.rename("Date"), categories], names=["Date", "Category"]
    )

    grid = daily.reindex(complete_index, fill_value=0).reset_index()
    grid[ROLLING_SPEND_COLUMN] = grid.groupby("Category", group_keys=False)[
        SPEND_COLUMN
    ].transform(lambda series: series.rolling(window=window, min_periods=1).mean())
    return grid


def write_spend_chart(spend_data: pd.DataFrame, output_path: Path) -> None:
    """Write an interactive stacked area chart to output_path."""
    fig = px.area(
        spend_data,
        x="Date",
        y=ROLLING_SPEND_COLUMN,
        color="Category",
        labels={
            "Date": "Date",
            "Category": "Category",
            ROLLING_SPEND_COLUMN: "Rolling average daily spend",
        },
        title="Historical Spend Profile",
        hover_data={
            "Date": "|%Y-%m-%d",
            "Category": True,
            ROLLING_SPEND_COLUMN: ":$.2f",
            SPEND_COLUMN: False,
        },
    )
    fig.update_layout(
        hovermode="x unified",
        yaxis_title="Rolling average daily spend",
        xaxis_title="Date",
        legend_title_text="Category",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn", full_html=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate interactive spending charts from transactions."
    )
    parser.add_argument("--source", choices=("csv", "sheets"), default="csv")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="CSV input path. Defaults to transactions_updated.csv when present.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--top-n-categories", type=int, default=None)
    parser.add_argument("--exclude-category", action="append", default=[])
    parser.add_argument("--skip-cleanup", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    args = build_parser().parse_args(argv)

    if args.source == "sheets":
        logger.info("Loading transactions from Google Sheets.")
        txns = load_transactions_from_sheets()
    else:
        input_path = args.input or DEFAULT_INPUT
        if not input_path.exists():
            raise FileNotFoundError(
                f"CSV input {input_path} does not exist. Pass --input or run "
                "updater.py --dry_run to create transactions_updated.csv."
            )
        logger.info("Loading transactions from %s.", input_path)
        txns = load_transactions_from_csv(input_path)

    spend_data = prepare_spend_data(
        txns,
        window=args.window,
        start_date=args.start_date,
        end_date=args.end_date,
        exclude_categories=args.exclude_category,
        top_n_categories=args.top_n_categories,
        skip_cleanup=args.skip_cleanup,
    )
    write_spend_chart(spend_data, args.output)
    logger.info("Wrote %s.", args.output)


if __name__ == "__main__":
    main()
