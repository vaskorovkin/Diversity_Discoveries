#!/usr/bin/env python3
"""Merge Hansen GEE exports with full cell panel.

Run after downloading Earth Engine exports to Data/regressors/hansen/.
Creates a complete cell-year or cell-quarter panel with forest loss variables.

Hansen Global Forest Change reports loss year, not loss month. For quarterly
variants this script repeats annual Hansen values across quarters and labels
the source frequency explicitly.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

from panel_variants import get_variant

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "regressors" / "hansen"
EXHIBITS_DIR = PROJECT_ROOT / "Exhibits" / "data"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--baseline-path", type=Path, default=None)
    parser.add_argument("--annual-path", type=Path, default=None)
    parser.add_argument("--panel-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    freq = "year"
    if variant is not None:
        freq = variant.freq
        data_dir = variant.regressors_root / "hansen"
        cell_tag = int(variant.cell_km)
        baseline_path = args.baseline_path or data_dir / f"hansen_baseline_forest_{cell_tag}km.csv"
        annual_path = args.annual_path or data_dir / f"hansen_forest_loss_{cell_tag}km_annual.csv"
        panel_path = args.panel_path or variant.bold_panel_csv
        suffix = "quarter_panel" if freq == "quarter" else "panel"
        out_path = args.output or data_dir / f"hansen_forest_loss_{cell_tag}km_{suffix}.csv"
        print(f"Variant: {variant.name} ({variant.suffix})")
    else:
        data_dir = DATA_DIR
        baseline_path = args.baseline_path or DATA_DIR / "hansen_baseline_forest_100km.csv"
        annual_path = args.annual_path or DATA_DIR / "hansen_forest_loss_100km_annual.csv"
        panel_path = args.panel_path or EXHIBITS_DIR / "bold_grid100_cell_year_panel_collection_2005_2025.csv"
        out_path = args.output or DATA_DIR / "hansen_forest_loss_100km_panel.csv"

    # Check for required files
    for p in [baseline_path, annual_path, panel_path]:
        if not p.exists():
            print(f"Missing: {p}")
            return 1

    data_dir.mkdir(parents=True, exist_ok=True)

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

    # Create full cell-year skeleton first; quarterly values are expanded after
    # annual cumulative and lag variables are computed.
    annual_panel = cells.assign(key=1).merge(
        pd.DataFrame({"year": years, "key": 1}),
        on="key"
    ).drop(columns="key")
    print(f"Skeleton: {len(annual_panel):,} cell-year rows")

    # Merge baseline
    annual_panel = annual_panel.merge(
        baseline[["cell_id", "baseline_forest_km2"]],
        on="cell_id",
        how="left"
    )

    # Merge annual loss
    annual_panel = annual_panel.merge(
        annual[["cell_id", "year", "forest_loss_km2"]],
        on=["cell_id", "year"],
        how="left"
    )

    # Fill missing values (cells with no forest or no loss)
    annual_panel["forest_loss_km2"] = annual_panel["forest_loss_km2"].fillna(0)
    annual_panel["baseline_forest_km2"] = annual_panel["baseline_forest_km2"].fillna(0)

    # Compute derived variables
    annual_panel["forest_loss_share"] = (
        annual_panel["forest_loss_km2"] / annual_panel["baseline_forest_km2"]
    ).fillna(0).replace([float("inf"), float("-inf")], 0)

    # Cumulative loss
    annual_panel = annual_panel.sort_values(["cell_id", "year"])
    annual_panel["cumulative_loss_km2"] = annual_panel.groupby("cell_id")["forest_loss_km2"].cumsum()
    annual_panel["cumulative_loss_share"] = (
        annual_panel["cumulative_loss_km2"] / annual_panel["baseline_forest_km2"]
    ).fillna(0).replace([float("inf"), float("-inf")], 0)

    # Lagged loss (1-year and 2-year)
    annual_panel["L1_forest_loss_km2"] = annual_panel.groupby("cell_id")["forest_loss_km2"].shift(1)
    annual_panel["L2_forest_loss_km2"] = annual_panel.groupby("cell_id")["forest_loss_km2"].shift(2)
    annual_panel["L1_forest_loss_share"] = annual_panel.groupby("cell_id")["forest_loss_share"].shift(1)
    annual_panel["L2_forest_loss_share"] = annual_panel.groupby("cell_id")["forest_loss_share"].shift(2)
    annual_panel["hansen_source_freq"] = "annual"

    if freq == "quarter":
        skeleton = annual_panel.assign(key=1).merge(
            pd.DataFrame({"quarter": [1, 2, 3, 4], "key": 1}),
            on="key",
        ).drop(columns="key")
        skeleton = skeleton.sort_values(["cell_id", "year", "quarter"])
        print(f"Expanded to quarterly skeleton: {len(skeleton):,} cell-quarter rows")
    else:
        skeleton = annual_panel

    # Summary stats
    print("\nSummary:")
    print(f"  Cells with forest: {(skeleton['baseline_forest_km2'] > 0).groupby(skeleton['cell_id']).first().sum():,}")
    print(f"  Cell-years with loss: {(skeleton['forest_loss_km2'] > 0).sum():,}")
    print(f"  Total baseline forest: {skeleton.groupby('cell_id')['baseline_forest_km2'].first().sum():,.0f} km²")
    print(f"  Total forest loss 2001-2023: {skeleton['forest_loss_km2'].sum():,.0f} km²")

    # Save
    skeleton.to_csv(out_path, index=False)
    print(f"\nWrote {len(skeleton):,} rows to {out_path}")

    # Also save summary
    summary_path = out_path.with_name(out_path.stem + "_summary.csv")
    summary = annual_panel.groupby("year").agg({
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
