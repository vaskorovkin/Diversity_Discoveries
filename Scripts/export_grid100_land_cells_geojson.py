#!/usr/bin/env python3
"""Export the 100 km BOLD land-cell grid as GeoJSON polygons.

The panel uses EPSG:6933 equal-area cell indices. This script reconstructs
polygon bounds from cell_x/cell_y and exports WGS84 GeoJSON suitable for upload
to Google Earth Engine.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from pipeline_utils import EQUAL_AREA_CRS, PROCESSED_BOLD, LAND_CELLS_CSV, ensure_output_dirs


DEFAULT_OUTPUT = PROCESSED_BOLD / "bold_grid100_land_cells.geojson"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cell-km", type=float, default=100)
    args = parser.parse_args()

    ensure_output_dirs()
    cells = pd.read_csv(args.input, dtype={"cell_id": str, "iso_a3": str})
    required = {"cell_id", "cell_x", "cell_y", "centroid_lon", "centroid_lat", "continent", "country", "iso_a3"}
    missing = sorted(required - set(cells.columns))
    if missing:
        raise ValueError(f"Missing required columns in {args.input}: {missing}")

    cell_m = args.cell_km * 1000
    geoms = [
        box(row.cell_x * cell_m, row.cell_y * cell_m, (row.cell_x + 1) * cell_m, (row.cell_y + 1) * cell_m)
        for row in cells.itertuples(index=False)
    ]
    grid = gpd.GeoDataFrame(cells, geometry=geoms, crs=EQUAL_AREA_CRS).to_crs("EPSG:4326")
    grid.to_file(args.output, driver="GeoJSON")
    print(f"Wrote {len(grid):,} cell polygons: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
