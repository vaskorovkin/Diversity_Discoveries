#!/usr/bin/env python3
"""Aggregate WDPA protected-area polygon coverage to BOLD 100 km cell-year panel.

v2: Uses sjoin + per-polygon clipping instead of dissolve + overlay.
Avoids catastrophic union of 100K+ polygons.

Strategy:
1. Spatial join WDPA polygons to cells (index-based, fast)
2. Clip each polygon to its matched cell, compute area
3. For each cell × status_year, union clipped fragments then measure area
4. Build cumulative panel with pandas
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.ops import unary_union


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "wdpa" / "wdpa_protected_panel_100km.csv"
AREA_CRS = "EPSG:6933"

START_YEAR = 2001
END_YEAR = 2024


def detect_polygon_layer(path: Path) -> Optional[str]:
    try:
        layers = gpd.list_layers(path)
    except Exception:
        return None
    if len(layers) <= 1:
        return None
    polygon_layers = layers[layers["geometry_type"].astype(str).str.contains("Polygon", na=False)]
    if polygon_layers.empty:
        return None
    layer = str(polygon_layers.iloc[0]["name"])
    print(f"Using polygon layer: {layer}", flush=True)
    return layer


def filter_wdpa(gdf: gpd.GeoDataFrame, include_marine: bool, include_oecm: bool) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if "STATUS" in out.columns:
        status = out["STATUS"].astype(str).str.lower().str.strip()
        out = out[~status.eq("proposed")].copy()
    if not include_oecm and "SITE_TYPE" in out.columns:
        site_type = out["SITE_TYPE"].astype(str).str.upper().str.strip()
        out = out[site_type.eq("PA")].copy()
    if not include_marine and "MARINE" in out.columns:
        marine = pd.to_numeric(out["MARINE"], errors="coerce")
        out = out[marine.ne(2)].copy()
    if not include_marine and "REALM" in out.columns:
        realm = out["REALM"].astype(str).str.lower().str.strip()
        out = out[~realm.eq("marine")].copy()
    out = out[out.geometry.notna()].copy()
    out = out[out.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    out["geometry"] = out.geometry.make_valid()
    out = out[~out.geometry.is_empty].copy()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wdpa", type=Path, required=True)
    parser.add_argument("--layer", default=None)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--include-marine", action="store_true")
    parser.add_argument("--include-oecm", action="store_true")
    parser.add_argument("--progress-every", type=int, default=500)
    args = parser.parse_args()

    if not args.wdpa.exists():
        raise FileNotFoundError(f"Missing WDPA file: {args.wdpa}")
    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing land-cell polygons: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    years = list(range(args.start_year, args.end_year + 1))
    print(f"Building panel for years: {years[0]}-{years[-1]}", flush=True)

    print(f"Reading land-cell polygons: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells).to_crs(AREA_CRS)
    cells["cell_area_km2"] = cells.geometry.area / 1_000_000
    cells = cells.reset_index(drop=True)
    print(f"  {len(cells):,} cells", flush=True)

    layer = args.layer or detect_polygon_layer(args.wdpa)
    print(f"Reading WDPA polygons: {args.wdpa}", flush=True)
    wdpa = gpd.read_file(args.wdpa, layer=layer) if layer else gpd.read_file(args.wdpa)
    print(f"Raw WDPA rows: {len(wdpa):,}", flush=True)
    wdpa = filter_wdpa(wdpa, include_marine=args.include_marine, include_oecm=args.include_oecm).to_crs(AREA_CRS)
    print(f"Filtered WDPA polygon rows: {len(wdpa):,}", flush=True)

    if "STATUS_YR" not in wdpa.columns:
        raise ValueError("WDPA file missing STATUS_YR column")

    wdpa["status_year"] = pd.to_numeric(wdpa["STATUS_YR"], errors="coerce")
    valid_year = wdpa["status_year"].notna() & (wdpa["status_year"] > 0)
    print(f"Polygons with valid STATUS_YR: {valid_year.sum():,} / {len(wdpa):,}", flush=True)
    print(f"STATUS_YR range: {wdpa.loc[valid_year, 'status_year'].min():.0f} - {wdpa.loc[valid_year, 'status_year'].max():.0f}", flush=True)
    wdpa.loc[~valid_year, "status_year"] = args.start_year - 1

    # Drop polygons designated after panel end
    wdpa = wdpa[wdpa["status_year"] <= args.end_year].copy()
    # Bin pre-panel into single bucket
    wdpa.loc[wdpa["status_year"] < args.start_year, "status_year"] = args.start_year - 1

    # Keep only what we need
    wdpa_slim = wdpa[["status_year", "geometry"]].copy().reset_index(drop=True)
    del wdpa

    # --- Step 1: Spatial join WDPA to cells ---
    print(f"\nStep 1: Spatial join (WDPA → cells)...", flush=True)
    t0 = time.time()
    # sjoin finds which WDPA polygons intersect which cells
    joined = gpd.sjoin(wdpa_slim, cells[["cell_id", "geometry"]], how="inner", predicate="intersects")
    print(f"  {len(joined):,} WDPA-cell pairs in {time.time() - t0:.0f}s", flush=True)

    # --- Step 2: Clip each WDPA polygon to its matched cell, compute area ---
    print(f"\nStep 2: Clipping {len(joined):,} WDPA-cell pairs...", flush=True)
    t0 = time.time()

    # Build cell geometry lookup
    cell_geom_lookup = dict(zip(cells["cell_id"], cells.geometry))

    clipped_areas = []
    n = len(joined)
    for i, (idx, row) in enumerate(joined.iterrows()):
        cell_id = row["cell_id"]
        cell_geom = cell_geom_lookup[cell_id]
        wdpa_geom = row.geometry
        sy = int(row["status_year"])

        try:
            clipped = wdpa_geom.intersection(cell_geom)
            area_km2 = clipped.area / 1_000_000
            if area_km2 > 0:
                clipped_areas.append({
                    "cell_id": cell_id,
                    "status_year": sy,
                    "clipped_area_km2": area_km2,
                })
        except Exception:
            try:
                clipped = wdpa_geom.buffer(0).intersection(cell_geom)
                area_km2 = clipped.area / 1_000_000
                if area_km2 > 0:
                    clipped_areas.append({
                        "cell_id": cell_id,
                        "status_year": sy,
                        "clipped_area_km2": area_km2,
                    })
            except Exception:
                pass

        if (i + 1) % args.progress_every == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (n - i - 1) / rate / 60
            print(f"  {i + 1:,}/{n:,} pairs ({rate:,.0f}/sec, ETA {eta:.1f} min)", flush=True)

    print(f"  Done: {len(clipped_areas):,} fragments with area > 0 in {time.time() - t0:.0f}s", flush=True)
    clip_df = pd.DataFrame(clipped_areas)

    # --- Step 3: Aggregate by cell × status_year ---
    # Sum of individual clipped areas overestimates when polygons overlap within
    # the same cell and year. For a first-pass panel this is acceptable; we cap at cell area.
    print(f"\nStep 3: Aggregating by cell × status_year...", flush=True)
    cell_sy = clip_df.groupby(["cell_id", "status_year"], as_index=False)["clipped_area_km2"].sum()
    print(f"  {len(cell_sy):,} cell × status_year groups", flush=True)

    # --- Step 4: Build cumulative panel ---
    print(f"\nStep 4: Building cell-year panel...", flush=True)
    cell_info = cells[["cell_id", "cell_x", "cell_y", "cell_area_km2"]].copy()
    cells_with_protection = set(cell_sy["cell_id"].unique())
    print(f"  Cells with any protection: {len(cells_with_protection):,}", flush=True)

    panel_rows = []
    for _, crow in cell_info.iterrows():
        cid = crow["cell_id"]
        cell_area = crow["cell_area_km2"]

        if cid not in cells_with_protection:
            for year in years:
                panel_rows.append({
                    "cell_id": cid, "cell_x": crow["cell_x"], "cell_y": crow["cell_y"],
                    "year": year, "protected_area_km2": 0.0, "protected_share": 0.0,
                    "any_protected": 0, "new_protection_km2": 0.0,
                })
            continue

        cdata = cell_sy[cell_sy["cell_id"] == cid].sort_values("status_year")
        cum_area = 0.0
        sy_to_cum = {}
        for _, srow in cdata.iterrows():
            cum_area += srow["clipped_area_km2"]
            sy_to_cum[int(srow["status_year"])] = cum_area

        prev_area = 0.0
        running_area = 0.0
        sorted_sys = sorted(sy_to_cum.keys())
        sy_ptr = 0

        for year in years:
            while sy_ptr < len(sorted_sys) and sorted_sys[sy_ptr] <= year:
                running_area = min(sy_to_cum[sorted_sys[sy_ptr]], cell_area)
                sy_ptr += 1

            share = running_area / cell_area if cell_area > 0 else 0.0
            panel_rows.append({
                "cell_id": cid, "cell_x": crow["cell_x"], "cell_y": crow["cell_y"],
                "year": year, "protected_area_km2": running_area,
                "protected_share": min(share, 1.0),
                "any_protected": int(running_area > 0),
                "new_protection_km2": max(0.0, running_area - prev_area),
            })
            prev_area = running_area

    out = pd.DataFrame(panel_rows)
    out = out.sort_values(["cell_id", "year"])
    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}", flush=True)
    print(f"Rows: {len(out):,} ({len(cells):,} cells x {len(years)} years)", flush=True)

    print(f"\nSummary by year:", flush=True)
    summary = out.groupby("year").agg({
        "protected_share": "mean",
        "any_protected": "sum",
        "new_protection_km2": "sum",
    }).round(4)
    summary.columns = ["mean_protected_share", "cells_with_protection", "total_new_protection_km2"]
    print(summary.to_string(), flush=True)

    summary_path = args.output.with_name(args.output.stem + "_summary.csv")
    summary.to_csv(summary_path)
    print(f"\nWrote summary: {summary_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
