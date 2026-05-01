#!/usr/bin/env python3
"""Build a zero-filled BOLD cell-year panel for Stata regressions.

The main panel uses BOLD sequence upload year, 2005-2025 by default. It bins
coordinate records to the same 100 km equal-area cells used by the map and
correlation scripts, then expands to all land cells x years with zeros.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from exhibit_utils import (
    EQUAL_AREA_CRS,
    EXHIBIT_DATA,
    LAND_CELLS_CSV,
    MINIMAL_CSV,
    ensure_exhibit_dirs,
)


OUTCOME_COLUMNS = [
    "total_records",
    "animalia_records",
    "plantae_records",
    "fungi_records",
    "bacteria_records",
    "plantae_fungi_records",
    "non_chordata_animalia_records",
    "arthropoda_records",
    "insecta_records",
    "chordata_records",
]


INPUT_COLUMNS = [
    "kingdom",
    "phylum",
    "class_name",
    "has_coord",
    "latitude",
    "longitude",
    "sequence_upload_year",
]


def cell_label(cell_km: float) -> str:
    return f"{cell_km:g}".replace(".", "p")


def default_output(cell_km: float, start_year: int, end_year: int) -> Path:
    return EXHIBIT_DATA / f"bold_grid{cell_label(cell_km)}_cell_year_panel_upload_{start_year}_{end_year}.csv"


def default_summary(output: Path) -> Path:
    return output.with_name(output.stem + "_summary.csv")


def load_land_cells(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing land-cell file: {path}. Run Scripts/exhibits/05_cell_correlations.py first."
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
    cell_km: float,
    chunksize: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    cell_m = cell_km * 1000
    grouped_chunks: list[pd.DataFrame] = []
    stats = {
        "rows_scanned": 0,
        "coordinate_rows": 0,
        "coordinate_rows_in_year_window": 0,
        "coordinate_rows_in_land_cells": 0,
        "coordinate_rows_outside_land_cells": 0,
    }
    started = time.time()

    print(f"Reading minimal records: {input_path}", flush=True)
    for chunk_index, chunk in enumerate(pd.read_csv(input_path, dtype=str, usecols=INPUT_COLUMNS, chunksize=chunksize), 1):
        stats["rows_scanned"] += len(chunk)
        coord_mask = chunk["has_coord"].fillna("") == "1"
        stats["coordinate_rows"] += int(coord_mask.sum())

        years = pd.to_numeric(chunk["sequence_upload_year"], errors="coerce")
        year_mask = years.between(start_year, end_year)
        sub = chunk.loc[coord_mask & year_mask].copy()
        sub_years = years.loc[coord_mask & year_mask].astype(int).to_numpy()
        stats["coordinate_rows_in_year_window"] += len(sub)

        if not sub.empty:
            lat = pd.to_numeric(sub["latitude"], errors="coerce")
            lon = pd.to_numeric(sub["longitude"], errors="coerce")
            valid = lat.between(-90, 90) & lon.between(-180, 180)
            sub = sub.loc[valid].copy()
            sub_years = sub_years[valid.to_numpy()]

        if not sub.empty:
            lon = pd.to_numeric(sub["longitude"], errors="coerce").to_numpy()
            lat = pd.to_numeric(sub["latitude"], errors="coerce").to_numpy()
            x, y = transformer.transform(lon, lat)
            cell_x = np.floor(x / cell_m).astype(int)
            cell_y = np.floor(y / cell_m).astype(int)
            cell_ids = np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))

            work = pd.DataFrame(
                {
                    "cell_id": cell_ids,
                    "year": sub_years,
                    "kingdom": sub["kingdom"].fillna("").to_numpy(),
                    "phylum": sub["phylum"].fillna("").to_numpy(),
                    "class_name": sub["class_name"].fillna("").to_numpy(),
                }
            )
            in_land = work["cell_id"].isin(land_cell_ids)
            stats["coordinate_rows_in_land_cells"] += int(in_land.sum())
            stats["coordinate_rows_outside_land_cells"] += int((~in_land).sum())
            work = work.loc[in_land].copy()

            if not work.empty:
                kingdom = work["kingdom"]
                phylum = work["phylum"]
                class_name = work["class_name"]
                work["total_records"] = 1
                work["animalia_records"] = (kingdom == "Animalia").astype(int)
                work["plantae_records"] = (kingdom == "Plantae").astype(int)
                work["fungi_records"] = (kingdom == "Fungi").astype(int)
                work["bacteria_records"] = (kingdom == "Bacteria").astype(int)
                work["plantae_fungi_records"] = kingdom.isin(["Plantae", "Fungi"]).astype(int)
                work["non_chordata_animalia_records"] = ((kingdom == "Animalia") & (phylum != "Chordata")).astype(int)
                work["arthropoda_records"] = (phylum == "Arthropoda").astype(int)
                work["insecta_records"] = (class_name == "Insecta").astype(int)
                work["chordata_records"] = (phylum == "Chordata").astype(int)
                grouped_chunks.append(work.groupby(["cell_id", "year"], as_index=False)[OUTCOME_COLUMNS].sum())

        elapsed = max(time.time() - started, 1)
        print(
            f"chunk {chunk_index:,}: {stats['rows_scanned']:,} rows scanned; "
            f"{stats['coordinate_rows_in_land_cells']:,} coordinate rows in land cells "
            f"({stats['rows_scanned'] / elapsed:,.0f} rows/sec)",
            flush=True,
        )

    if not grouped_chunks:
        return pd.DataFrame(columns=["cell_id", "year"] + OUTCOME_COLUMNS), stats

    counts = pd.concat(grouped_chunks, ignore_index=True)
    counts = counts.groupby(["cell_id", "year"], as_index=False)[OUTCOME_COLUMNS].sum()
    return counts, stats


def add_outcome_transforms(panel: pd.DataFrame) -> pd.DataFrame:
    for col in OUTCOME_COLUMNS:
        panel[col] = panel[col].fillna(0).astype(int)
        stem = col.removesuffix("_records")
        panel[f"any_{stem}"] = (panel[col] > 0).astype(int)
        panel[f"log1p_{stem}"] = np.log1p(panel[col])
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
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--cell-km", type=float, default=100)
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--chunksize", type=int, default=500_000)
    args = parser.parse_args()

    ensure_exhibit_dirs()
    output = args.output or default_output(args.cell_km, args.start_year, args.end_year)
    summary = args.summary or default_summary(output)

    print(f"Panel years: {args.start_year}-{args.end_year}", flush=True)
    land = load_land_cells(args.land_cells)
    print(f"Land cells: {len(land):,}", flush=True)
    panel = build_zero_panel(land, args.start_year, args.end_year)
    print(f"Zero-filled panel rows: {len(panel):,}", flush=True)

    counts, stats = aggregate_records(
        args.input,
        set(land["cell_id"]),
        args.start_year,
        args.end_year,
        args.cell_km,
        args.chunksize,
    )
    print(f"Nonzero cell-year rows from records: {len(counts):,}", flush=True)

    panel = panel.merge(counts, on=["cell_id", "year"], how="left")
    panel = add_outcome_transforms(panel)
    panel.to_csv(output, index=False)
    print(f"Wrote panel: {output}", flush=True)
    write_summary(summary, panel, stats, args.start_year, args.end_year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
