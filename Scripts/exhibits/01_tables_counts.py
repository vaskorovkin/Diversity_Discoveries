#!/usr/bin/env python3
"""Create exhibit tables with BOLD observation counts."""

from __future__ import annotations

import argparse
import csv
import time
from collections import defaultdict
from pathlib import Path

from exhibit_utils import EXHIBIT_TABLES, MINIMAL_CSV, clean, ensure_exhibit_dirs, iter_minimal_chunks, write_simple_latex_table


def add_group(stats: dict, key: str, row) -> None:
    item = stats[key]
    item["record_count"] += 1
    item["records_with_coordinates"] += int(clean(row.get("has_coord")) == "1")
    country = clean(row.get("country_ocean"))
    species = clean(row.get("species"))
    if country:
        item["countries"].add(country)
    if species:
        item["species"].add(species)
    cyear = clean(row.get("collection_year"))
    if cyear:
        y = int(cyear)
        item["first_collection_year"] = min(item["first_collection_year"], y)
        item["last_collection_year"] = max(item["last_collection_year"], y)
    order = clean(row.get("order"))
    family = clean(row.get("family"))
    if order:
        item["orders"].add(order)
    if family:
        item["families"].add(family)


def stats_factory() -> dict:
    return {
        "record_count": 0,
        "records_with_coordinates": 0,
        "countries": set(),
        "species": set(),
        "orders": set(),
        "families": set(),
        "first_collection_year": 9999,
        "last_collection_year": 0,
    }


def write_kingdom_table(path: Path, stats: dict) -> None:
    rows = []
    total = sum(v["record_count"] for v in stats.values())
    for kingdom, item in sorted(stats.items(), key=lambda kv: kv[1]["record_count"], reverse=True):
        n = item["record_count"]
        rows.append(
            {
                "kingdom": kingdom or "Unknown",
                "record_count": n,
                "record_share_percent": f"{100 * n / total:.2f}" if total else "0.00",
                "records_with_coordinates": item["records_with_coordinates"],
                "share_with_coordinates": f"{100 * item['records_with_coordinates'] / n:.2f}" if n else "0.00",
                "unique_countries": len(item["countries"]),
                "unique_species": len(item["species"]),
                "first_collection_year": "" if item["first_collection_year"] == 9999 else item["first_collection_year"],
                "last_collection_year": "" if item["last_collection_year"] == 0 else item["last_collection_year"],
            }
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["kingdom"])
        writer.writeheader()
        writer.writerows(rows)


def write_animalia_class_table(path: Path, stats: dict) -> None:
    rows = []
    total = sum(v["record_count"] for v in stats.values())
    for class_name, item in sorted(stats.items(), key=lambda kv: kv[1]["record_count"], reverse=True):
        n = item["record_count"]
        rows.append(
            {
                "class": class_name or "Unknown",
                "record_count": n,
                "record_share_percent": f"{100 * n / total:.2f}" if total else "0.00",
                "records_with_coordinates": item["records_with_coordinates"],
                "share_with_coordinates": f"{100 * item['records_with_coordinates'] / n:.2f}" if n else "0.00",
                "unique_countries": len(item["countries"]),
                "unique_orders": len(item["orders"]),
                "unique_families": len(item["families"]),
                "unique_species": len(item["species"]),
            }
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["class"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--outdir", type=Path, default=EXHIBIT_TABLES)
    parser.add_argument("--chunksize", type=int, default=500_000)
    args = parser.parse_args()

    ensure_exhibit_dirs()
    args.outdir.mkdir(parents=True, exist_ok=True)

    kingdom_stats = defaultdict(stats_factory)
    animalia_class_stats = defaultdict(stats_factory)
    total_rows = 0
    started = time.time()

    print(f"Reading minimal records: {args.input}", flush=True)
    for chunk_index, chunk in enumerate(iter_minimal_chunks(args.input, args.chunksize), 1):
        for _, row in chunk.iterrows():
            kingdom = clean(row.get("kingdom")) or "Unknown"
            add_group(kingdom_stats, kingdom, row)
            if kingdom == "Animalia":
                add_group(animalia_class_stats, clean(row.get("class_name")) or "Unknown", row)
        total_rows += len(chunk)
        elapsed = max(time.time() - started, 1)
        print(f"chunk {chunk_index:,}: {total_rows:,} rows ({total_rows / elapsed:,.0f} rows/sec)", flush=True)

    kingdom_csv = args.outdir / "table_observations_by_kingdom.csv"
    animalia_csv = args.outdir / "table_animalia_by_class.csv"
    write_kingdom_table(kingdom_csv, kingdom_stats)
    write_animalia_class_table(animalia_csv, animalia_class_stats)

    write_simple_latex_table(
        kingdom_csv,
        args.outdir / "table_observations_by_kingdom.tex",
        "BOLD observations by kingdom",
        "tab:bold_observations_by_kingdom",
    )
    write_simple_latex_table(
        animalia_csv,
        args.outdir / "table_animalia_by_class.tex",
        "BOLD Animalia observations by class",
        "tab:bold_animalia_by_class",
    )

    print(f"Wrote: {kingdom_csv}", flush=True)
    print(f"Wrote: {animalia_csv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
