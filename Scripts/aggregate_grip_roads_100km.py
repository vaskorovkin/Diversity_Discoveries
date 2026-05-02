#!/usr/bin/env python3
"""Aggregate GRIP4 road density raster to BOLD 100 km land cells.

GRIP4 provides road density in meters of road per square kilometer
at 5 arcminutes (~8km) resolution. We compute the mean road density
for each 100km cell.

This is a static baseline accessibility measure.

Requires: rasterio, geopandas, pandas, numpy
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_GRIP_DIR = PROJECT_ROOT / "Data" / "raw" / "grip"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "grip_roads_100km_cells.csv"


def extract_cell_mean(raster_path: Path, cells: gpd.GeoDataFrame) -> pd.Series:
    """Extract mean raster value for each cell polygon using bounding box sampling."""
    values = []

    with rasterio.open(raster_path) as src:
        nodata = src.nodata if src.nodata is not None else -9999
        data = src.read(1)
        transform = src.transform

        # Ensure cells are in WGS84 (same as raster)
        if cells.crs is not None and cells.crs.to_epsg() != 4326:
            cells_reproj = cells.to_crs("EPSG:4326")
        else:
            cells_reproj = cells

        for idx, row in cells_reproj.iterrows():
            geom = row.geometry
            minx, miny, maxx, maxy = geom.bounds

            # Convert bounds to pixel coordinates
            col_start = int((minx - transform.c) / transform.a)
            col_end = int((maxx - transform.c) / transform.a)
            row_start = int((transform.f - maxy) / (-transform.e))
            row_end = int((transform.f - miny) / (-transform.e))

            # Clamp to raster bounds
            col_start = max(0, col_start)
            col_end = min(data.shape[1], col_end)
            row_start = max(0, row_start)
            row_end = min(data.shape[0], row_end)

            if col_start >= col_end or row_start >= row_end:
                values.append(0.0)
                continue

            # Extract window
            window = data[row_start:row_end, col_start:col_end]
            # Mask nodata
            valid = window[window != nodata]

            if len(valid) > 0:
                values.append(float(np.mean(valid)))
            else:
                values.append(0.0)

    return pd.Series(values, index=cells.index)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grip-dir", type=Path, default=DEFAULT_GRIP_DIR)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    # Find the total density raster
    total_raster = args.grip_dir / "GRIP4_density_total.asc"
    if not total_raster.exists():
        # Try alternative names
        alternatives = list(args.grip_dir.glob("*total*.asc")) + list(args.grip_dir.glob("*density*.asc"))
        if alternatives:
            total_raster = alternatives[0]
        else:
            print(f"GRIP4 raster not found in: {args.grip_dir}")
            print("Run: python3 Scripts/download_grip_roads.py")
            return 1

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells)
    print(f"  {len(cells):,} cells", flush=True)

    print(f"Loading GRIP4 raster: {total_raster}", flush=True)
    print("Extracting road density per cell...", flush=True)

    road_density = extract_cell_mean(total_raster, cells)

    # Build output
    out = cells[["cell_id", "cell_x", "cell_y"]].copy()
    out["road_density_m_per_km2"] = road_density.values
    # Convert to km per km² for consistency (divide by 1000)
    out["road_density_km_per_km2"] = out["road_density_m_per_km2"] / 1000
    out["any_road"] = (out["road_density_m_per_km2"] > 0).astype(int)

    # Log transform for regression
    out["log_road_density"] = np.log1p(out["road_density_m_per_km2"])

    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}", flush=True)
    print(f"Rows: {len(out):,}", flush=True)

    # Summary
    print(f"\nSummary:", flush=True)
    print(f"  Cells with any road: {out['any_road'].sum():,} / {len(out):,}", flush=True)
    print(f"  Mean road density: {out['road_density_m_per_km2'].mean():.1f} m/km²", flush=True)
    print(f"  Max road density: {out['road_density_m_per_km2'].max():.1f} m/km²", flush=True)
    print(f"  Mean (cells with roads): {out.loc[out['any_road']==1, 'road_density_m_per_km2'].mean():.1f} m/km²", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
