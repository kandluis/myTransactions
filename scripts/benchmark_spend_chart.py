"""Fast local benchmark for spend chart memory usage."""

from __future__ import annotations

import argparse
import gc
import json
import logging
import resource
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import generate_spend_charts

logger = logging.getLogger(__name__)

DEFAULT_INPUT = PROJECT_ROOT / "data" / "transactions.csv"
DEFAULT_CACHE_INPUT = PROJECT_ROOT / "data" / "benchmark_transactions.csv"
DEFAULT_WINDOW = 31
DEFAULT_TOP_N_CATEGORIES = generate_spend_charts.DEFAULT_TOP_N_CATEGORIES


def _ru_maxrss_to_mb(ru_maxrss: int) -> float:
    rss_bytes = ru_maxrss if sys.platform == "darwin" else ru_maxrss * 1024
    return rss_bytes / (1024 * 1024)


def _peak_rss_mb() -> float:
    return _ru_maxrss_to_mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


@dataclass(frozen=True)
class BenchmarkResult:
    input_path: Path
    output_path: Path
    rows: int
    categories: int
    elapsed_seconds: float
    peak_rss_mb: float
    output_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "categories": self.categories,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "peak_rss_mb": round(self.peak_rss_mb, 2),
            "output_bytes": self.output_bytes,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark spend chart memory and runtime locally."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="CSV file containing real transactions to benchmark against.",
    )
    parser.add_argument(
        "--cache-input",
        type=Path,
        default=DEFAULT_CACHE_INPUT,
        help=(
            "Local cache path for a full Sheets export. "
            "Defaults to data/benchmark_transactions.csv."
        ),
    )
    parser.add_argument(
        "--refresh-from-sheets",
        action="store_true",
        help="Fetch the full transaction list from Sheets and refresh the cache.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional HTML path. Defaults to a temporary file.",
    )
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    parser.add_argument(
        "--top-n-categories",
        type=int,
        default=DEFAULT_TOP_N_CATEGORIES,
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip the cleanup pass to isolate chart costs.",
    )
    parser.add_argument(
        "--include-heatmap",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include the monthly heatmap in the benchmark chart.",
    )
    return parser


def _refresh_cache_from_sheets(cache_path: Path) -> Path:
    txns = generate_spend_charts.load_transactions_from_sheets()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    txns.to_csv(cache_path, index=False)
    return cache_path


def _resolve_input_path(input_path: Path, cache_path: Path) -> Path:
    if input_path != DEFAULT_INPUT:
        return input_path
    if cache_path.exists():
        return cache_path
    return input_path


def run_benchmark(
    *,
    input_path: Path,
    output_path: Optional[Path] = None,
    window: int = DEFAULT_WINDOW,
    top_n_categories: Optional[int] = DEFAULT_TOP_N_CATEGORIES,
    skip_cleanup: bool = False,
    include_heatmap: bool = True,
) -> BenchmarkResult:
    if not input_path.exists():
        raise FileNotFoundError(f"Benchmark input {input_path} does not exist.")

    gc.collect()
    started = time.perf_counter()
    txns = generate_spend_charts.load_transactions_from_csv(input_path)
    prepared = generate_spend_charts.prepare_spend_data(
        txns,
        window=window,
        top_n_categories=top_n_categories,
        skip_cleanup=skip_cleanup,
        job_id="benchmark",
    )

    if output_path is None:
        temp_file = tempfile.NamedTemporaryFile(
            prefix="spend_profile_", suffix=".html", delete=False
        )
        output_path = Path(temp_file.name)
        temp_file.close()
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_spend_charts.write_spend_chart(
        prepared,
        output_path,
        window=window,
        include_heatmap=include_heatmap,
        job_id="benchmark",
    )
    elapsed = time.perf_counter() - started
    return BenchmarkResult(
        input_path=input_path,
        output_path=output_path,
        rows=len(txns),
        categories=prepared["Category"].nunique() if not prepared.empty else 0,
        elapsed_seconds=elapsed,
        peak_rss_mb=_peak_rss_mb(),
        output_bytes=output_path.stat().st_size if output_path.exists() else 0,
    )


def main(argv: Optional[list[str]] = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    args = build_parser().parse_args(argv)
    input_path = args.input
    if args.refresh_from_sheets:
        input_path = _refresh_cache_from_sheets(args.cache_input)
    else:
        input_path = _resolve_input_path(input_path, args.cache_input)
    result = run_benchmark(
        input_path=input_path,
        output_path=args.output,
        window=args.window,
        top_n_categories=args.top_n_categories,
        skip_cleanup=args.skip_cleanup,
        include_heatmap=args.include_heatmap,
    )
    print(json.dumps(result.as_dict(), sort_keys=True))


if __name__ == "__main__":
    main()
