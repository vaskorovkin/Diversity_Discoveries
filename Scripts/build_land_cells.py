#!/usr/bin/env python3
"""Build the canonical land-cell universe for a grid/time variant.

This creates the CSV land-cell table and companion GeoJSON polygons used by
variant-aware upstream builders. It is intended to support both the stable
baseline and the `tests_spatial_time` experiment path.
"""

from __future__ import annotations

import argparse
import math
import tempfile
import zipfile
from pathlib import Path

import cartopy.io.shapereader as shpreader
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, Polygon

from panel_variants import PanelVariant, cell_label, get_variant
from pipeline_utils import EQUAL_AREA_CRS, ensure_output_dirs


def build_land_cells(cell_km: float) -> pd.DataFrame:
    print(f"Building {cell_km:g} km land-cell universe from Natural Earth.", flush=True)
    land_path = shpreader.natural_earth(resolution="110m", category="physical", name="land")
    country_path = shpreader.natural_earth(resolution="110m", category="cultural", name="admin_0_countries")
    land = gpd.read_file(land_path).to_crs(EQUAL_AREA_CRS)
    countries = gpd.read_file(country_path).to_crs("EPSG:4326")

    cell_m = cell_km * 1000
    bounds = land.total_bounds
    min_x = int(np.floor(bounds[0] / cell_m))
    max_x = int(np.ceil(bounds[2] / cell_m))
    min_y = int(np.floor(bounds[1] / cell_m))
    max_y = int(np.ceil(bounds[3] / cell_m))
    try:
        land_union = land.geometry.union_all()
    except AttributeError:
        land_union = land.geometry.unary_union
    to_lonlat = Transformer.from_crs(EQUAL_AREA_CRS, "EPSG:4326", always_xy=True)

    rows: list[dict[str, object]] = []
    total = (max_x - min_x + 1) * (max_y - min_y + 1)
    checked = 0
    for cell_x in range(min_x, max_x + 1):
        for cell_y in range(min_y, max_y + 1):
            checked += 1
            x = (cell_x + 0.5) * cell_m
            y = (cell_y + 0.5) * cell_m
            if not land_union.contains(Point(x, y)):
                continue
            lon, lat = to_lonlat.transform(x, y)
            rows.append(
                {
                    "cell_id": f"{cell_x}_{cell_y}",
                    "cell_x": cell_x,
                    "cell_y": cell_y,
                    "centroid_lon": lon,
                    "centroid_lat": lat,
                }
            )
        if checked % 5000 == 0:
            print(f"  checked {checked:,}/{total:,} candidate cells; land cells {len(rows):,}", flush=True)

    cells = pd.DataFrame(rows)
    points = gpd.GeoDataFrame(
        cells,
        geometry=gpd.points_from_xy(cells["centroid_lon"], cells["centroid_lat"]),
        crs="EPSG:4326",
    )
    keep = ["geometry"]
    for col in ["CONTINENT", "ADMIN", "ISO_A3"]:
        if col in countries.columns:
            keep.append(col)
    joined = gpd.sjoin(points, countries[keep], how="left", predicate="within")
    cells["continent"] = joined.get("CONTINENT", pd.Series([""] * len(joined))).fillna("").values
    cells["country"] = joined.get("ADMIN", pd.Series([""] * len(joined))).fillna("").values
    cells["iso_a3"] = joined.get("ISO_A3", pd.Series([""] * len(joined))).fillna("").values
    cells = cells[cells["continent"] != "Antarctica"].copy()
    return cells


def make_grid_geodataframe(cells: pd.DataFrame, cell_km: float) -> gpd.GeoDataFrame:
    cell_m = cell_km * 1000
    to_lonlat = Transformer.from_crs(EQUAL_AREA_CRS, "EPSG:4326", always_xy=True)
    geoms = []
    kept_rows = []
    for idx, row in enumerate(cells.itertuples(index=False)):
        x0 = row.cell_x * cell_m
        x1 = (row.cell_x + 1) * cell_m
        y0 = row.cell_y * cell_m
        y1 = (row.cell_y + 1) * cell_m

        ll = to_lonlat.transform(x0, y0)
        lr = to_lonlat.transform(x1, y0)
        ur = to_lonlat.transform(x1, y1)
        ul = to_lonlat.transform(x0, y1)
        corners = [ll, lr, ur, ul]
        if any((not math.isfinite(x) or not math.isfinite(y)) for x, y in corners):
            continue
        geoms.append(Polygon([ll, lr, ur, ul, ll]))
        kept_rows.append(idx)
    valid_cells = cells.iloc[kept_rows].copy()
    return gpd.GeoDataFrame(valid_cells, geometry=geoms, crs="EPSG:4326")


def write_geojson(cells: pd.DataFrame, output: Path, cell_km: float) -> gpd.GeoDataFrame:
    grid = make_grid_geodataframe(cells, cell_km)
    output.parent.mkdir(parents=True, exist_ok=True)
    grid.to_file(output, driver="GeoJSON")
    print(f"Wrote GeoJSON: {output}", flush=True)
    return grid


def write_shapefile_zip(grid: gpd.GeoDataFrame, output: Path) -> None:
    """Write a zipped Shapefile for Earth Engine table upload."""
    output.parent.mkdir(parents=True, exist_ok=True)
    upload_grid = grid[["cell_id", "cell_x", "cell_y", "geometry"]].copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        shp_path = tmpdir_path / "bold_grid_land_cells.shp"
        upload_grid.to_file(shp_path, driver="ESRI Shapefile")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for part in sorted(tmpdir_path.glob("bold_grid_land_cells.*")):
                zf.write(part, arcname=part.name)
    print(f"Wrote Earth Engine upload Shapefile ZIP: {output}", flush=True)


def default_csv(variant: PanelVariant | None, cell_km: float) -> Path:
    if variant is not None:
        return variant.land_cells_csv
    label = cell_label(cell_km)
    return Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries/Data/processed/bold") / f"bold_grid{label}_land_cells.csv"


def default_geojson(variant: PanelVariant | None, cell_km: float) -> Path:
    if variant is not None:
        return variant.land_cells_geojson
    label = cell_label(cell_km)
    return Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries/Data/processed/bold") / f"bold_grid{label}_land_cells.geojson"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=str, default=None)
    parser.add_argument("--cell-km", type=float, default=100)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-geojson", type=Path, default=None)
    parser.add_argument("--output-shapefile-zip", type=Path, default=None)
    args = parser.parse_args()

    ensure_output_dirs()
    variant = get_variant(args.variant) if args.variant else None
    if variant is not None:
        args.cell_km = variant.cell_km
        print(f"Variant: {variant.name} ({variant.suffix})", flush=True)

    output_csv = args.output_csv or default_csv(variant, args.cell_km)
    output_geojson = args.output_geojson or default_geojson(variant, args.cell_km)
    output_shapefile_zip = args.output_shapefile_zip or output_geojson.with_suffix(".zip")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    output_shapefile_zip.parent.mkdir(parents=True, exist_ok=True)

    cells = build_land_cells(args.cell_km)
    cells.to_csv(output_csv, index=False)
    print(f"Wrote land cells: {output_csv} ({len(cells):,} cells)", flush=True)
    grid = write_geojson(cells, output_geojson, args.cell_km)
    write_shapefile_zip(grid, output_shapefile_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
