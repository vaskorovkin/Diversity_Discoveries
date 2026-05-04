#!/usr/bin/env python3
"""Aggregate UCDP GED conflict events to BOLD 100 km land cells by year.

Input is a downloaded UCDP GED CSV. Output is a zero-filled cell-year panel with
raw conflict levels only; logs and lags should be generated in Stata.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
RAW_DIR = PROJECT_ROOT / "Data" / "raw" / "ucdp"
OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "ucdp"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.csv"
EQUAL_AREA_CRS = "EPSG:6933"

DEFAULT_START_YEAR = 2005
DEFAULT_END_YEAR = 2024
DEFAULT_OUTPUT = OUTDIR / "ucdp_ged_100km_cell_year_2005_2024.csv"

TYPE_LABELS = {
    1: "state",
    2: "nonstate",
    3: "onesided",
}

REQUIRED_COLUMNS = [
    "year",
    "type_of_violence",
    "where_prec",
    "latitude",
    "longitude",
    "best",
    "low",
    "high",
    "deaths_civilians",
]


def find_default_input() -> Path | None:
    candidates = sorted(RAW_DIR.glob("*.csv"))
    if len(candidates) == 1:
        return candidates[0]
    return None


def load_ged(path: Path) -> pd.DataFrame:
    print(f"Reading UCDP GED: {path}", flush=True)
    ged = pd.read_csv(path, low_memory=False)
    ged.columns = [str(c).strip().lower() for c in ged.columns]
    missing = sorted(set(REQUIRED_COLUMNS) - set(ged.columns))
    if missing:
        raise ValueError(f"UCDP GED file is missing required columns: {missing}")
    return ged


def load_land_cells(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing land-cell file: {path}. Run Scripts/05_cell_correlations.py first.")
    land = pd.read_csv(path, dtype={"cell_id": str, "iso_a3": str})
    required = {"cell_id", "cell_x", "cell_y"}
    missing = sorted(required - set(land.columns))
    if missing:
        raise ValueError(f"Land-cell file is missing columns: {missing}")
    return land


def build_skeleton(land: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    years = pd.DataFrame({"year": list(range(start_year, end_year + 1)), "key": 1})
    cells = land[["cell_id", "cell_x", "cell_y"]].drop_duplicates().assign(key=1)
    skeleton = cells.merge(years, on="key").drop(columns="key")
    return skeleton


def clean_events(ged: pd.DataFrame, start_year: int, end_year: int, cell_km: float, land_ids: set[str]) -> tuple[pd.DataFrame, dict[str, int]]:
    work = ged.copy()
    stats = {"raw_events": len(work)}

    for col in ["year", "type_of_violence", "where_prec", "latitude", "longitude", "best", "low", "high", "deaths_civilians"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    work = work[work["year"].between(start_year, end_year)].copy()
    stats["events_in_year_window"] = len(work)

    valid_coord = work["latitude"].between(-90, 90) & work["longitude"].between(-180, 180)
    work = work[valid_coord].copy()
    stats["events_with_valid_coordinates"] = len(work)

    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    cell_m = cell_km * 1000
    x, y = transformer.transform(work["longitude"].to_numpy(), work["latitude"].to_numpy())
    cell_x = np.floor(x / cell_m).astype(int)
    cell_y = np.floor(y / cell_m).astype(int)
    work["cell_x"] = cell_x
    work["cell_y"] = cell_y
    work["cell_id"] = np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))
    work["year"] = work["year"].astype(int)

    in_land = work["cell_id"].isin(land_ids)
    stats["events_in_land_cells"] = int(in_land.sum())
    stats["events_outside_land_cells"] = int((~in_land).sum())
    work = work[in_land].copy()

    for col in ["best", "low", "high", "deaths_civilians"]:
        work[col] = work[col].fillna(0)
    work["precise"] = work["where_prec"].isin([1, 2])
    work["type_label"] = work["type_of_violence"].map(TYPE_LABELS).fillna("unknown")
    return work, stats


def aggregate(events: pd.DataFrame) -> pd.DataFrame:
    keys = ["cell_id", "year"]
    out = events.groupby(keys).size().rename("ucdp_events_all").reset_index()
    sums = events.groupby(keys)[["best", "low", "high", "deaths_civilians"]].sum().reset_index()
    sums = sums.rename(
        columns={
            "best": "ucdp_best_all",
            "low": "ucdp_low_all",
            "high": "ucdp_high_all",
            "deaths_civilians": "ucdp_deaths_civilians_all",
        }
    )
    out = out.merge(sums, on=keys, how="outer")

    for type_code, label in TYPE_LABELS.items():
        sub = events[events["type_of_violence"] == type_code]
        out = merge_subset(out, sub, keys, label)

    precise = events[events["precise"]]
    out = merge_subset(out, precise, keys, "precise")
    for type_code, label in TYPE_LABELS.items():
        sub = precise[precise["type_of_violence"] == type_code]
        out = merge_subset(out, sub, keys, f"{label}_precise")

    return out


def merge_subset(base: pd.DataFrame, sub: pd.DataFrame, keys: list[str], suffix: str) -> pd.DataFrame:
    if sub.empty:
        return base
    counts = sub.groupby(keys).size().rename(f"ucdp_events_{suffix}").reset_index()
    sums = sub.groupby(keys)[["best", "low", "high", "deaths_civilians"]].sum().reset_index()
    sums = sums.rename(
        columns={
            "best": f"ucdp_best_{suffix}",
            "low": f"ucdp_low_{suffix}",
            "high": f"ucdp_high_{suffix}",
            "deaths_civilians": f"ucdp_deaths_civilians_{suffix}",
        }
    )
    return base.merge(counts, on=keys, how="outer").merge(sums, on=keys, how="outer")


def finalize(skeleton: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    panel = skeleton.merge(counts, on=["cell_id", "year"], how="left")
    ensure_output_columns(panel)
    value_cols = [c for c in panel.columns if c.startswith("ucdp_")]
    panel[value_cols] = panel[value_cols].fillna(0)
    for col in value_cols:
        panel[col] = panel[col].round().astype(int)

    event_cols = [c for c in value_cols if c.startswith("ucdp_events_")]
    for col in event_cols:
        any_col = col.replace("ucdp_events_", "ucdp_any_")
        panel[any_col] = (panel[col] > 0).astype(int)
    return panel


def ensure_output_columns(panel: pd.DataFrame) -> None:
    suffixes = ["all", "state", "nonstate", "onesided", "precise", "state_precise", "nonstate_precise", "onesided_precise"]
    measures = ["events", "best", "low", "high", "deaths_civilians"]
    for suffix in suffixes:
        for measure in measures:
            col = f"ucdp_{measure}_{suffix}"
            if col not in panel.columns:
                panel[col] = 0


def write_summary(path: Path, ged: pd.DataFrame, events: pd.DataFrame, panel: pd.DataFrame, stats: dict[str, int]) -> None:
    rows: list[tuple[str, object]] = list(stats.items())
    rows.extend(
        [
            ("output_rows", len(panel)),
            ("output_cells", panel["cell_id"].nunique()),
            ("output_years", panel["year"].nunique()),
            ("cell_years_with_ucdp_events_all", int((panel["ucdp_events_all"] > 0).sum())),
            ("ucdp_events_all", int(panel["ucdp_events_all"].sum())),
            ("ucdp_best_all", int(panel["ucdp_best_all"].sum())),
            ("ucdp_deaths_civilians_all", int(panel["ucdp_deaths_civilians_all"].sum())),
        ]
    )
    for code, label in TYPE_LABELS.items():
        rows.append((f"raw_type_{label}_events", int((ged["type_of_violence"] == code).sum())))
        if f"ucdp_events_{label}" in panel:
            rows.append((f"panel_{label}_events", int(panel[f"ucdp_events_{label}"].sum())))
            rows.append((f"panel_{label}_best", int(panel[f"ucdp_best_{label}"].sum())))

    if not events.empty:
        for prec, count in events["where_prec"].value_counts(dropna=False).sort_index().items():
            rows.append((f"where_prec_{prec}", int(count)))

    pd.DataFrame(rows, columns=["metric", "value"]).to_csv(path, index=False)
    print(f"Wrote summary: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None, help="Path to downloaded UCDP GED CSV.")
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--cell-km", type=float, default=100)
    args = parser.parse_args()

    input_path = args.input or find_default_input()
    if input_path is None:
        print(f"No input CSV found. Download UCDP GED CSV to {RAW_DIR}/ or pass --input PATH.")
        print("UCDP downloads: https://ucdp.uu.se/downloads/")
        return 1

    OUTDIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = args.summary or args.output.with_name(args.output.stem + "_summary.csv")

    ged = load_ged(input_path)
    land = load_land_cells(args.land_cells)
    skeleton = build_skeleton(land, args.start_year, args.end_year)
    events, stats = clean_events(ged, args.start_year, args.end_year, args.cell_km, set(land["cell_id"]))
    print(f"Events in land cells, {args.start_year}-{args.end_year}: {len(events):,}", flush=True)
    counts = aggregate(events)
    panel = finalize(skeleton, counts)
    panel.to_csv(args.output, index=False)
    print(f"Wrote UCDP cell-year panel: {args.output}", flush=True)
    write_summary(summary_path, ged, events, panel, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
