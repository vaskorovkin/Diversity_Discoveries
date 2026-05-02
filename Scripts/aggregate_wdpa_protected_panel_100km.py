#!/usr/bin/env python3
"""Aggregate WDPA protected-area polygon coverage to BOLD 100 km cell-year panel.

Uses STATUS_YR to build a time-varying panel: for each cell-year, computes
protected share using only polygons with STATUS_YR <= year.

Strategy: batch-overlay WDPA × cells once, compute each fragment's area,
then use pandas cumulative sums by STATUS_YR — no per-year geometry ops.

Limitations:
- Uses designation year, not exact polygon expansion history
- Current polygon boundaries are applied backward in time
- Downgrading/degazettement not captured (would need PADDD or historical WDPA)
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import numpy as np


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "wdpa" / "wdpa_protected_panel_100km.csv"
AREA_CRS = "EPSG:6933"

START_YEAR = 2001
END_YEAR = 2024

BATCH_SIZE = 500


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
    parser.add_argument("--wdpa", type=Path, required=True, help="Local WDPA polygon GPKG/SHP path.")
    parser.add_argument("--layer", default=None, help="Optional layer name for GDB/GPKG inputs.")
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--include-marine", action="store_true")
    parser.add_argument("--include-oecm", action="store_true")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
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
    print(f"  {len(cells):,} cells", flush=True)

    layer = args.layer or detect_polygon_layer(args.wdpa)
    print(f"Reading WDPA polygons: {args.wdpa}", flush=True)
    wdpa = gpd.read_file(args.wdpa, layer=layer) if layer else gpd.read_file(args.wdpa)
    print(f"Raw WDPA rows: {len(wdpa):,}", flush=True)
    wdpa = filter_wdpa(wdpa, include_marine=args.include_marine, include_oecm=args.include_oecm).to_crs(AREA_CRS)
    print(f"Filtered WDPA polygon rows: {len(wdpa):,}", flush=True)

    if "STATUS_YR" not in wdpa.columns:
        raise ValueError("WDPA file missing STATUS_YR column; cannot build time-varying panel")

    wdpa["status_year"] = pd.to_numeric(wdpa["STATUS_YR"], errors="coerce")
    valid_year = wdpa["status_year"].notna() & (wdpa["status_year"] > 0)
    print(f"Polygons with valid STATUS_YR: {valid_year.sum():,} / {len(wdpa):,}", flush=True)
    print(f"STATUS_YR range: {wdpa.loc[valid_year, 'status_year'].min():.0f} - {wdpa.loc[valid_year, 'status_year'].max():.0f}", flush=True)
    wdpa.loc[~valid_year, "status_year"] = args.start_year - 1

    # Bin status_year into panel-relevant buckets:
    # everything <= start_year-1 becomes start_year-1 (pre-panel baseline)
    # everything > end_year is dropped (not yet designated)
    wdpa = wdpa[wdpa["status_year"] <= args.end_year].copy()
    wdpa.loc[wdpa["status_year"] < args.start_year, "status_year"] = args.start_year - 1
    unique_sy = sorted(wdpa["status_year"].unique())
    print(f"Binned status_year buckets: {len(unique_sy)} unique values", flush=True)

    # Keep only columns needed for overlay
    wdpa_slim = wdpa[["status_year", "geometry"]].copy()
    wdpa_slim = wdpa_slim.reset_index(drop=True)
    cells_slim = cells[["cell_id", "cell_x", "cell_y", "cell_area_km2", "geometry"]].copy()
    cells_slim = cells_slim.reset_index(drop=True)

    # --- Step 1: Union WDPA polygons by status_year bucket ---
    print(f"\nStep 1: Dissolving WDPA by status_year...", flush=True)
    t0 = time.time()
    wdpa_slim["geometry"] = wdpa_slim.geometry.buffer(0)
    dissolved_parts = []
    for sy, group in wdpa_slim.groupby("status_year"):
        print(f"  dissolving status_year={int(sy)} ({len(group):,} polygons)...", end=" ", flush=True)
        try:
            d = group.dissolve().reset_index(drop=True)
            d["status_year"] = sy
            dissolved_parts.append(d)
            print("ok", flush=True)
        except Exception as e:
            # buffer(0) failed on dissolve — try chunked union
            print(f"error ({e}), trying chunked...", flush=True)
            try:
                from shapely.ops import unary_union
                chunk_size = 5000
                geoms = list(group.geometry)
                partial_unions = []
                for ci in range(0, len(geoms), chunk_size):
                    chunk = geoms[ci:ci + chunk_size]
                    chunk = [g.buffer(0) for g in chunk if g is not None and not g.is_empty]
                    if chunk:
                        partial_unions.append(unary_union(chunk))
                if partial_unions:
                    final = unary_union(partial_unions)
                    d = gpd.GeoDataFrame({"status_year": [sy]}, geometry=[final], crs=wdpa_slim.crs)
                    dissolved_parts.append(d)
                    print(f"    chunked ok", flush=True)
            except Exception as e2:
                print(f"    chunked also failed ({e2}), using raw polygons for this year", flush=True)
                raw = group[["status_year", "geometry"]].copy()
                dissolved_parts.append(raw)

    wdpa_dissolved = pd.concat(dissolved_parts, ignore_index=True)
    wdpa_dissolved = gpd.GeoDataFrame(wdpa_dissolved, geometry="geometry", crs=wdpa_slim.crs)
    wdpa_dissolved["geometry"] = wdpa_dissolved.geometry.make_valid()
    wdpa_dissolved = wdpa_dissolved[~wdpa_dissolved.geometry.is_empty].copy()
    print(f"  Dissolved to {len(wdpa_dissolved):,} rows in {time.time() - t0:.0f}s", flush=True)

    # --- Step 2: Overlay dissolved WDPA with cells ---
    print(f"\nStep 2: Overlaying dissolved WDPA × cells in batches of {args.batch_size}...", flush=True)
    t0 = time.time()
    fragments_list = []
    n_batches = (len(cells_slim) + args.batch_size - 1) // args.batch_size

    for batch_i in range(n_batches):
        start_idx = batch_i * args.batch_size
        end_idx = min(start_idx + args.batch_size, len(cells_slim))
        batch_cells = cells_slim.iloc[start_idx:end_idx].copy()

        try:
            frag = gpd.overlay(batch_cells, wdpa_dissolved, how="intersection", keep_geom_type=False)
            if len(frag) > 0:
                fragments_list.append(frag)
        except Exception as e:
            print(f"  Batch {batch_i + 1} overlay error: {e}", flush=True)
            # Fallback: process cells individually
            for ci in range(start_idx, end_idx):
                try:
                    one_cell = cells_slim.iloc[[ci]].copy()
                    frag = gpd.overlay(one_cell, wdpa_dissolved, how="intersection", keep_geom_type=False)
                    if len(frag) > 0:
                        fragments_list.append(frag)
                except Exception:
                    pass

        elapsed = time.time() - t0
        print(f"  batch {batch_i + 1}/{n_batches} ({end_idx}/{len(cells_slim)} cells, {elapsed:.0f}s)", flush=True)

    if not fragments_list:
        print("No overlay fragments — writing empty panel", flush=True)
        # Build empty panel
        panel_rows = []
        for _, row in cells_slim.iterrows():
            for year in years:
                panel_rows.append({
                    "cell_id": row["cell_id"], "cell_x": row["cell_x"], "cell_y": row["cell_y"],
                    "year": year, "protected_area_km2": 0.0, "protected_share": 0.0,
                    "any_protected": 0, "new_protection_km2": 0.0,
                })
        out = pd.DataFrame(panel_rows)
        out.to_csv(args.output, index=False)
        return 0

    fragments = pd.concat(fragments_list, ignore_index=True)
    print(f"\n  Total fragments: {len(fragments):,} in {time.time() - t0:.0f}s", flush=True)

    # --- Step 3: Compute fragment areas ---
    print(f"\nStep 3: Computing fragment areas...", flush=True)
    fragments["frag_area_km2"] = fragments.geometry.area / 1_000_000
    fragments = fragments[["cell_id", "cell_x", "cell_y", "cell_area_km2", "status_year", "frag_area_km2"]].copy()

    # Sum fragment area by cell × status_year (handles overlapping dissolved polygons)
    cell_sy = fragments.groupby(["cell_id", "status_year"], as_index=False)["frag_area_km2"].sum()

    # --- Step 4: Build cumulative panel ---
    print(f"\nStep 4: Building cumulative cell-year panel...", flush=True)
    cell_info = cells_slim[["cell_id", "cell_x", "cell_y", "cell_area_km2"]].copy()

    # For each cell, cumulative sum of frag_area over status_year
    # But we need to handle overlap: cumulative union area != sum of individual areas
    # Since we dissolved by status_year, fragments from different years CAN overlap spatially.
    # The dissolve within each year already handled within-year overlap.
    # Cross-year overlap is a limitation we accept (may slightly overestimate).

    panel_rows = []
    cells_with_protection = set(cell_sy["cell_id"].unique())

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

        cell_data = cell_sy[cell_sy["cell_id"] == cid].sort_values("status_year")
        # Build cumulative area by year
        cum_area = 0.0
        sy_to_cum = {}
        for _, srow in cell_data.iterrows():
            cum_area += srow["frag_area_km2"]
            sy_to_cum[int(srow["status_year"])] = cum_area

        # Cap at cell area to handle overlap overestimation
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

    # Summary stats
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
