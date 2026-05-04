#!/usr/bin/env python3
"""Create kingdom-by-kingdom cell-level correlation tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import cartopy.io.shapereader as shpreader
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point

from pipeline_utils import (
    EQUAL_AREA_CRS,
    EXHIBIT_FIGURES,
    EXHIBIT_TABLES,
    GRID_COUNTS_CSV,
    LAND_CELLS_CSV,
    ensure_output_dirs,
)


def build_land_cells(path: Path, cell_km: float) -> pd.DataFrame:
    print("Building 100 km land-cell universe from Natural Earth.", flush=True)
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

    rows = []
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
            rows.append({"cell_id": f"{cell_x}_{cell_y}", "cell_x": cell_x, "cell_y": cell_y, "centroid_lon": lon, "centroid_lat": lat})
        if checked % 5000 == 0:
            print(f"  checked {checked:,}/{total:,} candidate cells; land cells {len(rows):,}", flush=True)

    cells = pd.DataFrame(rows)
    points = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells["centroid_lon"], cells["centroid_lat"]), crs="EPSG:4326")
    keep = ["geometry"]
    for col in ["CONTINENT", "ADMIN", "ISO_A3"]:
        if col in countries.columns:
            keep.append(col)
    joined = gpd.sjoin(points, countries[keep], how="left", predicate="within")
    cells["continent"] = joined.get("CONTINENT", pd.Series([""] * len(joined))).fillna("").values
    cells["country"] = joined.get("ADMIN", pd.Series([""] * len(joined))).fillna("").values
    cells["iso_a3"] = joined.get("ISO_A3", pd.Series([""] * len(joined))).fillna("").values
    cells.to_csv(path, index=False)
    print(f"Wrote land cells: {path} ({len(cells):,} cells)", flush=True)
    return cells


def load_land_cells(path: Path, cell_km: float) -> pd.DataFrame:
    if path.exists():
        print(f"Reading land cells: {path}", flush=True)
        return pd.read_csv(path, dtype={"cell_id": str})
    return build_land_cells(path, cell_km)


def make_wide_counts(grid_counts: Path, land_cells: pd.DataFrame) -> pd.DataFrame:
    print(f"Reading grid counts: {grid_counts}", flush=True)
    counts = pd.read_csv(grid_counts, dtype={"cell_id": str, "kingdom": str})
    pivot = counts.pivot_table(index="cell_id", columns="kingdom", values="record_count", aggfunc="sum", fill_value=0)
    pivot.columns = [str(c) if str(c) else "Unknown" for c in pivot.columns]
    out = land_cells[["cell_id", "continent", "country", "centroid_lon", "centroid_lat"]].merge(
        pivot,
        left_on="cell_id",
        right_index=True,
        how="left",
    )
    kingdoms = [c for c in out.columns if c not in {"cell_id", "continent", "country", "centroid_lon", "centroid_lat"}]
    out[kingdoms] = out[kingdoms].fillna(0).astype(int)
    print(f"Wide cell table: {len(out):,} land cells, {len(kingdoms):,} kingdoms", flush=True)
    return out


def write_corrs(wide: pd.DataFrame, label: str, selector) -> None:
    sub = wide.loc[selector(wide)].copy()
    meta = {"cell_id", "continent", "country", "centroid_lon", "centroid_lat"}
    kingdoms = [c for c in sub.columns if c not in meta]
    levels = sub[kingdoms].corr()
    logs = np.log1p(sub[kingdoms]).corr()
    total_records = int(sub[kingdoms].sum().sum())
    nonzero_cells = int((sub[kingdoms].sum(axis=1) > 0).sum())
    kingdom_totals = sub[kingdoms].sum().astype(int).sort_values(ascending=False)

    metadata = [
        f"# region,{label}",
        f"# land_cells_used,{len(sub)}",
        f"# cells_with_any_observation,{nonzero_cells}",
        f"# total_observations,{total_records}",
    ]
    metadata.extend(f"# observations_{kingdom},{int(count)}" for kingdom, count in kingdom_totals.items())

    levels_path = EXHIBIT_TABLES / f"corr_kingdoms_{label}_levels.csv"
    logs_path = EXHIBIT_TABLES / f"corr_kingdoms_{label}_log1p.csv"
    write_corr_csv_with_metadata(levels, levels_path, metadata)
    write_corr_csv_with_metadata(logs, logs_path, metadata)
    print(f"Wrote: {levels_path}", flush=True)
    print(f"Wrote: {logs_path}", flush=True)

    for matrix, suffix in [(levels, "levels"), (logs, "log1p")]:
        fig, ax = plt.subplots(figsize=(7.5, 6.5))
        im = ax.imshow(matrix.values, vmin=-1, vmax=1, cmap="coolwarm")
        ax.set_xticks(range(len(matrix.columns)))
        ax.set_yticks(range(len(matrix.index)))
        ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
        ax.set_yticklabels(matrix.index)
        ax.set_title(f"Kingdom cell correlations: {label}, {suffix}")
        fig.colorbar(im, ax=ax, shrink=0.75)
        fig.tight_layout()
        out = EXHIBIT_FIGURES / f"heatmap_corr_kingdoms_{label}_{suffix}.png"
        fig.savefig(out, dpi=220)
        plt.close(fig)
        print(f"Wrote: {out}", flush=True)


def write_corr_csv_with_metadata(matrix: pd.DataFrame, path: Path, metadata: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("\n".join(metadata))
        f.write("\n")
        matrix.to_csv(f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid-counts", type=Path, default=GRID_COUNTS_CSV)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--cell-km", type=float, default=100)
    args = parser.parse_args()

    ensure_output_dirs()
    land = load_land_cells(args.land_cells, args.cell_km)
    wide = make_wide_counts(args.grid_counts, land)
    wide_path = args.grid_counts.with_name("bold_grid100_land_cells_by_kingdom_wide.csv")
    wide.to_csv(wide_path, index=False)
    print(f"Wrote wide cell counts: {wide_path}", flush=True)

    write_corrs(wide, "world", lambda df: pd.Series([True] * len(df), index=df.index))
    write_corrs(wide, "south_america", lambda df: df["continent"].fillna("") == "South America")
    write_corrs(wide, "africa", lambda df: df["continent"].fillna("") == "Africa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
