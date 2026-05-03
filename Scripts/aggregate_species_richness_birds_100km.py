#!/usr/bin/env python3
"""Aggregate BirdLife BOTW range maps to bird species richness per 100 km cell.

Separate from the main species richness script because the BOTW GeoPackage is
~9 GB and ~10,000+ species — running it alongside mammals/amphibians/reptiles
would exhaust RAM.

Filters to extant, native, resident/breeding ranges (presence=1, origin=1,
seasonal in {1,2}).

Input: BOTW GeoPackage in Data/raw/iucn_ranges/BOTW/
Output: Data/regressors/baseline_geography/species_richness_birds_100km_cells.csv

The main script's output and this script's output are merged in
merge_all_regressors.do (both keyed on cell_id).

Requires: geopandas, pandas, fiona
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_RANGE_DIR = PROJECT_ROOT / "Data" / "raw" / "iucn_ranges"
LAND_CELLS = PROJECT_ROOT / "Exhibits" / "data" / "bold_grid100_land_cells.geojson"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "species_richness_birds_100km_cells.csv"

IUCN_PRESENCE_EXTANT = 1
IUCN_ORIGIN_NATIVE = 1
IUCN_SEASONAL_RESIDENT_OR_BREEDING = {1, 2}


def find_botw(base_dir: Path) -> Path | None:
    for pattern in ["BOTW", "botw", "Birds"]:
        for subdir in base_dir.iterdir():
            if not subdir.is_dir():
                continue
            if pattern.lower() not in subdir.name.lower():
                continue
            for ext in [".gpkg", ".gdb", ".shp"]:
                candidates = sorted(subdir.glob(f"*{ext}"))
                if candidates:
                    return candidates[0]
    for gpkg in base_dir.rglob("*.gpkg"):
        if "botw" in gpkg.name.lower():
            return gpkg
    return None


def detect_species_column(gdf: gpd.GeoDataFrame) -> str:
    candidates = ["sci_name", "SCI_NAME", "binomial", "BINOMIAL",
                   "scientific_name", "SCIENTIFIC_NAME", "sciname", "SCINAME"]
    for c in candidates:
        if c in gdf.columns:
            return c
    for c in gdf.columns:
        if "sci" in c.lower() and "name" in c.lower():
            return c
    raise ValueError(f"Cannot find species name column. Available: {list(gdf.columns)}")


def detect_filter_columns(gdf: gpd.GeoDataFrame) -> dict:
    cols = {}
    for target, candidates in [
        ("presence", ["presence", "PRESENCE"]),
        ("origin", ["origin", "ORIGIN"]),
        ("seasonal", ["seasonal", "SEASONAL"]),
    ]:
        for c in candidates:
            if c in gdf.columns:
                cols[target] = c
                break
    return cols


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--botw", type=Path, default=None,
                        help="Path to BOTW GeoPackage/shapefile (auto-detected if omitted)")
    parser.add_argument("--range-dir", type=Path, default=DEFAULT_RANGE_DIR)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-filter", action="store_true",
                        help="Skip IUCN presence/origin/seasonal filters")
    args = parser.parse_args()

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    botw_path = args.botw or find_botw(args.range_dir)
    if botw_path is None or not botw_path.exists():
        print("BOTW file not found.")
        print(f"Place BOTW GeoPackage in {args.range_dir}/BOTW/")
        print("Or pass --botw /path/to/BOTW_2025.gpkg")
        return 1

    print(f"Loading land cells: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells)
    print(f"  {len(cells):,} cells", flush=True)

    print(f"\nLoading BOTW: {botw_path}", flush=True)
    print(f"  File size: {botw_path.stat().st_size / 1e9:.1f} GB", flush=True)

    try:
        import fiona
        layers = fiona.listlayers(str(botw_path))
    except ImportError:
        import pyogrio
        layers = pyogrio.list_layers(str(botw_path))
        layers = [l[0] for l in layers]
    print(f"  Layers: {layers}", flush=True)
    layer = layers[0] if layers else None

    print(f"  Reading layer '{layer}' (this may take several minutes) ...", flush=True)
    gdf = gpd.read_file(botw_path, layer=layer, engine="pyogrio")
    print(f"  Raw range polygons: {len(gdf):,}", flush=True)

    species_col = detect_species_column(gdf)
    print(f"  Species column: {species_col}")
    print(f"  Unique species (raw): {gdf[species_col].nunique():,}")

    if not args.no_filter:
        filter_cols = detect_filter_columns(gdf)
        n_before = len(gdf)

        if "presence" in filter_cols:
            gdf = gdf[gdf[filter_cols["presence"]] == IUCN_PRESENCE_EXTANT]
        if "origin" in filter_cols:
            gdf = gdf[gdf[filter_cols["origin"]] == IUCN_ORIGIN_NATIVE]
        if "seasonal" in filter_cols:
            gdf = gdf[gdf[filter_cols["seasonal"]].isin(IUCN_SEASONAL_RESIDENT_OR_BREEDING)]

        print(f"  After IUCN filters (extant/native/resident): {len(gdf):,} "
              f"(dropped {n_before - len(gdf):,})")
        print(f"  Unique species (filtered): {gdf[species_col].nunique():,}")

    if gdf.crs is not None and gdf.crs != cells.crs:
        print("  Reprojecting to match cell CRS ...", flush=True)
        gdf = gdf.to_crs(cells.crs)

    print(f"  Spatial join with {len(cells):,} cells ...", flush=True)
    joined = gpd.sjoin(
        cells[["cell_id", "geometry"]],
        gdf[[species_col, "geometry"]],
        how="left",
        predicate="intersects",
    )

    richness = joined.groupby("cell_id")[species_col].nunique()
    richness.name = "richness_birds"

    print(f"  Cells with ≥1 species: {(richness > 0).sum():,}")
    print(f"  Mean richness: {richness.mean():.1f}")
    print(f"  Max richness: {richness.max()}")

    out = cells[["cell_id", "cell_x", "cell_y"]].copy()
    out = out.merge(richness.reset_index(), on="cell_id", how="left")
    out["richness_birds"] = out["richness_birds"].fillna(0).astype(int)
    out["log1p_richness_birds"] = np.log1p(out["richness_birds"])

    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}")
    print(f"Rows: {len(out):,}")

    print(f"\nSummary:")
    print(f"  richness_birds: mean={out['richness_birds'].mean():.1f}, "
          f"median={out['richness_birds'].median():.0f}, "
          f"max={out['richness_birds'].max()}, "
          f"zeros={int((out['richness_birds'] == 0).sum())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
