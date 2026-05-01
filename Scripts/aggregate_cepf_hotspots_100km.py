#!/usr/bin/env python3
"""Assign CEPF biodiversity hotspot indicators to BOLD 100 km land cells.

The input hotspot polygons are the CEPF/Conservation International terrestrial
biodiversity hotspots. This script uses cell centroids and returns one row per
BOLD land cell with an any-hotspot indicator and hotspot name(s).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.csv"
DEFAULT_HOTSPOTS = PROJECT_ROOT / "Data" / "raw" / "baseline_geography" / "cepf_hotspots.geojson"
OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography"
DEFAULT_OUTPUT = OUTDIR / "cepf_hotspots_100km_cells.csv"


def join_unique(values: pd.Series) -> str:
    clean = sorted({str(v).strip() for v in values.dropna() if str(v).strip()})
    return " | ".join(clean)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--hotspots", type=Path, default=DEFAULT_HOTSPOTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing land-cell file: {args.land_cells}")
    if not args.hotspots.exists():
        raise FileNotFoundError(f"Missing hotspot file: {args.hotspots}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading land cells: {args.land_cells}", flush=True)
    cells = pd.read_csv(args.land_cells, dtype={"cell_id": str, "iso_a3": str})
    points = gpd.GeoDataFrame(
        cells,
        geometry=gpd.points_from_xy(cells["centroid_lon"], cells["centroid_lat"]),
        crs="EPSG:4326",
    )

    print(f"Reading CEPF hotspots: {args.hotspots}", flush=True)
    hotspots = gpd.read_file(args.hotspots).to_crs("EPSG:4326")
    name_col = "NAME" if "NAME" in hotspots.columns else "Name"
    hotspots = hotspots[[name_col, "geometry"]].rename(columns={name_col: "cepf_hotspot_name"})

    print("Joining cell centroids to hotspots.", flush=True)
    joined = gpd.sjoin(points, hotspots, how="left", predicate="within")
    grouped = (
        joined.groupby("cell_id", as_index=False)
        .agg(
            cepf_hotspot_names=("cepf_hotspot_name", join_unique),
            cepf_hotspot_count=("cepf_hotspot_name", lambda x: int(x.notna().sum())),
        )
    )
    grouped["cepf_hotspot_any"] = (grouped["cepf_hotspot_count"] > 0).astype(int)

    base_cols = ["cell_id", "cell_x", "cell_y", "centroid_lon", "centroid_lat", "continent", "country", "iso_a3"]
    out = cells[[c for c in base_cols if c in cells.columns]].merge(grouped, on="cell_id", how="left")
    out["cepf_hotspot_names"] = out["cepf_hotspot_names"].fillna("")
    out["cepf_hotspot_count"] = out["cepf_hotspot_count"].fillna(0).astype(int)
    out["cepf_hotspot_any"] = out["cepf_hotspot_any"].fillna(0).astype(int)
    out.to_csv(args.output, index=False)

    print(f"Wrote: {args.output}", flush=True)
    print(f"Cells: {len(out):,}; unique cells: {out['cell_id'].nunique():,}", flush=True)
    print(f"Cells in any hotspot: {int(out['cepf_hotspot_any'].sum()):,}", flush=True)
    print(f"Unique hotspot names hit: {joined['cepf_hotspot_name'].nunique(dropna=True):,}", flush=True)
    print(f"Cells matching multiple hotspots: {int((out['cepf_hotspot_count'] > 1).sum()):,}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
