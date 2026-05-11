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

from panel_variants import get_variant
from raster_zonal import aggregate_raster_file

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_GLOBIO_DIR = PROJECT_ROOT / "Data" / "raw" / "globio"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "globio_msa_100km_cells.csv"


def extract_cell_mean(raster_path: Path, cells: gpd.GeoDataFrame, nodata: float = None) -> pd.Series:
    """Extract mean raster value for each cell polygon."""
    return aggregate_raster_file(
        raster_path,
        cells,
        valid_mask=lambda arr: (arr >= 0) & (arr <= 1),
        fill_empty=np.nan,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--globio-dir", type=Path, default=DEFAULT_GLOBIO_DIR)
    parser.add_argument("--land-cells", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    land_cells_path = args.land_cells or (variant.land_cells_geojson if variant else LAND_CELLS)
    if variant is not None:
        output_path = args.output or variant.regressors_root / "baseline_geography" / f"globio_msa_{int(variant.cell_km)}km_cells.csv"
        print(f"Variant: {variant.name} ({variant.suffix})", flush=True)
    else:
        output_path = args.output or DEFAULT_OUTPUT

    if not land_cells_path.exists():
        raise FileNotFoundError(f"Missing: {land_cells_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {land_cells_path}", flush=True)
    cells = gpd.read_file(land_cells_path)
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

    out.to_csv(output_path, index=False)
    print(f"\nWrote: {output_path}", flush=True)
    print(f"Rows: {len(out):,}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
