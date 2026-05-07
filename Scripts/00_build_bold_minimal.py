#!/usr/bin/env python3
"""Build a compact BOLD record file for downstream scripts.

This streams selected raw BOLD TSV downloads and writes
`Data/processed/bold/bold_minimal_records.csv`. By default it excludes diagnostic
capped Cecidomyiidae files and the old capped Hemiptera order-level file.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline_utils import (
    BOLD_RAW,
    PROCESSED_BOLD,
    MINIMAL_CSV,
    MINIMAL_FIELDS,
    PROJECT_ROOT,
    discover_bold_sources,
    ensure_output_dirs,
    source_group,
)

RAW_USECOLS = [
    "processid",
    "record_id",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
    "country/ocean",
    "country_iso",
    "geopol_denorm.country_iso3",
    "province/state",
    "region",
    "sector",
    "site",
    "coord",
    "collection_date_start",
    "sequence_upload_date",
    "bin_uri",
    "bin_created_date",
    "inst",
    "collection_code",
    "collectors",
    "identified_by",
    "sequence_run_site",
    "funding_src",
]

COORD_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_coords_vec(coord: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    s = coord.fillna("")
    nums = s.str.findall(COORD_RE)
    has_two = nums.str.len() >= 2
    lat = pd.to_numeric(nums.str[0], errors="coerce")
    lon = pd.to_numeric(nums.str[1], errors="coerce")
    valid = has_two & lat.between(-90, 90) & lon.between(-180, 180)
    lat_out = lat.where(valid).map(lambda v: f"{v:.8g}" if pd.notna(v) else "", na_action=None)
    lon_out = lon.where(valid).map(lambda v: f"{v:.8g}" if pd.notna(v) else "", na_action=None)
    has_coord = valid.astype(int).astype(str)
    return lat_out, lon_out, has_coord


def parse_years_vec(dates: pd.Series) -> pd.Series:
    s = dates.fillna("").str[:4]
    numeric = pd.to_numeric(s, errors="coerce")
    valid = numeric.between(1800, 2100)
    return numeric.where(valid).astype("Int64").astype(str).where(valid, "")


def first_present_vec(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    result = pd.Series("", index=df.index)
    for col in reversed(cols):
        if col in df.columns:
            vals = df[col].fillna("").str.strip()
            mask = vals != ""
            result = result.where(~mask, vals)
    return result


def stream_source(
    source: Path,
    out_handle,
    chunksize: int,
    source_file_str: str,
    source_group_str: str,
    header_written: bool,
) -> tuple[int, int, bool]:
    rows = 0
    coord_rows = 0
    started = time.time()

    with source.open("r", encoding="utf-8", errors="replace") as fh:
        header_line = fh.readline().strip().split("\t")
    avail = [c for c in RAW_USECOLS if c in header_line]

    for chunk in pd.read_csv(
        source,
        sep="\t",
        usecols=avail,
        dtype=str,
        chunksize=chunksize,
        encoding="utf-8",
        on_bad_lines="skip",
    ):
        n = len(chunk)

        lat, lon, has_coord = parse_coords_vec(chunk["coord"] if "coord" in chunk.columns else pd.Series("", index=chunk.index))

        out = pd.DataFrame({
            "source_file": source_file_str,
            "source_group": source_group_str,
            "processid": chunk.get("processid", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "record_id": chunk.get("record_id", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "kingdom": chunk.get("kingdom", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "phylum": chunk.get("phylum", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "class_name": chunk.get("class", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "order": chunk.get("order", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "family": chunk.get("family", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "genus": chunk.get("genus", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "species": chunk.get("species", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "country_ocean": chunk.get("country/ocean", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "country_iso": first_present_vec(chunk, ["country_iso", "geopol_denorm.country_iso3"]),
            "province_state": chunk.get("province/state", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "region": chunk.get("region", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "sector": chunk.get("sector", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "site": chunk.get("site", pd.Series("", index=chunk.index)).fillna("").str.strip(),
            "latitude": lat.values,
            "longitude": lon.values,
            "has_coord": has_coord.values,
            "collection_year": parse_years_vec(chunk.get("collection_date_start", pd.Series("", index=chunk.index))).values,
            "sequence_upload_year": parse_years_vec(chunk.get("sequence_upload_date", pd.Series("", index=chunk.index))).values,
            "bin_uri": chunk.get("bin_uri", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
            "bin_created_date": chunk.get("bin_created_date", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
            "inst": chunk.get("inst", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
            "collection_code": chunk.get("collection_code", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
            "collectors": chunk.get("collectors", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
            "identified_by": chunk.get("identified_by", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
            "sequence_run_site": chunk.get("sequence_run_site", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
            "funding_src": chunk.get("funding_src", pd.Series("", index=chunk.index)).fillna("").str.strip().values,
        })

        out.to_csv(out_handle, index=False, header=not header_written, columns=MINIMAL_FIELDS)
        header_written = True

        rows += n
        coord_rows += int((has_coord == "1").sum())
        elapsed = max(time.time() - started, 1)
        if rows % (chunksize * 2) < chunksize:
            print(
                f"  {rows:,} rows streamed from {source.name} "
                f"({rows / elapsed:,.0f} rows/sec)",
                flush=True,
            )

    return rows, coord_rows, header_written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--inventory", type=Path, default=PROCESSED_BOLD / "bold_minimal_source_inventory.csv")
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument("--chunksize", type=int, default=500_000)
    parser.add_argument(
        "--include-cecidomyiidae-costa-rica-capped",
        action="store_true",
        help=(
            "Deprecated compatibility flag. The incomplete capped Costa Rica "
            "Cecidomyiidae file is now included by default."
        ),
    )
    args = parser.parse_args()

    ensure_output_dirs()
    sources = discover_bold_sources(args.include_cecidomyiidae_costa_rica_capped)
    if args.limit_files is not None:
        sources = sources[: args.limit_files]

    print(f"Project root: {PROJECT_ROOT}", flush=True)
    print(f"Raw BOLD root: {BOLD_RAW}", flush=True)
    print(f"Sources selected: {len(sources):,}", flush=True)
    print(f"Output: {args.output}", flush=True)

    total_rows = 0
    total_coord = 0
    inventory_rows = []
    started = time.time()
    header_written = False

    with args.output.open("w", newline="", encoding="utf-8") as out:
        for index, source in enumerate(sources, 1):
            rel = str(source.relative_to(PROJECT_ROOT))
            sg = source_group(source)
            print(f"[{index:,}/{len(sources):,}] {rel}", flush=True)
            try:
                rows, coord_rows, header_written = stream_source(
                    source, out, args.chunksize, rel, sg, header_written,
                )
            except Exception as exc:
                print(f"ERROR while reading {source}: {exc}", file=sys.stderr, flush=True)
                raise
            total_rows += rows
            total_coord += coord_rows
            inventory_rows.append(
                {
                    "source_file": rel,
                    "source_group": sg,
                    "rows": rows,
                    "rows_with_coordinates": coord_rows,
                }
            )
            print(
                f"  done: {rows:,} rows, {coord_rows:,} with coordinates",
                flush=True,
            )

    with args.inventory.open("w", newline="", encoding="utf-8") as inv:
        writer = csv.DictWriter(
            inv,
            fieldnames=["source_file", "source_group", "rows", "rows_with_coordinates"],
        )
        writer.writeheader()
        writer.writerows(inventory_rows)

    elapsed = max(time.time() - started, 1)
    print(f"Wrote minimal records: {args.output}", flush=True)
    print(f"Wrote inventory: {args.inventory}", flush=True)
    print(f"Total rows: {total_rows:,}", flush=True)
    print(f"Rows with coordinates: {total_coord:,}", flush=True)
    print(f"Elapsed: {elapsed / 60:.1f} minutes", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
