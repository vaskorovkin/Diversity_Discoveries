#!/usr/bin/env python3
"""Extract a deduplicated GBIF plant species universe from the two local archives.

This unions species-like names from:
  1. the main preserved/material GBIF plant archive (2005-2025)
  2. the pre-period preserved/material GBIF plant archive (1999-2004)

The result is a project-relevant candidate species universe for downstream BIEN
range-map availability checks. It is not a global plant universe.
"""


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
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_MAIN = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_dwca_2005_2025"
    / "occurrence.txt"
)
DEFAULT_PRE = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "gbif"
    / "plantae"
    / "0011961-260430073515954"
    / "occurrence.txt"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "Data"
    / "regressors"
    / "plants"
    / "gbif_plantae_species_universe_1999_2025.csv"
)
DEFAULT_TXT = (
    PROJECT_ROOT
    / "Data"
    / "regressors"
    / "plants"
    / "gbif_plantae_species_universe_1999_2025.txt"
)
DEFAULT_SUMMARY = (
    PROJECT_ROOT
    / "Data"
    / "regressors"
    / "plants"
    / "gbif_plantae_species_universe_1999_2025_summary.csv"
)


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return " ".join(str(value).strip().split())


def parse_year(value: str) -> int | None:
    value = clean(value)
    if len(value) >= 4 and value[:4].isdigit():
        year = int(value[:4])
        if 1800 <= year <= 2100:
            return year
    return None


def species_token(accepted: str, species: str, scientific: str) -> str:
    for value in (accepted, species, scientific):
        token = clean(value)
        if token:
            return token
    return ""


def stream_archive(
    path: Path,
    source_tag: str,
    counters: dict[str, dict[str, object]],
    progress_every: int,
) -> dict[str, int]:
    stats = {
        "rows_scanned": 0,
        "rows_with_species_token": 0,
        "rows_with_year": 0,
    }

    csv.field_size_limit(100_000_000)

    with path.open(newline="", encoding="utf-8", errors="replace") as src:
        reader = csv.reader(src, delimiter="\t")
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        required = {"acceptedScientificName", "species", "scientificName", "year", "eventDate"}
        missing = sorted(required - set(idx))
        if missing:
            raise ValueError(f"{path} missing expected columns: {missing}")

        for row_num, row in enumerate(reader, 1):
            stats["rows_scanned"] += 1
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))

            token = species_token(
                row[idx["acceptedScientificName"]],
                row[idx["species"]],
                row[idx["scientificName"]],
            )
            if not token:
                continue
            stats["rows_with_species_token"] += 1

            year = parse_year(row[idx["year"]])
            if year is None:
                year = parse_year(row[idx["eventDate"]])
            if year is not None:
                stats["rows_with_year"] += 1

            rec = counters[token]
            rec[f"{source_tag}_records"] += 1
            rec[f"{source_tag}_present"] = 1
            if year is not None:
                if rec["first_year"] is None or year < rec["first_year"]:
                    rec["first_year"] = year
                if rec["last_year"] is None or year > rec["last_year"]:
                    rec["last_year"] = year

            if row_num % progress_every == 0:
                print(
                    f"  {source_tag}: rows {row_num:,}, "
                    f"tokens={stats['rows_with_species_token']:,}, "
                    f"unique_species={len(counters):,}",
                    flush=True,
                )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-input", type=Path, default=DEFAULT_MAIN)
    parser.add_argument("--pre-input", type=Path, default=DEFAULT_PRE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--txt-output", type=Path, default=DEFAULT_TXT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--progress-every", type=int, default=500_000)
    args = parser.parse_args()

    for path in (args.main_input, args.pre_input):
        if not path.exists():
            raise FileNotFoundError(f"Missing GBIF archive: {path}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.txt_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    counters: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "main_records": 0,
            "preperiod_records": 0,
            "main_present": 0,
            "preperiod_present": 0,
            "first_year": None,
            "last_year": None,
        }
    )

    main_stats = stream_archive(args.main_input, "main", counters, args.progress_every)
    pre_stats = stream_archive(args.pre_input, "preperiod", counters, args.progress_every)

    rows = []
    for token, rec in counters.items():
        rows.append(
            {
                "species_name": token,
                "main_records": rec["main_records"],
                "preperiod_records": rec["preperiod_records"],
                "total_records": rec["main_records"] + rec["preperiod_records"],
                "main_present": rec["main_present"],
                "preperiod_present": rec["preperiod_present"],
                "first_year": rec["first_year"] if rec["first_year"] is not None else "",
                "last_year": rec["last_year"] if rec["last_year"] is not None else "",
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(
        by=["total_records", "main_records", "preperiod_records", "species_name"],
        ascending=[False, False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    out.to_csv(args.output, index=False)

    with args.txt_output.open("w", encoding="utf-8") as fh:
        for species in out["species_name"]:
            fh.write(f"{species}\n")

    summary = pd.DataFrame(
        [
            ("main_rows_scanned", main_stats["rows_scanned"]),
            ("main_rows_with_species_token", main_stats["rows_with_species_token"]),
            ("preperiod_rows_scanned", pre_stats["rows_scanned"]),
            ("preperiod_rows_with_species_token", pre_stats["rows_with_species_token"]),
            ("species_universe_size", len(out)),
            ("species_only_in_main", int(((out["main_present"] == 1) & (out["preperiod_present"] == 0)).sum())),
            ("species_only_in_preperiod", int(((out["main_present"] == 0) & (out["preperiod_present"] == 1)).sum())),
            ("species_in_both", int(((out["main_present"] == 1) & (out["preperiod_present"] == 1)).sum())),
            ("top_species_total_records", int(out["total_records"].max()) if len(out) else 0),
        ],
        columns=["metric", "value"],
    )
    summary.to_csv(args.summary, index=False)

    print(f"Wrote species universe CSV: {args.output}")
    print(f"Wrote species universe TXT: {args.txt_output}")
    print(f"Wrote summary: {args.summary}")
    print(f"Unique species: {len(out):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
