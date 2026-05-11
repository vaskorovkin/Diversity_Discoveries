#!/usr/bin/env python3
"""Merge nighttime lights GEE export into a cell-time panel.

Run after downloading the Earth Engine export to Data/regressors/nightlights/.
Uses the Li, Zhou et al. (2020) harmonized NTL dataset — a single consistent
scale across 2005-2023 (no sensor dummy needed).

Quarterly variants use the annual harmonized export expanded to four quarters.
This preserves 2005-2023 coverage, but the resulting NTL regressor is not truly
quarter-resolved and is labeled with source frequency.

Reference: Li et al. (2020) "A harmonized global nighttime light dataset
1992-2018" Scientific Data 7(1).
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

from panel_variants import get_variant

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "regressors" / "nightlights"
EXHIBITS_DIR = PROJECT_ROOT / "Exhibits" / "data"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--ntl-path", type=Path, default=None)
    parser.add_argument("--panel-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    freq = "year"
    if variant is not None:
        freq = variant.freq
        data_dir = variant.regressors_root / "nightlights"
        ntl_path = args.ntl_path or data_dir / f"harmonized_nightlights_{int(variant.cell_km)}km.csv"
        panel_path = args.panel_path or variant.bold_panel_csv
        suffix = "quarter_panel" if freq == "quarter" else "panel"
        out_path = args.output or data_dir / f"nightlights_{int(variant.cell_km)}km_{suffix}.csv"
        print(f"Variant: {variant.name} ({variant.suffix})")
    else:
        data_dir = DATA_DIR
        ntl_path = args.ntl_path or DATA_DIR / "harmonized_nightlights_100km.csv"
        panel_path = args.panel_path or EXHIBITS_DIR / "bold_grid100_cell_year_panel_collection_2005_2025.csv"
        out_path = args.output or DATA_DIR / "nightlights_100km_panel.csv"

    for p in [ntl_path, panel_path]:
        if not p.exists():
            print(f"Missing: {p}")
            return 1

    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading NTL: {ntl_path}")
    ntl = pd.read_csv(ntl_path)
    time_label = "cell-quarter" if freq == "quarter" else "cell-year"
    print(f"  {len(ntl):,} {time_label} rows ({ntl['year'].min()}-{ntl['year'].max()})")

    print(f"Loading BOLD panel for cell list: {panel_path}")
    panel = pd.read_csv(panel_path)
    cells = panel[["cell_id", "cell_x", "cell_y"]].drop_duplicates()
    print(f"  {len(cells):,} unique cells")

    years = sorted(panel["year"].unique() if freq == "quarter" else ntl["year"].unique())
    print(f"Years: {min(years)}-{max(years)}")

    skeleton = cells.assign(key=1).merge(
        pd.DataFrame({"year": years, "key": 1}), on="key"
    ).drop(columns="key")
    if freq == "quarter":
        skeleton = skeleton.assign(key=1).merge(
            pd.DataFrame({"quarter": [1, 2, 3, 4], "key": 1}), on="key"
        ).drop(columns="key")
        print(f"Skeleton: {len(skeleton):,} cell-quarter rows")
        sort_cols = ["cell_id", "year", "quarter"]
    else:
        print(f"Skeleton: {len(skeleton):,} cell-year rows")
        sort_cols = ["cell_id", "year"]

    skeleton = skeleton.merge(
        ntl[["cell_id", "year", "ntl_mean"]],
        on=["cell_id", "year"],
        how="left",
    )
    skeleton["ntl_mean"] = skeleton["ntl_mean"].fillna(0)
    skeleton["ntl_source_freq"] = "annual_harmonized"

    skeleton["log1p_ntl"] = np.log1p(skeleton["ntl_mean"])
    skeleton["any_light"] = np.where(skeleton["ntl_mean"].notna(), (skeleton["ntl_mean"] > 0).astype(int), np.nan)

    skeleton = skeleton.sort_values(sort_cols)
    skeleton["L1_log1p_ntl"] = skeleton.groupby("cell_id")["log1p_ntl"].shift(1)

    print("\nSummary:")
    print(f"  Mean NTL: {skeleton['ntl_mean'].mean():.3f}")
    print(f"  Median NTL: {skeleton['ntl_mean'].median():.3f}")
    print(f"  Max NTL: {skeleton['ntl_mean'].max():.2f}")
    print(f"  Cells with any light: {skeleton.groupby('cell_id')['any_light'].max().sum():,}")

    skeleton.to_csv(out_path, index=False)
    print(f"\nWrote {len(skeleton):,} rows to {out_path}")

    summary_path = out_path.with_name(out_path.stem + "_summary.csv")
    group_cols = ["year"] + (["quarter"] if freq == "quarter" else [])
    summary = skeleton.groupby(group_cols).agg(
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
