#!/usr/bin/env python3
"""Shared helpers and path constants for BOLD data pipeline scripts."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
BOLD_RAW = PROJECT_ROOT / "Data" / "raw" / "bold"
PROCESSED_BOLD = PROJECT_ROOT / "Data" / "processed" / "bold"
EXHIBITS = PROJECT_ROOT / "Exhibits"
EXHIBIT_TABLES = EXHIBITS / "tables"
EXHIBIT_FIGURES = EXHIBITS / "figures"
EXHIBIT_MAPS = EXHIBITS / "maps"
MINIMAL_CSV = PROCESSED_BOLD / "bold_minimal_records.csv"
GRID_COUNTS_CSV = PROCESSED_BOLD / "bold_grid100_counts_by_kingdom.csv"
LAND_CELLS_CSV = PROCESSED_BOLD / "bold_grid100_land_cells.csv"
EQUAL_AREA_CRS = "EPSG:6933"

MINIMAL_FIELDS = [
    "source_file",
    "source_group",
    "processid",
    "record_id",
    "kingdom",
    "phylum",
    "class_name",
    "order",
    "family",
    "genus",
    "species",
    "country_ocean",
    "country_iso",
    "province_state",
    "region",
    "sector",
    "site",
    "latitude",
    "longitude",
    "has_coord",
    "collection_year",
    "sequence_upload_year",
    "bin_uri",
    "bin_created_date",
    "inst",
    "collection_code",
    "collectors",
    "identified_by",
    "sequence_run_site",
    "funding_src",
]


def ensure_output_dirs() -> None:
    for path in [PROCESSED_BOLD, EXHIBIT_TABLES, EXHIBIT_FIGURES, EXHIBIT_MAPS]:
        path.mkdir(parents=True, exist_ok=True)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def first_present(row: dict, fields: list[str]) -> str:
    for field in fields:
        value = clean(row.get(field))
        if value:
            return value
    return ""


def parse_year(value: str) -> str:
    value = clean(value)
    if len(value) >= 4 and value[:4].isdigit():
        year = int(value[:4])
        if 1800 <= year <= 2100:
            return str(year)
    return ""


def parse_coord(value: str) -> tuple[str, str, str]:
    value = clean(value)
    if not value:
        return "", "", "0"
    nums = re.findall(r"-?\d+(?:\.\d+)?", value)
    if len(nums) < 2:
        return "", "", "0"
    lat = float(nums[0])
    lon = float(nums[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return "", "", "0"
    return f"{lat:.8g}", f"{lon:.8g}", "1"


def source_group(path: Path) -> str:
    rel = path.relative_to(BOLD_RAW)
    if len(rel.parts) == 1:
        return "bold_root"
    return rel.parts[0]


def should_include_source(path: Path, include_cecidomyiidae_costa_rica_capped: bool) -> bool:
    name = path.name
    text = str(path.relative_to(BOLD_RAW))
    if not name.endswith("_records.tsv"):
        return False
    if text.startswith("diptera_cecidomyiidae_costa_rica_capped/"):
        return True
    if text.startswith("diagnostic_capped_redundant/"):
        return False
    if text.startswith("bold_trochilidae_"):
        return False
    if text == "bold_global_hemiptera_records.tsv":
        return False
    if "cecidomyiidae_capped_records.tsv" in text:
        return False
    return True


def discover_bold_sources(include_cecidomyiidae_costa_rica_capped: bool = False) -> list[Path]:
    files = sorted(BOLD_RAW.rglob("*_records.tsv"))
    return [path for path in files if should_include_source(path, include_cecidomyiidae_costa_rica_capped)]


def iter_minimal_chunks(path: Path = MINIMAL_CSV, chunksize: int = 500_000):
    import pandas as pd

    return pd.read_csv(path, dtype=str, chunksize=chunksize)


def write_simple_latex_table(csv_path: Path, tex_path: Path, caption: str, label: str) -> None:
    rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8")))
    if not rows:
        tex_path.write_text("% Empty table\n", encoding="utf-8")
        return
    fields = rows[0].keys()
    lines = [
        "\\begin{table}[!htbp]",
        "\\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\begin{tabular}{" + "l" * len(list(fields)) + "}",
        "\\hline",
        " & ".join(field.replace("_", "\\_") for field in fields) + " \\\\",
        "\\hline",
    ]
    for row in rows:
        lines.append(" & ".join(clean(row[field]).replace("_", "\\_") for field in fields) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}", "\\end{table}", ""])
    tex_path.write_text("\n".join(lines), encoding="utf-8")


def lognorm_or_none(max_count: int):
    from matplotlib.colors import LogNorm

    if max_count <= 0:
        return None
    return LogNorm(vmin=1, vmax=max_count)


def finite_float(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(out):
        return out
    return None
