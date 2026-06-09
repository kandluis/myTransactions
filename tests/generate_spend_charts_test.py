import os
from pathlib import Path

import pandas as pd
import pytest

from _pytest.monkeypatch import MonkeyPatch

from scripts import generate_spend_charts


@pytest.fixture()
def category_config(monkeypatch: MonkeyPatch) -> MonkeyPatch:
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "MERCHANT_TO_CATEGORY_MAP",
        {"Coffee": "Food/Dining Coffee"},
    )
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "EXACT_MERCHANT_TO_CATEGORY_MAP",
        {},
    )
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "CATEGORY_MAP",
        {"Old Category": "Mapped Category"},
    )
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "MERCHANT_NORMALIZATION",
        [],
    )
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "IGNORED_CATEGORIES",
        [],
    )
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "IGNORED_MERCHANTS",
        [],
    )
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "IGNORED_TXNS",
        [],
    )
    monkeypatch.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "SKIPPED_ACCOUNTS",
        [],
    )
    return monkeypatch


def _sample_txns() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": "2026-01-01",
                "Merchant": "Coffee Shop",
                "Amount": -10.0,
                "Category": "Uncategorized",
                "Account": "Checking",
                "ID": "1",
                "Description": "Coffee Shop",
            },
            {
                "Date": "2026-01-03",
                "Merchant": "Market",
                "Amount": -20.0,
                "Category": "Groceries",
                "Account": "Checking",
                "ID": "2",
                "Description": "Market",
            },
            {
                "Date": "2026-01-03",
                "Merchant": "Refunded Store",
                "Amount": 5.0,
                "Category": "Shopping",
                "Account": "Checking",
                "ID": "3",
                "Description": "Refunded Store",
            },
        ]
    )


def _outlier_txns() -> pd.DataFrame:
    txns = _sample_txns()
    return pd.concat(
        [
            txns,
            pd.DataFrame(
                [
                    {
                        "Date": "2026-01-04",
                        "Merchant": "Furniture Store",
                        "Amount": -1500.0,
                        "Category": "Shopping",
                        "Account": "Checking",
                        "ID": "4",
                        "Description": "Furniture Store",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )


def _auto_cap_txns() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": "2026-01-01",
                "Merchant": "Grocery One",
                "Amount": -10.0,
                "Category": "Groceries",
                "Account": "Checking",
                "ID": "auto-1",
                "Description": "Grocery One",
            },
            {
                "Date": "2026-01-02",
                "Merchant": "Grocery Two",
                "Amount": -12.0,
                "Category": "Groceries",
                "Account": "Checking",
                "ID": "auto-2",
                "Description": "Grocery Two",
            },
            {
                "Date": "2026-01-03",
                "Merchant": "Grocery Three",
                "Amount": -11.0,
                "Category": "Groceries",
                "Account": "Checking",
                "ID": "auto-3",
                "Description": "Grocery Three",
            },
            {
                "Date": "2026-01-04",
                "Merchant": "Bad Grocery",
                "Amount": -5000.0,
                "Category": "Groceries",
                "Account": "Checking",
                "ID": "auto-4",
                "Description": "Bad Grocery",
            },
        ]
    )


def test_prepare_spend_data_fills_dates_and_rolls_by_calendar_day(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _sample_txns(), window=2, skip_cleanup=True
    )

    coffee = spend[spend["Category"] == "Food/Dining Coffee"].reset_index(drop=True)
    assert list(coffee["Date"].dt.strftime("%Y-%m-%d")) == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
    ]
    assert list(coffee[generate_spend_charts.SPEND_COLUMN]) == [10.0, 0.0, 0.0]
    assert list(coffee[generate_spend_charts.ROLLING_SPEND_COLUMN]) == [
        10.0,
        5.0,
        0.0,
    ]


def test_prepare_spend_data_uses_absolute_amounts_and_category_rules(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _sample_txns(), window=31, skip_cleanup=True
    )

    day_three = spend[spend["Date"] == pd.Timestamp("2026-01-03")]
    totals = dict(zip(day_three["Category"], day_three["Spend"]))
    assert totals["Food/Dining Coffee"] == 0.0
    assert totals["Groceries"] == 20.0
    assert totals["Shopping"] == 5.0


def test_prepare_spend_data_filters_dates_and_categories(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _sample_txns(),
        start_date="2026-01-02",
        end_date="2026-01-03",
        exclude_categories=["Shopping"],
        skip_cleanup=True,
    )

    assert set(spend["Date"].dt.strftime("%Y-%m-%d")) == {
        "2026-01-03",
    }
    assert set(spend["Category"]) == {"Groceries"}


def test_prepare_spend_data_groups_tail_categories_into_other(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _sample_txns(), top_n_categories=1, skip_cleanup=True
    )

    assert set(spend["Category"]) == {"Groceries", "Other"}
    other = spend[
        (spend["Date"] == pd.Timestamp("2026-01-01")) & (spend["Category"] == "Other")
    ]
    assert other.iloc[0][generate_spend_charts.SPEND_COLUMN] == 10.0


def test_prepare_spend_data_cleanup_excludes_ignored_categories(
    category_config: MonkeyPatch,
) -> None:
    category_config.setattr(
        generate_spend_charts.remote.config.GLOBAL,
        "IGNORED_CATEGORIES",
        ["Groceries"],
    )

    spend = generate_spend_charts.prepare_spend_data(_sample_txns())

    assert "Groceries" not in set(spend["Category"])


def test_prepare_spend_data_caps_display_only(category_config: MonkeyPatch) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _outlier_txns(),
        top_n_categories=None,
        cap_daily_spend=100.0,
        skip_cleanup=True,
    )

    shopping_mask = (spend["Date"] == pd.Timestamp("2026-01-04")) & (
        spend["Category"] == "Shopping"
    )
    shopping = spend[shopping_mask].iloc[0]
    assert shopping[generate_spend_charts.SPEND_COLUMN] == 1500.0
    assert shopping[generate_spend_charts.DISPLAY_SPEND_COLUMN] == 100.0
    assert shopping[generate_spend_charts.CAPPED_COLUMN]


def test_prepare_spend_data_auto_caps_extreme_values(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _auto_cap_txns(),
        top_n_categories=None,
        skip_cleanup=True,
    )

    capped = spend[spend[generate_spend_charts.CAPPED_COLUMN]].iloc[0]
    assert capped["Date"] == pd.Timestamp("2026-01-04")
    assert capped[generate_spend_charts.SPEND_COLUMN] == 5000.0
    assert capped[generate_spend_charts.DISPLAY_SPEND_COLUMN] < 5000.0
    assert spend.attrs[generate_spend_charts.CAP_ATTR] is not None


def test_prepare_total_spend_data_rolls_display_and_raw(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _outlier_txns(),
        window=2,
        top_n_categories=None,
        cap_daily_spend=100.0,
        skip_cleanup=True,
    )

    total = generate_spend_charts.prepare_total_spend_data(spend, window=2)
    final_day = total[total["Date"] == pd.Timestamp("2026-01-04")].iloc[0]
    assert final_day[generate_spend_charts.ROLLING_SPEND_COLUMN] == 62.5
    assert final_day[generate_spend_charts.RAW_ROLLING_SPEND_COLUMN] == 762.5


def test_prepare_category_share_data_sums_to_100_for_non_zero_days(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _sample_txns(),
        window=2,
        top_n_categories=None,
        skip_cleanup=True,
    )

    share = generate_spend_charts.prepare_category_share_data(spend)
    day_three = share[share["Date"] == pd.Timestamp("2026-01-03")]

    assert day_three[generate_spend_charts.SHARE_PERCENT_COLUMN].sum() == 100.0
    groceries = day_three[day_three["Category"] == "Groceries"].iloc[0]
    assert groceries[generate_spend_charts.SHARE_PERCENT_COLUMN] == 80.0
    assert groceries[generate_spend_charts.ROLLING_SPEND_COLUMN] == 10.0
    assert groceries[generate_spend_charts.RAW_ROLLING_SPEND_COLUMN] == 10.0


def test_prepare_category_share_data_gaps_zero_total_days(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _sample_txns(),
        window=1,
        top_n_categories=None,
        skip_cleanup=True,
    )

    share = generate_spend_charts.prepare_category_share_data(spend)
    zero_day = share[share["Date"] == pd.Timestamp("2026-01-02")]

    assert zero_day[generate_spend_charts.SHARE_PERCENT_COLUMN].isna().all()


def test_prepare_monthly_heatmap_data_uses_raw_spend(
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _outlier_txns(),
        top_n_categories=None,
        cap_daily_spend=100.0,
        skip_cleanup=True,
    )

    monthly = generate_spend_charts.prepare_monthly_heatmap_data(spend)
    shopping_mask = (monthly["Month"] == pd.Timestamp("2026-01-01")) & (
        monthly["Category"] == "Shopping"
    )
    shopping = monthly[shopping_mask].iloc[0]
    assert shopping[generate_spend_charts.SPEND_COLUMN] == 1505.0


def test_build_outlier_report_includes_capped_day_transactions(
    category_config: MonkeyPatch,
) -> None:
    txns = generate_spend_charts._prepare_transactions(
        _outlier_txns(), skip_cleanup=True
    )
    spend = generate_spend_charts.prepare_spend_data(
        txns,
        top_n_categories=None,
        cap_daily_spend=100.0,
        skip_cleanup=True,
    )

    report = generate_spend_charts.build_outlier_report(
        txns, spend, cap_daily_spend=100.0
    )

    assert set(report["ID"]) == {"4"}
    assert report.iloc[0][generate_spend_charts.DAILY_CATEGORY_SPEND_COLUMN] == 1500.0


def test_main_writes_html_from_csv(
    tmp_path: Path, category_config: MonkeyPatch
) -> None:
    input_path = tmp_path / "transactions.csv"
    output_path = tmp_path / "spend.html"
    outlier_path = tmp_path / "outliers.csv"
    _outlier_txns().to_csv(input_path, index=False)

    generate_spend_charts.main(
        [
            "--input",
            os.fspath(input_path),
            "--output",
            os.fspath(output_path),
            "--cap-daily-spend",
            "100",
            "--outlier-report",
            os.fspath(outlier_path),
            "--skip-cleanup",
        ]
    )

    assert output_path.exists()
    assert outlier_path.exists()
    assert "plotly" in output_path.read_text().lower()
    assert "Rolling category share of spend" in output_path.read_text()
    assert "Furniture Store" in outlier_path.read_text()


def test_write_spend_chart_logs_and_writes_html(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    category_config: MonkeyPatch,
) -> None:
    spend = generate_spend_charts.prepare_spend_data(
        _outlier_txns(),
        top_n_categories=None,
        cap_daily_spend=100.0,
        skip_cleanup=True,
    )
    output_path = tmp_path / "spend.html"

    with caplog.at_level("INFO"):
        generate_spend_charts.write_spend_chart(
            spend,
            output_path,
            window=2,
            job_id="job-1",
        )

    messages = "\n".join(record.message for record in caplog.records)
    assert "[report job job-1]" in messages
    assert "Starting chart build" in messages
    assert "Prepared total spend series" in messages
    assert "Prepared share series" in messages
    assert "Prepared monthly heatmap" in messages
    assert "Added" in messages
    assert "Wrote chart HTML" in messages
    assert "Finished chart build" in messages
    assert output_path.exists()
    assert output_path.stat().st_size > 0
