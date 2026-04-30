#!/usr/bin/env python3
"""Summarize top countries for oversized Diptera families from BOLD summaries.

This uses BOLD summary metadata only; it does not download specimen records.
The output helps decide how to split the four over-cap Diptera families into
country-level requests.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from download_bold_fungi import PROJECT_ROOT, SUMMARY_FIELDS, api_get_json, write_json


FAMILIES = ["Cecidomyiidae", "Chironomidae", "Phoridae", "Sciaridae"]
TOP_N = 5
OUTDIR = PROJECT_ROOT / "Data" / "raw" / "bold" / "diptera_by_family"
AUDIT_DIR = PROJECT_ROOT / "Output" / "audits"


def slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("/", "_")


def summary_path(family: str) -> Path:
    return OUTDIR / f"bold_global_diptera_family_{slug(family)}_oversized_summary.json"


def get_summary(family: str, timeout: int, refresh: bool) -> dict:
    path = summary_path(family)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    query = f"tax:family:{family}"
    preprocessor = api_get_json("/query/preprocessor", {"query": query}, timeout=timeout)
    failed_terms = preprocessor.get("failed_terms") or []
    if failed_terms:
        raise RuntimeError(f"BOLD rejected {family}: {json.dumps(failed_terms)}")

    summary = api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )
    write_json(path, summary)
    return summary


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--top", type=int, default=TOP_N)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for family in FAMILIES:
        summary = get_summary(family, args.timeout, args.refresh)
        n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
        country_counts = summary.get("country/ocean", {}) or {}
        top_countries = sorted(country_counts.items(), key=lambda kv: int(kv[1]), reverse=True)[
            : args.top
        ]
        print(f"{family}: {n_records:,} records")
        for rank, (country, count) in enumerate(top_countries, 1):
            share = 100 * int(count) / n_records if n_records else 0
            print(f"  {rank}. {country}: {int(count):,} ({share:.1f}%)")
            rows.append(
                {
                    "family": family,
                    "rank": rank,
                    "country_or_ocean": country,
                    "records": int(count),
                    "family_records": n_records,
                    "share_percent": f"{share:.2f}",
                }
            )

    csv_path = AUDIT_DIR / "bold_diptera_oversized_family_top_countries.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "family",
                "rank",
                "country_or_ocean",
                "records",
                "family_records",
                "share_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    md_path = AUDIT_DIR / "bold_diptera_oversized_family_top_countries.md"
    lines = [
        "# Top BOLD countries for oversized Diptera families",
        "",
        "BOLD summary metadata only; no specimen records downloaded by this script.",
        "",
        "| Family | Rank | Country/ocean | Records | Share |",
        "|---|---:|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['family']} | {row['rank']} | {row['country_or_ocean']} | "
            f"{int(row['records']):,} | {row['share_percent']}% |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"CSV: {csv_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
