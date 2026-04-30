#!/usr/bin/env python3
"""Download selected non-insect arthropod and microbe-like BOLD groups.

Each group is below the 1M-record BOLD query cap in the current summary table,
so this script downloads one TSV per group. Zero-record groups are logged as
empty and skipped.
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


DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "bold" / "non_insect_arthropods_and_microbes"
DEFAULT_RETRY_SLEEP = 61
DEFAULT_BETWEEN_GROUP_SLEEP = 11
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

GROUPS = [
    ("Araneae", "tax:order:Araneae"),
    ("Acari", "tax:order:Acari"),
    ("Scorpiones", "tax:order:Scorpiones"),
    ("Opiliones", "tax:order:Opiliones"),
    ("Pseudoscorpiones", "tax:order:Pseudoscorpiones"),
    ("Decapoda", "tax:order:Decapoda"),
    ("Amphipoda", "tax:order:Amphipoda"),
    ("Isopoda", "tax:order:Isopoda"),
    ("Copepoda", "tax:class:Copepoda"),
    ("Ostracoda", "tax:class:Ostracoda"),
    ("Chilopoda", "tax:class:Chilopoda"),
    ("Diplopoda", "tax:class:Diplopoda"),
    ("Symphyla", "tax:class:Symphyla"),
    ("Pauropoda", "tax:class:Pauropoda"),
    ("Pycnogonida", "tax:class:Pycnogonida"),
    ("Xiphosura", "tax:class:Xiphosura"),
    ("Chromista", "tax:kingdom:Chromista"),
    ("Protozoa", "tax:kingdom:Protozoa"),
    ("Archaea", "tax:kingdom:Archaea"),
    ("Bacteria", "tax:kingdom:Bacteria"),
]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def is_http_403(exc: BaseException) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code == 403


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


def summarize_query(query: str, timeout: int) -> tuple[int, int, float]:
    preprocessor = api_get_json(
        "/query/preprocessor",
        {"query": query},
        timeout=timeout,
    )
    failed_terms = preprocessor.get("failed_terms") or []
    if failed_terms:
        raise RuntimeError(f"BOLD rejected query terms: {json.dumps(failed_terms)}")

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_coord / n_records if n_records else 0.0
    return n_records, n_coord, coord_share


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


def download_group(name: str, query: str, outdir: Path, fmt: str, timeout: int) -> None:
    stem = f"bold_global_{slug(name)}"
    query_payload = api_get_json(
        "/query",
        {"query": query, "extent": "full"},
        timeout=timeout,
    )
    write_json(outdir / f"{stem}_query.json", query_payload)

    query_id = query_payload.get("query_id")
    if not query_id:
        raise RuntimeError(f"No query_id returned for {name}: {json.dumps(query_payload)}")

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': fmt})}"
    )
    output_path = outdir / f"{stem}_records.{fmt}"
    print(f"{name}: downloading to {output_path}", flush=True)
    download_stream(download_url, output_path, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--format", default="tsv", choices=["tsv", "json", "dwc"])
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--retry-sleep", type=float, default=DEFAULT_RETRY_SLEEP)
    parser.add_argument("--between-group-sleep", type=float, default=DEFAULT_BETWEEN_GROUP_SLEEP)
    parser.add_argument(
        "--max-consecutive-403",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_403,
        help="Stop after this many consecutive group failures ending in HTTP 403.",
    )
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--groups", nargs="*", default=None, help="Optional explicit group names.")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    summary_path = args.outdir / "non_insect_arthropods_and_microbes_summary.csv"
    failed_path = args.outdir / "non_insect_arthropods_and_microbes_failed.csv"

    groups = GROUPS
    if args.groups:
        keep = set(args.groups)
        groups = [row for row in groups if row[0] in keep]
    if args.failed_only:
        failed = set()
        if failed_path.exists():
            with failed_path.open("r", newline="", encoding="utf-8") as f:
                failed = {row["group"] for row in csv.DictReader(f) if row.get("group")}
        groups = [row for row in groups if row[0] in failed]
    if args.limit is not None:
        groups = groups[: args.limit]

    print(f"Groups to process: {len(groups)}", flush=True)

    summary_fields = [
        "group",
        "query",
        "records",
        "records_with_coordinates",
        "coordinate_coverage_percent",
        "status",
        "error",
    ]
    failed_fields = ["group", "query", "error"]
    if not args.failed_only:
        initialize_csv(failed_path, failed_fields)
    consecutive_403 = 0

    for name, query in groups:
        stem = f"bold_global_{slug(name)}"
        output_path = args.outdir / f"{stem}_records.{args.format}"

        if output_path.exists() and not args.force:
            print(f"{name}: output exists, skipping", flush=True)
            continue

        try:
            n_records, n_coord, coord_share = retry_call(
                f"{name} summary",
                lambda query=query: summarize_query(query, args.timeout),
                args.retries,
                args.retry_sleep,
            )
            print(f"{name}: {n_records:,} records; {n_coord:,} coords ({coord_share:.1f}%)")
            if n_records > MAX_RECORDS_PER_QUERY:
                raise RuntimeError(f"{name} exceeds {MAX_RECORDS_PER_QUERY:,}-record cap")

            if args.summary_only or n_records == 0:
                append_csv(
                    summary_path,
                    {
                        "group": name,
                        "query": query,
                        "records": n_records,
                        "records_with_coordinates": n_coord,
                        "coordinate_coverage_percent": f"{coord_share:.1f}",
                        "status": "summary_only" if args.summary_only else "empty",
                        "error": "",
                    },
                    summary_fields,
                )
                consecutive_403 = 0
                continue

            retry_call(
                f"{name} download",
                lambda name=name, query=query: download_group(
                    name, query, args.outdir, args.format, args.timeout
                ),
                args.retries,
                args.retry_sleep,
            )
            append_csv(
                summary_path,
                {
                    "group": name,
                    "query": query,
                    "records": n_records,
                    "records_with_coordinates": n_coord,
                    "coordinate_coverage_percent": f"{coord_share:.1f}",
                    "status": "downloaded",
                    "error": "",
                },
                summary_fields,
            )
            consecutive_403 = 0
            if args.between_group_sleep > 0:
                print(
                    f"{name}: sleeping {args.between_group_sleep:g}s before next group",
                    flush=True,
                )
                time.sleep(args.between_group_sleep)
        except RETRY_EXCEPTIONS as exc:
            print(f"{name}: failed after retries: {exc}", file=sys.stderr, flush=True)
            append_csv(failed_path, {"group": name, "query": query, "error": str(exc)}, failed_fields)
            if is_http_403(exc):
                consecutive_403 += 1
                print(
                    f"{name}: consecutive HTTP 403 failures: "
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

    print(f"Summary: {summary_path}")
    print(f"Failed downloads: {failed_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
