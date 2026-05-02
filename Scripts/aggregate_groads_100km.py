#!/usr/bin/env python3
"""Aggregate gROADS road network to BOLD 100 km land cells.

Computes road density (km of road per km² of cell area) for each cell.
This is a static baseline accessibility measure (roads circa 1980-2010).

gROADS attributes include road type, but coverage varies by country.
We compute total road length regardless of type for the main variable.

Requires: geopandas, shapely, pandas
Warning: This script is slow (~2-4 hours for 14K cells) due to spatial operations.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_GROADS = PROJECT_ROOT / "Data" / "raw" / "groads" / "gROADS-v1-global.shp"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "groads_100km_cells.csv"

# Equal-area CRS for length calculations
AREA_CRS = "EPSG:6933"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groads", type=Path, default=DEFAULT_GROADS)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("MINX", "MINY", "MAXX", "MAXY"),
                        help="Optional bounding box filter (WGS84) to speed up testing.")
    args = parser.parse_args()

    if not args.groads.exists():
        print(f"gROADS shapefile not found: {args.groads}")
        print("Run: python3 Scripts/download_groads.py")
        print("Then download manually from NASA SEDAC.")
        return 1

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells)
    print(f"  {len(cells):,} cells", flush=True)

    # Optional bbox filter for testing
    if args.bbox:
        minx, miny, maxx, maxy = args.bbox
        bbox_geom = box(minx, miny, maxx, maxy)
        cells = cells[cells.geometry.intersects(bbox_geom)].copy()
        print(f"  Filtered to bbox: {len(cells):,} cells", flush=True)

    print(f"Loading gROADS: {args.groads}", flush=True)
    print("  (This may take a few minutes for the global file...)", flush=True)
    roads = gpd.read_file(args.groads)
    print(f"  {len(roads):,} road segments", flush=True)

    # Reproject to equal-area for accurate length calculations
    print("Reprojecting to equal-area CRS...", flush=True)
    cells_ea = cells.to_crs(AREA_CRS)
    roads_ea = roads.to_crs(AREA_CRS)

    # Compute cell areas
    cells_ea["cell_area_km2"] = cells_ea.geometry.area / 1_000_000

    # Build spatial index for roads
    print("Building spatial index...", flush=True)
    roads_sindex = roads_ea.sindex

    # Process each cell
    print("Computing road density per cell...", flush=True)
    rows = []
    start = time.time()

    for i, (idx, cell_row) in enumerate(cells_ea.iterrows(), start=1):
        cell_geom = cell_row.geometry
        cell_area_km2 = cell_row.cell_area_km2

        # Find candidate roads that intersect cell bounds
        candidate_idx = list(roads_sindex.query(cell_geom, predicate="intersects"))

        road_length_km = 0.0
        n_segments = 0

        if candidate_idx:
            candidates = roads_ea.iloc[candidate_idx]
            for _, road_row in candidates.iterrows():
                road_geom = road_row.geometry
                try:
                    # Clip road to cell boundary
                    clipped = road_geom.intersection(cell_geom)
                    if not clipped.is_empty:
                        # Length in meters, convert to km
                        road_length_km += clipped.length / 1000
                        n_segments += 1
                except Exception:
                    pass

        road_density = road_length_km / cell_area_km2 if cell_area_km2 > 0 else 0.0

        rows.append({
            "cell_id": cell_row.cell_id,
            "cell_x": cell_row.cell_x,
            "cell_y": cell_row.cell_y,
            "cell_area_km2": cell_area_km2,
            "road_length_km": road_length_km,
            "road_density_km_per_km2": road_density,
            "road_segments": n_segments,
            "any_road": int(road_length_km > 0),
        })

        if i % args.progress_every == 0:
            elapsed = time.time() - start
            rate = i / elapsed
            eta = (len(cells_ea) - i) / rate / 60
            print(f"  {i:,}/{len(cells_ea):,} cells ({rate:.1f}/sec, ETA {eta:.0f} min)", flush=True)

    # Create output dataframe
    out = pd.DataFrame(rows)
    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}", flush=True)
    print(f"Rows: {len(out):,}", flush=True)

    # Summary stats
    print(f"\nSummary:", flush=True)
    print(f"  Cells with any road: {out['any_road'].sum():,} / {len(out):,}", flush=True)
    print(f"  Total road length: {out['road_length_km'].sum():,.0f} km", flush=True)
    print(f"  Mean road density: {out['road_density_km_per_km2'].mean():.4f} km/km²", flush=True)
    print(f"  Max road density: {out['road_density_km_per_km2'].max():.4f} km/km²", flush=True)

    elapsed = time.time() - start
    print(f"\nTotal time: {elapsed / 60:.1f} minutes", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
