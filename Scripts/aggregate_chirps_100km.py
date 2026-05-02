#!/usr/bin/env python3
"""Aggregate CHIRPS annual precipitation to BOLD 100 km cell-year panel.

Computes annual precipitation totals and anomalies for each cell.
Anomalies are computed relative to a 1981-2010 baseline climatology.

CHIRPS coverage: 50°S to 50°N (quasi-global, excludes polar regions).
Cells outside this range will have NaN values.

Requires: rasterio, geopandas, pandas, numpy
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_CHIRPS_DIR = PROJECT_ROOT / "Data" / "raw" / "chirps"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "chirps" / "chirps_100km_panel.csv"

BASELINE_START = 1981
BASELINE_END = 2010
PANEL_START = 2001
PANEL_END = 2023


def extract_cell_mean(raster_path: Path, cells: gpd.GeoDataFrame) -> pd.Series:
    """Extract mean raster value for each cell polygon."""
    values = []

    with rasterio.open(raster_path) as src:
        # Ensure cells are in same CRS as raster (EPSG:4326 for CHIRPS)
        if cells.crs.to_epsg() != 4326:
            cells_reproj = cells.to_crs("EPSG:4326")
        else:
            cells_reproj = cells

        for idx, row in cells_reproj.iterrows():
            geom = row.geometry
            # Check if cell is within raster bounds (CHIRPS is 50S-50N)
            bounds = geom.bounds  # minx, miny, maxx, maxy
            if bounds[1] < -50 or bounds[3] > 50:
                # Cell partially or fully outside CHIRPS coverage
                values.append(np.nan)
                continue

            try:
                out_image, _ = mask(src, [mapping(geom)], crop=True, nodata=np.nan)
                # CHIRPS uses -9999 as nodata in some files
                out_image = np.where(out_image < -999, np.nan, out_image)
                cell_mean = np.nanmean(out_image)
                values.append(cell_mean if not np.isnan(cell_mean) else np.nan)
            except Exception:
                values.append(np.nan)

    return pd.Series(values, index=cells.index)


def compute_baseline(chirps_dir: Path, cells: gpd.GeoDataFrame, start: int, end: int) -> pd.Series:
    """Compute baseline climatology (mean annual precip 1981-2010)."""
    print(f"  Computing baseline climatology ({start}-{end})...", flush=True)
    annual_values = []

    for year in range(start, end + 1):
        path = chirps_dir / f"chirps-v2.0.{year}.tif"
        if not path.exists():
            print(f"    Warning: missing {year}, skipping", flush=True)
            continue
        vals = extract_cell_mean(path, cells)
        annual_values.append(vals)

    if not annual_values:
        raise ValueError("No baseline data found")

    stacked = pd.concat(annual_values, axis=1)
    climatology = stacked.mean(axis=1)
    return climatology


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chirps-dir", type=Path, default=DEFAULT_CHIRPS_DIR)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--panel-start", type=int, default=PANEL_START)
    parser.add_argument("--panel-end", type=int, default=PANEL_END)
    parser.add_argument("--baseline-start", type=int, default=BASELINE_START)
    parser.add_argument("--baseline-end", type=int, default=BASELINE_END)
    parser.add_argument("--skip-baseline", action="store_true")
    args = parser.parse_args()

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells)
    print(f"  {len(cells):,} cells", flush=True)

    years = list(range(args.panel_start, args.panel_end + 1))
    print(f"Panel years: {years[0]}-{years[-1]}", flush=True)

    # Compute baseline climatology
    climatology = None
    if not args.skip_baseline:
        try:
            climatology = compute_baseline(
                args.chirps_dir, cells, args.baseline_start, args.baseline_end
            )
        except Exception as e:
            print(f"  Warning: could not compute baseline: {e}", flush=True)

    # Initialize output
    rows = []
    for _, row in cells.iterrows():
        for year in years:
            rows.append({
                "cell_id": row["cell_id"],
                "cell_x": row["cell_x"],
                "cell_y": row["cell_y"],
                "year": year,
            })
    out = pd.DataFrame(rows)

    # Process each year
    for year in years:
        path = args.chirps_dir / f"chirps-v2.0.{year}.tif"
        if not path.exists():
            print(f"  {year}: missing", flush=True)
            continue

        print(f"  {year}...", flush=True)
        try:
            cell_values = extract_cell_mean(path, cells)
            mask = out["year"] == year
            out.loc[mask, "chirps_precip_mm"] = cell_values.values

            if climatology is not None:
                anomaly = cell_values - climatology
                out.loc[mask, "chirps_precip_anomaly"] = anomaly.values
                # Standardized anomaly (z-score style, but using climatology as reference)
                # Negative = drier than normal
        except Exception as e:
            print(f"    Error: {e}", flush=True)

    # Sort and save
    out = out.sort_values(["cell_id", "year"])
    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}", flush=True)
    print(f"Rows: {len(out):,}", flush=True)

    # Summary stats
    if "chirps_precip_mm" in out.columns:
        valid = out["chirps_precip_mm"].notna()
        print(f"Cells with CHIRPS coverage: {valid.groupby(out['cell_id']).first().sum():,}", flush=True)
        print(f"Mean annual precip: {out['chirps_precip_mm'].mean():.1f} mm", flush=True)
    if "chirps_precip_anomaly" in out.columns:
        print(f"Mean anomaly: {out['chirps_precip_anomaly'].mean():.1f} mm", flush=True)

    # Save summary
    summary_path = args.output.with_name(args.output.stem + "_summary.csv")
    agg_cols = [c for c in out.columns if c.startswith("chirps_")]
    if agg_cols:
        summary = out.groupby("year")[agg_cols].agg(["mean", "std", "count"]).round(2)
        summary.columns = ["_".join(c) for c in summary.columns]
        summary.to_csv(summary_path)
        print(f"Wrote summary: {summary_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
