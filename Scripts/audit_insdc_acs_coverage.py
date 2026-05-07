#!/usr/bin/env python3
"""Audit `insdc_acs` fill rate per BOLD source_group.

Streams `Data/processed/bold/bold_minimal_records.csv` and writes
`Output/audits/insdc_acs_coverage.csv` with one row per source_group plus
a TOTAL row: records, records_with_insdc_acs, fill_rate.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd

from pipeline_utils import MINIMAL_CSV, PROJECT_ROOT


AUDIT_CSV = PROJECT_ROOT / "Output" / "audits" / "insdc_acs_coverage.csv"
USECOLS = ["source_group", "insdc_acs"]
FIELDS = ["source_group", "records", "records_with_insdc_acs", "fill_rate"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--output", type=Path, default=AUDIT_CSV)
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Input : {args.input}", flush=True)
    print(f"Output: {args.output}", flush=True)

    totals: dict[str, int] = defaultdict(int)
    filled: dict[str, int] = defaultdict(int)
    rows_seen = 0

    for i, chunk in enumerate(
        pd.read_csv(args.input, dtype=str, usecols=USECOLS, chunksize=args.chunksize), 1
    ):
        sg = chunk["source_group"].fillna("")
        has_acs = chunk["insdc_acs"].fillna("").str.len() > 0
        for k, v in sg.value_counts().items():
            totals[k] += int(v)
        for k, v in sg[has_acs].value_counts().items():
            filled[k] += int(v)
        rows_seen += len(chunk)
        print(f"  chunk {i}: {rows_seen:,} rows scanned", flush=True)

    rows = []
    for sg in sorted(totals, key=lambda k: totals[k], reverse=True):
        n = totals[sg]
        m = filled.get(sg, 0)
        rows.append({
            "source_group": sg,
            "records": n,
            "records_with_insdc_acs": m,
            "fill_rate": round(m / n, 6) if n else 0.0,
        })

    n_total = sum(totals.values())
    m_total = sum(filled.values())
    rows.append({
        "source_group": "TOTAL",
        "records": n_total,
        "records_with_insdc_acs": m_total,
        "fill_rate": round(m_total / n_total, 6) if n_total else 0.0,
    })

    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote: {args.output}", flush=True)
    print(f"source_groups: {len(totals):,}", flush=True)
    print(f"records (total): {n_total:,}", flush=True)
    pct = 100 * m_total / n_total if n_total else 0.0
    print(f"records with insdc_acs: {m_total:,} ({pct:.2f}%)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
