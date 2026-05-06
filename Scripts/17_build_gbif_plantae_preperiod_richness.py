#!/usr/bin/env python3
"""Build a baseline GBIF plant richness moderator from the pre-period archive.

This script streams a GBIF preserved/material plant occurrence table, assigns
records to the BOLD 100 km equal-area land-cell grid, and counts distinct plant
species and genera per cell over a fixed pre-period.

Default input:
    Data/raw/gbif/plantae/0011961-260430073515954/occurrence.txt

Default output:
    Data/regressors/plants/gbif_plantae_preperiod_richness_1999_2004.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline_utils import EQUAL_AREA_CRS, LAND_CELLS_CSV


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_INPUT = PROJECT_ROOT / "Data" / "raw" / "gbif" / "plantae" / "0011961-260430073515954" / "occurrence.txt"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "plants" / "gbif_plantae_preperiod_richness_1999_2004.csv"
DEFAULT_SUMMARY = PROJECT_ROOT / "Data" / "regressors" / "plants" / "gbif_plantae_preperiod_richness_1999_2004_summary.csv"


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def parse_year(value: str) -> int | None:
    value = clean(value)
    if len(value) >= 4 and value[:4].isdigit():
        year = int(value[:4])
        if 1800 <= year <= 2100:
            return year
    return None


def parse_coord(lat: str, lon: str) -> tuple[float | None, float | None]:
    lat = clean(lat)
    lon = clean(lon)
    if not lat or not lon:
        return None, None
    try:
        f_lat = float(lat)
        f_lon = float(lon)
    except ValueError:
        return None, None
    if not (-90 <= f_lat <= 90 and -180 <= f_lon <= 180):
        return None, None
    return f_lat, f_lon


def species_token(accepted: str, species: str, scientific: str) -> str:
    for value in (accepted, species, scientific):
        value = clean(value)
        if value:
            return value
    return ""


def zscore(series: pd.Series) -> pd.Series:
    mean = series.mean()
    sd = series.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - mean) / sd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--start-year", type=int, default=1999)
    parser.add_argument("--end-year", type=int, default=2004)
    parser.add_argument("--progress-every", type=int, default=200_000)
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Missing GBIF occurrence file: {args.input}")
    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing land-cell file: {args.land_cells}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    land = pd.read_csv(args.land_cells, dtype={"cell_id": str})
    if "cell_id" not in land.columns:
        raise ValueError(f"Land-cell file missing cell_id: {args.land_cells}")
    land_ids = set(land["cell_id"])

    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)

    csv.field_size_limit(100_000_000)

    stats = {
        "rows_scanned": 0,
        "rows_in_year_window": 0,
        "rows_with_valid_coords": 0,
        "rows_in_land_cells": 0,
        "rows_outside_land_cells": 0,
        "rows_with_species_token": 0,
        "rows_with_genus": 0,
    }

    species_sets: dict[str, set[str]] = {}
    genus_sets: dict[str, set[str]] = {}

    with args.input.open(newline="", encoding="utf-8", errors="replace") as src:
        reader = csv.reader(src, delimiter="\t")
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        required = {
            "year",
            "eventDate",
            "decimalLatitude",
            "decimalLongitude",
            "acceptedScientificName",
            "species",
            "scientificName",
            "genus",
        }
        missing = sorted(required - set(idx))
        if missing:
            raise ValueError(f"Missing expected columns: {missing}")

        for row_num, row in enumerate(reader, 1):
            stats["rows_scanned"] += 1
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))

            year = parse_year(row[idx["year"]])
            if year is None:
                year = parse_year(row[idx["eventDate"]])
            if year is None or year < args.start_year or year > args.end_year:
                continue
            stats["rows_in_year_window"] += 1

            lat, lon = parse_coord(row[idx["decimalLatitude"]], row[idx["decimalLongitude"]])
            if lat is None or lon is None:
                continue
            stats["rows_with_valid_coords"] += 1

            x, y = transformer.transform(lon, lat)
            cell_x = math.floor(x / 100_000)
            cell_y = math.floor(y / 100_000)
            cell_id = f"{cell_x}_{cell_y}"
            if cell_id not in land_ids:
                stats["rows_outside_land_cells"] += 1
                continue
            stats["rows_in_land_cells"] += 1

            sp = species_token(
                row[idx["acceptedScientificName"]],
                row[idx["species"]],
                row[idx["scientificName"]],
            )
            genus = clean(row[idx["genus"]])

            if sp:
                species_sets.setdefault(cell_id, set()).add(sp)
                stats["rows_with_species_token"] += 1
            if genus:
                genus_sets.setdefault(cell_id, set()).add(genus)
                stats["rows_with_genus"] += 1

            if row_num % args.progress_every == 0:
                print(
                    f"  rows {row_num:,}: in_window={stats['rows_in_year_window']:,}, "
                    f"in_land_cells={stats['rows_in_land_cells']:,}, "
                    f"species_cells={len(species_sets):,}",
                    flush=True,
                )

    out = land[["cell_id"]].copy()
    out["gbif_plant_richness_base"] = out["cell_id"].map(lambda c: len(species_sets.get(c, set()))).astype(int)
    out["gbif_plant_genus_richness_base"] = out["cell_id"].map(lambda c: len(genus_sets.get(c, set()))).astype(int)
    out["gbif_plant_richness_base_any"] = (out["gbif_plant_richness_base"] > 0).astype(int)
    out["gbif_plant_genus_richness_base_any"] = (out["gbif_plant_genus_richness_base"] > 0).astype(int)
    out["gbif_plant_richness_base_log1p"] = np.log1p(out["gbif_plant_richness_base"])
    out["gbif_plant_genus_richness_base_log1p"] = np.log1p(out["gbif_plant_genus_richness_base"])
    out["gbif_plant_richness_base_z"] = zscore(out["gbif_plant_richness_base"].astype(float))
    out["gbif_plant_genus_richness_base_z"] = zscore(out["gbif_plant_genus_richness_base"].astype(float))

    out.to_csv(args.output, index=False)

    summary_rows = [
        ("start_year", args.start_year),
        ("end_year", args.end_year),
        ("rows_scanned", stats["rows_scanned"]),
        ("rows_in_year_window", stats["rows_in_year_window"]),
        ("rows_with_valid_coords", stats["rows_with_valid_coords"]),
        ("rows_in_land_cells", stats["rows_in_land_cells"]),
        ("rows_outside_land_cells", stats["rows_outside_land_cells"]),
        ("rows_with_species_token", stats["rows_with_species_token"]),
        ("rows_with_genus", stats["rows_with_genus"]),
        ("cells_total", len(out)),
        ("cells_with_species_richness", int((out["gbif_plant_richness_base"] > 0).sum())),
        ("cells_with_genus_richness", int((out["gbif_plant_genus_richness_base"] > 0).sum())),
        ("species_richness_mean", float(out["gbif_plant_richness_base"].mean())),
        ("species_richness_median", float(out["gbif_plant_richness_base"].median())),
        ("species_richness_max", int(out["gbif_plant_richness_base"].max())),
        ("genus_richness_mean", float(out["gbif_plant_genus_richness_base"].mean())),
        ("genus_richness_median", float(out["gbif_plant_genus_richness_base"].median())),
        ("genus_richness_max", int(out["gbif_plant_genus_richness_base"].max())),
    ]
    pd.DataFrame(summary_rows, columns=["metric", "value"]).to_csv(args.summary, index=False)

    print(f"Wrote GBIF pre-period richness: {args.output}", flush=True)
    print(f"Wrote summary: {args.summary}", flush=True)
    print(f"Rows scanned: {stats['rows_scanned']:,}", flush=True)
    print(f"Rows in year window: {stats['rows_in_year_window']:,}", flush=True)
    print(f"Rows in land cells: {stats['rows_in_land_cells']:,}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
