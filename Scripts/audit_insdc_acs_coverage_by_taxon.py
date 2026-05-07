#!/usr/bin/env python3
"""Audit `insdc_acs` fill rate by kingdom (and Arthropoda subdivisions).

Streams `Data/processed/bold/bold_minimal_records.csv` and writes
`Output/audits/insdc_acs_coverage_by_taxon.csv` with one row per
(level, group) at three levels:

  - kingdom: all kingdoms
  - phylum:  phyla within kingdom Animalia
  - class:   classes within phylum Arthropoda

Columns: level, group, records, records_with_insdc_acs, fill_rate.
Each level segment is sorted by record count desc; a TOTAL row per level
is appended.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd

from pipeline_utils import MINIMAL_CSV, PROJECT_ROOT


AUDIT_CSV = PROJECT_ROOT / "Output" / "audits" / "insdc_acs_coverage_by_taxon.csv"
USECOLS = ["kingdom", "phylum", "class_name", "insdc_acs"]
FIELDS = ["level", "group", "records", "records_with_insdc_acs", "fill_rate"]


def accumulate(series, has_acs, totals, filled):
    s = series.fillna("").replace("", "(blank)")
    for k, v in s.value_counts().items():
        totals[k] += int(v)
    for k, v in s[has_acs].value_counts().items():
        filled[k] += int(v)


def emit_level(level, totals, filled, rows):
    n_total = sum(totals.values())
    m_total = sum(filled.values())
    for g in sorted(totals, key=lambda k: totals[k], reverse=True):
        n = totals[g]
        m = filled.get(g, 0)
        rows.append({
            "level": level,
            "group": g,
            "records": n,
            "records_with_insdc_acs": m,
            "fill_rate": round(m / n, 6) if n else 0.0,
        })
    rows.append({
        "level": level,
        "group": "TOTAL",
        "records": n_total,
        "records_with_insdc_acs": m_total,
        "fill_rate": round(m_total / n_total, 6) if n_total else 0.0,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--output", type=Path, default=AUDIT_CSV)
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Input : {args.input}", flush=True)
    print(f"Output: {args.output}", flush=True)

    k_tot, k_fil = defaultdict(int), defaultdict(int)
    p_tot, p_fil = defaultdict(int), defaultdict(int)
    c_tot, c_fil = defaultdict(int), defaultdict(int)
    rows_seen = 0

    for i, chunk in enumerate(
        pd.read_csv(args.input, dtype=str, usecols=USECOLS, chunksize=args.chunksize), 1
    ):
        has_acs = chunk["insdc_acs"].fillna("").str.len() > 0

        accumulate(chunk["kingdom"], has_acs, k_tot, k_fil)

        animalia = chunk["kingdom"].fillna("") == "Animalia"
        accumulate(chunk.loc[animalia, "phylum"], has_acs[animalia], p_tot, p_fil)

        arthropoda = animalia & (chunk["phylum"].fillna("") == "Arthropoda")
        accumulate(chunk.loc[arthropoda, "class_name"], has_acs[arthropoda], c_tot, c_fil)

        rows_seen += len(chunk)
        print(f"  chunk {i}: {rows_seen:,} rows scanned", flush=True)

    rows = []
    emit_level("kingdom", k_tot, k_fil, rows)
    emit_level("phylum_in_animalia", p_tot, p_fil, rows)
    emit_level("class_in_arthropoda", c_tot, c_fil, rows)

    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote: {args.output}", flush=True)
    print(f"kingdoms: {len(k_tot):,}", flush=True)
    print(f"phyla in Animalia: {len(p_tot):,}", flush=True)
    print(f"classes in Arthropoda: {len(c_tot):,}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
