#!/usr/bin/env python3
"""Append BOLD summary counts for non-insect groups to bold_taxon_size_notes.txt."""

from __future__ import annotations

import argparse
import csv
import time
import urllib.error
from pathlib import Path

from download_bold_fungi import PROJECT_ROOT, SUMMARY_FIELDS, api_get_json


OUTDIR = PROJECT_ROOT / "Output" / "audits"
NOTES = PROJECT_ROOT / "bold_taxon_size_notes.txt"

GROUPS = [
    ("Downloaded backbone", "Plantae", "tax:kingdom:Plantae"),
    ("Downloaded backbone", "Fungi", "tax:kingdom:Fungi"),
    ("Downloaded backbone", "Mollusca", "tax:phylum:Mollusca"),
    ("Downloaded backbone", "Chordata", "tax:phylum:Chordata"),
    ("Downloaded non-arthropod animals", "Annelida", "tax:phylum:Annelida"),
    ("Downloaded non-arthropod animals", "Cnidaria", "tax:phylum:Cnidaria"),
    ("Downloaded non-arthropod animals", "Echinodermata", "tax:phylum:Echinodermata"),
    ("Downloaded non-arthropod animals", "Nematoda", "tax:phylum:Nematoda"),
    ("Downloaded non-arthropod animals", "Platyhelminthes", "tax:phylum:Platyhelminthes"),
    ("Downloaded non-arthropod animals", "Porifera", "tax:phylum:Porifera"),
    ("Downloaded non-arthropod animals", "Rotifera", "tax:phylum:Rotifera"),
    ("Downloaded non-arthropod animals", "Bryozoa", "tax:phylum:Bryozoa"),
    ("Downloaded non-arthropod animals", "Nemertea", "tax:phylum:Nemertea"),
    ("Downloaded non-arthropod animals", "Tardigrada", "tax:phylum:Tardigrada"),
    ("Downloaded non-arthropod animals", "Onychophora", "tax:phylum:Onychophora"),
    ("Downloaded non-arthropod animals", "Acanthocephala", "tax:phylum:Acanthocephala"),
    ("Downloaded non-arthropod animals", "Brachiopoda", "tax:phylum:Brachiopoda"),
    ("Downloaded non-arthropod animals", "Chaetognatha", "tax:phylum:Chaetognatha"),
    ("Downloaded non-arthropod animals", "Ctenophora", "tax:phylum:Ctenophora"),
    ("Downloaded non-arthropod animals", "Entoprocta", "tax:phylum:Entoprocta"),
    ("Downloaded non-arthropod animals", "Gastrotricha", "tax:phylum:Gastrotricha"),
    ("Downloaded non-arthropod animals", "Hemichordata", "tax:phylum:Hemichordata"),
    ("Downloaded non-arthropod animals", "Kinorhyncha", "tax:phylum:Kinorhyncha"),
    ("Downloaded non-arthropod animals", "Phoronida", "tax:phylum:Phoronida"),
    ("Downloaded non-arthropod animals", "Priapulida", "tax:phylum:Priapulida"),
    ("Downloaded non-arthropod animals", "Xenacoelomorpha", "tax:phylum:Xenacoelomorpha"),
    ("Non-insect arthropods", "Araneae", "tax:order:Araneae"),
    ("Non-insect arthropods", "Acari", "tax:order:Acari"),
    ("Non-insect arthropods", "Scorpiones", "tax:order:Scorpiones"),
    ("Non-insect arthropods", "Opiliones", "tax:order:Opiliones"),
    ("Non-insect arthropods", "Pseudoscorpiones", "tax:order:Pseudoscorpiones"),
    ("Non-insect arthropods", "Decapoda", "tax:order:Decapoda"),
    ("Non-insect arthropods", "Amphipoda", "tax:order:Amphipoda"),
    ("Non-insect arthropods", "Isopoda", "tax:order:Isopoda"),
    ("Non-insect arthropods", "Copepoda", "tax:class:Copepoda"),
    ("Non-insect arthropods", "Ostracoda", "tax:class:Ostracoda"),
    ("Non-insect arthropods", "Chilopoda", "tax:class:Chilopoda"),
    ("Non-insect arthropods", "Diplopoda", "tax:class:Diplopoda"),
    ("Non-insect arthropods", "Symphyla", "tax:class:Symphyla"),
    ("Non-insect arthropods", "Pauropoda", "tax:class:Pauropoda"),
    ("Non-insect arthropods", "Pycnogonida", "tax:class:Pycnogonida"),
    ("Non-insect arthropods", "Xiphosura", "tax:class:Xiphosura"),
    ("Other kingdoms/domains", "Chromista", "tax:kingdom:Chromista"),
    ("Other kingdoms/domains", "Protozoa", "tax:kingdom:Protozoa"),
    ("Other kingdoms/domains", "Archaea", "tax:kingdom:Archaea"),
    ("Other kingdoms/domains", "Bacteria", "tax:kingdom:Bacteria"),
]


def compact_count(value: int | None) -> str:
    if value is None:
        return ""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return str(value)


def summarize(query: str, timeout: int) -> tuple[str, int | None, int | None, float | None, str]:
    preprocessor = api_get_json("/query/preprocessor", {"query": query}, timeout=timeout)
    failed_terms = preprocessor.get("failed_terms") or []
    if failed_terms:
        return "failed_terms", None, None, None, str(failed_terms)

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_coord / n_records if n_records else 0.0
    return "ok", n_records, n_coord, coord_share, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--between-query-sleep", type=float, default=1)
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTDIR / "bold_non_insect_group_summaries.csv"
    rows = []

    for category, group, query in GROUPS:
        try:
            status, n_records, n_coord, coord_share, error = summarize(query, args.timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            status, n_records, n_coord, coord_share, error = "error", None, None, None, str(exc)
        row = {
            "category": category,
            "group": group,
            "query": query,
            "status": status,
            "records": n_records if n_records is not None else "",
            "records_with_coordinates": n_coord if n_coord is not None else "",
            "coordinate_coverage_percent": f"{coord_share:.1f}" if coord_share is not None else "",
            "error": error,
        }
        rows.append(row)
        print(
            f"{group}: {status}"
            + (f", {n_records:,} records" if n_records is not None else ""),
            flush=True,
        )
        if args.between_query_sleep > 0:
            time.sleep(args.between_query_sleep)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "group",
                "query",
                "status",
                "records",
                "records_with_coordinates",
                "coordinate_coverage_percent",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "",
        "",
        "Non-insect BOLD group summary",
        "=============================",
        "",
        "Source note: approximate global public BOLD summary counts from BOLD",
        "Portal API queries. These are query-level public record counts and",
        "coordinate coverage estimates, not cleaned unique-specimen counts.",
        f"Full CSV: {csv_path.relative_to(PROJECT_ROOT)}",
        "",
        "| Category | Group | Query | Records | Coord coverage | Status |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        records = compact_count(int(row["records"])) if row["records"] != "" else ""
        coord = (
            f"{row['coordinate_coverage_percent']}%"
            if row["coordinate_coverage_percent"] != ""
            else ""
        )
        lines.append(
            f"| {row['category']} | {row['group']} | `{row['query']}` | "
            f"{records} | {coord} | {row['status']} |"
        )

    with NOTES.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    print(f"Wrote CSV: {csv_path}")
    print(f"Appended: {NOTES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
