"""Generate interactive historical spending charts."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import plotly.graph_objects as go  # type: ignore[import-untyped]
import pygsheets
from plotly.subplots import make_subplots  # type: ignore[import-untyped]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import auth  # noqa: E402
import config  # noqa: E402
import remote  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_INPUT = Path("transactions_updated.csv")
DEFAULT_OUTPUT = Path("spend_profile.html")
DEFAULT_TOP_N_CATEGORIES = 10
SPEND_COLUMN = "Spend"
DISPLAY_SPEND_COLUMN = "DisplaySpend"
ROLLING_SPEND_COLUMN = "RollingAverageSpend"
RAW_ROLLING_SPEND_COLUMN = "RawRollingAverageSpend"
CAPPED_COLUMN = "IsCapped"
DAILY_CATEGORY_SPEND_COLUMN = "DailyCategorySpend"
DAILY_TOTAL_SPEND_COLUMN = "DailyTotalSpend"


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


def _prepare_transactions(
    txns: pd.DataFrame,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exclude_categories: Optional[Iterable[str]] = None,
    skip_cleanup: bool = False,
) -> pd.DataFrame:
    """Apply shared transaction cleanup, category rules, and filters."""
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

    prepared = prepared.copy()
    prepared[SPEND_COLUMN] = prepared["Amount"].abs()
    return prepared


def _apply_top_n_category_grouping(
    txns: pd.DataFrame, top_n_categories: Optional[int]
) -> pd.DataFrame:
    """Group non-top categories into Other using raw spend totals."""
    if top_n_categories is None or txns.empty:
        return txns

    grouped = txns.copy()
    totals = grouped.groupby("Category", sort=False)[SPEND_COLUMN].sum()
    top_categories = set(
        totals.sort_values(ascending=False).head(top_n_categories).index
    )
    grouped["Category"] = grouped["Category"].where(
        grouped["Category"].isin(top_categories), "Other"
    )
    return grouped


def prepare_spend_data(
    txns: pd.DataFrame,
    *,
    window: int = 31,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exclude_categories: Optional[Iterable[str]] = None,
    top_n_categories: Optional[int] = DEFAULT_TOP_N_CATEGORIES,
    skip_cleanup: bool = False,
    cap_daily_spend: Optional[float] = None,
) -> pd.DataFrame:
    """Apply category rules and build a daily category spend grid."""
    if window < 1:
        raise ValueError("--window must be at least 1.")
    if top_n_categories is not None and top_n_categories < 1:
        raise ValueError("--top-n-categories must be at least 1 when provided.")
    if cap_daily_spend is not None and cap_daily_spend <= 0:
        raise ValueError("--cap-daily-spend must be greater than 0 when provided.")

    prepared = _prepare_transactions(
        txns,
        start_date=start_date,
        end_date=end_date,
        exclude_categories=exclude_categories,
        skip_cleanup=skip_cleanup,
    )

    if prepared.empty:
        return pd.DataFrame(
            columns=[
                "Date",
                "Category",
                SPEND_COLUMN,
                DISPLAY_SPEND_COLUMN,
                ROLLING_SPEND_COLUMN,
                RAW_ROLLING_SPEND_COLUMN,
                CAPPED_COLUMN,
            ]
        )

    prepared = _apply_top_n_category_grouping(prepared, top_n_categories)

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
    grid[DISPLAY_SPEND_COLUMN] = grid[SPEND_COLUMN]
    if cap_daily_spend is not None:
        grid[CAPPED_COLUMN] = grid[SPEND_COLUMN] > cap_daily_spend
        grid[DISPLAY_SPEND_COLUMN] = grid[DISPLAY_SPEND_COLUMN].clip(
            upper=cap_daily_spend
        )
    else:
        grid[CAPPED_COLUMN] = False

    grid[ROLLING_SPEND_COLUMN] = grid.groupby("Category", group_keys=False)[
        DISPLAY_SPEND_COLUMN
    ].transform(lambda series: series.rolling(window=window, min_periods=1).mean())
    grid[RAW_ROLLING_SPEND_COLUMN] = grid.groupby("Category", group_keys=False)[
        SPEND_COLUMN
    ].transform(lambda series: series.rolling(window=window, min_periods=1).mean())
    return grid


def prepare_monthly_heatmap_data(spend_data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw daily category spend by calendar month."""
    if spend_data.empty:
        return pd.DataFrame(columns=["Month", "Category", SPEND_COLUMN])

    monthly = spend_data.copy()
    monthly["Month"] = monthly["Date"].dt.to_period("M").dt.to_timestamp()
    return (
        monthly.groupby(["Month", "Category"], as_index=False)[[SPEND_COLUMN]]
        .sum()
        .sort_values(["Category", "Month"])
    )


def prepare_total_spend_data(spend_data: pd.DataFrame, *, window: int) -> pd.DataFrame:
    """Build a total daily rolling spend series from category grid data."""
    if spend_data.empty:
        return pd.DataFrame(columns=["Date", SPEND_COLUMN, DISPLAY_SPEND_COLUMN])

    daily_total = (
        spend_data.groupby("Date", as_index=False)[[SPEND_COLUMN, DISPLAY_SPEND_COLUMN]]
        .sum()
        .sort_values("Date")
    )
    daily_total[ROLLING_SPEND_COLUMN] = (
        daily_total[DISPLAY_SPEND_COLUMN].rolling(window=window, min_periods=1).mean()
    )
    daily_total[RAW_ROLLING_SPEND_COLUMN] = (
        daily_total[SPEND_COLUMN].rolling(window=window, min_periods=1).mean()
    )
    return daily_total


def build_outlier_report(
    txns: pd.DataFrame,
    spend_data: pd.DataFrame,
    *,
    cap_daily_spend: Optional[float] = None,
) -> pd.DataFrame:
    """Return transactions belonging to unusually large daily category spikes."""
    if txns.empty or spend_data.empty:
        return pd.DataFrame()

    category_spend = spend_data[["Date", "Category", SPEND_COLUMN]].copy()
    daily_totals = spend_data.groupby("Date", as_index=False)[[SPEND_COLUMN]].sum()
    daily_totals = daily_totals.rename(columns={SPEND_COLUMN: DAILY_TOTAL_SPEND_COLUMN})
    category_spend = category_spend.merge(daily_totals, on="Date", how="left")
    category_spend = category_spend.rename(
        columns={SPEND_COLUMN: DAILY_CATEGORY_SPEND_COLUMN}
    )

    if cap_daily_spend is not None:
        spikes = category_spend[
            category_spend[DAILY_CATEGORY_SPEND_COLUMN] > cap_daily_spend
        ].copy()
        spikes["OutlierReason"] = f"daily category spend over ${cap_daily_spend:,.2f}"
    else:
        q1 = daily_totals[DAILY_TOTAL_SPEND_COLUMN].quantile(0.25)
        q3 = daily_totals[DAILY_TOTAL_SPEND_COLUMN].quantile(0.75)
        iqr = q3 - q1
        threshold = q3 + (3 * iqr)
        spikes = category_spend[
            category_spend[DAILY_TOTAL_SPEND_COLUMN] > threshold
        ].copy()
        spikes["OutlierReason"] = f"daily total spend over ${threshold:,.2f}"

    if spikes.empty:
        return pd.DataFrame(
            columns=[
                "Date",
                "Category",
                "Merchant",
                "Amount",
                SPEND_COLUMN,
                DAILY_CATEGORY_SPEND_COLUMN,
                DAILY_TOTAL_SPEND_COLUMN,
                "OutlierReason",
            ]
        )

    outlier_txns = txns.merge(
        spikes[
            [
                "Date",
                "Category",
                DAILY_CATEGORY_SPEND_COLUMN,
                DAILY_TOTAL_SPEND_COLUMN,
                "OutlierReason",
            ]
        ],
        on=["Date", "Category"],
        how="inner",
    )
    return outlier_txns.sort_values(
        ["Date", DAILY_CATEGORY_SPEND_COLUMN, SPEND_COLUMN],
        ascending=[True, False, False],
    )


def write_outlier_report(outlier_report: pd.DataFrame, output_path: Path) -> None:
    """Write outlier transactions to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    outlier_report.to_csv(output_path, index=False)


def _add_total_spend_trace(fig: go.Figure, total_spend: pd.DataFrame) -> None:
    fig.add_trace(
        go.Scatter(
            x=total_spend["Date"],
            y=total_spend[ROLLING_SPEND_COLUMN],
            mode="lines",
            name="Total rolling spend",
            line={"color": "#1f77b4", "width": 2},
            customdata=total_spend[[RAW_ROLLING_SPEND_COLUMN]],
            hovertemplate=(
                "%{x|%Y-%m-%d}<br>"
                "Displayed rolling spend: $%{y:,.2f}<br>"
                "Raw rolling spend: $%{customdata[0]:,.2f}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )


def _add_outlier_markers(fig: go.Figure, spend_data: pd.DataFrame) -> None:
    capped_totals = (
        spend_data[spend_data[CAPPED_COLUMN]]
        .groupby("Date", as_index=False)[[SPEND_COLUMN]]
        .sum()
        .sort_values("Date")
    )
    if capped_totals.empty:
        return

    fig.add_trace(
        go.Scatter(
            x=capped_totals["Date"],
            y=capped_totals[SPEND_COLUMN],
            mode="markers",
            name="Capped/outlier days",
            marker={"color": "#d62728", "size": 8, "symbol": "diamond"},
            hovertemplate=(
                "%{x|%Y-%m-%d}<br>"
                "Raw capped-category spend: $%{y:,.2f}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )


def _add_category_area_traces(fig: go.Figure, spend_data: pd.DataFrame) -> None:
    for category in sorted(spend_data["Category"].unique()):
        category_data = spend_data[spend_data["Category"] == category]
        fig.add_trace(
            go.Scatter(
                x=category_data["Date"],
                y=category_data[ROLLING_SPEND_COLUMN],
                mode="lines",
                stackgroup="category_spend",
                name=category,
                customdata=category_data[
                    [RAW_ROLLING_SPEND_COLUMN, SPEND_COLUMN, CAPPED_COLUMN]
                ],
                hovertemplate=(
                    "%{x|%Y-%m-%d}<br>"
                    f"{category}<br>"
                    "Displayed rolling spend: $%{y:,.2f}<br>"
                    "Raw rolling spend: $%{customdata[0]:,.2f}<br>"
                    "Raw daily spend: $%{customdata[1]:,.2f}<br>"
                    "Capped: %{customdata[2]}<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )


def _add_monthly_heatmap(fig: go.Figure, monthly_spend: pd.DataFrame) -> None:
    if monthly_spend.empty:
        return

    heatmap = monthly_spend.pivot(
        index="Category", columns="Month", values=SPEND_COLUMN
    ).fillna(0)
    fig.add_trace(
        go.Heatmap(
            x=heatmap.columns,
            y=heatmap.index,
            z=heatmap.values,
            colorscale="Viridis",
            colorbar={"title": "Monthly spend"},
            hovertemplate=(
                "%{x|%Y-%m}<br>%{y}<br>Monthly spend: $%{z:,.2f}<extra></extra>"
            ),
        ),
        row=3,
        col=1,
    )


def write_spend_chart(
    spend_data: pd.DataFrame, output_path: Path, *, window: int
) -> None:
    """Write an interactive multi-view spending report to output_path."""
    total_spend = prepare_total_spend_data(spend_data, window=window)
    monthly_spend = prepare_monthly_heatmap_data(spend_data)
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.09,
        row_heights=[0.22, 0.43, 0.35],
        subplot_titles=(
            "Total rolling daily spend",
            "Rolling daily spend by category",
            "Monthly category spend",
        ),
    )

    if not total_spend.empty:
        _add_total_spend_trace(fig, total_spend)
        _add_outlier_markers(fig, spend_data)
    if not spend_data.empty:
        _add_category_area_traces(fig, spend_data)
        _add_monthly_heatmap(fig, monthly_spend)

    fig.update_layout(
        title="Historical Spend Profile",
        hovermode="closest",
        height=1100,
        legend_title_text="Category",
    )
    fig.update_yaxes(title_text="Rolling average", row=1, col=1)
    fig.update_yaxes(
        title_text="Rolling average daily spend",
        row=2,
        col=1,
    )
    fig.update_xaxes(title_text="Date", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_xaxes(title_text="Month", row=3, col=1)
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
    parser.add_argument(
        "--top-n-categories", type=int, default=DEFAULT_TOP_N_CATEGORIES
    )
    parser.add_argument(
        "--cap-daily-spend",
        type=float,
        default=None,
        help="Visual-only cap for daily category spend before rolling averages.",
    )
    parser.add_argument(
        "--outlier-report",
        type=Path,
        default=None,
        help="Optional CSV path for transactions on outlier days/categories.",
    )
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

    prepared_txns = _prepare_transactions(
        txns,
        start_date=args.start_date,
        end_date=args.end_date,
        exclude_categories=args.exclude_category,
        skip_cleanup=args.skip_cleanup,
    )
    grouped_txns = _apply_top_n_category_grouping(prepared_txns, args.top_n_categories)
    spend_data = prepare_spend_data(
        grouped_txns,
        window=args.window,
        top_n_categories=None,
        skip_cleanup=True,
        cap_daily_spend=args.cap_daily_spend,
    )
    write_spend_chart(spend_data, args.output, window=args.window)
    logger.info("Wrote %s.", args.output)

    if args.outlier_report is not None:
        outlier_report = build_outlier_report(
            grouped_txns,
            spend_data,
            cap_daily_spend=args.cap_daily_spend,
        )
        write_outlier_report(outlier_report, args.outlier_report)
        logger.info("Wrote %s.", args.outlier_report)


if __name__ == "__main__":
    main()
