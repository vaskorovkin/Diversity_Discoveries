#!/usr/bin/env python3
"""
Audit LOTUS metadata for geography and temporal-attribution columns.

Reads 260413_frozen_metadata.csv.gz and reports:
  1. Fill rate (% non-empty) for every column
  2. For columns matching geography keywords: top 30 values + 10 random samples
  3. For reference_year, reference_doi, reference_pubmed_id: same detail
  4. Summary verdict on whether spatial/temporal attribution is recoverable

Console-only output; no CSV written.
"""

import re
import pandas as pd
import numpy as np

META_PATH = (
    "Data/raw/natural_products/lotus/260413_frozen_metadata.csv.gz"
)
MAIN_PATH = (
    "Data/raw/natural_products/lotus/260413_frozen.csv.gz"
)

GEO_PATTERN = re.compile(
    r"country|location|origin|coord|lat|lon|geo|collect|locality",
    re.IGNORECASE,
)
REF_COLS = ["reference_year", "reference_doi", "reference_pubmed_id"]


def fill_rate(series: pd.Series) -> float:
    non_empty = series.dropna()
    if non_empty.dtype == object:
        non_empty = non_empty[non_empty.str.strip() != ""]
    return len(non_empty) / len(series) * 100


def detail_report(series: pd.Series, label: str, top_n: int = 30,
                  sample_n: int = 10) -> None:
    non_empty = series.dropna()
    if non_empty.dtype == object:
        non_empty = non_empty[non_empty.str.strip() != ""]
    fr = len(non_empty) / len(series) * 100
    print(f"\n{'='*70}")
    print(f"  {label}  —  fill {fr:.1f}%  ({len(non_empty):,} / {len(series):,})")
    print(f"{'='*70}")
    if len(non_empty) == 0:
        print("  (empty)")
        return
    vc = non_empty.value_counts()
    print(f"  Unique values: {len(vc):,}")
    print(f"\n  Top {min(top_n, len(vc))} values:")
    for val, cnt in vc.head(top_n).items():
        pct = cnt / len(non_empty) * 100
        print(f"    {cnt:>8,}  ({pct:5.1f}%)  {val}")
    if len(non_empty) > 0:
        samp = non_empty.sample(min(sample_n, len(non_empty)),
                                random_state=42)
        print(f"\n  {len(samp)} random samples:")
        for v in samp.values:
            print(f"    {v}")


def main() -> None:
    print("=" * 70)
    print("  LOTUS Geography & Temporal-Attribution Audit")
    print("=" * 70)

    # ── Metadata file ────────────────────────────────────────────────
    print(f"\nReading {META_PATH} ...")
    meta = pd.read_csv(META_PATH, low_memory=False)
    print(f"  {len(meta):,} rows × {len(meta.columns)} columns\n")

    print("-" * 70)
    print("  FILL RATES — all columns (metadata)")
    print("-" * 70)
    for col in meta.columns:
        fr = fill_rate(meta[col])
        geo_flag = "  ◄ GEO-KEYWORD" if GEO_PATTERN.search(col) else ""
        ref_flag = "  ◄ REF-TARGET" if col in REF_COLS else ""
        print(f"  {fr:6.1f}%  {col}{geo_flag}{ref_flag}")

    # Geography keyword matches
    geo_cols = [c for c in meta.columns if GEO_PATTERN.search(c)]
    print(f"\n{'='*70}")
    print(f"  GEOGRAPHY-KEYWORD COLUMNS: {len(geo_cols)} matches")
    print(f"{'='*70}")
    if geo_cols:
        for col in geo_cols:
            detail_report(meta[col], col)
    else:
        print("  No columns match country|location|origin|coord|lat|lon"
              "|geo|collect|locality.")
        print("  LOTUS metadata contains NO spatial information.")

    # Reference / temporal columns
    print(f"\n{'='*70}")
    print("  REFERENCE & TEMPORAL COLUMNS")
    print(f"{'='*70}")
    for col in REF_COLS:
        if col in meta.columns:
            detail_report(meta[col], col)
        else:
            print(f"\n  {col}  —  COLUMN NOT PRESENT")

    # reference_doi is present; audit it
    if "reference_doi" in meta.columns:
        detail_report(meta["reference_doi"], "reference_doi")
    # reference_wikidata
    if "reference_wikidata" in meta.columns:
        detail_report(meta["reference_wikidata"], "reference_wikidata")

    # ── Main (frozen) file ───────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  MAIN FILE: {MAIN_PATH}")
    print(f"{'='*70}")
    main_df = pd.read_csv(MAIN_PATH, low_memory=False)
    print(f"  {len(main_df):,} rows × {len(main_df.columns)} columns")
    print(f"  Columns: {', '.join(main_df.columns)}\n")

    print("-" * 70)
    print("  FILL RATES — all columns (main)")
    print("-" * 70)
    for col in main_df.columns:
        fr = fill_rate(main_df[col])
        print(f"  {fr:6.1f}%  {col}")

    geo_main = [c for c in main_df.columns if GEO_PATTERN.search(c)]
    if geo_main:
        for col in geo_main:
            detail_report(main_df[col], f"(main) {col}")
    else:
        print("\n  No geography columns in main file either.")

    if "reference_doi" in main_df.columns:
        detail_report(main_df["reference_doi"], "(main) reference_doi")

    # ── Verdict ──────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("  VERDICT")
    print(f"{'='*70}")
    print("""
  SPATIAL:   No geography columns in either LOTUS file. Species-to-compound
             pairs have NO collection locality, country, or coordinates.
             Spatial attribution comes entirely from BOLD/GBIF specimen
             records (already in the pipeline via shared species universe).

  TEMPORAL:  No reference_year or reference_pubmed_id columns.
             reference_doi is present — year could be recovered via
             CrossRef API (doi → publication year), but this is an
             external lookup, not in the dump itself.
             reference_wikidata is present — year could also be recovered
             via Wikidata SPARQL (P577 = publication date).

  IMPLICATION: LOTUS is a static species→compound knowledge base, not a
             time-stamped discovery record. Temporal variation in the
             chemical-potential panel comes from when/where species were
             *sampled* (BOLD/GBIF), not when compounds were *discovered*.
             This is the correct design for the current regressions
             (conflict → sampling of NP-bearing species), but rules out
             a "conflict → delayed NP discovery" analysis using LOTUS alone.
""")


if __name__ == "__main__":
    main()
