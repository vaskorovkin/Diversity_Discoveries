#!/usr/bin/env python3
"""Aggregate TerraClimate NetCDF data to BOLD 100 km cell-year panel.

Computes annual means and anomalies for:
- PDSI: Palmer Drought Severity Index (negative = drought)
- tmax: Maximum temperature (°C)
- ppt: Precipitation (mm)

Anomalies are computed relative to a 1981-2010 baseline climatology.

Requires: xarray, rioxarray, geopandas, pandas, numpy
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_TERRACLIMATE_DIR = PROJECT_ROOT / "Data" / "raw" / "terraclimate"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "terraclimate" / "terraclimate_100km_panel.csv"

# Baseline period for anomaly calculation
BASELINE_START = 1981
BASELINE_END = 2010

# Panel years
PANEL_START = 2001
PANEL_END = 2023

# Variables to process
VARIABLES = ["PDSI", "tmax", "ppt"]


def load_annual_mean(var_dir: Path, var: str, year: int) -> xr.DataArray:
    """Load a TerraClimate NetCDF and compute annual mean."""
    path = var_dir / f"TerraClimate_{var}_{year}.nc"
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}")

    ds = xr.open_dataset(path)
    # TerraClimate variable names match the filename variable
    da = ds[var.lower()] if var.lower() in ds else ds[var]
    # Compute annual mean across time dimension
    annual_mean = da.mean(dim="time")
    ds.close()
    return annual_mean


def compute_baseline_climatology(var_dir: Path, var: str, start: int, end: int) -> xr.DataArray:
    """Compute baseline climatology (mean of annual means)."""
    print(f"  Computing {var} baseline climatology ({start}-{end})...", flush=True)
    annual_means = []
    for year in range(start, end + 1):
        try:
            am = load_annual_mean(var_dir, var, year)
            annual_means.append(am)
        except FileNotFoundError:
            print(f"    Warning: missing {var} {year}, skipping", flush=True)

    if not annual_means:
        raise ValueError(f"No baseline data found for {var}")

    stacked = xr.concat(annual_means, dim="year")
    climatology = stacked.mean(dim="year")
    return climatology


def extract_cell_values(da: xr.DataArray, cells: gpd.GeoDataFrame) -> pd.Series:
    """Extract mean raster values for each cell polygon."""
    # Ensure CRS matches (TerraClimate is EPSG:4326)
    if cells.crs.to_epsg() != 4326:
        cells = cells.to_crs("EPSG:4326")

    values = []
    for idx, row in cells.iterrows():
        geom = row.geometry
        minx, miny, maxx, maxy = geom.bounds

        # Clip raster to bounding box
        try:
            clipped = da.sel(lon=slice(minx, maxx), lat=slice(maxy, miny))
            if clipped.size == 0:
                values.append(np.nan)
            else:
                # Simple mean of all pixels in bounding box
                # (For 100km cells at 4km resolution, this is ~625 pixels)
                values.append(float(clipped.mean().values))
        except Exception:
            values.append(np.nan)

    return pd.Series(values, index=cells.index)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terraclimate-dir", type=Path, default=DEFAULT_TERRACLIMATE_DIR)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--panel-start", type=int, default=PANEL_START)
    parser.add_argument("--panel-end", type=int, default=PANEL_END)
    parser.add_argument("--baseline-start", type=int, default=BASELINE_START)
    parser.add_argument("--baseline-end", type=int, default=BASELINE_END)
    parser.add_argument("--variables", nargs="+", default=VARIABLES)
    parser.add_argument("--skip-baseline", action="store_true", help="Skip anomaly calculation, output raw values only.")
    args = parser.parse_args()

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing land cells: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells)
    print(f"  {len(cells):,} cells", flush=True)

    years = list(range(args.panel_start, args.panel_end + 1))
    print(f"Panel years: {years[0]}-{years[-1]}", flush=True)

    # Initialize output dataframe
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

    # Process each variable
    for var in args.variables:
        var_lower = var.lower()
        var_dir = args.terraclimate_dir / var_lower
        if not var_dir.exists():
            print(f"Warning: {var_dir} not found, skipping {var}", flush=True)
            continue

        print(f"\nProcessing {var}...", flush=True)

        # Compute baseline climatology if needed
        climatology = None
        clim_values = None
        if not args.skip_baseline:
            try:
                climatology = compute_baseline_climatology(
                    var_dir, var, args.baseline_start, args.baseline_end
                )
                clim_values = extract_cell_values(climatology, cells)
                print(f"  Baseline climatology extracted for {len(cells):,} cells", flush=True)
            except Exception as e:
                print(f"  Warning: could not compute baseline: {e}", flush=True)
                print(f"  Proceeding without anomalies for {var}", flush=True)

        # Process each year
        for year in years:
            print(f"  {var} {year}...", flush=True)
            try:
                annual_mean = load_annual_mean(var_dir, var, year)

                # Extract values for each cell
                cell_values = extract_cell_values(annual_mean, cells)

                # Add to output
                mask = out["year"] == year
                out.loc[mask, f"{var_lower}_mean"] = cell_values.values

                # Compute anomaly if we have climatology
                if clim_values is not None:
                    anomaly = cell_values - clim_values
                    out.loc[mask, f"{var_lower}_anomaly"] = anomaly.values

            except FileNotFoundError:
                print(f"    Missing data for {year}", flush=True)
            except Exception as e:
                print(f"    Error: {e}", flush=True)

    # Sort and save
    out = out.sort_values(["cell_id", "year"])
    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}", flush=True)
    print(f"Rows: {len(out):,}", flush=True)

    # Summary
    for var in args.variables:
        var_lower = var.lower()
        if f"{var_lower}_mean" in out.columns:
            mean_col = out[f"{var_lower}_mean"]
            print(f"{var} mean: {mean_col.mean():.2f} (std: {mean_col.std():.2f})", flush=True)
        if f"{var_lower}_anomaly" in out.columns:
            anom_col = out[f"{var_lower}_anomaly"]
            print(f"{var} anomaly: {anom_col.mean():.3f} (std: {anom_col.std():.3f})", flush=True)

    # Save summary
    summary_path = args.output.with_name(args.output.stem + "_summary.csv")
    summary = out.groupby("year").agg({
        col: ["mean", "std"] for col in out.columns
        if col.endswith("_mean") or col.endswith("_anomaly")
    }).round(4)
    if len(summary.columns) > 0:
        summary.columns = ["_".join(c) for c in summary.columns]
        summary.to_csv(summary_path)
        print(f"Wrote summary: {summary_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
