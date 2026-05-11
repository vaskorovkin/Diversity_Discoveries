#!/usr/bin/env python3
"""Merge MODIS burned area GEE exports with full cell panel.

Run after downloading Earth Engine exports to Data/regressors/modis/.
Creates a complete cell-year panel with burned area variables.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

from panel_variants import get_variant

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "regressors" / "modis"
EXHIBITS_DIR = PROJECT_ROOT / "Exhibits" / "data"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--annual-path", type=Path, default=None)
    parser.add_argument("--panel-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    if variant is not None:
        data_dir = variant.regressors_root / "modis"
        panel_path = args.panel_path or variant.bold_panel_csv
        if variant.freq == "quarter":
            annual_path = args.annual_path or data_dir / f"modis_burned_area_{int(variant.cell_km)}km_quarterly.csv"
            out_path = args.output or data_dir / f"modis_burned_area_{int(variant.cell_km)}km_quarter_panel.csv"
        else:
            annual_path = args.annual_path or data_dir / f"modis_burned_area_{int(variant.cell_km)}km_annual.csv"
            out_path = args.output or data_dir / f"modis_burned_area_{int(variant.cell_km)}km_panel.csv"
        print(f"Variant: {variant.name} ({variant.suffix})")
    else:
        data_dir = DATA_DIR
        annual_path = args.annual_path or DATA_DIR / "modis_burned_area_100km_annual.csv"
        panel_path = args.panel_path or EXHIBITS_DIR / "bold_grid100_cell_year_panel_collection_2005_2025.csv"
        out_path = args.output or DATA_DIR / "modis_burned_area_100km_panel.csv"

    # Check for required files
    for p in [annual_path, panel_path]:
        if not p.exists():
            print(f"Missing: {p}")
            return 1

    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading burned area: {annual_path}")
    annual = pd.read_csv(annual_path)
    print(f"  {len(annual):,} rows")

    print(f"Loading BOLD panel for cell list: {panel_path}")
    panel = pd.read_csv(panel_path)
    cells = panel[["cell_id", "cell_x", "cell_y"]].drop_duplicates()
    print(f"  {len(cells):,} unique cells")

    if variant is not None and variant.freq == "quarter":
        periods = panel[["cell_id", "cell_x", "cell_y", "year", "quarter"]].drop_duplicates()
        skeleton = periods.copy()
        print(f"Skeleton: {len(skeleton):,} cell-quarter rows")
        skeleton = skeleton.merge(
            annual[["cell_id", "year", "quarter", "burned_area_km2", "any_burned"]],
            on=["cell_id", "year", "quarter"],
            how="left"
        )
    else:
        years = list(range(2001, 2024))
        print(f"Years: {years[0]}-{years[-1]}")
        skeleton = cells.assign(key=1).merge(
            pd.DataFrame({"year": years, "key": 1}),
            on="key"
        ).drop(columns="key")
        print(f"Skeleton: {len(skeleton):,} cell-year rows")
        skeleton = skeleton.merge(
            annual[["cell_id", "year", "burned_area_km2", "any_burned"]],
            on=["cell_id", "year"],
            how="left"
        )

    # Fill missing values (cells with no fire)
    skeleton["burned_area_km2"] = skeleton["burned_area_km2"].fillna(0)
    skeleton["any_burned"] = skeleton["any_burned"].fillna(0).astype(int)

    sort_cols = ["cell_id", "year"] + (["quarter"] if "quarter" in skeleton.columns else [])
    skeleton = skeleton.sort_values(sort_cols)
    skeleton["cumulative_burned_km2"] = skeleton.groupby("cell_id")["burned_area_km2"].cumsum()

    # Lagged burned area over the active time frequency.
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
    skeleton.to_csv(out_path, index=False)
    print(f"\nWrote {len(skeleton):,} rows to {out_path}")

    # Also save summary
    summary_path = out_path.with_name(out_path.stem + "_summary.csv")
    group_cols = ["year"] + (["quarter"] if "quarter" in skeleton.columns else [])
    summary = skeleton.groupby(group_cols).agg({
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
