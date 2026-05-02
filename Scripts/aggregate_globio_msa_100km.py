#!/usr/bin/env python3
"""Aggregate GLOBIO4 MSA rasters to BOLD 100 km land cells.

Computes mean MSA (Mean Species Abundance) for each cell.
MSA is a 0-1 scale where 1 = pristine/undisturbed biodiversity.

This is a static baseline biodiversity intactness measure (2015).

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
DEFAULT_GLOBIO_DIR = PROJECT_ROOT / "Data" / "raw" / "globio"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "globio_msa_100km_cells.csv"


def extract_cell_mean(raster_path: Path, cells: gpd.GeoDataFrame, nodata: float = None) -> pd.Series:
    """Extract mean raster value for each cell using bounding box."""
    values = []

    with rasterio.open(raster_path) as src:
        if nodata is None:
            nodata = src.nodata
        data = src.read(1)
        transform = src.transform

        # Cells should be in WGS84
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
                values.append(np.nan)
                continue

            window = data[row_start:row_end, col_start:col_end]

            # Handle nodata
            if nodata is not None:
                valid = window[(window != nodata) & (~np.isnan(window)) & (window >= 0) & (window <= 1)]
            else:
                valid = window[(~np.isnan(window)) & (window >= 0) & (window <= 1)]

            if len(valid) > 0:
                values.append(float(np.mean(valid)))
            else:
                values.append(np.nan)

    return pd.Series(values, index=cells.index)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--globio-dir", type=Path, default=DEFAULT_GLOBIO_DIR)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells)
    print(f"  {len(cells):,} cells", flush=True)

    # Find available MSA tifs
    tifs = list(args.globio_dir.glob("*.tif"))
    if not tifs:
        print(f"No .tif files found in {args.globio_dir}")
        print("Run: python3 Scripts/download_globio_msa.py")
        return 1

    print(f"Found MSA rasters: {[t.name for t in tifs]}", flush=True)

    # Build output with cell info
    out = cells[["cell_id", "cell_x", "cell_y"]].copy()

    # Process each MSA type
    for tif_path in tifs:
        name = tif_path.stem.lower()

        # Determine column name
        if "plants" in name:
            col_name = "msa_plants"
        elif "wbvert" in name:
            col_name = "msa_vertebrates"
        elif "terrestrialmsa" in name.replace("_", ""):
            col_name = "msa_overall"
        else:
            col_name = f"msa_{name[:20]}"

        print(f"\nProcessing {tif_path.name} -> {col_name}...", flush=True)

        msa_values = extract_cell_mean(tif_path, cells)
        out[col_name] = msa_values.values

        valid = out[col_name].notna()
        print(f"  Cells with data: {valid.sum():,} / {len(out):,}", flush=True)
        print(f"  Mean MSA: {out[col_name].mean():.3f}", flush=True)
        print(f"  Range: {out[col_name].min():.3f} - {out[col_name].max():.3f}", flush=True)

    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}", flush=True)
    print(f"Rows: {len(out):,}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
