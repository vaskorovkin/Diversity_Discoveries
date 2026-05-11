#!/usr/bin/env python3
"""Shared grid/time variants for baseline and spatial-time tests.

This module centralizes the canonical naming and output roots for panel
builders. The goal is to let upstream scripts support:

- the stable baseline: 100 km + yearly
- test path 1: 50 km + yearly
- test path 2: 50 km + quarterly

without scattering path logic across many scripts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline_utils import PROJECT_ROOT


def cell_label(cell_km: float) -> str:
    return f"{cell_km:g}".replace(".", "p")


@dataclass(frozen=True)
class PanelVariant:
    name: str
    cell_km: float
    freq: str
    start_year: int
    end_year: int
    root_tag: str

    @property
    def suffix(self) -> str:
        return f"{cell_label(self.cell_km)}km_{self.freq}"

    @property
    def is_baseline(self) -> bool:
        return self.root_tag == "baseline"

    @property
    def processed_root(self) -> Path:
        if self.is_baseline:
            return PROJECT_ROOT / "Data" / "processed"
        return PROJECT_ROOT / "Data" / "processed" / self.root_tag

    @property
    def regressors_root(self) -> Path:
        if self.is_baseline:
            return PROJECT_ROOT / "Data" / "regressors"
        return PROJECT_ROOT / "Data" / "regressors" / self.root_tag

    @property
    def analysis_root(self) -> Path:
        if self.is_baseline:
            return PROJECT_ROOT / "Data" / "analysis"
        return PROJECT_ROOT / "Data" / "analysis" / self.root_tag

    @property
    def bold_root(self) -> Path:
        return self.processed_root / "bold"

    @property
    def gbif_root(self) -> Path:
        return self.processed_root / "gbif"

    @property
    def discovery_root(self) -> Path:
        return self.processed_root / "discovery"

    @property
    def land_cells_csv(self) -> Path:
        return self.bold_root / f"bold_grid{cell_label(self.cell_km)}_land_cells.csv"

    @property
    def land_cells_geojson(self) -> Path:
        return self.bold_root / f"bold_grid{cell_label(self.cell_km)}_land_cells.geojson"

    @property
    def grid_counts_csv(self) -> Path:
        return self.bold_root / f"bold_grid{cell_label(self.cell_km)}_counts_by_kingdom.csv"

    @property
    def bold_panel_stem(self) -> str:
        period = "cell_year_panel" if self.freq == "year" else "cell_quarter_panel"
        return (
            f"bold_grid{cell_label(self.cell_km)}_{period}_collection_"
            f"{self.start_year}_{self.end_year}"
        )

    @property
    def bold_panel_csv(self) -> Path:
        return self.bold_root / f"{self.bold_panel_stem}.csv"

    @property
    def bold_panel_summary_csv(self) -> Path:
        return self.bold_root / f"{self.bold_panel_stem}_summary.csv"

    @property
    def analysis_panel_dta(self) -> Path:
        freq_tag = "year" if self.freq == "year" else "quarter"
        return self.analysis_root / f"BOLD_regressor_panel_{cell_label(self.cell_km)}km_{freq_tag}.dta"


VARIANTS: dict[str, PanelVariant] = {
    "baseline_100km_year": PanelVariant(
        name="baseline_100km_year",
        cell_km=100,
        freq="year",
        start_year=2005,
        end_year=2025,
        root_tag="baseline",
    ),
    "test_50km_year": PanelVariant(
        name="test_50km_year",
        cell_km=50,
        freq="year",
        start_year=2005,
        end_year=2025,
        root_tag="tests_spatial_time",
    ),
    "test_50km_quarter": PanelVariant(
        name="test_50km_quarter",
        cell_km=50,
        freq="quarter",
        start_year=2005,
        end_year=2025,
        root_tag="tests_spatial_time",
    ),
}


def get_variant(name: str) -> PanelVariant:
    try:
        return VARIANTS[name]
    except KeyError as exc:
        valid = ", ".join(sorted(VARIANTS))
        raise KeyError(f"Unknown panel variant '{name}'. Valid options: {valid}") from exc
