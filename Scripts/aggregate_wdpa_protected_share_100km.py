#!/usr/bin/env python3
"""Aggregate WDPA protected-area polygon coverage to BOLD 100 km land cells.

Input should be a local Protected Planet / WDPA polygon file, usually a GPKG or
shapefile downloaded from protectedplanet.net. The script computes protected
area share by intersecting WDPA polygons with the BOLD 100 km land-cell
polygons. Candidate protected polygons are unioned within each cell before area
calculation, so overlapping WDPA polygons are not double counted.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "wdpa_protected_share_100km_cells.csv"
AREA_CRS = "EPSG:6933"


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
    parser.add_argument("--layer", default=None, help="Optional layer name for GDB/GPKG inputs. Defaults to first polygon layer.")
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-marine", action="store_true", help="Keep WDPA records marked fully marine.")
    parser.add_argument("--include-oecm", action="store_true", help="Keep OECM records when the input is a combined WDPA/WDOECM file.")
    parser.add_argument("--progress-every", type=int, default=500)
    args = parser.parse_args()

    if not args.wdpa.exists():
        raise FileNotFoundError(f"Missing WDPA file: {args.wdpa}")
    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing land-cell polygons: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading land-cell polygons: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells).to_crs(AREA_CRS)
    cells["cell_area_km2"] = cells.geometry.area / 1_000_000

    layer = args.layer or detect_polygon_layer(args.wdpa)
    print(f"Reading WDPA polygons: {args.wdpa}", flush=True)
    wdpa = gpd.read_file(args.wdpa, layer=layer) if layer else gpd.read_file(args.wdpa)
    print(f"Raw WDPA rows: {len(wdpa):,}", flush=True)
    wdpa = filter_wdpa(wdpa, include_marine=args.include_marine, include_oecm=args.include_oecm).to_crs(AREA_CRS)
    print(f"Filtered WDPA polygon rows: {len(wdpa):,}", flush=True)

    spatial_index = wdpa.sindex
    rows: list[dict[str, object]] = []
    start = time.time()
    for i, row in enumerate(cells.itertuples(index=False), start=1):
        cell_geom = row.geometry
        candidate_idx = list(spatial_index.query(cell_geom, predicate="intersects"))
        protected_area_km2 = 0.0
        n_candidates = len(candidate_idx)
        if candidate_idx:
            candidates = wdpa.iloc[candidate_idx]
            try:
                unioned = candidates.geometry.union_all()
            except AttributeError:
                unioned = candidates.geometry.unary_union
            clipped = unioned.intersection(cell_geom)
            protected_area_km2 = clipped.area / 1_000_000

        cell_area_km2 = float(row.cell_area_km2)
        protected_share = protected_area_km2 / cell_area_km2 if cell_area_km2 > 0 else 0.0
        rows.append(
            {
                "cell_id": row.cell_id,
                "cell_x": row.cell_x,
                "cell_y": row.cell_y,
                "centroid_lon": row.centroid_lon,
                "centroid_lat": row.centroid_lat,
                "continent": row.continent,
                "country": row.country,
                "iso_a3": row.iso_a3,
                "cell_area_km2": cell_area_km2,
                "wdpa_candidate_polygons": n_candidates,
                "wdpa_protected_area_km2": protected_area_km2,
                "wdpa_protected_share": min(protected_share, 1.0),
                "wdpa_any_protected": int(protected_area_km2 > 0),
            }
        )
        if i % args.progress_every == 0:
            elapsed = time.time() - start
            print(f"processed {i:,}/{len(cells):,} cells ({i / elapsed:,.1f} cells/sec)", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(args.output, index=False)
    print(f"Wrote: {args.output}", flush=True)
    print(f"Rows: {len(out):,}; unique cells: {out['cell_id'].nunique():,}", flush=True)
    print(f"Cells with any protected area: {int(out['wdpa_any_protected'].sum()):,}", flush=True)
    print(f"Mean protected share: {out['wdpa_protected_share'].mean():.4f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
