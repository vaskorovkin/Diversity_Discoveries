#!/usr/bin/env python3
"""Download global public BOLD Fungi records.

This uses the current BOLD Portal API:
  1. validate query terms with /api/query/preprocessor
  2. get a summary with /api/summary
  3. obtain a 24-hour query token with /api/query
  4. stream records from /api/documents/<query_id>/download

The default query is tax:kingdom:Fungi. As of the initial project audit this is
below BOLD's 1,000,000-record per-query download cap.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_BASE = "https://portal.boldsystems.org/api"
PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_QUERY = "tax:kingdom:Fungi"
DEFAULT_STEM = "bold_global_fungi"
SUMMARY_FIELDS = "specimens,coord,country/ocean,collection_date_start,marker_code,species"
MAX_RECORDS_PER_QUERY = 1_000_000
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
    ),
    "Accept": "application/json,text/tab-separated-values,text/plain,*/*",
}


def api_get_json(endpoint: str, params: dict[str, str], timeout: int) -> dict:
    url = f"{API_BASE}{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def download_stream(url: str, output_path: Path, timeout: int) -> None:
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")
    bytes_read = 0
    started = time.time()

    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        with tmp_path.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                bytes_read += len(chunk)
                if bytes_read % (100 * 1024 * 1024) < 1024 * 1024:
                    elapsed = max(time.time() - started, 1)
                    mb = bytes_read / (1024 * 1024)
                    print(f"Downloaded {mb:,.0f} MB ({mb / elapsed:,.1f} MB/s)")

    tmp_path.replace(output_path)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download public BOLD records as TSV/JSON/Darwin Core."
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="BOLD query string.")
    parser.add_argument(
        "--stem",
        default=DEFAULT_STEM,
        help="Output filename stem, for example bold_global_fungi.",
    )
    parser.add_argument(
        "--format",
        default="tsv",
        choices=["tsv", "json", "dwc"],
        help="BOLD download format. Use tsv for BCDM TSV, dwc for Darwin Core TSV.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=PROJECT_ROOT / "Data" / "raw" / "bold",
        help="Directory for output files.",
    )
    parser.add_argument("--timeout", type=int, default=600, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output table if it already exists.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Validate the query and save summary metadata, but do not download records.",
    )
    parser.add_argument(
        "--ignore-cap",
        action="store_true",
        help="Attempt download even when the summary exceeds BOLD's 1M-record cap.",
    )
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    stem = args.stem
    preprocessor_path = args.outdir / f"{stem}_preprocessor.json"
    summary_path = args.outdir / f"{stem}_summary.json"
    query_path = args.outdir / f"{stem}_query.json"
    output_path = args.outdir / f"{stem}_records.{args.format}"

    if output_path.exists() and not args.force:
        print(f"Output exists: {output_path}")
        print("Use --force to overwrite.")
        return 0

    print(f"Validating query: {args.query}")
    preprocessor = api_get_json(
        "/query/preprocessor",
        {"query": args.query},
        timeout=args.timeout,
    )
    write_json(preprocessor_path, preprocessor)

    if "failed_terms" in preprocessor and preprocessor["failed_terms"]:
        print("BOLD rejected one or more query terms:", file=sys.stderr)
        print(json.dumps(preprocessor["failed_terms"], indent=2), file=sys.stderr)
        return 1

    print("Fetching summary.")
    summary = api_get_json(
        "/summary",
        {"query": args.query, "fields": SUMMARY_FIELDS},
        timeout=args.timeout,
    )
    write_json(summary_path, summary)

    n_records = int(summary.get("counts", {}).get("specimens", 0))
    n_with_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_with_coord / n_records if n_records else 0
    print(f"Records: {n_records:,}")
    print(f"Records with coordinates: {n_with_coord:,} ({coord_share:.1f}%)")

    if n_records > MAX_RECORDS_PER_QUERY and not args.ignore_cap:
        print(
            f"Query exceeds BOLD's {MAX_RECORDS_PER_QUERY:,}-record per-query cap. "
            "Split by country, taxon, or another query dimension.",
            file=sys.stderr,
        )
        return 2
    if n_records > MAX_RECORDS_PER_QUERY and args.ignore_cap:
        print(
            f"Warning: query exceeds BOLD's {MAX_RECORDS_PER_QUERY:,}-record cap; "
            "attempting download because --ignore-cap was supplied.",
            file=sys.stderr,
        )

    if args.summary_only:
        print("Summary-only mode: stopping before query token and record download.")
        return 0

    print("Requesting query token.")
    query_payload = api_get_json(
        "/query",
        {"query": args.query, "extent": "full"},
        timeout=args.timeout,
    )
    write_json(query_path, query_payload)

    query_id = query_payload.get("query_id")
    if not query_id:
        print("No query_id returned by BOLD.", file=sys.stderr)
        print(json.dumps(query_payload, indent=2), file=sys.stderr)
        return 1

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': args.format})}"
    )
    print(f"Downloading to: {output_path}")
    download_stream(download_url, output_path, timeout=args.timeout)
    print(f"Done: {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"HTTP error {exc.code}: {exc.reason}", file=sys.stderr)
        raise SystemExit(1)
    except urllib.error.URLError as exc:
        print(f"URL error: {exc.reason}", file=sys.stderr)
        raise SystemExit(1)
