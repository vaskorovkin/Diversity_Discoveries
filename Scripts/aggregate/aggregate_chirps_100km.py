#!/usr/bin/env python3
"""Aggregate CHIRPS precipitation to BOLD cell-time panels.

Computes annual or quarterly precipitation totals and anomalies for each cell.
Anomalies are computed relative to a 1981-2010 period-specific climatology.

CHIRPS coverage: 50°S to 50°N (quasi-global, excludes polar regions).
Cells outside this range will have NaN values.

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
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd

from panel_variants import get_variant
from raster_zonal import aggregate_raster_file

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_CHIRPS_DIR = PROJECT_ROOT / "Data" / "raw" / "chirps"
DEFAULT_CHIRPS_MONTHLY_DIR = PROJECT_ROOT / "Data" / "raw" / "chirps_monthly"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "chirps" / "chirps_100km_panel.csv"

BASELINE_START = 1981
BASELINE_END = 2010
PANEL_START = 2001
PANEL_END = 2023


def extract_cell_mean(raster_path: Path, cells: gpd.GeoDataFrame) -> pd.Series:
    """Extract mean raster value for each cell polygon."""
    return aggregate_raster_file(
        raster_path,
        cells,
        valid_mask=lambda arr: arr > -999,
        fill_empty=np.nan,
    )


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


def monthly_path(chirps_dir: Path, year: int, month: int) -> Path:
    return chirps_dir / f"chirps-v2.0.{year}.{month:02d}.tif"


def extract_quarter_total(chirps_dir: Path, cells: gpd.GeoDataFrame, year: int, quarter: int) -> Optional[pd.Series]:
    """Return cell-level quarterly precipitation total from monthly CHIRPS files."""
    months = range((quarter - 1) * 3 + 1, quarter * 3 + 1)
    monthly_values = []
    missing = []

    for month in months:
        path = monthly_path(chirps_dir, year, month)
        if not path.exists():
            missing.append(path.name)
            continue
        monthly_values.append(extract_cell_mean(path, cells))

    if missing:
        print(f"  {year} Q{quarter}: missing monthly CHIRPS files: {', '.join(missing)}", flush=True)
        return None

    if not monthly_values:
        return None

    return pd.concat(monthly_values, axis=1).sum(axis=1, min_count=1)


def compute_quarter_baseline(
    chirps_dir: Path,
    cells: gpd.GeoDataFrame,
    start: int,
    end: int,
) -> dict[int, pd.Series]:
    """Compute quarter-specific baseline climatology from monthly CHIRPS."""
    print(f"  Computing quarterly baseline climatology ({start}-{end})...", flush=True)
    climatology: dict[int, pd.Series] = {}

    for quarter in range(1, 5):
        values = []
        for year in range(start, end + 1):
            vals = extract_quarter_total(chirps_dir, cells, year, quarter)
            if vals is not None:
                values.append(vals)
        if values:
            climatology[quarter] = pd.concat(values, axis=1).mean(axis=1)
        else:
            print(f"    Warning: no baseline data for Q{quarter}", flush=True)

    if not climatology:
        raise ValueError("No quarterly baseline data found")

    return climatology


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--chirps-dir", type=Path, default=None)
    parser.add_argument("--land-cells", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--panel-start", type=int, default=PANEL_START)
    parser.add_argument("--panel-end", type=int, default=PANEL_END)
    parser.add_argument("--baseline-start", type=int, default=BASELINE_START)
    parser.add_argument("--baseline-end", type=int, default=BASELINE_END)
    parser.add_argument("--skip-baseline", action="store_true")
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    land_cells_path = args.land_cells or (variant.land_cells_geojson if variant else LAND_CELLS)
    freq = "year"
    if variant is not None:
        freq = variant.freq
        default_dir = DEFAULT_CHIRPS_MONTHLY_DIR if freq == "quarter" else DEFAULT_CHIRPS_DIR
        args.chirps_dir = args.chirps_dir or default_dir
        suffix = "quarter_panel" if freq == "quarter" else "panel"
        output_path = args.output or variant.regressors_root / "chirps" / f"chirps_{int(variant.cell_km)}km_{suffix}.csv"
        print(f"Variant: {variant.name} ({variant.suffix})", flush=True)
    else:
        args.chirps_dir = args.chirps_dir or DEFAULT_CHIRPS_DIR
        output_path = args.output or DEFAULT_OUTPUT

    if not land_cells_path.exists():
        raise FileNotFoundError(f"Missing: {land_cells_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {land_cells_path}", flush=True)
    cells = gpd.read_file(land_cells_path)
    print(f"  {len(cells):,} cells", flush=True)

    years = list(range(args.panel_start, args.panel_end + 1))
    print(f"Panel years: {years[0]}-{years[-1]}", flush=True)
    print(f"Panel frequency: {freq}", flush=True)
    print(f"CHIRPS directory: {args.chirps_dir}", flush=True)

    # Compute baseline climatology
    climatology = None
    if not args.skip_baseline:
        try:
            if freq == "quarter":
                climatology = compute_quarter_baseline(
                    args.chirps_dir, cells, args.baseline_start, args.baseline_end
                )
            else:
                climatology = compute_baseline(
                    args.chirps_dir, cells, args.baseline_start, args.baseline_end
                )
        except Exception as e:
            print(f"  Warning: could not compute baseline: {e}", flush=True)

    # Initialize output
    rows = []
    for _, row in cells.iterrows():
        for year in years:
            if freq == "quarter":
                for quarter in range(1, 5):
                    rows.append({
                        "cell_id": row["cell_id"],
                        "cell_x": row["cell_x"],
                        "cell_y": row["cell_y"],
                        "year": year,
                        "quarter": quarter,
                    })
            else:
                rows.append({
                    "cell_id": row["cell_id"],
                    "cell_x": row["cell_x"],
                    "cell_y": row["cell_y"],
                    "year": year,
                })
    out = pd.DataFrame(rows)

    if freq == "quarter":
        for year in years:
            for quarter in range(1, 5):
                print(f"  {year} Q{quarter}...", flush=True)
                try:
                    cell_values = extract_quarter_total(args.chirps_dir, cells, year, quarter)
                    if cell_values is None:
                        continue
                    mask = (out["year"] == year) & (out["quarter"] == quarter)
                    out.loc[mask, "chirps_precip_mm"] = cell_values.values

                    if climatology is not None and quarter in climatology:
                        anomaly = cell_values - climatology[quarter]
                        out.loc[mask, "chirps_precip_anomaly"] = anomaly.values
                except Exception as e:
                    print(f"    Error: {e}", flush=True)
    else:
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
            except Exception as e:
                print(f"    Error: {e}", flush=True)

    # Sort and save
    sort_cols = ["cell_id", "year"] + (["quarter"] if freq == "quarter" else [])
    out = out.sort_values(sort_cols)
    out.to_csv(output_path, index=False)
    print(f"\nWrote: {output_path}", flush=True)
    print(f"Rows: {len(out):,}", flush=True)

    # Summary stats
    if "chirps_precip_mm" in out.columns:
        valid = out["chirps_precip_mm"].notna()
        print(f"Cells with CHIRPS coverage: {valid.groupby(out['cell_id']).first().sum():,}", flush=True)
        print(f"Mean annual precip: {out['chirps_precip_mm'].mean():.1f} mm", flush=True)
    if "chirps_precip_anomaly" in out.columns:
        print(f"Mean anomaly: {out['chirps_precip_anomaly'].mean():.1f} mm", flush=True)

    # Save summary
    summary_path = output_path.with_name(output_path.stem + "_summary.csv")
    agg_cols = [c for c in out.columns if c.startswith("chirps_")]
    if agg_cols:
        group_cols = ["year"] + (["quarter"] if freq == "quarter" else [])
        summary = out.groupby(group_cols)[agg_cols].agg(["mean", "std", "count"]).round(2)
        summary.columns = ["_".join(c) for c in summary.columns]
        summary.to_csv(summary_path)
        print(f"Wrote summary: {summary_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
