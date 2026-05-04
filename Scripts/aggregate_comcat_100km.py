#!/usr/bin/env python3
"""Aggregate USGS ComCat earthquake events to BOLD 100 km land cells by year."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
RAW_DIR = PROJECT_ROOT / "Data" / "raw" / "comcat"
OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "comcat"
LAND_CELLS = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_grid100_land_cells.csv"
OLD_LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.csv"
EQUAL_AREA_CRS = "EPSG:6933"

DEFAULT_START_YEAR = 2005
DEFAULT_END_YEAR = 2025

REQUIRED_COLUMNS = ["time", "latitude", "longitude", "depth", "mag", "id", "type", "status"]


def find_default_input() -> Path | None:
    candidates = sorted(RAW_DIR.glob("comcat_earthquakes_*.csv"))
    if candidates:
        return candidates[-1]
    return None


def load_comcat(path: Path) -> pd.DataFrame:
    print(f"Reading ComCat: {path}", flush=True)
    df = pd.read_csv(path, low_memory=False)
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"ComCat file missing required columns: {missing}")
    return df


def load_land_cells(path: Path) -> pd.DataFrame:
    actual_path = path
    if not actual_path.exists() and path == LAND_CELLS and OLD_LAND_CELLS.exists():
        actual_path = OLD_LAND_CELLS
    if not actual_path.exists():
        raise FileNotFoundError(f"Missing land-cell file: {path}")
    print(f"Reading land cells: {actual_path}", flush=True)
    land = pd.read_csv(actual_path, dtype={"cell_id": str})
    needed = {"cell_id", "cell_x", "cell_y"}
    missing = sorted(needed - set(land.columns))
    if missing:
        raise ValueError(f"Land-cell file missing columns: {missing}")
    return land


def build_skeleton(land: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    years = pd.DataFrame({"year": list(range(start_year, end_year + 1)), "key": 1})
    cells = land[["cell_id", "cell_x", "cell_y"]].drop_duplicates().assign(key=1)
    return cells.merge(years, on="key").drop(columns="key")


def clean_events(
    df: pd.DataFrame,
    start_year: int,
    end_year: int,
    min_magnitude: float,
    land_ids: set[str],
    reviewed_only: bool,
) -> tuple[pd.DataFrame, dict[str, int]]:
    work = df.copy()
    stats = {"raw_rows": len(work)}

    work["time"] = pd.to_datetime(work["time"], errors="coerce", utc=True)
    work = work.dropna(subset=["time"]).copy()
    work["year"] = work["time"].dt.year.astype(int)
    work = work[work["year"].between(start_year, end_year)].copy()
    stats["rows_in_year_window"] = len(work)

    for col in ["latitude", "longitude", "depth", "mag"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    work = work[work["type"].fillna("").eq("earthquake")].copy()
    stats["rows_after_type_filter"] = len(work)

    if reviewed_only:
        work = work[work["status"].fillna("").eq("reviewed")].copy()
        stats["rows_after_reviewed_filter"] = len(work)

    work = work[work["mag"].ge(min_magnitude).fillna(False)].copy()
    stats["rows_after_magnitude_filter"] = len(work)

    valid_coord = work["latitude"].between(-90, 90) & work["longitude"].between(-180, 180)
    work = work[valid_coord].copy()
    stats["rows_with_valid_coordinates"] = len(work)

    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    x, y = transformer.transform(work["longitude"].to_numpy(), work["latitude"].to_numpy())
    cell_x = np.floor(x / 100_000).astype(int)
    cell_y = np.floor(y / 100_000).astype(int)
    work["cell_x"] = cell_x
    work["cell_y"] = cell_y
    work["cell_id"] = np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))

    in_land = work["cell_id"].isin(land_ids)
    stats["rows_in_land_cells"] = int(in_land.sum())
    stats["rows_outside_land_cells"] = int((~in_land).sum())
    work = work[in_land].copy()

    work["mag_ge_6"] = work["mag"].ge(6.0)
    work["mag_ge_7"] = work["mag"].ge(7.0)
    work["depth_le_70"] = work["depth"].le(70).fillna(False)
    return work, stats


def aggregate(events: pd.DataFrame) -> pd.DataFrame:
    return (
        events.groupby(["cell_id", "year"])
        .agg(
            comcat_events_all=("id", "size"),
            comcat_events_m6=("mag_ge_6", "sum"),
            comcat_events_m7=("mag_ge_7", "sum"),
            comcat_shallow_events=("depth_le_70", "sum"),
            comcat_max_mag=("mag", "max"),
            comcat_mean_mag=("mag", "mean"),
            comcat_mean_depth_km=("depth", "mean"),
        )
        .reset_index()
    )


def finalize(skeleton: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    panel = skeleton.merge(counts, on=["cell_id", "year"], how="left")
    count_cols = [
        "comcat_events_all",
        "comcat_events_m6",
        "comcat_events_m7",
        "comcat_shallow_events",
    ]
    for col in count_cols:
        panel[col] = panel[col].fillna(0).round().astype(int)
    panel["comcat_any_all"] = (panel["comcat_events_all"] > 0).astype(int)
    panel["comcat_max_mag"] = panel["comcat_max_mag"].fillna(0)
    return panel


def write_summary(path: Path, panel: pd.DataFrame, stats: dict[str, int]) -> None:
    rows: list[tuple[str, object]] = list(stats.items())
    rows.extend(
        [
            ("output_rows", len(panel)),
            ("output_cells", panel["cell_id"].nunique()),
            ("output_years", panel["year"].nunique()),
            ("cell_years_with_quakes", int((panel["comcat_any_all"] > 0).sum())),
            ("events_all", int(panel["comcat_events_all"].sum())),
            ("events_m6", int(panel["comcat_events_m6"].sum())),
            ("events_m7", int(panel["comcat_events_m7"].sum())),
        ]
    )
    pd.DataFrame(rows, columns=["metric", "value"]).to_csv(path, index=False)
    print(f"Wrote summary: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTDIR / f"comcat_100km_cell_year_{DEFAULT_START_YEAR}_{DEFAULT_END_YEAR}.csv",
    )
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--min-magnitude", type=float, default=4.5)
    parser.add_argument("--reviewed-only", action="store_true")
    args = parser.parse_args()

    input_path = args.input or find_default_input()
    if input_path is None:
        print(f"No ComCat CSV found in {RAW_DIR}")
        print("Run: python3 Scripts/download_comcat_earthquakes.py")
        return 1

    OUTDIR.mkdir(parents=True, exist_ok=True)
    summary_path = args.summary or args.output.with_name(args.output.stem + "_summary.csv")

    events = load_comcat(input_path)
    land = load_land_cells(args.land_cells)
    skeleton = build_skeleton(land, args.start_year, args.end_year)
    events, stats = clean_events(
        events,
        start_year=args.start_year,
        end_year=args.end_year,
        min_magnitude=args.min_magnitude,
        land_ids=set(land["cell_id"]),
        reviewed_only=args.reviewed_only,
    )
    print(f"Events in land cells, {args.start_year}-{args.end_year}: {len(events):,}", flush=True)

    counts = aggregate(events)
    panel = finalize(skeleton, counts)
    panel.to_csv(args.output, index=False)
    print(f"Wrote ComCat cell-year panel: {args.output}", flush=True)
    write_summary(summary_path, panel, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
