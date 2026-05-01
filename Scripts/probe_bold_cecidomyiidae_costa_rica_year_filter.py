#!/usr/bin/env python3
"""Probe whether BOLD supports year/date filters for Costa Rica Cecidomyiidae.

This script only calls BOLD preprocessor/summary endpoints. It does not request
a query token and does not download records.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
from pathlib import Path

from download_bold_fungi import PROJECT_ROOT, SUMMARY_FIELDS, api_get_json


BASE_QUERY = "tax:family:Cecidomyiidae;geo:country/ocean:Costa Rica"
DEFAULT_OUTDIR = PROJECT_ROOT / "Output" / "audits"


def query_summary(query: str, timeout: int) -> dict[str, object]:
    preprocessor = api_get_json("/query/preprocessor", {"query": query}, timeout=timeout)
    failed_terms = preprocessor.get("failed_terms") or []
    if failed_terms:
        return {
            "query": query,
            "status": "failed_terms",
            "records": "",
            "records_with_coordinates": "",
            "error": json.dumps(failed_terms, sort_keys=True),
        }

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    return {
        "query": query,
        "status": "ok",
        "records": n_records,
        "records_with_coordinates": n_coord,
        "error": "",
    }


def candidate_queries(year: int) -> list[tuple[str, str]]:
    return [
        ("collection_date_start_year", f"{BASE_QUERY};collection_date_start:{year}"),
        ("collection_date_start_date", f"{BASE_QUERY};collection_date_start:{year}-01-01"),
        ("collection_date_start_range_slash", f"{BASE_QUERY};collection_date_start:{year}-01-01/{year}-12-31"),
        ("collection_date_start_range_colon", f"{BASE_QUERY};collection_date_start:{year}-01-01:{year}-12-31"),
        ("collection_year", f"{BASE_QUERY};collection_year:{year}"),
        ("year", f"{BASE_QUERY};year:{year}"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--sleep", type=float, default=1)
    parser.add_argument("--years", nargs="*", type=int, default=[2010, 2015, 2020])
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    output_path = args.outdir / "bold_cecidomyiidae_costa_rica_year_filter_probe.csv"

    rows: list[dict[str, object]] = []

    try:
        base = query_summary(BASE_QUERY, args.timeout)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"Base query failed: {exc}", file=sys.stderr)
        return 1

    base_records = int(base["records"]) if base["records"] != "" else 0
    rows.append(
        {
            "label": "base",
            "year": "",
            "status": base["status"],
            "records": base["records"],
            "records_with_coordinates": base["records_with_coordinates"],
            "same_as_base": "",
            "error": base["error"],
            "query": base["query"],
        }
    )
    print(f"base: {base_records:,} records", flush=True)

    for year in args.years:
        for label, query in candidate_queries(year):
            try:
                row = query_summary(query, args.timeout)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
                row = {
                    "query": query,
                    "status": "error",
                    "records": "",
                    "records_with_coordinates": "",
                    "error": str(exc),
                }
            same_as_base = ""
            if row["records"] != "":
                same_as_base = int(row["records"]) == base_records
            rows.append(
                {
                    "label": label,
                    "year": year,
                    "status": row["status"],
                    "records": row["records"],
                    "records_with_coordinates": row["records_with_coordinates"],
                    "same_as_base": same_as_base,
                    "error": row["error"],
                    "query": row["query"],
                }
            )
            print(
                f"{year} {label}: {row['status']}"
                + (f", {int(row['records']):,} records" if row["records"] != "" else "")
                + (f", same_as_base={same_as_base}" if same_as_base != "" else "")
                ,
                flush=True,
            )
            if args.sleep > 0:
                time.sleep(args.sleep)

    fieldnames = [
        "label",
        "year",
        "status",
        "records",
        "records_with_coordinates",
        "same_as_base",
        "error",
        "query",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote: {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
