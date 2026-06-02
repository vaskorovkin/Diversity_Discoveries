#!/usr/bin/env python3
"""Create BOLD observation time-series exhibits."""


from __future__ import annotations


from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _path in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import argparse
import csv
import time
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pipeline_utils import (
    PROCESSED_BOLD,
    EXHIBIT_FIGURES,
    MINIMAL_CSV,
    ensure_output_dirs,
    iter_minimal_chunks,
    mirror_to_codex_figures,
)


# Impossible future collection/upload years (BOLD date-field data-entry errors --
# a handful of records carry years well past the present) are dropped from the
# *plotted* series so the x-axis ends just past the last real collection year.
# The raw tally CSVs are left complete and auditable; only the figures are clipped.
MAX_PLOT_YEAR = 2024


def write_counter(path: Path, counter: Counter, key_name: str = "year") -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[key_name, "record_count"])
        writer.writeheader()
        for key in sorted(counter):
            writer.writerow({key_name: key, "record_count": counter[key]})


def write_by_kingdom(path: Path, counter: dict[tuple[str, str], int], year_name: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["kingdom", year_name, "record_count"])
        writer.writeheader()
        for (kingdom, year), count in sorted(counter.items()):
            writer.writerow({"kingdom": kingdom, year_name: year, "record_count": count})


def load_counter(path: Path, counter: Counter, key_name: str) -> None:
    """Load a cached year->count tally CSV back into a Counter (for --from-csv)."""
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counter[row[key_name]] += int(row["record_count"])


def load_by_kingdom(path: Path, counter: dict[tuple[str, str], int], year_name: str) -> None:
    """Load a cached (kingdom, year)->count tally CSV back into a dict (for --from-csv)."""
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counter[(row["kingdom"], row[year_name])] += int(row["record_count"])


def plot_series(counter: Counter, output: Path, title: str, ylabel: str, log1p: bool, xlabel: str = "Collection year") -> None:
    years = sorted(int(y) for y in counter if str(y).isdigit() and int(y) <= MAX_PLOT_YEAR)
    counts = np.array([counter[str(y)] for y in years], dtype=float)
    yvals = np.log1p(counts) if log1p else counts

    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(years, yvals, color="#1f77b4", linewidth=2)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def plot_by_kingdom(counter: dict[tuple[str, str], int], output: Path, title: str, log1p: bool) -> None:
    kingdoms = sorted({k for k, _ in counter})
    years = sorted({int(y) for _, y in counter if str(y).isdigit() and int(y) <= MAX_PLOT_YEAR})
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for kingdom in kingdoms:
        counts = np.array([counter.get((kingdom, str(y)), 0) for y in years], dtype=float)
        yvals = np.log1p(counts) if log1p else counts
        ax.plot(years, yvals, linewidth=1.6, label=kingdom or "Unknown")
    ax.set_title(title)
    ax.set_xlabel("Collection year")
    ax.set_ylabel("log(1 + record count)" if log1p else "record count")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--chunksize", type=int, default=500_000)
    parser.add_argument(
        "--from-csv",
        action="store_true",
        help="Re-plot from the cached timeseries CSVs instead of re-reading the 8GB minimal records.",
    )
    args = parser.parse_args()

    ensure_output_dirs()
    collection = Counter()
    upload = Counter()
    collection_by_kingdom = defaultdict(int)

    collection_csv = PROCESSED_BOLD / "bold_timeseries_collection_year.csv"
    upload_csv = PROCESSED_BOLD / "bold_timeseries_sequence_upload_year.csv"
    collection_kingdom_csv = PROCESSED_BOLD / "bold_timeseries_collection_year_by_kingdom.csv"

    if args.from_csv:
        print("Re-plotting from cached timeseries CSVs (skipping minimal-records read).", flush=True)
        load_counter(collection_csv, collection, "collection_year")
        load_counter(upload_csv, upload, "sequence_upload_year")
        load_by_kingdom(collection_kingdom_csv, collection_by_kingdom, "collection_year")
    else:
        total_rows = 0
        started = time.time()

        print(f"Reading minimal records: {args.input}", flush=True)
        for chunk_index, chunk in enumerate(iter_minimal_chunks(args.input, args.chunksize), 1):
            cyear = chunk["collection_year"].fillna("").str.strip()
            cyear_valid = cyear[cyear != ""]
            if not cyear_valid.empty:
                for yr, cnt in cyear_valid.value_counts().items():
                    collection[yr] += cnt

            uyear = chunk["sequence_upload_year"].fillna("").str.strip()
            uyear_valid = uyear[uyear != ""]
            if not uyear_valid.empty:
                for yr, cnt in uyear_valid.value_counts().items():
                    upload[yr] += cnt

            kingdom = chunk["kingdom"].fillna("").str.strip().replace("", "Unknown")
            pair = kingdom.str.cat(cyear, sep="\t")
            pair_valid = pair[cyear != ""]
            if not pair_valid.empty:
                for kyr, cnt in pair_valid.value_counts().items():
                    k, y = kyr.split("\t", 1)
                    collection_by_kingdom[(k, y)] += cnt

            total_rows += len(chunk)
            elapsed = max(time.time() - started, 1)
            print(f"chunk {chunk_index:,}: {total_rows:,} rows ({total_rows / elapsed:,.0f} rows/sec)", flush=True)

        write_counter(collection_csv, collection, "collection_year")
        write_counter(upload_csv, upload, "sequence_upload_year")
        write_by_kingdom(collection_kingdom_csv, collection_by_kingdom, "collection_year")

    collection_raw_png = EXHIBIT_FIGURES / "fig_observations_by_collection_year_raw.png"
    collection_log_png = EXHIBIT_FIGURES / "fig_observations_by_collection_year_log1p.png"
    upload_raw_png = EXHIBIT_FIGURES / "fig_observations_by_sequence_upload_year_raw.png"
    upload_log_png = EXHIBIT_FIGURES / "fig_observations_by_sequence_upload_year_log1p.png"
    kingdom_raw_png = EXHIBIT_FIGURES / "fig_observations_by_collection_year_by_kingdom_raw.png"
    kingdom_log_png = EXHIBIT_FIGURES / "fig_observations_by_collection_year_by_kingdom_log1p.png"

    plot_series(
        collection,
        collection_raw_png,
        "BOLD observations by collection year",
        "record count",
        False,
    )
    plot_series(
        collection,
        collection_log_png,
        "BOLD observations by collection year",
        "log(1 + record count)",
        True,
    )
    plot_series(
        upload,
        upload_raw_png,
        "BOLD observations by sequence upload year",
        "record count",
        False,
        xlabel="Sequence upload year",
    )
    plot_series(
        upload,
        upload_log_png,
        "BOLD observations by sequence upload year",
        "log(1 + record count)",
        True,
        xlabel="Sequence upload year",
    )
    plot_by_kingdom(
        collection_by_kingdom,
        kingdom_raw_png,
        "BOLD observations by collection year and kingdom",
        False,
    )
    plot_by_kingdom(
        collection_by_kingdom,
        kingdom_log_png,
        "BOLD observations by collection year and kingdom",
        True,
    )

    mirror_to_codex_figures(collection_log_png)
    mirror_to_codex_figures(kingdom_log_png)
    mirror_to_codex_figures(collection_raw_png)
    mirror_to_codex_figures(kingdom_raw_png)

    if not args.from_csv:
        print(f"Wrote: {collection_csv}", flush=True)
        print(f"Wrote: {upload_csv}", flush=True)
    print(f"Wrote figures to: {EXHIBIT_FIGURES} (plotted years capped at {MAX_PLOT_YEAR})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
