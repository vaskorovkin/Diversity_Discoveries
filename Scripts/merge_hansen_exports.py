#!/usr/bin/env python3
"""Merge Hansen GEE exports with full cell panel.

Run after downloading Earth Engine exports to Data/regressors/hansen/.
Creates a complete cell-year panel with forest loss variables.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "regressors" / "hansen"
EXHIBITS_DIR = PROJECT_ROOT / "Exhibits" / "data"


def main() -> int:
    # Check for required files
    baseline_path = DATA_DIR / "hansen_baseline_forest_100km.csv"
    annual_path = DATA_DIR / "hansen_forest_loss_100km_annual.csv"
    panel_path = EXHIBITS_DIR / "bold_grid100_cell_year_panel_collection_2005_2025.csv"

    for p in [baseline_path, annual_path, panel_path]:
        if not p.exists():
            print(f"Missing: {p}")
            return 1

    print(f"Loading baseline: {baseline_path}")
    baseline = pd.read_csv(baseline_path)
    print(f"  {len(baseline):,} cells")

    print(f"Loading annual loss: {annual_path}")
    annual = pd.read_csv(annual_path)
    print(f"  {len(annual):,} cell-year rows")

    print(f"Loading BOLD panel for cell list: {panel_path}")
    panel = pd.read_csv(panel_path)
    cells = panel[["cell_id", "cell_x", "cell_y"]].drop_duplicates()
    print(f"  {len(cells):,} unique cells")

    # Hansen covers 2001-2023
    years = list(range(2001, 2024))
    print(f"Years: {years[0]}-{years[-1]}")

    # Create full cell-year skeleton
    skeleton = cells.assign(key=1).merge(
        pd.DataFrame({"year": years, "key": 1}),
        on="key"
    ).drop(columns="key")
    print(f"Skeleton: {len(skeleton):,} cell-year rows")

    # Merge baseline
    skeleton = skeleton.merge(
        baseline[["cell_id", "baseline_forest_km2"]],
        on="cell_id",
        how="left"
    )

    # Merge annual loss
    skeleton = skeleton.merge(
        annual[["cell_id", "year", "forest_loss_km2"]],
        on=["cell_id", "year"],
        how="left"
    )

    # Fill missing values (cells with no forest or no loss)
    skeleton["forest_loss_km2"] = skeleton["forest_loss_km2"].fillna(0)
    skeleton["baseline_forest_km2"] = skeleton["baseline_forest_km2"].fillna(0)

    # Compute derived variables
    skeleton["forest_loss_share"] = (
        skeleton["forest_loss_km2"] / skeleton["baseline_forest_km2"]
    ).fillna(0).replace([float("inf"), float("-inf")], 0)

    # Cumulative loss
    skeleton = skeleton.sort_values(["cell_id", "year"])
    skeleton["cumulative_loss_km2"] = skeleton.groupby("cell_id")["forest_loss_km2"].cumsum()
    skeleton["cumulative_loss_share"] = (
        skeleton["cumulative_loss_km2"] / skeleton["baseline_forest_km2"]
    ).fillna(0).replace([float("inf"), float("-inf")], 0)

    # Lagged loss (1-year and 2-year)
    skeleton["L1_forest_loss_km2"] = skeleton.groupby("cell_id")["forest_loss_km2"].shift(1)
    skeleton["L2_forest_loss_km2"] = skeleton.groupby("cell_id")["forest_loss_km2"].shift(2)
    skeleton["L1_forest_loss_share"] = skeleton.groupby("cell_id")["forest_loss_share"].shift(1)
    skeleton["L2_forest_loss_share"] = skeleton.groupby("cell_id")["forest_loss_share"].shift(2)

    # Summary stats
    print("\nSummary:")
    print(f"  Cells with forest: {(skeleton['baseline_forest_km2'] > 0).groupby(skeleton['cell_id']).first().sum():,}")
    print(f"  Cell-years with loss: {(skeleton['forest_loss_km2'] > 0).sum():,}")
    print(f"  Total baseline forest: {skeleton.groupby('cell_id')['baseline_forest_km2'].first().sum():,.0f} km²")
    print(f"  Total forest loss 2001-2023: {skeleton['forest_loss_km2'].sum():,.0f} km²")

    # Save
    out_path = DATA_DIR / "hansen_forest_loss_100km_panel.csv"
    skeleton.to_csv(out_path, index=False)
    print(f"\nWrote {len(skeleton):,} rows to {out_path}")

    # Also save summary
    summary_path = DATA_DIR / "hansen_forest_loss_100km_panel_summary.csv"
    summary = skeleton.groupby("year").agg({
        "forest_loss_km2": ["sum", "mean", "std"],
        "forest_loss_share": ["mean", "std"],
        "cumulative_loss_km2": "sum",
    }).round(4)
    summary.columns = ["_".join(c) for c in summary.columns]
    summary.to_csv(summary_path)
    print(f"Wrote annual summary to {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
