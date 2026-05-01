#!/usr/bin/env python3
"""Build a compact BOLD record file for exhibit scripts.

This streams selected raw BOLD TSV downloads and writes
`Exhibits/data/bold_minimal_records.csv`. By default it excludes diagnostic
capped Cecidomyiidae files and the old capped Hemiptera order-level file.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from exhibit_utils import (
    BOLD_RAW,
    EXHIBIT_DATA,
    MINIMAL_CSV,
    MINIMAL_FIELDS,
    PROJECT_ROOT,
    clean,
    discover_bold_sources,
    ensure_exhibit_dirs,
    first_present,
    parse_coord,
    parse_year,
    source_group,
)


def minimal_row(row: dict, source: Path) -> dict[str, str]:
    lat, lon, has_coord = parse_coord(clean(row.get("coord")))
    return {
        "source_file": str(source.relative_to(PROJECT_ROOT)),
        "source_group": source_group(source),
        "processid": clean(row.get("processid")),
        "record_id": clean(row.get("record_id")),
        "kingdom": clean(row.get("kingdom")),
        "phylum": clean(row.get("phylum")),
        "class_name": clean(row.get("class")),
        "order": clean(row.get("order")),
        "family": clean(row.get("family")),
        "genus": clean(row.get("genus")),
        "species": clean(row.get("species")),
        "country_ocean": clean(row.get("country/ocean")),
        "country_iso": first_present(row, ["country_iso", "geopol_denorm.country_iso3"]),
        "province_state": clean(row.get("province/state")),
        "region": clean(row.get("region")),
        "sector": clean(row.get("sector")),
        "site": clean(row.get("site")),
        "latitude": lat,
        "longitude": lon,
        "has_coord": has_coord,
        "collection_year": parse_year(clean(row.get("collection_date_start"))),
        "sequence_upload_year": parse_year(clean(row.get("sequence_upload_date"))),
    }


def stream_source(source: Path, writer: csv.DictWriter, progress_every: int) -> tuple[int, int]:
    rows = 0
    coord_rows = 0
    started = time.time()
    with source.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            out = minimal_row(row, source)
            writer.writerow(out)
            rows += 1
            coord_rows += int(out["has_coord"] == "1")
            if rows % progress_every == 0:
                elapsed = max(time.time() - started, 1)
                print(
                    f"  {rows:,} rows streamed from {source.name} "
                    f"({rows / elapsed:,.0f} rows/sec)",
                    flush=True,
                )
    return rows, coord_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--inventory", type=Path, default=EXHIBIT_DATA / "bold_minimal_source_inventory.csv")
    parser.add_argument("--progress-every", type=int, default=250_000)
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument(
        "--include-cecidomyiidae-costa-rica-capped",
        action="store_true",
        help=(
            "Deprecated compatibility flag. The incomplete capped Costa Rica "
            "Cecidomyiidae file is now included by default."
        ),
    )
    args = parser.parse_args()

    ensure_exhibit_dirs()
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

    with args.output.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=MINIMAL_FIELDS)
        writer.writeheader()
        for index, source in enumerate(sources, 1):
            print(f"[{index:,}/{len(sources):,}] {source.relative_to(PROJECT_ROOT)}", flush=True)
            try:
                rows, coord_rows = stream_source(source, writer, args.progress_every)
            except Exception as exc:
                print(f"ERROR while reading {source}: {exc}", file=sys.stderr, flush=True)
                raise
            total_rows += rows
            total_coord += coord_rows
            inventory_rows.append(
                {
                    "source_file": str(source.relative_to(PROJECT_ROOT)),
                    "source_group": source_group(source),
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
