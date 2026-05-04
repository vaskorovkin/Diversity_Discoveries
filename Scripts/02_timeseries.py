#!/usr/bin/env python3
"""Create BOLD observation time-series exhibits."""

from __future__ import annotations

import argparse
import csv
import time
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pipeline_utils import PROCESSED_BOLD, EXHIBIT_FIGURES, MINIMAL_CSV, ensure_output_dirs, iter_minimal_chunks


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


def plot_series(counter: Counter, output: Path, title: str, ylabel: str, log1p: bool) -> None:
    years = sorted(int(y) for y in counter if str(y).isdigit())
    counts = np.array([counter[str(y)] for y in years], dtype=float)
    yvals = np.log1p(counts) if log1p else counts

    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(years, yvals, color="#1f77b4", linewidth=2)
    ax.set_title(title)
    ax.set_xlabel("Collection year")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def plot_by_kingdom(counter: dict[tuple[str, str], int], output: Path, title: str, log1p: bool) -> None:
    kingdoms = sorted({k for k, _ in counter})
    years = sorted({int(y) for _, y in counter if str(y).isdigit()})
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
    args = parser.parse_args()

    ensure_output_dirs()
    collection = Counter()
    upload = Counter()
    collection_by_kingdom = defaultdict(int)
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

    collection_csv = PROCESSED_BOLD / "bold_timeseries_collection_year.csv"
    upload_csv = PROCESSED_BOLD / "bold_timeseries_sequence_upload_year.csv"
    collection_kingdom_csv = PROCESSED_BOLD / "bold_timeseries_collection_year_by_kingdom.csv"
    write_counter(collection_csv, collection, "collection_year")
    write_counter(upload_csv, upload, "sequence_upload_year")
    write_by_kingdom(collection_kingdom_csv, collection_by_kingdom, "collection_year")

    plot_series(
        collection,
        EXHIBIT_FIGURES / "fig_observations_by_collection_year_raw.png",
        "BOLD observations by collection year",
        "record count",
        False,
    )
    plot_series(
        collection,
        EXHIBIT_FIGURES / "fig_observations_by_collection_year_log1p.png",
        "BOLD observations by collection year",
        "log(1 + record count)",
        True,
    )
    plot_series(
        upload,
        EXHIBIT_FIGURES / "fig_observations_by_sequence_upload_year_raw.png",
        "BOLD observations by sequence upload year",
        "record count",
        False,
    )
    plot_by_kingdom(
        collection_by_kingdom,
        EXHIBIT_FIGURES / "fig_observations_by_collection_year_by_kingdom_raw.png",
        "BOLD observations by collection year and kingdom",
        False,
    )
    plot_by_kingdom(
        collection_by_kingdom,
        EXHIBIT_FIGURES / "fig_observations_by_collection_year_by_kingdom_log1p.png",
        "BOLD observations by collection year and kingdom",
        True,
    )

    print(f"Wrote: {collection_csv}", flush=True)
    print(f"Wrote: {upload_csv}", flush=True)
    print(f"Wrote figures to: {EXHIBIT_FIGURES}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
