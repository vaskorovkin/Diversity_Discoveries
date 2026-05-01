#!/usr/bin/env python3
"""Merge MODIS burned area GEE exports with full cell panel.

Run after downloading Earth Engine exports to Data/regressors/modis/.
Creates a complete cell-year panel with burned area variables.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "regressors" / "modis"
EXHIBITS_DIR = PROJECT_ROOT / "Exhibits" / "data"


def main() -> int:
    # Check for required files
    annual_path = DATA_DIR / "modis_burned_area_100km_annual.csv"
    panel_path = EXHIBITS_DIR / "bold_grid100_cell_year_panel_collection_2005_2025.csv"

    for p in [annual_path, panel_path]:
        if not p.exists():
            print(f"Missing: {p}")
            return 1

    print(f"Loading burned area: {annual_path}")
    annual = pd.read_csv(annual_path)
    print(f"  {len(annual):,} cell-year rows")

    print(f"Loading BOLD panel for cell list: {panel_path}")
    panel = pd.read_csv(panel_path)
    cells = panel[["cell_id", "cell_x", "cell_y"]].drop_duplicates()
    print(f"  {len(cells):,} unique cells")

    # MODIS covers 2001-2023
    years = list(range(2001, 2024))
    print(f"Years: {years[0]}-{years[-1]}")

    # Create full cell-year skeleton
    skeleton = cells.assign(key=1).merge(
        pd.DataFrame({"year": years, "key": 1}),
        on="key"
    ).drop(columns="key")
    print(f"Skeleton: {len(skeleton):,} cell-year rows")

    # Merge annual burned area
    skeleton = skeleton.merge(
        annual[["cell_id", "year", "burned_area_km2", "any_burned"]],
        on=["cell_id", "year"],
        how="left"
    )

    # Fill missing values (cells with no fire)
    skeleton["burned_area_km2"] = skeleton["burned_area_km2"].fillna(0)
    skeleton["any_burned"] = skeleton["any_burned"].fillna(0).astype(int)

    # Cumulative burned area
    skeleton = skeleton.sort_values(["cell_id", "year"])
    skeleton["cumulative_burned_km2"] = skeleton.groupby("cell_id")["burned_area_km2"].cumsum()

    # Lagged burned area (1-year and 2-year)
    skeleton["L1_burned_area_km2"] = skeleton.groupby("cell_id")["burned_area_km2"].shift(1)
    skeleton["L2_burned_area_km2"] = skeleton.groupby("cell_id")["burned_area_km2"].shift(2)
    skeleton["L1_any_burned"] = skeleton.groupby("cell_id")["any_burned"].shift(1)
    skeleton["L2_any_burned"] = skeleton.groupby("cell_id")["any_burned"].shift(2)

    # Summary stats
    print("\nSummary:")
    print(f"  Cell-years with fire: {(skeleton['any_burned'] > 0).sum():,}")
    print(f"  Total burned area 2001-2023: {skeleton['burned_area_km2'].sum():,.0f} km²")
    print(f"  Max burned area single cell-year: {skeleton['burned_area_km2'].max():,.0f} km²")

    # Save
    out_path = DATA_DIR / "modis_burned_area_100km_panel.csv"
    skeleton.to_csv(out_path, index=False)
    print(f"\nWrote {len(skeleton):,} rows to {out_path}")

    # Also save summary
    summary_path = DATA_DIR / "modis_burned_area_100km_panel_summary.csv"
    summary = skeleton.groupby("year").agg({
        "burned_area_km2": ["sum", "mean", "std"],
        "any_burned": ["sum", "mean"],
        "cumulative_burned_km2": "sum",
    }).round(4)
    summary.columns = ["_".join(c) for c in summary.columns]
    summary.to_csv(summary_path)
    print(f"Wrote annual summary to {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
