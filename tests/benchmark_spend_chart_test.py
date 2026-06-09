import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import benchmark_spend_chart


@pytest.fixture()
def empty_category_config(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "MERCHANT_TO_CATEGORY_MAP",
        {},
    )
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "EXACT_MERCHANT_TO_CATEGORY_MAP",
        {},
    )
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "CATEGORY_MAP",
        {},
    )
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "MERCHANT_NORMALIZATION",
        [],
    )
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "IGNORED_CATEGORIES",
        [],
    )
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "IGNORED_MERCHANTS",
        [],
    )
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "IGNORED_TXNS",
        [],
    )
    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts.remote.config.GLOBAL,
        "SKIPPED_ACCOUNTS",
        [],
    )
    return monkeypatch


def test_run_benchmark_writes_html_and_reports_metrics(
    tmp_path: Path, empty_category_config: pytest.MonkeyPatch
) -> None:
    input_path = tmp_path / "transactions.csv"
    pd.DataFrame(
        [
            {
                "Date": "2026-01-01",
                "Merchant": "Coffee Shop",
                "Amount": -10.0,
                "Category": "Food",
                "Account": "Checking",
                "ID": "1",
                "Description": "Coffee Shop",
            },
            {
                "Date": "2026-01-02",
                "Merchant": "Market",
                "Amount": -20.0,
                "Category": "Groceries",
                "Account": "Checking",
                "ID": "2",
                "Description": "Market",
            },
            {
                "Date": "2026-01-03",
                "Merchant": "Book Store",
                "Amount": -30.0,
                "Category": "Shopping",
                "Account": "Checking",
                "ID": "3",
                "Description": "Book Store",
            },
            {
                "Date": "2026-01-04",
                "Merchant": "Refund",
                "Amount": 5.0,
                "Category": "Shopping",
                "Account": "Checking",
                "ID": "4",
                "Description": "Refund",
            },
        ]
    ).to_csv(input_path, index=False)

    output_path = tmp_path / "report.html"
    result = benchmark_spend_chart.run_benchmark(
        input_path=input_path,
        output_path=output_path,
        window=2,
        top_n_categories=None,
        skip_cleanup=True,
    )

    assert result.input_path == input_path
    assert result.output_path == output_path
    assert result.rows == 4
    assert result.categories >= 1
    assert result.elapsed_seconds >= 0
    assert result.peak_rss_mb > 0
    assert result.output_bytes > 0
    assert output_path.exists()
    assert "plotly" in output_path.read_text().lower()


def test_main_prints_json_metrics(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    result = benchmark_spend_chart.BenchmarkResult(
        input_path=Path("input.csv"),
        output_path=Path("report.html"),
        rows=4,
        categories=2,
        elapsed_seconds=1.2345,
        peak_rss_mb=128.9,
        output_bytes=4096,
        include_heatmap=False,
        include_total_spend=True,
        include_category_share=True,
        include_customdata=True,
    )
    monkeypatch.setattr(benchmark_spend_chart, "run_benchmark", lambda **kwargs: result)

    benchmark_spend_chart.main(["--input", "input.csv"])

    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout) == result.as_dict()


def test_run_benchmark_matrix_runs_four_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    class Completed:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(command, check, capture_output, text):
        assert check is True
        assert capture_output is True
        assert text is True
        commands.append(command)
        payload = {
            "input_path": "input.csv",
            "output_path": command[command.index("--output") + 1],
            "rows": 1,
            "categories": 1,
            "elapsed_seconds": 0.1,
            "peak_rss_mb": 100.0,
            "output_bytes": 10,
            "include_heatmap": False,
            "include_total_spend": "--include-total-spend" in command,
            "include_category_share": "--include-category-share" in command,
            "include_customdata": "--include-customdata" in command,
        }
        return Completed(json.dumps(payload))

    monkeypatch.setattr(benchmark_spend_chart.subprocess, "run", fake_run)

    results = benchmark_spend_chart.run_benchmark_matrix(
        input_path=Path("input.csv"),
        output_dir=tmp_path,
    )

    assert len(commands) == 8
    combos = {
        (
            "--include-total-spend" in command,
            "--include-category-share" in command,
            "--include-customdata" in command,
        )
        for command in commands
    }
    assert combos == {
        (True, True, True),
        (True, True, False),
        (True, False, True),
        (True, False, False),
        (False, True, True),
        (False, True, False),
        (False, False, True),
        (False, False, False),
    }
    assert len(results) == 8
    assert all(not result.include_heatmap for result in results)
    assert results[0].output_path.name.endswith("total-1_share-1_custom-1.html")


def test_refresh_cache_from_sheets_writes_full_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    txns = pd.DataFrame(
        [
            {
                "Date": "2026-01-01",
                "Merchant": "Coffee Shop",
                "Amount": -10.0,
                "Category": "Food",
                "Account": "Checking",
                "ID": "1",
                "Description": "Coffee Shop",
            }
        ]
    )
    cache_path = tmp_path / "benchmark_transactions.csv"

    monkeypatch.setattr(
        benchmark_spend_chart.generate_spend_charts,
        "load_transactions_from_sheets",
        lambda: txns,
    )

    written_cache = benchmark_spend_chart._refresh_cache_from_sheets(cache_path)

    assert written_cache == cache_path
    assert cache_path.exists()
    assert "Coffee Shop" in cache_path.read_text()
