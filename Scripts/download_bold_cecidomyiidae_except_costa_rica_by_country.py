#!/usr/bin/env python3
"""Download BOLD Cecidomyiidae records country by country, excluding Costa Rica.

Cecidomyiidae is above the 1M-record BOLD query cap at the family level, and
Costa Rica alone is also above the cap. This script downloads all positive
country/ocean buckets except Costa Rica, one TSV per country/ocean value.
Costa Rica must be split separately.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

from download_bold_fungi import (
    API_BASE,
    MAX_RECORDS_PER_QUERY,
    PROJECT_ROOT,
    SUMMARY_FIELDS,
    api_get_json,
    download_stream,
    write_json,
)


FAMILY = "Cecidomyiidae"
EXCLUDED_COUNTRIES = {"Costa Rica"}
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "bold" / "diptera_cecidomyiidae_except_costa_rica_by_country"
FAMILY_SUMMARY_PATH = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "bold"
    / "diptera_by_family"
    / "bold_global_diptera_family_cecidomyiidae_oversized_summary.json"
)
DEFAULT_RETRIES = 3
DEFAULT_RETRY_SLEEP = 61
DEFAULT_BETWEEN_COUNTRY_SLEEP = 11
DEFAULT_TIMEOUT = 180
DEFAULT_MAX_CONSECUTIVE_403 = 2

RETRY_EXCEPTIONS = (
    urllib.error.HTTPError,
    urllib.error.URLError,
    TimeoutError,
    socket.timeout,
    http.client.HTTPException,
    OSError,
    RuntimeError,
)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def retry_call(label: str, func, retries: int, retry_sleep: float):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except RETRY_EXCEPTIONS as exc:
            last_exc = exc
            print(f"{label}: attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(retry_sleep)
    raise last_exc


def is_http_403(exc: BaseException) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code == 403


def append_csv(path: Path, row: dict[str, object], fieldnames: list[str]) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def initialize_csv(path: Path, fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def load_or_fetch_family_summary(timeout: int, refresh: bool) -> dict:
    if FAMILY_SUMMARY_PATH.exists() and not refresh:
        return json.loads(FAMILY_SUMMARY_PATH.read_text(encoding="utf-8"))

    query = f"tax:family:{FAMILY}"
    preprocessor = api_get_json("/query/preprocessor", {"query": query}, timeout=timeout)
    failed_terms = preprocessor.get("failed_terms") or []
    if failed_terms:
        raise RuntimeError(f"BOLD rejected {FAMILY}: {json.dumps(failed_terms)}")

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    FAMILY_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(FAMILY_SUMMARY_PATH, summary)
    return summary


def country_rows_from_summary(summary: dict, include_excluded: bool) -> list[dict[str, object]]:
    country_counts = summary.get("country/ocean", {}) or {}
    rows = []
    for country, count in country_counts.items():
        if not country or int(count) <= 0:
            continue
        if country in EXCLUDED_COUNTRIES and not include_excluded:
            continue
        rows.append({"country_or_ocean": country, "records_family_summary": int(count)})
    return sorted(rows, key=lambda row: int(row["records_family_summary"]), reverse=True)


def country_query(country_or_ocean: str) -> str:
    return f"tax:family:{FAMILY};geo:country/ocean:{country_or_ocean}"


def summarize_country(country_or_ocean: str, timeout: int) -> tuple[int, int, float]:
    query = country_query(country_or_ocean)
    preprocessor = api_get_json("/query/preprocessor", {"query": query}, timeout=timeout)
    failed_terms = preprocessor.get("failed_terms") or []
    if failed_terms:
        raise RuntimeError(f"BOLD rejected {country_or_ocean}: {json.dumps(failed_terms)}")

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_coord / n_records if n_records else 0.0
    return n_records, n_coord, coord_share


def download_country(country_or_ocean: str, outdir: Path, fmt: str, timeout: int) -> None:
    query = country_query(country_or_ocean)
    query_payload = api_get_json(
        "/query",
        {"query": query, "extent": "full"},
        timeout=timeout,
    )
    stem = f"bold_global_diptera_family_cecidomyiidae_country_{slug(country_or_ocean)}"
    write_json(outdir / f"{stem}_query.json", query_payload)

    query_id = query_payload.get("query_id")
    if not query_id:
        raise RuntimeError(f"No query_id returned for {country_or_ocean}: {json.dumps(query_payload)}")

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': fmt})}"
    )
    output_path = outdir / f"{stem}_records.{fmt}"
    print(f"{country_or_ocean}: downloading to {output_path}", flush=True)
    download_stream(download_url, output_path, timeout=timeout)


def read_failed_countries(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", newline="", encoding="utf-8") as f:
        return {row["country_or_ocean"] for row in csv.DictReader(f) if row.get("country_or_ocean")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--format", default="tsv", choices=["tsv", "json", "dwc"])
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--retry-sleep", type=float, default=DEFAULT_RETRY_SLEEP)
    parser.add_argument("--between-country-sleep", type=float, default=DEFAULT_BETWEEN_COUNTRY_SLEEP)
    parser.add_argument(
        "--max-consecutive-403",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_403,
        help="Stop after this many consecutive country failures ending in HTTP 403.",
    )
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--refresh-family-summary", action="store_true")
    parser.add_argument(
        "--include-costa-rica",
        action="store_true",
        help="Include Costa Rica despite it exceeding the 1M cap; mainly for diagnostics.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--countries", nargs="*", default=None, help="Optional explicit country/ocean names.")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.outdir / "cecidomyiidae_except_costa_rica_country_manifest.csv"
    summary_path = args.outdir / "cecidomyiidae_except_costa_rica_country_download_summary.csv"
    failed_path = args.outdir / "cecidomyiidae_except_costa_rica_country_failed_downloads.csv"

    family_summary = load_or_fetch_family_summary(args.timeout, args.refresh_family_summary)
    countries = country_rows_from_summary(family_summary, args.include_costa_rica)

    if args.countries:
        keep = set(args.countries)
        countries = [row for row in countries if row["country_or_ocean"] in keep]
    elif args.failed_only:
        failed = read_failed_countries(failed_path)
        countries = [row for row in countries if row["country_or_ocean"] in failed]
    if args.limit is not None:
        countries = countries[: args.limit]

    manifest_fields = ["country_or_ocean", "records_family_summary"]
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=manifest_fields)
        writer.writeheader()
        writer.writerows(countries)

    summary_fields = [
        "country_or_ocean",
        "records_family_summary",
        "records_v5_summary",
        "records_with_coordinates",
        "coordinate_coverage_percent",
        "status",
        "error",
    ]
    failed_fields = ["country_or_ocean", "records_family_summary", "error"]
    if not args.failed_only:
        initialize_csv(failed_path, failed_fields)

    print(f"Countries/oceans to process: {len(countries)}", flush=True)
    consecutive_403 = 0

    for row in countries:
        country = str(row["country_or_ocean"])
        stem = f"bold_global_diptera_family_cecidomyiidae_country_{slug(country)}"
        output_path = args.outdir / f"{stem}_records.{args.format}"

        if output_path.exists() and not args.force:
            print(f"{country}: output exists, skipping", flush=True)
            continue

        try:
            n_records, n_coord, coord_share = retry_call(
                f"{country} summary",
                lambda country=country: summarize_country(country, args.timeout),
                args.retries,
                args.retry_sleep,
            )
            print(f"{country}: {n_records:,} records; {n_coord:,} coords ({coord_share:.1f}%)")

            if args.summary_only or n_records == 0:
                append_csv(
                    summary_path,
                    {
                        "country_or_ocean": country,
                        "records_family_summary": row["records_family_summary"],
                        "records_v5_summary": n_records,
                        "records_with_coordinates": n_coord,
                        "coordinate_coverage_percent": f"{coord_share:.1f}",
                        "status": "summary_only" if args.summary_only else "empty",
                        "error": "",
                    },
                    summary_fields,
                )
                consecutive_403 = 0
                continue
            if n_records > MAX_RECORDS_PER_QUERY:
                raise RuntimeError(
                    f"{country} exceeds {MAX_RECORDS_PER_QUERY:,}-record cap; split further"
                )

            retry_call(
                f"{country} download",
                lambda country=country: download_country(country, args.outdir, args.format, args.timeout),
                args.retries,
                args.retry_sleep,
            )
            append_csv(
                summary_path,
                {
                    "country_or_ocean": country,
                    "records_family_summary": row["records_family_summary"],
                    "records_v5_summary": n_records,
                    "records_with_coordinates": n_coord,
                    "coordinate_coverage_percent": f"{coord_share:.1f}",
                    "status": "downloaded",
                    "error": "",
                },
                summary_fields,
            )
            consecutive_403 = 0
            if args.between_country_sleep > 0:
                print(f"{country}: sleeping {args.between_country_sleep:g}s before next country", flush=True)
                time.sleep(args.between_country_sleep)
        except RETRY_EXCEPTIONS as exc:
            print(f"{country}: failed after retries: {exc}", file=sys.stderr, flush=True)
            append_csv(
                failed_path,
                {
                    "country_or_ocean": country,
                    "records_family_summary": row["records_family_summary"],
                    "error": str(exc),
                },
                failed_fields,
            )
            if is_http_403(exc):
                consecutive_403 += 1
                print(
                    f"{country}: consecutive HTTP 403 failures: "
                    f"{consecutive_403}/{args.max_consecutive_403}",
                    file=sys.stderr,
                    flush=True,
                )
                if (
                    args.max_consecutive_403 > 0
                    and consecutive_403 >= args.max_consecutive_403
                ):
                    print(
                        "Stopping because BOLD is still returning HTTP 403. "
                        "Wait and rerun later; completed country files will be skipped.",
                        file=sys.stderr,
                        flush=True,
                    )
                    return 2
            else:
                consecutive_403 = 0

    print(f"Manifest: {manifest_path}", flush=True)
    print(f"Summary: {summary_path}", flush=True)
    print(f"Failed downloads: {failed_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
