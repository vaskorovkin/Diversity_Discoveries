#!/usr/bin/env python3
"""Assign RESOLVE 2017 ecoregion/biome/realm to BOLD 100 km land cells.

This first-pass baseline geography uses cell centroids. It creates one
ecoregion, biome, and realm label per BOLD land cell.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.csv"
DEFAULT_ECOREGIONS = PROJECT_ROOT / "Data" / "raw" / "baseline_geography" / "resolve_ecoregions" / "Ecoregions2017.shp"
OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography"
DEFAULT_OUTPUT = OUTDIR / "resolve_ecoregions_100km_cells.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--ecoregions", type=Path, default=DEFAULT_ECOREGIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing land-cell file: {args.land_cells}")
    if not args.ecoregions.exists():
        raise FileNotFoundError(f"Missing RESOLVE shapefile: {args.ecoregions}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading land cells: {args.land_cells}", flush=True)
    cells = pd.read_csv(args.land_cells, dtype={"cell_id": str, "iso_a3": str})
    points = gpd.GeoDataFrame(
        cells,
        geometry=gpd.points_from_xy(cells["centroid_lon"], cells["centroid_lat"]),
        crs="EPSG:4326",
    )

    print(f"Reading RESOLVE ecoregions: {args.ecoregions}", flush=True)
    eco = gpd.read_file(args.ecoregions).to_crs("EPSG:4326")
    keep = [
        "ECO_ID",
        "ECO_NAME",
        "BIOME_NUM",
        "BIOME_NAME",
        "REALM",
        "ECO_BIOME_",
        "NNH",
        "NNH_NAME",
        "LICENSE",
        "geometry",
    ]
    eco = eco[[c for c in keep if c in eco.columns]].copy()

    print("Joining cell centroids to ecoregions.", flush=True)
    joined = gpd.sjoin(points, eco, how="left", predicate="within")
    out_cols = [
        "cell_id",
        "cell_x",
        "cell_y",
        "centroid_lon",
        "centroid_lat",
        "continent",
        "country",
        "iso_a3",
        "ECO_ID",
        "ECO_NAME",
        "BIOME_NUM",
        "BIOME_NAME",
        "REALM",
        "ECO_BIOME_",
        "NNH",
        "NNH_NAME",
        "LICENSE",
    ]
    out = pd.DataFrame(joined[[c for c in out_cols if c in joined.columns]].drop(columns=[], errors="ignore"))
    out = out.rename(
        columns={
            "ECO_ID": "resolve_eco_id",
            "ECO_NAME": "resolve_eco_name",
            "BIOME_NUM": "resolve_biome_num",
            "BIOME_NAME": "resolve_biome_name",
            "REALM": "resolve_realm",
            "ECO_BIOME_": "resolve_eco_biome",
            "NNH": "resolve_nnh",
            "NNH_NAME": "resolve_nnh_name",
            "LICENSE": "resolve_license",
        }
    )
    out["resolve_matched"] = out["resolve_eco_id"].notna().astype(int)
    out["resolve_rock_ice"] = (out["resolve_eco_name"] == "Rock and Ice").astype(int)
    rock_ice = out["resolve_rock_ice"] == 1
    for col in ["resolve_biome_name", "resolve_realm", "resolve_nnh_name"]:
        normalized = out[col].astype(str).str.strip()
        missing = out[col].isna() | normalized.eq("") | normalized.eq("N/A")
        out.loc[rock_ice & missing, col] = "Rock and Ice"
    out.to_csv(args.output, index=False)

    matched = out["resolve_eco_id"].notna().sum()
    print(f"Wrote: {args.output}", flush=True)
    print(f"Cells: {len(out):,}; matched to ecoregion: {matched:,}; unmatched: {len(out) - matched:,}", flush=True)
    print(f"Unique ecoregions in cells: {out['resolve_eco_id'].nunique(dropna=True):,}", flush=True)
    print(f"Unique biomes in cells: {out['resolve_biome_name'].nunique(dropna=True):,}", flush=True)
    print(f"Unique realms in cells: {out['resolve_realm'].nunique(dropna=True):,}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
