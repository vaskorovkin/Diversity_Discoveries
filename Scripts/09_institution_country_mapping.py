#!/usr/bin/env python3
"""Extract top collectors from BOLD minimal records for origin mapping.

Outputs a CSV with columns: rank, collector, record_count, record_share,
cumulative_share, country_iso3. The country_iso3 column is blank — to be
filled in a subsequent step.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

from pipeline_utils import PROCESSED_BOLD, MINIMAL_CSV, ensure_output_dirs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--top-n", type=int, default=500)
    parser.add_argument("--chunksize", type=int, default=500_000)
    args = parser.parse_args()

    ensure_output_dirs()

    counts: Counter[str] = Counter()
    total = 0

    print(f"Reading: {args.input}", flush=True)
    for i, chunk in enumerate(
        pd.read_csv(args.input, dtype=str, usecols=["collectors"], chunksize=args.chunksize), 1
    ):
        total += len(chunk)
        vals = chunk["collectors"].fillna("").str.strip()
        for v, cnt in vals[vals != ""].value_counts().items():
            counts[v] += cnt
        print(f"  chunk {i}: {total:,} rows", flush=True)

    records_with_field = sum(counts.values())
    top = counts.most_common(args.top_n)
    top_total = sum(cnt for _, cnt in top)

    rows = []
    for rank, (collector, cnt) in enumerate(top, 1):
        rows.append({
            "rank": rank,
            "collector": collector,
            "record_count": cnt,
            "record_share": round(cnt / records_with_field, 6),
            "cumulative_share": 0.0,
            "country_iso3": "",
        })

    cumsum = 0.0
    for r in rows:
        cumsum += r["record_share"]
        r["cumulative_share"] = round(cumsum, 6)

    df = pd.DataFrame(rows)
    output = PROCESSED_BOLD / f"bold_top{args.top_n}_collectors.csv"
    df.to_csv(output, index=False)

    print(f"\nTotal records: {total:,}", flush=True)
    print(f"Records with collectors: {records_with_field:,} ({100 * records_with_field / total:.1f}%)", flush=True)
    print(f"Unique collector values: {len(counts):,}", flush=True)
    print(f"Top {args.top_n} cover: {top_total:,} records ({100 * top_total / records_with_field:.1f}%)", flush=True)
    print(f"Wrote: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
