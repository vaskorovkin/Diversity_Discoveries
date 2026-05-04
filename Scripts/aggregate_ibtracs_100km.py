#!/usr/bin/env python3
"""Aggregate IBTrACS cyclone track points to BOLD 100 km land cells by year."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
RAW_DIR = PROJECT_ROOT / "Data" / "raw" / "ibtracs"
OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "ibtracs"
LAND_CELLS = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_grid100_land_cells.csv"
OLD_LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.csv"
EQUAL_AREA_CRS = "EPSG:6933"

DEFAULT_START_YEAR = 2005
DEFAULT_END_YEAR = 2025

REQUIRED_COLUMNS = [
    "SID",
    "SEASON",
    "ISO_TIME",
    "NATURE",
    "LAT",
    "LON",
    "WMO_WIND",
    "WMO_PRES",
    "TRACK_TYPE",
    "DIST2LAND",
]


def find_default_input() -> Path | None:
    candidates = sorted(RAW_DIR.glob("ibtracs_*_list_v04r01.csv"))
    if len(candidates) == 1:
        return candidates[0]
    for path in candidates:
        if "since1980" in path.name:
            return path
    return None


def load_ibtracs(path: Path) -> pd.DataFrame:
    print(f"Reading IBTrACS: {path}", flush=True)
    df = pd.read_csv(path, skiprows=[1], low_memory=False, na_values=[" ", ""])
    df.columns = [str(c).strip().upper() for c in df.columns]
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"IBTrACS file missing required columns: {missing}")
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


def clean_points(
    df: pd.DataFrame,
    start_year: int,
    end_year: int,
    land_ids: set[str],
    main_track_only: bool,
) -> tuple[pd.DataFrame, dict[str, int]]:
    work = df.copy()
    stats = {"raw_rows": len(work)}

    work["ISO_TIME"] = pd.to_datetime(work["ISO_TIME"], errors="coerce", utc=True)
    work = work.dropna(subset=["ISO_TIME"]).copy()
    work["year"] = work["ISO_TIME"].dt.year.astype(int)
    work = work[work["year"].between(start_year, end_year)].copy()
    stats["rows_in_year_window"] = len(work)

    track_type = work["TRACK_TYPE"].fillna("").astype(str).str.strip().str.lower()
    if main_track_only:
        keep_track = track_type.eq("main")
    else:
        keep_track = ~track_type.str.contains("spur", na=False)
    work = work[keep_track].copy()
    stats["rows_after_track_filter"] = len(work)

    for col in ["LAT", "LON", "WMO_WIND", "WMO_PRES", "DIST2LAND"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    valid_coord = work["LAT"].between(-90, 90) & work["LON"].between(-180, 180)
    work = work[valid_coord].copy()
    stats["rows_with_valid_coordinates"] = len(work)

    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    x, y = transformer.transform(work["LON"].to_numpy(), work["LAT"].to_numpy())
    cell_x = np.floor(x / 100_000).astype(int)
    cell_y = np.floor(y / 100_000).astype(int)
    work["cell_x"] = cell_x
    work["cell_y"] = cell_y
    work["cell_id"] = np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))

    in_land = work["cell_id"].isin(land_ids)
    stats["rows_in_land_cells"] = int(in_land.sum())
    stats["rows_outside_land_cells"] = int((~in_land).sum())
    work = work[in_land].copy()

    work["wind_34kt"] = work["WMO_WIND"].ge(34).fillna(False)
    work["wind_64kt"] = work["WMO_WIND"].ge(64).fillna(False)
    return work, stats


def subset_counts(sub: pd.DataFrame, suffix: str) -> pd.DataFrame:
    if sub.empty:
        return pd.DataFrame(columns=["cell_id", "year"])
    return (
        sub.groupby(["cell_id", "year"])
        .agg(
            **{
                f"ibtracs_points_{suffix}": ("SID", "size"),
                f"ibtracs_storms_{suffix}": ("SID", pd.Series.nunique),
            }
        )
        .reset_index()
    )


def aggregate(points: pd.DataFrame) -> pd.DataFrame:
    agg = (
        points.groupby(["cell_id", "year"])
        .agg(
            ibtracs_points_all=("SID", "size"),
            ibtracs_storms_all=("SID", pd.Series.nunique),
            ibtracs_max_wmo_wind_kts=("WMO_WIND", "max"),
            ibtracs_min_dist2land_km=("DIST2LAND", "min"),
        )
        .reset_index()
    )
    for subset, suffix in [
        (points[points["wind_34kt"]], "34kt"),
        (points[points["wind_64kt"]], "64kt"),
    ]:
        agg = agg.merge(subset_counts(subset, suffix), on=["cell_id", "year"], how="left")
    return agg


def finalize(skeleton: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    panel = skeleton.merge(counts, on=["cell_id", "year"], how="left")
    for col in [
        "ibtracs_points_all",
        "ibtracs_storms_all",
        "ibtracs_points_34kt",
        "ibtracs_storms_34kt",
        "ibtracs_points_64kt",
        "ibtracs_storms_64kt",
    ]:
        if col not in panel.columns:
            panel[col] = 0
    count_cols = [c for c in panel.columns if c.startswith("ibtracs_points_") or c.startswith("ibtracs_storms_")]
    panel[count_cols] = panel[count_cols].fillna(0).round().astype(int)
    panel["ibtracs_any_all"] = (panel["ibtracs_points_all"] > 0).astype(int)
    panel["ibtracs_any_34kt"] = (panel["ibtracs_points_34kt"] > 0).astype(int)
    panel["ibtracs_any_64kt"] = (panel["ibtracs_points_64kt"] > 0).astype(int)
    panel["ibtracs_max_wmo_wind_kts"] = panel["ibtracs_max_wmo_wind_kts"].fillna(0)
    return panel


def write_summary(path: Path, panel: pd.DataFrame, stats: dict[str, int]) -> None:
    rows: list[tuple[str, object]] = list(stats.items())
    rows.extend(
        [
            ("output_rows", len(panel)),
            ("output_cells", panel["cell_id"].nunique()),
            ("output_years", panel["year"].nunique()),
            ("cell_years_with_cyclone", int((panel["ibtracs_any_all"] > 0).sum())),
            ("track_points_all", int(panel["ibtracs_points_all"].sum())),
            ("storms_all", int(panel["ibtracs_storms_all"].sum())),
            ("track_points_34kt", int(panel.get("ibtracs_points_34kt", pd.Series(dtype=float)).sum())),
            ("track_points_64kt", int(panel.get("ibtracs_points_64kt", pd.Series(dtype=float)).sum())),
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
        default=OUTDIR / f"ibtracs_100km_cell_year_{DEFAULT_START_YEAR}_{DEFAULT_END_YEAR}.csv",
    )
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--main-track-only", action="store_true")
    args = parser.parse_args()

    input_path = args.input or find_default_input()
    if input_path is None:
        print(f"No IBTrACS CSV found in {RAW_DIR}")
        print("Run: python3 Scripts/download_ibtracs.py")
        return 1

    OUTDIR.mkdir(parents=True, exist_ok=True)
    summary_path = args.summary or args.output.with_name(args.output.stem + "_summary.csv")

    points = load_ibtracs(input_path)
    land = load_land_cells(args.land_cells)
    skeleton = build_skeleton(land, args.start_year, args.end_year)
    points, stats = clean_points(
        points,
        start_year=args.start_year,
        end_year=args.end_year,
        land_ids=set(land["cell_id"]),
        main_track_only=args.main_track_only,
    )
    print(f"Track points in land cells, {args.start_year}-{args.end_year}: {len(points):,}", flush=True)

    counts = aggregate(points)
    panel = finalize(skeleton, counts)
    panel.to_csv(args.output, index=False)
    print(f"Wrote IBTrACS cell-year panel: {args.output}", flush=True)
    write_summary(summary_path, panel, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
