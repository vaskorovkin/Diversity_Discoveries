#!/usr/bin/env python3
"""Audit the two capped Cecidomyiidae BOLD downloads.

The script streams the global capped family extract and the Costa Rica capped
extract. It reports candidate split fields and how much the two files overlap
by BOLD record identifiers.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from download_bold_fungi import PROJECT_ROOT


GLOBAL_FILE = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "bold"
    / "diptera_by_family"
    / "bold_global_diptera_family_cecidomyiidae_capped_records.tsv"
)
COSTA_RICA_FILE = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "bold"
    / "diptera_cecidomyiidae_costa_rica"
    / "bold_cecidomyiidae_costa_rica_capped_records.tsv"
)
OUTDIR = PROJECT_ROOT / "Output" / "audits"

CANDIDATE_FIELDS = [
    "country/ocean",
    "country_iso",
    "province/state",
    "region",
    "sector",
    "site",
    "site_code",
    "coord",
    "coord_accuracy",
    "coord_source",
    "elev",
    "depth",
    "collection_date_start",
    "collection_date_end",
    "collection_date_accuracy",
    "collection_event_id",
    "collection_code",
    "inst",
    "sovereign_inst",
    "collectors",
    "sequence_run_site",
    "sequence_upload_date",
    "bold_recordset_code_arr",
    "marker_code",
    "bin_uri",
    "taxid",
    "genus",
    "species",
    "identification",
    "funding_src",
    "sampling_protocol",
    "habitat",
    "biome",
    "ecoregion",
    "realm",
]


def value(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def record_key(row: dict[str, str]) -> str:
    for field in ("record_id", "processid", "sampleid"):
        v = value(row, field)
        if v:
            return f"{field}:{v}"
    payload = "\t".join(value(row, field) for field in sorted(row))
    return "hash:" + hashlib.md5(payload.encode("utf-8", errors="replace")).hexdigest()


def year_from_date(date_value: str) -> str:
    date_value = date_value.strip()
    if len(date_value) >= 4 and date_value[:4].isdigit():
        return date_value[:4]
    return ""


def audit_file(path: Path, label: str, collect_keys: bool = False) -> tuple[dict, set[str]]:
    stats = {
        "label": label,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "rows": 0,
        "costa_rica_rows": 0,
        "unique_keys": 0,
        "fields": {},
        "top_values": defaultdict(Counter),
        "year_counts": Counter(),
    }
    keys: set[str] = set()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = reader.fieldnames or []
        tracked_fields = [field for field in CANDIDATE_FIELDS if field in fields]
        for row in reader:
            stats["rows"] += 1
            key = record_key(row)
            if collect_keys:
                keys.add(key)
            if value(row, "country/ocean") == "Costa Rica":
                stats["costa_rica_rows"] += 1
            for field in tracked_fields:
                v = value(row, field)
                if v:
                    field_stats = stats["fields"].setdefault(
                        field,
                        {
                            "nonmissing": 0,
                            "unique_values": set(),
                        },
                    )
                    field_stats["nonmissing"] += 1
                    field_stats["unique_values"].add(v)
                    stats["top_values"][field][v] += 1
            year = year_from_date(value(row, "collection_date_start"))
            if year:
                stats["year_counts"][year] += 1
    if collect_keys:
        stats["unique_keys"] = len(keys)
    for field_stats in stats["fields"].values():
        field_stats["unique_count"] = len(field_stats["unique_values"])
        del field_stats["unique_values"]
    return stats, keys


def write_field_summary(path: Path, stats_list: list[dict]) -> None:
    fields = [
        "file",
        "field",
        "rows",
        "nonmissing",
        "nonmissing_share",
        "unique_count",
        "top1",
        "top1_count",
        "top2",
        "top2_count",
        "top3",
        "top3_count",
        "max_bucket_share",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for stats in stats_list:
            rows = int(stats["rows"])
            for field in CANDIDATE_FIELDS:
                if field not in stats["fields"]:
                    continue
                fstats = stats["fields"][field]
                top = stats["top_values"][field].most_common(3)
                row = {
                    "file": stats["label"],
                    "field": field,
                    "rows": rows,
                    "nonmissing": fstats["nonmissing"],
                    "nonmissing_share": f"{100 * fstats['nonmissing'] / rows:.2f}",
                    "unique_count": fstats["unique_count"],
                    "top1": top[0][0] if len(top) > 0 else "",
                    "top1_count": top[0][1] if len(top) > 0 else "",
                    "top2": top[1][0] if len(top) > 1 else "",
                    "top2_count": top[1][1] if len(top) > 1 else "",
                    "top3": top[2][0] if len(top) > 2 else "",
                    "top3_count": top[2][1] if len(top) > 2 else "",
                    "max_bucket_share": f"{100 * top[0][1] / rows:.2f}" if top else "",
                }
                writer.writerow(row)


def write_year_counts(path: Path, stats_list: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "year", "records"])
        writer.writeheader()
        for stats in stats_list:
            for year, count in sorted(stats["year_counts"].items()):
                writer.writerow({"file": stats["label"], "year": year, "records": count})


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    global_stats, global_keys = audit_file(GLOBAL_FILE, "global_capped", collect_keys=True)
    cr_stats, cr_keys = audit_file(COSTA_RICA_FILE, "costa_rica_capped", collect_keys=True)
    overlap = len(global_keys & cr_keys)
    union = len(global_keys | cr_keys)

    field_summary = OUTDIR / "bold_cecidomyiidae_capped_file_field_audit.csv"
    year_summary = OUTDIR / "bold_cecidomyiidae_capped_file_year_counts.csv"
    md_path = OUTDIR / "bold_cecidomyiidae_capped_file_audit.md"
    write_field_summary(field_summary, [global_stats, cr_stats])
    write_year_counts(year_summary, [global_stats, cr_stats])

    lines = [
        "# Cecidomyiidae capped file audit",
        "",
        "| File | Rows | Costa Rica rows | Unique keys |",
        "|---|---:|---:|---:|",
        f"| global_capped | {global_stats['rows']:,} | {global_stats['costa_rica_rows']:,} | {global_stats['unique_keys']:,} |",
        f"| costa_rica_capped | {cr_stats['rows']:,} | {cr_stats['costa_rica_rows']:,} | {cr_stats['unique_keys']:,} |",
        "",
        f"Overlap by record/process/sample key: {overlap:,}",
        f"Union by record/process/sample key: {union:,}",
        "",
        "Full field summary:",
        f"`{field_summary.relative_to(PROJECT_ROOT)}`",
        "",
        "Year counts:",
        f"`{year_summary.relative_to(PROJECT_ROOT)}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"global rows: {global_stats['rows']:,}")
    print(f"global Costa Rica rows: {global_stats['costa_rica_rows']:,}")
    print(f"Costa Rica capped rows: {cr_stats['rows']:,}")
    print(f"overlap keys: {overlap:,}")
    print(f"union keys: {union:,}")
    print(f"field summary: {field_summary}")
    print(f"year counts: {year_summary}")
    print(f"markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
