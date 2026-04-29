#!/usr/bin/env python3
"""Download selected smaller insect orders from BOLD, one file per order."""

from __future__ import annotations

import argparse
import csv
import json
import sys
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


ORDERS = [
    "Psocodea",
    "Orthoptera",
    "Trichoptera",
    "Thysanoptera",
    "Blattodea",
    "Ephemeroptera",
    "Neuroptera",
    "Odonata",
    "Plecoptera",
]


def slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("/", "_")


def summarize_order(order: str, outdir: Path, timeout: int) -> tuple[int, int, float]:
    query = f"tax:order:{order}"
    stem = f"bold_global_{slug(order)}"

    preprocessor = api_get_json(
        "/query/preprocessor",
        {"query": query},
        timeout=timeout,
    )
    write_json(outdir / f"{stem}_preprocessor.json", preprocessor)

    if preprocessor.get("failed_terms"):
        print(f"{order}: rejected by BOLD query preprocessor", file=sys.stderr)
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


def download_order(order: str, outdir: Path, fmt: str, timeout: int, force: bool) -> None:
    query = f"tax:order:{order}"
    stem = f"bold_global_{slug(order)}"
    output_path = outdir / f"{stem}_records.{fmt}"

    if output_path.exists() and not force:
        print(f"{order}: output exists, skipping: {output_path}")
        return

    query_payload = api_get_json(
        "/query",
        {"query": query, "extent": "full"},
        timeout=timeout,
    )
    write_json(outdir / f"{stem}_query.json", query_payload)

    query_id = query_payload.get("query_id")
    if not query_id:
        raise RuntimeError(f"{order}: no query_id returned: {json.dumps(query_payload)}")

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': fmt})}"
    )
    print(f"{order}: downloading to {output_path}")
    download_stream(download_url, output_path, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=PROJECT_ROOT / "Data" / "raw" / "bold" / "insect_orders_small",
    )
    parser.add_argument("--format", default="tsv", choices=["tsv", "json", "dwc"])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--orders", nargs="*", default=ORDERS)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    summary_csv = args.outdir / "bold_insect_orders_small_summary.csv"
    rows = []

    for order in args.orders:
        print(f"Summarizing {order}")
        n_records, n_coord, coord_share = summarize_order(order, args.outdir, args.timeout)
        print(f"{order}: {n_records:,} records; {n_coord:,} with coordinates ({coord_share:.1f}%)")
        rows.append(
            {
                "order": order,
                "records": n_records,
                "records_with_coordinates": n_coord,
                "coordinate_coverage_percent": f"{coord_share:.1f}",
            }
        )

        if n_records == 0 or args.summary_only:
            continue
        if n_records > MAX_RECORDS_PER_QUERY:
            print(
                f"{order}: exceeds {MAX_RECORDS_PER_QUERY:,}-record cap; split before downloading.",
                file=sys.stderr,
            )
            continue
        download_order(order, args.outdir, args.format, args.timeout, args.force)

    with summary_csv.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=[
                "order",
                "records",
                "records_with_coordinates",
                "coordinate_coverage_percent",
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
