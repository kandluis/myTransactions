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


def test_main_writes_html_from_csv(
    tmp_path: Path, category_config: MonkeyPatch
) -> None:
    input_path = tmp_path / "transactions.csv"
    output_path = tmp_path / "spend.html"
    _sample_txns().to_csv(input_path, index=False)

    generate_spend_charts.main(
        [
            "--input",
            os.fspath(input_path),
            "--output",
            os.fspath(output_path),
            "--skip-cleanup",
        ]
    )

    assert output_path.exists()
    assert "plotly" in output_path.read_text().lower()
