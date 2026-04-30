#!/usr/bin/env python3
"""Summarize BOLD Cecidomyiidae records for New World countries.

This is a planning script for splitting the over-cap Cecidomyiidae family by
geography. It does not download records; it queries BOLD summaries one
country/territory at a time and writes a CSV of record counts.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
from pathlib import Path

from download_bold_fungi import PROJECT_ROOT, SUMMARY_FIELDS, api_get_json, write_json


FAMILY = "Cecidomyiidae"
DEFAULT_OUTDIR = PROJECT_ROOT / "Output" / "audits"
DEFAULT_RETRIES = 2
DEFAULT_RETRY_SLEEP = 61
DEFAULT_BETWEEN_COUNTRY_SLEEP = 2

NEW_WORLD_COUNTRIES = [
    "Canada",
    "United States",
    "Mexico",
    "Belize",
    "Costa Rica",
    "El Salvador",
    "Guatemala",
    "Honduras",
    "Nicaragua",
    "Panama",
    "Argentina",
    "Bolivia",
    "Brazil",
    "Chile",
    "Colombia",
    "Ecuador",
    "Guyana",
    "Paraguay",
    "Peru",
    "Suriname",
    "Uruguay",
    "Venezuela",
    "Antigua and Barbuda",
    "Bahamas",
    "Barbados",
    "Cuba",
    "Dominica",
    "Dominican Republic",
    "Grenada",
    "Haiti",
    "Jamaica",
    "Saint Kitts and Nevis",
    "Saint Lucia",
    "Saint Vincent and the Grenadines",
    "Trinidad and Tobago",
    "Anguilla",
    "Aruba",
    "Bermuda",
    "Bonaire, Sint Eustatius and Saba",
    "British Virgin Islands",
    "Cayman Islands",
    "Curacao",
    "Falkland Islands (Malvinas)",
    "French Guiana",
    "Greenland",
    "Guadeloupe",
    "Martinique",
    "Montserrat",
    "Puerto Rico",
    "Saint Barthelemy",
    "Saint Martin",
    "Saint Pierre and Miquelon",
    "Sint Maarten",
    "Turks and Caicos Islands",
    "United States Virgin Islands",
]


def retry_call(label: str, func, retries: int, retry_sleep: float):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            print(f"{label}: attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(retry_sleep)
    raise last_exc


def summarize_country(country: str, timeout: int) -> dict[str, object]:
    query = f"tax:family:{FAMILY};geo:country/ocean:{country}"
    preprocessor = api_get_json(
        "/query/preprocessor",
        {"query": query},
        timeout=timeout,
    )
    failed_terms = preprocessor.get("failed_terms") or []
    if failed_terms:
        return {
            "country": country,
            "query": query,
            "status": "failed_terms",
            "records": "",
            "records_with_coordinates": "",
            "coordinate_coverage_percent": "",
            "error": json.dumps(failed_terms, sort_keys=True),
        }

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_coord / n_records if n_records else 0.0
    return {
        "country": country,
        "query": query,
        "status": "ok",
        "records": n_records,
        "records_with_coordinates": n_coord,
        "coordinate_coverage_percent": f"{coord_share:.1f}",
        "error": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--retry-sleep", type=float, default=DEFAULT_RETRY_SLEEP)
    parser.add_argument("--between-country-sleep", type=float, default=DEFAULT_BETWEEN_COUNTRY_SLEEP)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    countries = NEW_WORLD_COUNTRIES[: args.limit] if args.limit else NEW_WORLD_COUNTRIES
    output_path = args.outdir / "bold_cecidomyiidae_new_world_country_summary.csv"

    fieldnames = [
        "country",
        "status",
        "records",
        "records_with_coordinates",
        "coordinate_coverage_percent",
        "error",
        "query",
    ]
    rows = []
    for country in countries:
        try:
            row = retry_call(
                f"{country} summary",
                lambda country=country: summarize_country(country, args.timeout),
                args.retries,
                args.retry_sleep,
            )
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            row = {
                "country": country,
                "query": f"tax:family:{FAMILY};geo:country/ocean:{country}",
                "status": "error",
                "records": "",
                "records_with_coordinates": "",
                "coordinate_coverage_percent": "",
                "error": str(exc),
            }
        rows.append(row)
        print(
            f"{country}: {row['status']}"
            + (f", {int(row['records']):,} records" if row["records"] != "" else ""),
            flush=True,
        )
        if args.between_country_sleep > 0:
            time.sleep(args.between_country_sleep)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [row for row in rows if row["status"] == "ok"]
    total_records = sum(int(row["records"]) for row in ok_rows)
    total_coords = sum(int(row["records_with_coordinates"]) for row in ok_rows)
    print(f"Wrote: {output_path}")
    print(f"Countries/territories queried: {len(rows)}")
    print(f"OK rows: {len(ok_rows)}")
    print(f"Summed records across OK rows: {total_records:,}")
    print(f"Summed records with coordinates: {total_coords:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
