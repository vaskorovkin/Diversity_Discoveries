#!/usr/bin/env python3
"""Aggregate IUCN/BirdLife range maps to species richness per 100 km cell.

Computes baseline species richness by overlaying expert range polygons with
the BOLD 100 km land-cell grid. For each cell, counts the number of species
whose range polygon intersects the cell.

Handles multi-part shapefiles (e.g. AMPHIBIANS_PART1.shp, AMPHIBIANS_PART2.shp)
by loading and concatenating all parts before the spatial join.

Filters to extant, native, resident/breeding ranges by default (IUCN
presence=1, origin=1, seasonal in {1,2}) to get a clean baseline richness
estimate. These filters match standard practice in macroecology.

Input: IUCN range shapefiles/geodatabases in Data/raw/iucn_ranges/
Output: Data/regressors/baseline_geography/species_richness_100km_cells.csv

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
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "regressors" / "baseline_geography" / "species_richness_100km_cells.csv"

TAXON_CONFIGS = {
    "MAMMALS": {"label": "mammals"},
    "AMPHIBIANS": {"label": "amphibians"},
    "REPTILES": {"label": "reptiles"},
}

IUCN_PRESENCE_EXTANT = 1
IUCN_ORIGIN_NATIVE = 1
IUCN_SEASONAL_RESIDENT_OR_BREEDING = {1, 2}


def find_range_files(base_dir: Path, taxon: str) -> list[Path]:
    """Find all shapefiles/geodatabases for a taxon, including multi-part."""
    keyword = taxon.lower()
    found: list[Path] = []

    for subdir in base_dir.iterdir():
        if not subdir.is_dir():
            continue
        if keyword not in subdir.name.lower():
            continue
        gdbs = list(subdir.glob("*.gdb"))
        if gdbs:
            return gdbs
        shps = sorted(subdir.glob("*.shp"))
        if shps:
            found.extend(shps)

    if not found:
        for shp in sorted(base_dir.rglob("*.shp")):
            if keyword in shp.name.lower():
                found.append(shp)

    return found


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


def load_and_concat(paths: list[Path]) -> gpd.GeoDataFrame:
    """Load one or more shapefiles/geodatabases and concatenate."""
    parts = []
    for p in paths:
        print(f"  Loading {p.name} ...", flush=True)
        if p.suffix in (".gdb", ".gpkg"):
            try:
                import fiona
                layers = fiona.listlayers(str(p))
            except ImportError:
                import pyogrio
                layers = [l[0] for l in pyogrio.list_layers(str(p))]
            gdf = gpd.read_file(p, layer=layers[0] if layers else None, engine="pyogrio")
        else:
            gdf = gpd.read_file(p)
        print(f"    {len(gdf):,} polygons", flush=True)
        parts.append(gdf)

    if len(parts) == 1:
        return parts[0]

    combined = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=parts[0].crs)


def count_species_per_cell(
    gdf: gpd.GeoDataFrame,
    cells: gpd.GeoDataFrame,
    label: str,
    filter_ranges: bool = True,
) -> pd.Series:
    """Count unique species per cell from range polygons."""
    species_col = detect_species_column(gdf)
    print(f"  Species column: {species_col}")
    print(f"  Unique species (raw): {gdf[species_col].nunique():,}")

    if filter_ranges:
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
        gdf = gdf.to_crs(cells.crs)

    print(f"  Spatial join with {len(cells):,} cells ...", flush=True)
    joined = gpd.sjoin(
        cells[["cell_id", "geometry"]],
        gdf[[species_col, "geometry"]],
        how="left",
        predicate="intersects",
    )

    richness = joined.groupby("cell_id")[species_col].nunique()
    richness.name = f"richness_{label}"

    print(f"  Cells with ≥1 species: {(richness > 0).sum():,}")
    print(f"  Mean richness: {richness.mean():.1f}")
    print(f"  Max richness: {richness.max()}")

    return richness


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--range-dir", type=Path, default=DEFAULT_RANGE_DIR)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-filter", action="store_true",
                        help="Skip IUCN presence/origin/seasonal filters")
    args = parser.parse_args()

    if not args.land_cells.exists():
        raise FileNotFoundError(f"Missing: {args.land_cells}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading land cells: {args.land_cells}", flush=True)
    cells = gpd.read_file(args.land_cells)
    print(f"  {len(cells):,} cells", flush=True)

    out = cells[["cell_id", "cell_x", "cell_y"]].copy()

    found_any = False
    richness_cols = []

    for taxon, config in TAXON_CONFIGS.items():
        paths = find_range_files(args.range_dir, taxon)
        if not paths:
            print(f"\n{taxon}: not found, skipping", flush=True)
            continue

        found_any = True
        label = config["label"]
        print(f"\n{taxon} ({label}): {len(paths)} file(s)", flush=True)

        gdf = load_and_concat(paths)
        print(f"  Total polygons: {len(gdf):,}", flush=True)

        richness = count_species_per_cell(
            gdf, cells, label, filter_ranges=not args.no_filter
        )
        col = f"richness_{label}"
        richness_cols.append(col)
        out = out.merge(richness.reset_index(), on="cell_id", how="left")
        out[col] = out[col].fillna(0).astype(int)

    if not found_any:
        print(f"\nNo range files found in {args.range_dir}")
        print("Run: python3 Scripts/download_species_richness.py")
        return 1

    if richness_cols:
        out["richness_total"] = out[richness_cols].sum(axis=1)
        out["log1p_richness_total"] = np.log1p(out["richness_total"])

    out.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output}")
    print(f"Rows: {len(out):,}")
    print(f"Columns: {list(out.columns)}")

    print("\nSummary:")
    for col in richness_cols + ["richness_total"]:
        if col in out.columns:
            print(f"  {col}: mean={out[col].mean():.1f}, "
                  f"median={out[col].median():.0f}, "
                  f"max={out[col].max()}, "
                  f"zeros={int((out[col] == 0).sum())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
