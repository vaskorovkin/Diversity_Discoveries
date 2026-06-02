#!/usr/bin/env python3
"""Country-level BOLD sampling statistics: richness gaps, protected area, conflict.

Produces three figures:
  fig_country_richness_vs_sampling.png  -- scatter: richness vs records/km², coloured by conflict
  fig_country_protected_vs_sampling.png -- scatter: protected area vs records/km², coloured by conflict
  fig_country_top20_sampling.png        -- horizontal bar: top-20 countries by total records

All figures are written locally (Exhibits/figures) and published into the
merged deck (merged_beamer/Figures) via mirror_to_codex_figures().
"""

from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _p in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pipeline_utils import (
    PROJECT_ROOT,
    EXHIBIT_FIGURES,
    ensure_output_dirs,
    mirror_to_codex_figures,
)

PANEL_DTA = PROJECT_ROOT / "Data" / "analysis" / "BOLD_regressor_panel.dta"
SAMPLE_YEARS = (2005, 2023)

LOAD_COLS = [
    "country_name", "iso_a3", "year",
    "total_records", "cell_area_km2",
    "richness_total", "wdpa_protected_share",
    "ucdp_any_all", "msa_overall", "foreign_share",
]

# Always label these ISO codes on scatter plots (narrative-relevant countries)
LABEL_ISO = {
    "BRA", "COL", "PER", "ECU", "PNG", "COD", "IDN", "MEX",
    "CRI", "USA", "CAN", "IND", "AUS", "ZAF", "ETH", "SOM",
    "AFG", "SYR", "MMR", "UKR", "CMR", "VEN", "NGA", "PHL",
}


# ---------------------------------------------------------------------------
# Data prep
# ---------------------------------------------------------------------------

def build_country_df(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel[(panel.year >= SAMPLE_YEARS[0]) & (panel.year <= SAMPLE_YEARS[1])].copy()
    grp = df.groupby(["country_name", "iso_a3"])
    agg = grp.agg(
        total_records=("total_records", "sum"),
        sum_area=("cell_area_km2", "sum"),   # sum over cell-years; divide by n_years below
        richness_total=("richness_total", "mean"),
        protected_share=("wdpa_protected_share", "mean"),
        conflict_rate=("ucdp_any_all", "mean"),
        msa=("msa_overall", "mean"),
        foreign_share=("foreign_share", "mean"),
    ).reset_index()
    # Each cell appears once per year → country land area = sum_area / n_unique_years
    n_years_per_country = grp["year"].nunique().reset_index(name="n_years")
    agg = agg.merge(n_years_per_country, on=["country_name", "iso_a3"])
    agg["land_area_km2"] = agg["sum_area"] / agg["n_years"]
    agg["records_per_km2"] = agg["total_records"] / agg["land_area_km2"].replace(0, float("nan"))
    return agg.dropna(subset=["records_per_km2", "richness_total"])


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _conflict_scatter_setup(ax, cdf, x, y):
    """Shared scatter layer coloured by conflict rate; returns ScalarMappable for colorbar."""
    vmax = float(np.quantile(cdf.conflict_rate.dropna(), 0.95))
    norm = mcolors.Normalize(vmin=0, vmax=max(vmax, 1e-6))
    sc = ax.scatter(
        x, y,
        c=cdf.conflict_rate, cmap="YlOrRd", norm=norm,
        s=55, alpha=0.78, edgecolors="none", zorder=3,
    )
    return sc, norm


def plot_richness_vs_sampling(cdf: pd.DataFrame, output: Path) -> None:
    """Scatter: species richness vs log(1 + records/km²), coloured by conflict rate."""
    fig, ax = plt.subplots(figsize=(11, 7))
    x = cdf.richness_total
    y = np.log1p(cdf.records_per_km2)
    sc, _ = _conflict_scatter_setup(ax, cdf, x, y)
    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Mean fraction of cell-years with conflict (UCDP)", fontsize=9)

    for _, row in cdf.iterrows():
        if row.iso_a3 in LABEL_ISO:
            ax.annotate(
                row.iso_a3,
                (row.richness_total, np.log1p(row.records_per_km2)),
                fontsize=7, color="#333333",
                xytext=(4, 2), textcoords="offset points",
            )

    ax.set_xlabel("Mean species richness (IUCN mammals + amphibians + reptiles)", fontsize=10)
    ax.set_ylabel("log(1 + BOLD records / km²)  [2005–2023]", fontsize=10)
    ax.set_title(
        "Biodiversity richness vs. BOLD sampling intensity by country\n"
        "Colour = mean conflict rate (UCDP armed conflict events)",
        fontsize=11,
    )
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def plot_protected_vs_sampling(cdf: pd.DataFrame, output: Path) -> None:
    """Scatter: protected area share vs log(1 + records/km²), coloured by conflict rate."""
    fig, ax = plt.subplots(figsize=(10, 6.5))
    x = cdf.protected_share * 100
    y = np.log1p(cdf.records_per_km2)
    sc, _ = _conflict_scatter_setup(ax, cdf, x, y)
    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Mean conflict rate (UCDP)", fontsize=9)

    for _, row in cdf.iterrows():
        if row.iso_a3 in LABEL_ISO:
            ax.annotate(
                row.iso_a3,
                (row.protected_share * 100, np.log1p(row.records_per_km2)),
                fontsize=7, color="#333333",
                xytext=(4, 2), textcoords="offset points",
            )

    ax.set_xlabel("Mean protected area share (%, WDPA)", fontsize=10)
    ax.set_ylabel("log(1 + BOLD records / km²)  [2005–2023]", fontsize=10)
    ax.set_title(
        "Protected area coverage vs. BOLD sampling intensity by country\n"
        "Colour = mean conflict rate",
        fontsize=11,
    )
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def plot_top20(cdf: pd.DataFrame, output: Path) -> None:
    """Horizontal bar: top-20 countries by total BOLD records (2005–2023)."""
    top = cdf.nlargest(20, "total_records").sort_values("total_records")
    vmax = float(top.conflict_rate.max()) or 1e-9
    bar_colors = plt.cm.YlOrRd(top.conflict_rate.fillna(0) / vmax)

    fig, ax = plt.subplots(figsize=(9, 7))
    bars = ax.barh(top.country_name, top.total_records / 1e6, color=bar_colors, edgecolor="none")
    ax.set_xlabel("Total BOLD records, millions  (2005–2023)", fontsize=10)
    ax.set_title(
        "Top 20 countries by BOLD sampling volume\n"
        "Colour: darker red = higher mean conflict rate (UCDP)",
        fontsize=11,
    )
    ax.grid(True, alpha=0.2, axis="x")
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ensure_output_dirs()

    print(f"Loading panel from {PANEL_DTA} ...", flush=True)
    panel = pd.read_stata(PANEL_DTA, columns=LOAD_COLS)
    print(f"Loaded {len(panel):,} rows. Collapsing to country level ...", flush=True)

    cdf = build_country_df(panel)
    print(f"Countries in sample ({SAMPLE_YEARS[0]}–{SAMPLE_YEARS[1]}): {len(cdf)}", flush=True)

    out_richness  = EXHIBIT_FIGURES / "fig_country_richness_vs_sampling.png"
    out_protected = EXHIBIT_FIGURES / "fig_country_protected_vs_sampling.png"
    out_top20     = EXHIBIT_FIGURES / "fig_country_top20_sampling.png"

    print("Plotting richness vs sampling ...", flush=True)
    plot_richness_vs_sampling(cdf, out_richness)

    print("Plotting protected area vs sampling ...", flush=True)
    plot_protected_vs_sampling(cdf, out_protected)

    print("Plotting top-20 bar chart ...", flush=True)
    plot_top20(cdf, out_top20)

    for path in (out_richness, out_protected, out_top20):
        mirror_to_codex_figures(path)
        print(f"Wrote + mirrored: {path.name}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
