#!/usr/bin/env python3
"""Aggregate ACLED conflict events to BOLD land cells by period.

Input: downloaded ACLED CSV from download_acled.py.
Output: zero-filled cell-period panel with event counts and fatalities by type.

Supported variants:
  baseline_100km_year
  test_50km_year
  test_50km_quarter

ACLED event types:
  Battles, Explosions/Remote violence, Violence against civilians,
  Protests, Riots, Strategic developments
"""


from __future__ import annotations


from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _path in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from panel_variants import get_variant


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
RAW_DIR = PROJECT_ROOT / "Data" / "raw" / "acled"
OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "acled"
LAND_CELLS = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_grid100_land_cells.csv"
EQUAL_AREA_CRS = "EPSG:6933"

DEFAULT_START_YEAR = 2005
DEFAULT_END_YEAR = 2024

EVENT_TYPE_SLUGS = {
    "Battles": "battles",
    "Explosions/Remote violence": "explosions",
    "Violence against civilians": "vac",
    "Protests": "protests",
    "Riots": "riots",
    "Strategic developments": "strategic",
}


def find_default_input() -> Path | None:
    candidates = sorted(RAW_DIR.glob("acled_events_*.csv"))
    if len(candidates) == 1:
        return candidates[0]
    candidates = sorted(RAW_DIR.glob("*.csv"))
    if len(candidates) == 1:
        return candidates[0]
    return None


def load_acled(path: Path) -> pd.DataFrame:
    print(f"Reading ACLED: {path}", flush=True)
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    required = {"year", "event_date", "latitude", "longitude", "event_type", "fatalities"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"ACLED file missing columns: {missing}")
    return df


def load_land_cells(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing land-cell file: {path}")
    land = pd.read_csv(path, dtype={"cell_id": str})
    required = {"cell_id", "cell_x", "cell_y"}
    missing = sorted(required - set(land.columns))
    if missing:
        raise ValueError(f"Land-cell file missing columns: {missing}")
    return land


def clean_events(
    events: pd.DataFrame,
    start_year: int,
    end_year: int,
    freq: str,
    cell_km: float,
    land_ids: set[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    work = events.copy()
    stats = {"raw_events": len(work)}

    work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work["latitude"] = pd.to_numeric(work["latitude"], errors="coerce")
    work["longitude"] = pd.to_numeric(work["longitude"], errors="coerce")
    work["fatalities"] = pd.to_numeric(work["fatalities"], errors="coerce").fillna(0)

    work = work[work["year"].between(start_year, end_year)].copy()
    stats["events_in_year_window"] = len(work)

    if freq == "quarter":
        work["event_date"] = pd.to_datetime(work["event_date"], errors="coerce")
        work = work.dropna(subset=["event_date"]).copy()
        work["quarter"] = work["event_date"].dt.quarter.astype(int)
        stats["events_with_valid_quarter"] = len(work)

    valid_coord = work["latitude"].between(-90, 90) & work["longitude"].between(-180, 180)
    work = work[valid_coord].copy()
    stats["events_with_valid_coordinates"] = len(work)

    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    cell_m = cell_km * 1000
    ex, ey = transformer.transform(work["longitude"].to_numpy(), work["latitude"].to_numpy())
    cell_x = np.floor(np.array(ex) / cell_m).astype(int)
    cell_y = np.floor(np.array(ey) / cell_m).astype(int)
    work["cell_x"] = cell_x
    work["cell_y"] = cell_y
    work["cell_id"] = np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))
    work["year"] = work["year"].astype(int)
    work["fatalities"] = work["fatalities"].round().astype(int)

    in_land = work["cell_id"].isin(land_ids)
    stats["events_in_land_cells"] = int(in_land.sum())
    stats["events_outside_land_cells"] = int((~in_land).sum())
    return work[in_land].copy(), stats


def build_skeleton(land: pd.DataFrame, start_year: int, end_year: int, freq: str) -> pd.DataFrame:
    years = pd.DataFrame({"year": list(range(start_year, end_year + 1)), "key": 1})
    cells = land[["cell_id", "cell_x", "cell_y"]].drop_duplicates().assign(key=1)
    if freq == "year":
        return cells.merge(years, on="key").drop(columns="key")
    quarters = pd.DataFrame({"quarter": [1, 2, 3, 4], "key2": 1})
    return (
        cells.merge(years, on="key")
        .drop(columns="key")
        .assign(key2=1)
        .merge(quarters, on="key2")
        .drop(columns="key2")
    )


def aggregate(events: pd.DataFrame, skeleton: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate events into cell-period counts and fatalities."""
    keys = ["cell_id", "year"] + (["quarter"] if freq == "quarter" else [])
    out = skeleton.copy()

    total = events.groupby(keys).agg(
        acled_events_all=("event_type", "size"),
        acled_fatalities_all=("fatalities", "sum"),
    ).reset_index()
    out = out.merge(total, on=keys, how="left")

    for etype, slug in EVENT_TYPE_SLUGS.items():
        sub = events[events["event_type"] == etype]
        agg = sub.groupby(keys).agg(
            events=("event_type", "size"),
            fatalities=("fatalities", "sum"),
        ).reset_index()
        agg.columns = keys + [f"acled_events_{slug}", f"acled_fatalities_{slug}"]
        out = out.merge(agg, on=keys, how="left")

    fill_cols = [c for c in out.columns if c.startswith("acled_")]
    out[fill_cols] = out[fill_cols].fillna(0).astype(int)

    out["acled_any_all"] = (out["acled_events_all"] > 0).astype(int)
    out["acled_any_violent"] = (
        (out.get("acled_events_battles", 0) +
         out.get("acled_events_explosions", 0) +
         out.get("acled_events_vac", 0)) > 0
    ).astype(int)

    return out


def write_summary(path: Path, raw: pd.DataFrame, events: pd.DataFrame, out: pd.DataFrame, stats: dict[str, int]) -> None:
    rows: list[tuple[str, object]] = list(stats.items())
    rows.extend(
        [
            ("output_rows", len(out)),
            ("output_cells", out["cell_id"].nunique()),
            ("output_years", out["year"].nunique()),
            ("output_quarters", out["quarter"].nunique() if "quarter" in out.columns else ""),
            ("cell_periods_with_any_event", int((out["acled_any_all"] > 0).sum())),
            ("cell_periods_with_violent_event", int((out["acled_any_violent"] > 0).sum())),
            ("acled_events_all", int(out["acled_events_all"].sum())),
            ("acled_fatalities_all", int(out["acled_fatalities_all"].sum())),
        ]
    )
    for etype, slug in EVENT_TYPE_SLUGS.items():
        rows.append((f"raw_{slug}_events", int((raw["event_type"] == etype).sum())))
        rows.append((f"panel_{slug}_events", int(out[f"acled_events_{slug}"].sum())))
        rows.append((f"panel_{slug}_fatalities", int(out[f"acled_fatalities_{slug}"].sum())))

    pd.DataFrame(rows, columns=["metric", "value"]).to_csv(path, index=False)
    print(f"Wrote summary to {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--acled", type=Path, help="Path to ACLED CSV")
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--cell-km", type=float, default=100)
    parser.add_argument("--land-cells", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--outdir", type=Path, default=OUTDIR)
    args = parser.parse_args()

    variant = get_variant(args.variant) if args.variant else None
    freq = "year"
    if variant is not None:
        freq = variant.freq
        args.cell_km = variant.cell_km
        args.start_year = variant.start_year
        args.end_year = min(variant.end_year, DEFAULT_END_YEAR)
        args.outdir = variant.regressors_root / "acled"

    period = "cell_quarter" if freq == "quarter" else "cell_year"
    land_cells_path = args.land_cells or (variant.land_cells_csv if variant else LAND_CELLS)
    output_path = args.output or args.outdir / (
        f"acled_{int(args.cell_km)}km_{period}_{args.start_year}_{args.end_year}.csv"
    )
    summary_path = args.summary or output_path.with_name(output_path.stem + "_summary.csv")

    acled_path = args.acled or find_default_input()
    if acled_path is None:
        print(f"No ACLED CSV found in {RAW_DIR}")
        print("Run: python3 Scripts/download/download_acled.py --token YOUR_TOKEN")
        return 1

    acled = load_acled(acled_path)
    if variant is not None:
        print(f"Variant: {variant.name} ({variant.suffix})", flush=True)
    print(f"  Raw events: {len(acled):,}")

    land = load_land_cells(land_cells_path)
    print(f"Land cells: {len(land):,}")

    events_in, stats = clean_events(
        acled,
        args.start_year,
        args.end_year,
        freq,
        args.cell_km,
        set(land["cell_id"]),
    )
    print(f"  Events in land cells: {len(events_in):,}")
    print(f"  Events outside: {stats['events_outside_land_cells']:,}")

    skeleton = build_skeleton(land, args.start_year, args.end_year, freq)
    print(f"Skeleton: {len(skeleton):,} cell-period rows")

    out = aggregate(events_in, skeleton, freq)

    args.outdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    print(f"\nWrote {len(out):,} rows to {output_path}")

    print("\nAudit:")
    print(f"  cell_periods_with_any_event: {(out['acled_any_all'] > 0).sum():,}")
    print(f"  total_events: {out['acled_events_all'].sum():,}")
    print(f"  total_fatalities: {out['acled_fatalities_all'].sum():,}")
    for etype, slug in EVENT_TYPE_SLUGS.items():
        col = f"acled_events_{slug}"
        print(f"  {etype}: {out[col].sum():,}")

    write_summary(summary_path, acled, events_in, out, stats)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
