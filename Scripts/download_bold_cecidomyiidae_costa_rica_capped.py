#!/usr/bin/env python3
"""Download BOLD Cecidomyiidae records for Costa Rica (capped at 1M).

Costa Rica has ~1.12M Cecidomyiidae records, exceeding BOLD's 1M query cap.
This script downloads a capped extract of 1M records. The BOLD API does not
support date or coordinate filtering, so we cannot split Costa Rica further
through the API.

This file is intentionally separate from the global capped Cecidomyiidae file
(bold_global_diptera_family_cecidomyiidae_capped_records.tsv), which contains
765K Costa Rica records mixed with other countries. The two files may have
different record compositions depending on BOLD's internal ordering, and their
union may provide better coverage than either alone.

Known gap: ~122K Costa Rica records cannot be downloaded through the API.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

from download_bold_fungi import (
    API_BASE,
    HTTP_HEADERS,
    MAX_RECORDS_PER_QUERY,
    PROJECT_ROOT,
    SUMMARY_FIELDS,
    api_get_json,
    download_stream,
    write_json,
)


FAMILY = "Cecidomyiidae"
COUNTRY = "Costa Rica"
QUERY = f"tax:family:{FAMILY};geo:country/ocean:{COUNTRY}"
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "bold" / "diptera_cecidomyiidae_costa_rica"
DEFAULT_STEM = "bold_cecidomyiidae_costa_rica_capped"
DEFAULT_TIMEOUT = 600


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--stem", default=DEFAULT_STEM)
    parser.add_argument("--format", default="tsv", choices=["tsv", "json", "dwc"])
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    preprocessor_path = args.outdir / f"{args.stem}_preprocessor.json"
    summary_path = args.outdir / f"{args.stem}_summary.json"
    query_path = args.outdir / f"{args.stem}_query.json"
    output_path = args.outdir / f"{args.stem}_records.{args.format}"
    gap_path = args.outdir / f"{args.stem}_gap_notes.txt"

    if output_path.exists() and not args.force:
        print(f"Output exists: {output_path}")
        print("Use --force to overwrite.")
        return 0

    print(f"Query: {QUERY}")

    print("Validating query...")
    preprocessor = api_get_json(
        "/query/preprocessor",
        {"query": QUERY},
        timeout=args.timeout,
    )
    write_json(preprocessor_path, preprocessor)

    if preprocessor.get("failed_terms"):
        print(f"BOLD rejected query terms: {preprocessor['failed_terms']}", file=sys.stderr)
        return 1

    print("Fetching summary...")
    summary = api_get_json(
        "/summary",
        {"query": QUERY, "fields": SUMMARY_FIELDS},
        timeout=args.timeout,
    )
    write_json(summary_path, summary)

    n_records = int(summary.get("counts", {}).get("specimens", 0))
    n_with_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_with_coord / n_records if n_records else 0

    print(f"Total records: {n_records:,}")
    print(f"Records with coordinates: {n_with_coord:,} ({coord_share:.1f}%)")

    if n_records > MAX_RECORDS_PER_QUERY:
        gap = n_records - MAX_RECORDS_PER_QUERY
        coverage = 100 * MAX_RECORDS_PER_QUERY / n_records
        print(f"WARNING: Exceeds {MAX_RECORDS_PER_QUERY:,}-record cap by {gap:,} records.")
        print(f"Download will capture ~{coverage:.1f}% of Costa Rica Cecidomyiidae.")

        gap_notes = [
            f"Costa Rica Cecidomyiidae download gap notes",
            f"",
            f"Total records in BOLD: {n_records:,}",
            f"BOLD query cap: {MAX_RECORDS_PER_QUERY:,}",
            f"Records NOT downloaded: {gap:,}",
            f"Coverage: {coverage:.1f}%",
            f"",
            f"The BOLD Portal API does not support date or coordinate filtering.",
            f"The ~{gap:,} missing records cannot be obtained through the API.",
            f"",
            f"Possible complements:",
            f"- Global capped file: diptera_by_family/bold_global_diptera_family_cecidomyiidae_capped_records.tsv",
            f"  Contains 765K Costa Rica records; may have different composition.",
            f"- Contact BOLD for research bulk export.",
            f"",
        ]
        gap_path.write_text("\n".join(gap_notes), encoding="utf-8")
        print(f"Wrote gap notes: {gap_path}")

    if args.summary_only:
        print("Summary-only mode: stopping before download.")
        return 0

    print("Requesting query token...")
    query_payload = api_get_json(
        "/query",
        {"query": QUERY, "extent": "full"},
        timeout=args.timeout,
    )
    write_json(query_path, query_payload)

    query_id = query_payload.get("query_id")
    if not query_id:
        print(f"No query_id returned: {json.dumps(query_payload)}", file=sys.stderr)
        return 1

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': args.format})}"
    )
    print(f"Downloading to: {output_path}")
    print("(This will be capped at 1M records)")
    download_stream(download_url, output_path, timeout=args.timeout)

    print(f"Done: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
