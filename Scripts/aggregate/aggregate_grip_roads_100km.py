#!/usr/bin/env python3
"""Aggregate GRIP4 road density raster to BOLD 100 km land cells.

GRIP4 provides road density in meters of road per square kilometer
at 5 arcminutes (~8km) resolution. We compute the mean road density
for each 100km cell.

This is a static baseline accessibility measure.

Requires: rasterio, geopandas, pandas, numpy
"""


from __future__ import annotations


from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _path in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from panel_variants import get_variant
from raster_zonal import aggregate_raster_file

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_GRIP_DIR = PROJECT_ROOT / "Data" / "raw" / "grip"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "grip_roads_100km_cells.csv"


def extract_cell_mean(raster_path: Path, cells: gpd.GeoDataFrame) -> pd.Series:
    """Extract mean raster value for each cell polygon."""
    return aggregate_raster_file(
        raster_path,
        cells,
        valid_mask=lambda arr: arr >= 0,
        fill_empty=0.0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--grip-dir", type=Path, default=DEFAULT_GRIP_DIR)
    parser.add_argument("--land-cells", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    land_cells_path = args.land_cells or (variant.land_cells_geojson if variant else LAND_CELLS)
    if variant is not None:
        output_path = args.output or variant.regressors_root / "baseline_geography" / f"grip_roads_{int(variant.cell_km)}km_cells.csv"
        print(f"Variant: {variant.name} ({variant.suffix})", flush=True)
    else:
        output_path = args.output or DEFAULT_OUTPUT

    # Find the total density raster
    total_raster = args.grip_dir / "GRIP4_density_total.asc"
    if not total_raster.exists():
        # Try alternative names
        alternatives = list(args.grip_dir.glob("*total*.asc")) + list(args.grip_dir.glob("*density*.asc"))
        if alternatives:
            total_raster = alternatives[0]
        else:
            print(f"GRIP4 raster not found in: {args.grip_dir}")
            print("Run: python3 Scripts/download/download_grip_roads.py")
            return 1

    if not land_cells_path.exists():
        raise FileNotFoundError(f"Missing: {land_cells_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {land_cells_path}", flush=True)
    cells = gpd.read_file(land_cells_path)
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

    out.to_csv(output_path, index=False)
    print(f"\nWrote: {output_path}", flush=True)
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
