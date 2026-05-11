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
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from panel_variants import get_variant
from raster_zonal import XarrayCellMeanExtractor

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
    annual_mean = da.mean(dim="time").load()
    ds.close()
    return annual_mean


def load_quarter_value(var_dir: Path, var: str, year: int, quarter: int) -> xr.DataArray:
    """Load a TerraClimate NetCDF and compute one quarter's value."""
    path = var_dir / f"TerraClimate_{var}_{year}.nc"
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}")

    ds = xr.open_dataset(path)
    da = ds[var.lower()] if var.lower() in ds else ds[var]
    months = [quarter * 3 - 2, quarter * 3 - 1, quarter * 3]
    q = da.sel(time=da["time"].dt.month.isin(months))
    # PDSI and tmax are state/mean variables; precipitation should accumulate.
    out = (q.sum(dim="time") if var.lower() == "ppt" else q.mean(dim="time")).load()
    ds.close()
    return out


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


def compute_quarter_baseline_climatology(var_dir: Path, var: str, quarter: int, start: int, end: int) -> xr.DataArray:
    print(f"  Computing {var} Q{quarter} baseline climatology ({start}-{end})...", flush=True)
    quarter_values = []
    for year in range(start, end + 1):
        try:
            qv = load_quarter_value(var_dir, var, year, quarter)
            quarter_values.append(qv)
        except FileNotFoundError:
            print(f"    Warning: missing {var} {year}, skipping", flush=True)

    if not quarter_values:
        raise ValueError(f"No baseline data found for {var} Q{quarter}")

    stacked = xr.concat(quarter_values, dim="year")
    return stacked.mean(dim="year")


def extract_cell_values(
    da: xr.DataArray,
    cells: gpd.GeoDataFrame,
    extractor: Optional[XarrayCellMeanExtractor] = None,
) -> pd.Series:
    """Extract mean raster values for each cell polygon."""
    if extractor is None:
        extractor = XarrayCellMeanExtractor(cells)
    return extractor.aggregate(da)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--terraclimate-dir", type=Path, default=DEFAULT_TERRACLIMATE_DIR)
    parser.add_argument("--land-cells", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--panel-start", type=int, default=PANEL_START)
    parser.add_argument("--panel-end", type=int, default=PANEL_END)
    parser.add_argument("--baseline-start", type=int, default=BASELINE_START)
    parser.add_argument("--baseline-end", type=int, default=BASELINE_END)
    parser.add_argument("--variables", nargs="+", default=VARIABLES)
    parser.add_argument("--skip-baseline", action="store_true", help="Skip anomaly calculation, output raw values only.")
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    freq = "year"
    land_cells_path = args.land_cells or (variant.land_cells_geojson if variant else LAND_CELLS)
    if variant is not None:
        freq = variant.freq
        suffix = "quarter_panel" if freq == "quarter" else "panel"
        output_path = args.output or variant.regressors_root / "terraclimate" / f"terraclimate_{int(variant.cell_km)}km_{suffix}.csv"
        print(f"Variant: {variant.name} ({variant.suffix})", flush=True)
    else:
        output_path = args.output or DEFAULT_OUTPUT

    if not land_cells_path.exists():
        raise FileNotFoundError(f"Missing land cells: {land_cells_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {land_cells_path}", flush=True)
    cells = gpd.read_file(land_cells_path)
    print(f"  {len(cells):,} cells", flush=True)
    cell_extractor = XarrayCellMeanExtractor(cells)

    years = list(range(args.panel_start, args.panel_end + 1))
    print(f"Panel years: {years[0]}-{years[-1]}", flush=True)

    rows = []
    for _, row in cells.iterrows():
        for year in years:
            quarters = [1, 2, 3, 4] if freq == "quarter" else [None]
            for quarter in quarters:
                out_row = {
                    "cell_id": row["cell_id"],
                    "cell_x": row["cell_x"],
                    "cell_y": row["cell_y"],
                    "year": year,
                }
                if quarter is not None:
                    out_row["quarter"] = quarter
                rows.append(out_row)
    out = pd.DataFrame(rows)

    # Process each variable
    for var in args.variables:
        var_lower = var.lower()
        var_dir = args.terraclimate_dir / var_lower
        if not var_dir.exists():
            print(f"Warning: {var_dir} not found, skipping {var}", flush=True)
            continue

        print(f"\nProcessing {var}...", flush=True)

        climatology = None
        clim_values = None
        quarter_clim_values = {}
        if not args.skip_baseline:
            try:
                if freq == "quarter":
                    for quarter in [1, 2, 3, 4]:
                        climatology = compute_quarter_baseline_climatology(
                            var_dir, var, quarter, args.baseline_start, args.baseline_end
                        )
                        quarter_clim_values[quarter] = extract_cell_values(climatology, cells, cell_extractor)
                    print(f"  Quarterly baseline climatology extracted for {len(cells):,} cells", flush=True)
                else:
                    climatology = compute_baseline_climatology(
                        var_dir, var, args.baseline_start, args.baseline_end
                    )
                    clim_values = extract_cell_values(climatology, cells, cell_extractor)
                    print(f"  Baseline climatology extracted for {len(cells):,} cells", flush=True)
            except Exception as e:
                print(f"  Warning: could not compute baseline: {e}", flush=True)
                print(f"  Proceeding without anomalies for {var}", flush=True)

        for year in years:
            quarters = [1, 2, 3, 4] if freq == "quarter" else [None]
            for quarter in quarters:
                label = f"{year} Q{quarter}" if quarter is not None else str(year)
                print(f"  {var} {label}...", flush=True)
                try:
                    period_value = load_quarter_value(var_dir, var, year, quarter) if quarter is not None else load_annual_mean(var_dir, var, year)
                    cell_values = extract_cell_values(period_value, cells, cell_extractor)
                    mask = (out["year"] == year)
                    if quarter is not None:
                        mask = mask & (out["quarter"] == quarter)
                    out.loc[mask, f"{var_lower}_mean"] = cell_values.values
                    base_values = quarter_clim_values.get(quarter) if quarter is not None else clim_values
                    if base_values is not None:
                        out.loc[mask, f"{var_lower}_anomaly"] = (cell_values - base_values).values
                except FileNotFoundError:
                    print(f"    Missing data for {label}", flush=True)
                except Exception as e:
                    print(f"    Error: {e}", flush=True)

    # Sort and save
    sort_cols = ["cell_id", "year"] + (["quarter"] if freq == "quarter" else [])
    out = out.sort_values(sort_cols)
    out.to_csv(output_path, index=False)
    print(f"\nWrote: {output_path}", flush=True)
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
    summary_path = output_path.with_name(output_path.stem + "_summary.csv")
    group_cols = ["year"] + (["quarter"] if freq == "quarter" else [])
    summary = out.groupby(group_cols).agg({
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
