#!/usr/bin/env python3
"""Build a zero-filled GBIF plant cell-year panel on the BOLD 100 km grid.

This script consumes the minimal GBIF preserved/material plant CSV and produces
cell-year counts using the same 100 km equal-area grid as the BOLD panel.

Main outputs:
    Data/processed/gbif/plantae/gbif_plantae_preserved_material_cell_year_panel_2005_2025.csv
    Data/processed/gbif/plantae/gbif_plantae_preserved_material_cell_year_panel_2005_2025_summary.csv
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline_utils import EQUAL_AREA_CRS, PROCESSED_BOLD, LAND_CELLS_CSV, ensure_output_dirs


INPUT_CSV = (
    PROCESSED_BOLD
    / ".."
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal.csv"
).resolve()
OUT_DIR = PROCESSED_BOLD / ".." / "gbif" / "plantae"

OUTCOME_COLUMNS = [
    "total_records",
    "plant_records",
    "preserved_specimen_records",
    "material_sample_records",
]


def default_output(start_year: int, end_year: int) -> Path:
    return OUT_DIR / f"gbif_plantae_preserved_material_cell_year_panel_{start_year}_{end_year}.csv"


def default_summary(output: Path) -> Path:
    return output.with_name(output.stem + "_summary.csv")


def load_land_cells(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing land-cell file: {path}. Run Scripts/05_cell_correlations.py first."
        )
    land = pd.read_csv(path, dtype={"cell_id": str, "iso_a3": str})
    required = {"cell_id", "cell_x", "cell_y", "centroid_lon", "centroid_lat", "continent", "country", "iso_a3"}
    missing = sorted(required - set(land.columns))
    if missing:
        raise ValueError(f"Land-cell file is missing columns: {missing}")
    return land


def build_zero_panel(land: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    years = np.arange(start_year, end_year + 1, dtype=int)
    panel = land.loc[land.index.repeat(len(years))].copy()
    panel["year"] = np.tile(years, len(land))
    country = panel["country"].fillna("")
    continent = panel["continent"].fillna("")
    panel["drop_rich_region_flag"] = (
        continent.isin(["Europe", "North America"]) | country.isin(["Australia", "New Zealand"])
    ).astype(int)
    return panel[
        [
            "cell_id",
            "cell_x",
            "cell_y",
            "year",
            "centroid_lon",
            "centroid_lat",
            "continent",
            "country",
            "iso_a3",
            "drop_rich_region_flag",
        ]
    ]


def aggregate_records(
    input_path: Path,
    land_cell_ids: set[str],
    start_year: int,
    end_year: int,
    chunksize: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    grouped_chunks: list[pd.DataFrame] = []
    stats = {
        "rows_scanned": 0,
        "coordinate_rows": 0,
        "coordinate_rows_in_year_window": 0,
        "coordinate_rows_in_land_cells": 0,
        "coordinate_rows_outside_land_cells": 0,
        "preserved_specimen_rows": 0,
        "material_sample_rows": 0,
    }
    started = time.time()

    print(f"Reading minimal GBIF plant file: {input_path}", flush=True)
    for chunk_index, chunk in enumerate(pd.read_csv(input_path, dtype=str, chunksize=chunksize), 1):
        stats["rows_scanned"] += len(chunk)
        coord_mask = chunk["has_coord"].fillna("") == "1"
        stats["coordinate_rows"] += int(coord_mask.sum())

        years = pd.to_numeric(chunk["year"], errors="coerce")
        year_mask = years.between(start_year, end_year)
        sub = chunk.loc[coord_mask & year_mask].copy()
        sub_years = years.loc[coord_mask & year_mask].astype(int).to_numpy()
        stats["coordinate_rows_in_year_window"] += len(sub)

        if sub.empty:
            print(f"  chunk {chunk_index}: {stats['rows_scanned']:,} rows scanned; no usable coordinates", flush=True)
            continue

        lat = pd.to_numeric(sub["latitude"], errors="coerce")
        lon = pd.to_numeric(sub["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        sub = sub.loc[valid].copy()
        sub_years = sub_years[valid.to_numpy()]
        if sub.empty:
            print(f"  chunk {chunk_index}: {stats['rows_scanned']:,} rows scanned; no valid coords", flush=True)
            continue

        lon = pd.to_numeric(sub["longitude"], errors="coerce").to_numpy()
        lat = pd.to_numeric(sub["latitude"], errors="coerce").to_numpy()
        x, y = transformer.transform(lon, lat)
        cell_x = np.floor(x / 100_000).astype(int)
        cell_y = np.floor(y / 100_000).astype(int)
        cell_ids = np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))

        work = pd.DataFrame(
            {
                "cell_id": cell_ids,
                "year": sub_years,
                "basis_of_record": sub["basis_of_record"].fillna("").to_numpy(),
                "kingdom": sub["kingdom"].fillna("").to_numpy(),
            }
        )
        in_land = work["cell_id"].isin(land_cell_ids)
        stats["coordinate_rows_in_land_cells"] += int(in_land.sum())
        stats["coordinate_rows_outside_land_cells"] += int((~in_land).sum())
        work = work.loc[in_land].copy()

        if work.empty:
            print(f"  chunk {chunk_index}: {stats['rows_scanned']:,} rows scanned; no land-cell matches", flush=True)
            continue

        work["total_records"] = 1
        work["plant_records"] = (work["kingdom"] == "Plantae").astype(int)
        work["preserved_specimen_records"] = (work["basis_of_record"] == "PRESERVED_SPECIMEN").astype(int)
        work["material_sample_records"] = (work["basis_of_record"] == "MATERIAL_SAMPLE").astype(int)

        stats["preserved_specimen_rows"] += int(work["preserved_specimen_records"].sum())
        stats["material_sample_rows"] += int(work["material_sample_records"].sum())

        grouped_chunks.append(work.groupby(["cell_id", "year"], as_index=False)[OUTCOME_COLUMNS].sum())

        elapsed = max(time.time() - started, 1)
        print(
            f"  chunk {chunk_index}: {stats['rows_scanned']:,} rows scanned; "
            f"{stats['coordinate_rows_in_land_cells']:,} in land cells "
            f"({stats['rows_scanned'] / elapsed:,.0f} rows/sec)",
            flush=True,
        )

    if not grouped_chunks:
        empty = pd.DataFrame(columns=["cell_id", "year"] + OUTCOME_COLUMNS)
        return empty, stats

    counts = pd.concat(grouped_chunks, ignore_index=True)
    counts = counts.groupby(["cell_id", "year"], as_index=False)[OUTCOME_COLUMNS].sum()
    return counts, stats


def add_outcome_transforms(panel: pd.DataFrame) -> pd.DataFrame:
    for col in OUTCOME_COLUMNS:
        panel[col] = panel[col].fillna(0).astype(int)
        panel[f"any_{col}"] = (panel[col] > 0).astype(int)
        panel[f"log1p_{col}"] = np.log1p(panel[col])
    return panel


def write_summary(path: Path, panel: pd.DataFrame, stats: dict[str, int], start_year: int, end_year: int) -> None:
    rows = [
        ("start_year", start_year),
        ("end_year", end_year),
        ("land_cells", panel["cell_id"].nunique()),
        ("panel_rows", len(panel)),
    ]
    rows.extend(stats.items())
    for col in OUTCOME_COLUMNS:
        rows.append((col, int(panel[col].sum())))
        rows.append((f"cell_years_with_{col}", int((panel[col] > 0).sum())))
    pd.DataFrame(rows, columns=["metric", "value"]).to_csv(path, index=False)
    print(f"Wrote summary: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--chunksize", type=int, default=250_000)
    args = parser.parse_args()

    ensure_output_dirs()
    land = load_land_cells(args.land_cells)
    output = args.output or default_output(args.start_year, args.end_year)
    summary = args.summary or default_summary(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)

    panel = build_zero_panel(land, args.start_year, args.end_year)
    print(f"Zero-filled panel rows: {len(panel):,}", flush=True)
    land_cell_ids = set(panel["cell_id"].astype(str))

    counts, stats = aggregate_records(
        input_path=args.input,
        land_cell_ids=land_cell_ids,
        start_year=args.start_year,
        end_year=args.end_year,
        chunksize=args.chunksize,
    )
    panel = panel.merge(counts, on=["cell_id", "year"], how="left")
    panel = add_outcome_transforms(panel)
    panel.to_csv(output, index=False)
    print(f"Wrote panel: {output}", flush=True)
    write_summary(summary, panel, stats, args.start_year, args.end_year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
