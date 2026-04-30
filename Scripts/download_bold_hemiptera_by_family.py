#!/usr/bin/env python3
"""Download Hemiptera from BOLD family by family.

This avoids the 1M-record query cap by scraping the BOLD v4 taxonomy browser
for Hemiptera family names, then issuing one BOLD Portal query per family.
Failures are logged to CSV and can be retried later with --failed-only.
"""

from __future__ import annotations

import argparse
import csv
import html
import http.client
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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


ORDER = "Hemiptera"
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "bold" / "hemiptera_by_family"
DEFAULT_RETRY_SLEEP = 61
DEFAULT_BETWEEN_FAMILY_SLEEP = 11
DEFAULT_RETRIES = 3
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


def get_text(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def find_order_taxid(order: str, timeout: int) -> str:
    url = "https://v4.boldsystems.org/index.php/API_Tax/TaxonSearch?" + urllib.parse.urlencode(
        {"taxName": order}
    )
    text = get_text(url, timeout)
    match = re.search(r'"taxid"\s*:\s*(\d+).*?"taxon"\s*:\s*"' + re.escape(order) + r'"', text)
    if not match:
        raise RuntimeError(f"Could not find BOLD taxid for {order}")
    return match.group(1)


def scrape_hemiptera_families(timeout: int) -> list[dict[str, object]]:
    taxid = find_order_taxid(ORDER, timeout)
    url = f"https://v4.boldsystems.org/index.php/Taxbrowser_Taxonpage?taxid={taxid}"
    text = get_text(url, timeout)
    section = re.search(r"Families \(\d+\).*?</ol>", text, flags=re.S)
    if not section:
        raise RuntimeError("Could not find Hemiptera Families section on BOLD v4 page")

    rows = []
    for family_taxid, family, count in re.findall(
        r'href="\?taxid=(\d+)">([^<\[]+?) \[(\d+)\]</a>',
        section.group(0),
    ):
        rows.append(
            {
                "family": html.unescape(family.strip()),
                "taxid": family_taxid,
                "records_v4_taxbrowser": int(count),
            }
        )
    return sorted(rows, key=lambda row: int(row["records_v4_taxbrowser"]), reverse=True)


def read_failed_families(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", newline="", encoding="utf-8") as f:
        return {row["family"] for row in csv.DictReader(f) if row.get("family")}


def write_family_manifest(path: Path, families: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["family", "taxid", "records_v4_taxbrowser"]
        )
        writer.writeheader()
        writer.writerows(families)


def append_csv(path: Path, row: dict[str, object], fieldnames: list[str]) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def append_summary(
    path: Path,
    family: str,
    row: dict[str, object],
    n_records: int,
    n_coord: int,
    coord_share: float,
    status: str,
    error: str = "",
) -> None:
    append_csv(
        path,
        {
            "family": family,
            "taxid": row["taxid"],
            "records_v4_taxbrowser": row["records_v4_taxbrowser"],
            "records_v5_summary": n_records,
            "records_with_coordinates": n_coord,
            "coordinate_coverage_percent": f"{coord_share:.1f}",
            "status": status,
            "error": error,
        },
        [
            "family",
            "taxid",
            "records_v4_taxbrowser",
            "records_v5_summary",
            "records_with_coordinates",
            "coordinate_coverage_percent",
            "status",
            "error",
        ],
    )


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


def summarize_family(family: str, timeout: int) -> tuple[int, int, float]:
    query = f"tax:family:{family}"
    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_coord / n_records if n_records else 0.0
    return n_records, n_coord, coord_share


def download_family(family: str, outdir: Path, fmt: str, timeout: int) -> None:
    query = f"tax:family:{family}"
    query_payload = api_get_json(
        "/query",
        {"query": query, "extent": "full"},
        timeout=timeout,
    )
    stem = f"bold_global_hemiptera_family_{slug(family)}"
    write_json(outdir / f"{stem}_query.json", query_payload)

    query_id = query_payload.get("query_id")
    if not query_id:
        raise RuntimeError(f"No query_id returned for {family}: {json.dumps(query_payload)}")

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': fmt})}"
    )
    output_path = outdir / f"{stem}_records.{fmt}"
    print(f"{family}: downloading to {output_path}", flush=True)
    download_stream(download_url, output_path, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--format", default="tsv", choices=["tsv", "json", "dwc"])
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--retry-sleep", type=float, default=DEFAULT_RETRY_SLEEP)
    parser.add_argument("--between-family-sleep", type=float, default=DEFAULT_BETWEEN_FAMILY_SLEEP)
    parser.add_argument(
        "--max-consecutive-403",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_403,
        help="Stop after this many consecutive family failures ending in HTTP 403.",
    )
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Optional max families to process.")
    parser.add_argument("--families", nargs="*", default=None, help="Optional explicit family names.")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.outdir / "hemiptera_family_manifest.csv"
    summary_path = args.outdir / "hemiptera_family_download_summary.csv"
    failed_path = args.outdir / "hemiptera_family_failed_downloads.csv"

    families = scrape_hemiptera_families(args.timeout)
    write_family_manifest(manifest_path, families)

    if args.families:
        keep = set(args.families)
        families = [row for row in families if row["family"] in keep]
    if args.failed_only:
        failed = read_failed_families(failed_path)
        families = [row for row in families if row["family"] in failed]
    if args.limit is not None:
        families = families[: args.limit]

    print(f"Families to process: {len(families)}", flush=True)

    consecutive_403 = 0
    for row in families:
        family = str(row["family"])
        stem = f"bold_global_hemiptera_family_{slug(family)}"
        output_path = args.outdir / f"{stem}_records.{args.format}"

        if output_path.exists() and not args.force:
            print(f"{family}: output exists, skipping", flush=True)
            continue

        try:
            n_records, n_coord, coord_share = retry_call(
                f"{family} summary",
                lambda family=family: summarize_family(family, args.timeout),
                args.retries,
                args.retry_sleep,
            )
            print(
                f"{family}: {n_records:,} records; {n_coord:,} coords ({coord_share:.1f}%)",
                flush=True,
            )

            if args.summary_only or n_records == 0:
                append_summary(
                    summary_path,
                    family,
                    row,
                    n_records,
                    n_coord,
                    coord_share,
                    "summary_only" if args.summary_only else "empty",
                )
                consecutive_403 = 0
                continue
            if n_records > MAX_RECORDS_PER_QUERY:
                raise RuntimeError(
                    f"{family} exceeds {MAX_RECORDS_PER_QUERY:,}-record cap; split further"
                )

            retry_call(
                f"{family} download",
                lambda family=family: download_family(
                    family, args.outdir, args.format, args.timeout
                ),
                args.retries,
                args.retry_sleep,
            )
            append_summary(
                summary_path,
                family,
                row,
                n_records,
                n_coord,
                coord_share,
                "downloaded",
            )
            consecutive_403 = 0
            if args.between_family_sleep > 0:
                print(
                    f"{family}: sleeping {args.between_family_sleep:g}s before next family",
                    flush=True,
                )
                time.sleep(args.between_family_sleep)
        except RETRY_EXCEPTIONS as exc:
            print(f"{family}: failed after retries: {exc}", file=sys.stderr, flush=True)
            append_csv(
                failed_path,
                {
                    "family": family,
                    "taxid": row["taxid"],
                    "records_v4_taxbrowser": row["records_v4_taxbrowser"],
                    "error": str(exc),
                },
                ["family", "taxid", "records_v4_taxbrowser", "error"],
            )
            if is_http_403(exc):
                consecutive_403 += 1
                print(
                    f"{family}: consecutive HTTP 403 failures: "
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
                        "Wait and rerun later; completed files will be skipped.",
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
