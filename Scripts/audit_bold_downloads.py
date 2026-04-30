#!/usr/bin/env python3
"""Audit downloaded BOLD TSV files against their BOLD summary JSON files."""

from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
RAW_BOLD = PROJECT_ROOT / "Data" / "raw" / "bold"
OUTDIR = PROJECT_ROOT / "Output" / "audits"


def count_lines(path: Path) -> int:
    with path.open("rb") as f:
        return sum(1 for _ in f)


def header_fields(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        header = f.readline().rstrip("\n")
    return len(header.split("\t")) if header else 0


def first_last_ids(path: Path) -> tuple[str, str]:
    first = ""
    last = ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        header = f.readline()
        for line_no, line in enumerate(f, start=2):
            value = line.split("\t", 1)[0].strip()
            if not first:
                first = value
            last = value
    return first, last


def load_summary(path: Path) -> tuple[int | None, int | None]:
    if not path.exists():
        return None, None
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    counts = payload.get("counts") or {}
    specimens = counts.get("specimens")
    coords = payload.get("coord") or {}
    coord_records = sum(int(v) for v in coords.values()) if coords else 0
    return int(specimens) if specimens is not None else None, coord_records


def status_for(data_rows: int, specimens: int | None) -> str:
    if specimens is None:
        return "NO_SUMMARY"
    if data_rows == 1_000_000 and specimens > data_rows:
        return "CAPPED_AT_1M"
    if data_rows < specimens:
        return "ROWS_LT_SPECIMENS"
    return "OK_ROWS_GE_SPECIMENS"


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows = []

    part_files = sorted(RAW_BOLD.rglob("*_records.tsv.part"))
    for path in sorted(RAW_BOLD.rglob("*_records.tsv")):
        summary_path = path.with_name(path.name.replace("_records.tsv", "_summary.json"))
        total_lines = count_lines(path)
        data_rows = max(total_lines - 1, 0)
        specimens, coord_records = load_summary(summary_path)
        size_mb = path.stat().st_size / (1024 * 1024)
        first_id, last_id = first_last_ids(path)
        rows.append(
            {
                "relative_path": str(path.relative_to(PROJECT_ROOT)),
                "size_mb": f"{size_mb:.1f}",
                "total_lines": total_lines,
                "data_rows": data_rows,
                "summary_specimens": "" if specimens is None else specimens,
                "summary_coord_records": "" if coord_records is None else coord_records,
                "data_rows_minus_specimens": "" if specimens is None else data_rows - specimens,
                "header_fields": header_fields(path),
                "first_processid": first_id,
                "last_processid": last_id,
                "status": status_for(data_rows, specimens),
            }
        )

    output = OUTDIR / "bold_download_audit.csv"
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Audited files: {len(rows)}")
    print(f"Partial .part files: {len(part_files)}")
    for part in part_files:
        print(f"PARTIAL\t{part.relative_to(PROJECT_ROOT)}")
    print(f"Wrote: {output}")

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")

    print("\nSuspicious rows:")
    for row in rows:
        if row["status"] != "OK_ROWS_GE_SPECIMENS":
            print(
                f"{row['status']}\t{row['relative_path']}\t"
                f"rows={row['data_rows']}\tspecimens={row['summary_specimens']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
