#!/usr/bin/env python3
"""Download BOLD Animalia excluding Arthropoda, Chordata, and Mollusca.

BOLD's public query syntax is most reliable for positive taxon queries, so this
script downloads the complement as one file per remaining animal phylum rather
than using a single negative/exclusion query.
"""

from __future__ import annotations

import argparse
import csv
import json
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


PHYLA = [
    "Annelida",
    "Cnidaria",
    "Echinodermata",
    "Nematoda",
    "Platyhelminthes",
    "Porifera",
    "Rotifera",
    "Bryozoa",
    "Nemertea",
    "Tardigrada",
    "Onychophora",
    "Acanthocephala",
    "Brachiopoda",
    "Chaetognatha",
    "Ctenophora",
    "Entoprocta",
    "Gastrotricha",
    "Hemichordata",
    "Kinorhyncha",
    "Phoronida",
    "Priapulida",
    "Xenacoelomorpha",
]


def slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("/", "_")


def summarize_phylum(phylum: str, outdir: Path, timeout: int) -> tuple[int, int, float]:
    query = f"tax:phylum:{phylum}"
    stem = f"bold_global_{slug(phylum)}"

    preprocessor = api_get_json(
        "/query/preprocessor",
        {"query": query},
        timeout=timeout,
    )
    write_json(outdir / f"{stem}_preprocessor.json", preprocessor)

    if preprocessor.get("failed_terms"):
        print(f"{phylum}: rejected by BOLD query preprocessor", file=sys.stderr)
        return 0, 0, 0.0

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    write_json(outdir / f"{stem}_summary.json", summary)

    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_coord / n_records if n_records else 0.0
    return n_records, n_coord, coord_share


def download_phylum(phylum: str, outdir: Path, fmt: str, timeout: int, force: bool) -> None:
    query = f"tax:phylum:{phylum}"
    stem = f"bold_global_{slug(phylum)}"
    output_path = outdir / f"{stem}_records.{fmt}"

    if output_path.exists() and not force:
        print(f"{phylum}: output exists, skipping: {output_path}")
        return

    query_payload = api_get_json(
        "/query",
        {"query": query, "extent": "full"},
        timeout=timeout,
    )
    write_json(outdir / f"{stem}_query.json", query_payload)

    query_id = query_payload.get("query_id")
    if not query_id:
        raise RuntimeError(f"{phylum}: no query_id returned: {json.dumps(query_payload)}")

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': fmt})}"
    )
    print(f"{phylum}: downloading to {output_path}")
    download_stream(download_url, output_path, timeout=timeout)


def retry_call(label: str, func, attempts: int, sleep_seconds: float):
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            last_exc = exc
            print(f"{label}: attempt {attempt}/{attempts} failed: {exc}", file=sys.stderr)
            if attempt < attempts:
                time.sleep(sleep_seconds * attempt)
    raise last_exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=PROJECT_ROOT / "Data" / "raw" / "bold" / "animals_except_acm",
    )
    parser.add_argument("--format", default="tsv", choices=["tsv", "json", "dwc"])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep", type=float, default=20)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--phyla",
        nargs="*",
        default=PHYLA,
        help="Override the phylum list. Defaults to Animalia excluding Arthropoda, Chordata, Mollusca.",
    )
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    summary_csv = args.outdir / "bold_animals_except_acm_summary.csv"
    rows = []

    for phylum in args.phyla:
        print(f"Summarizing {phylum}")
        try:
            n_records, n_coord, coord_share = retry_call(
                f"{phylum} summary",
                lambda phylum=phylum: summarize_phylum(phylum, args.outdir, args.timeout),
                args.retries,
                args.retry_sleep,
            )
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            print(f"{phylum}: summary failed: {exc}", file=sys.stderr)
            rows.append(
                {
                    "phylum": phylum,
                    "records": "",
                    "records_with_coordinates": "",
                    "coordinate_coverage_percent": "",
                    "download_error": f"summary failed: {exc}",
                }
            )
            continue
        print(f"{phylum}: {n_records:,} records; {n_coord:,} with coordinates ({coord_share:.1f}%)")
        rows.append(
            {
                "phylum": phylum,
                "records": n_records,
                "records_with_coordinates": n_coord,
                "coordinate_coverage_percent": f"{coord_share:.1f}",
                "download_error": "",
            }
        )

        if n_records == 0 or args.summary_only:
            continue
        if n_records > MAX_RECORDS_PER_QUERY:
            print(
                f"{phylum}: exceeds {MAX_RECORDS_PER_QUERY:,}-record cap; split before downloading.",
                file=sys.stderr,
            )
            continue
        try:
            retry_call(
                f"{phylum} download",
                lambda phylum=phylum: download_phylum(
                    phylum, args.outdir, args.format, args.timeout, args.force
                ),
                args.retries,
                args.retry_sleep,
            )
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            print(f"{phylum}: download failed: {exc}", file=sys.stderr)
            rows[-1]["download_error"] = str(exc)

    with summary_csv.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=[
                "phylum",
                "records",
                "records_with_coordinates",
                "coordinate_coverage_percent",
                "download_error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote summary: {summary_csv}")
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
