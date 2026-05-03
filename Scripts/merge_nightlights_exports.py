#!/usr/bin/env python3
"""Merge harmonized nighttime lights GEE export into a cell-year panel.

Run after downloading the Earth Engine export to Data/regressors/nightlights/.
Uses the Li, Zhou et al. (2020) harmonized NTL dataset — a single consistent
scale across 2005-2023 (no sensor dummy needed).

Reference: Li et al. (2020) "A harmonized global nighttime light dataset
1992-2018" Scientific Data 7(1).
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "regressors" / "nightlights"
EXHIBITS_DIR = PROJECT_ROOT / "Exhibits" / "data"


def main() -> int:
    ntl_path = DATA_DIR / "harmonized_nightlights_100km.csv"
    panel_path = EXHIBITS_DIR / "bold_grid100_cell_year_panel_collection_2005_2025.csv"

    for p in [ntl_path, panel_path]:
        if not p.exists():
            print(f"Missing: {p}")
            return 1

    print(f"Loading harmonized NTL: {ntl_path}")
    ntl = pd.read_csv(ntl_path)
    print(f"  {len(ntl):,} cell-year rows ({ntl['year'].min()}-{ntl['year'].max()})")

    print(f"Loading BOLD panel for cell list: {panel_path}")
    panel = pd.read_csv(panel_path)
    cells = panel[["cell_id", "cell_x", "cell_y"]].drop_duplicates()
    print(f"  {len(cells):,} unique cells")

    years = sorted(ntl["year"].unique())
    print(f"Years: {min(years)}-{max(years)}")

    skeleton = cells.assign(key=1).merge(
        pd.DataFrame({"year": years, "key": 1}), on="key"
    ).drop(columns="key")
    print(f"Skeleton: {len(skeleton):,} cell-year rows")

    skeleton = skeleton.merge(
        ntl[["cell_id", "year", "ntl_mean"]],
        on=["cell_id", "year"],
        how="left",
    )

    skeleton["ntl_mean"] = skeleton["ntl_mean"].fillna(0)
    skeleton["log1p_ntl"] = np.log1p(skeleton["ntl_mean"])
    skeleton["any_light"] = (skeleton["ntl_mean"] > 0).astype(int)

    skeleton = skeleton.sort_values(["cell_id", "year"])
    skeleton["L1_log1p_ntl"] = skeleton.groupby("cell_id")["log1p_ntl"].shift(1)

    print("\nSummary:")
    print(f"  Mean NTL: {skeleton['ntl_mean'].mean():.3f}")
    print(f"  Median NTL: {skeleton['ntl_mean'].median():.3f}")
    print(f"  Max NTL: {skeleton['ntl_mean'].max():.2f}")
    print(f"  Cells with any light: {skeleton.groupby('cell_id')['any_light'].max().sum():,}")

    out_path = DATA_DIR / "nightlights_100km_panel.csv"
    skeleton.to_csv(out_path, index=False)
    print(f"\nWrote {len(skeleton):,} rows to {out_path}")

    summary_path = DATA_DIR / "nightlights_100km_panel_summary.csv"
    summary = skeleton.groupby("year").agg(
        ntl_mean_mean=("ntl_mean", "mean"),
        ntl_mean_median=("ntl_mean", "median"),
        log1p_ntl_mean=("log1p_ntl", "mean"),
        any_light_share=("any_light", "mean"),
        n_cells=("cell_id", "count"),
    ).round(4)
    summary.to_csv(summary_path)
    print(f"Wrote summary to {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
