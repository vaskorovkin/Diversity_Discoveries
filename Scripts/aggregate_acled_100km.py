#!/usr/bin/env python3
"""Aggregate ACLED conflict events to BOLD 100 km land cells by year.

Follows the same pattern as aggregate_ucdp_ged_100km.py.
Input: downloaded ACLED CSV from download_acled.py.
Output: zero-filled cell-year panel with event counts and fatalities by type.

ACLED event types:
  Battles, Explosions/Remote violence, Violence against civilians,
  Protests, Riots, Strategic developments
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
RAW_DIR = PROJECT_ROOT / "Data" / "raw" / "acled"
OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "acled"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.csv"
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
    return None


def load_acled(path: Path) -> pd.DataFrame:
    print(f"Reading ACLED: {path}", flush=True)
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    required = {"year", "latitude", "longitude", "event_type", "fatalities"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"ACLED file missing columns: {missing}")
    return df


def load_land_cells(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing land-cell file: {path}")
    land = pd.read_csv(path, dtype={"cell_id": str})
    return land


def assign_cells(events: pd.DataFrame, land: pd.DataFrame) -> pd.DataFrame:
    """Assign each event to the nearest 100km land cell."""
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)

    ex, ey = transformer.transform(
        events["longitude"].values, events["latitude"].values
    )

    cell_size = 100_000
    events = events.copy()
    events["cell_x"] = np.floor(np.array(ex) / cell_size).astype(int)
    events["cell_y"] = np.floor(np.array(ey) / cell_size).astype(int)

    cell_set = set(zip(land["cell_x"], land["cell_y"]))
    mask = [
        (cx, cy) in cell_set
        for cx, cy in zip(events["cell_x"], events["cell_y"])
    ]
    events_in = events.loc[mask].copy()

    cell_lookup = land.set_index(["cell_x", "cell_y"])["cell_id"]
    events_in["cell_id"] = events_in.apply(
        lambda r: cell_lookup.get((r["cell_x"], r["cell_y"]), None), axis=1
    )
    events_in = events_in.dropna(subset=["cell_id"])

    return events_in


def build_skeleton(land: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    years = pd.DataFrame({"year": list(range(start_year, end_year + 1)), "key": 1})
    cells = land[["cell_id", "cell_x", "cell_y"]].drop_duplicates().assign(key=1)
    skeleton = cells.merge(years, on="key").drop(columns="key")
    return skeleton


def aggregate(events: pd.DataFrame, skeleton: pd.DataFrame) -> pd.DataFrame:
    """Aggregate events into cell-year counts and fatalities."""
    out = skeleton.copy()

    total = events.groupby(["cell_id", "year"]).agg(
        acled_events_all=("event_type", "size"),
        acled_fatalities_all=("fatalities", "sum"),
    ).reset_index()
    out = out.merge(total, on=["cell_id", "year"], how="left")

    for etype, slug in EVENT_TYPE_SLUGS.items():
        sub = events[events["event_type"] == etype]
        agg = sub.groupby(["cell_id", "year"]).agg(
            events=("event_type", "size"),
            fatalities=("fatalities", "sum"),
        ).reset_index()
        agg.columns = ["cell_id", "year", f"acled_events_{slug}", f"acled_fatalities_{slug}"]
        out = out.merge(agg, on=["cell_id", "year"], how="left")

    fill_cols = [c for c in out.columns if c.startswith("acled_")]
    out[fill_cols] = out[fill_cols].fillna(0).astype(int)

    out["acled_any_all"] = (out["acled_events_all"] > 0).astype(int)
    out["acled_any_violent"] = (
        (out.get("acled_events_battles", 0) +
         out.get("acled_events_explosions", 0) +
         out.get("acled_events_vac", 0)) > 0
    ).astype(int)

    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--acled", type=Path, help="Path to ACLED CSV")
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--outdir", type=Path, default=OUTDIR)
    args = parser.parse_args()

    acled_path = args.acled or find_default_input()
    if acled_path is None:
        print(f"No ACLED CSV found in {RAW_DIR}")
        print("Run: python3 Scripts/download_acled.py --key YOUR_KEY --email YOUR_EMAIL")
        return 1

    acled = load_acled(acled_path)
    print(f"  Raw events: {len(acled):,}")

    acled = acled[(acled["year"] >= args.start_year) & (acled["year"] <= args.end_year)]
    print(f"  Events in {args.start_year}-{args.end_year}: {len(acled):,}")

    acled = acled.dropna(subset=["latitude", "longitude"])
    print(f"  Events with coordinates: {len(acled):,}")

    acled["fatalities"] = pd.to_numeric(acled["fatalities"], errors="coerce").fillna(0).astype(int)

    land = load_land_cells(LAND_CELLS)
    print(f"Land cells: {len(land):,}")

    print("Assigning events to cells ...", flush=True)
    events_in = assign_cells(acled, land)
    print(f"  Events in land cells: {len(events_in):,}")
    print(f"  Events outside: {len(acled) - len(events_in):,}")

    skeleton = build_skeleton(land, args.start_year, args.end_year)
    print(f"Skeleton: {len(skeleton):,} cell-year rows")

    out = aggregate(events_in, skeleton)

    args.outdir.mkdir(parents=True, exist_ok=True)
    outpath = args.outdir / f"acled_100km_cell_year_{args.start_year}_{args.end_year}.csv"
    out.to_csv(outpath, index=False)
    print(f"\nWrote {len(out):,} rows to {outpath}")

    print("\nAudit:")
    print(f"  cell_years_with_any_event: {(out['acled_any_all'] > 0).sum():,}")
    print(f"  total_events: {out['acled_events_all'].sum():,}")
    print(f"  total_fatalities: {out['acled_fatalities_all'].sum():,}")
    for etype, slug in EVENT_TYPE_SLUGS.items():
        col = f"acled_events_{slug}"
        print(f"  {etype}: {out[col].sum():,}")

    summary_path = args.outdir / f"acled_100km_cell_year_{args.start_year}_{args.end_year}_summary.csv"
    summary = out.groupby("year").agg(
        events_all=("acled_events_all", "sum"),
        fatalities_all=("acled_fatalities_all", "sum"),
        cells_with_events=("acled_any_all", "sum"),
    )
    summary.to_csv(summary_path)
    print(f"Wrote summary to {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
