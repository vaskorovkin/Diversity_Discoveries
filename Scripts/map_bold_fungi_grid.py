#!/usr/bin/env python3
"""Map BOLD Fungi sampling counts on an equal-area grid.

Default grid size is 100 km, close to the 111 x 111 km terrestrial-animal
resolution used in Bernardo-Madrid et al. (2025). For sensitivity, rerun with
--cell-km 50 or --cell-km 200.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm
from shapely.geometry import box


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_INPUT = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_global_fungi_minimal.tsv"
DEFAULT_OUTDIR = PROJECT_ROOT / "Output" / "maps"
EQUAL_AREA_CRS = "EPSG:6933"  # World Cylindrical Equal Area


def load_points(path: Path) -> gpd.GeoDataFrame:
    usecols = [
        "processid",
        "record_id",
        "species",
        "country_ocean",
        "collection_date_start",
        "latitude",
        "longitude",
    ]
    df = pd.read_csv(path, sep="\t", usecols=usecols, dtype=str)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df[
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
    ].copy()
    points = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )
    return points.to_crs(EQUAL_AREA_CRS)


def build_grid_counts(points: gpd.GeoDataFrame, cell_km: float) -> gpd.GeoDataFrame:
    cell_m = cell_km * 1000
    xs = points.geometry.x
    ys = points.geometry.y

    finite = np.isfinite(xs) & np.isfinite(ys)
    points = points.loc[finite].copy()
    xs = points.geometry.x
    ys = points.geometry.y

    points["cell_x"] = (xs // cell_m).astype(int)
    points["cell_y"] = (ys // cell_m).astype(int)

    counts = (
        points.groupby(["cell_x", "cell_y"])
        .size()
        .rename("n_records")
        .reset_index()
    )
    counts["x0"] = counts["cell_x"] * cell_m
    counts["y0"] = counts["cell_y"] * cell_m
    counts["x1"] = counts["x0"] + cell_m
    counts["y1"] = counts["y0"] + cell_m
    counts["cell_id"] = (
        counts["cell_x"].astype(str) + "_" + counts["cell_y"].astype(str)
    )
    counts["geometry"] = [
        box(x0, y0, x1, y1)
        for x0, y0, x1, y1 in zip(counts["x0"], counts["y0"], counts["x1"], counts["y1"])
    ]

    grid = gpd.GeoDataFrame(counts, geometry="geometry", crs=EQUAL_AREA_CRS)

    centroids = grid.copy()
    centroids["geometry"] = centroids.geometry.centroid
    centroids = centroids.to_crs("EPSG:4326")
    grid["centroid_lon"] = centroids.geometry.x
    grid["centroid_lat"] = centroids.geometry.y
    return grid


def plot_grid(grid: gpd.GeoDataFrame, output_png: Path, cell_km: float) -> None:
    min_x = int(grid["cell_x"].min())
    max_x = int(grid["cell_x"].max())
    min_y = int(grid["cell_y"].min())
    max_y = int(grid["cell_y"].max())
    nx = max_x - min_x + 1
    ny = max_y - min_y + 1

    arr = np.full((ny, nx), np.nan)
    for row in grid.itertuples(index=False):
        arr[int(row.cell_y) - min_y, int(row.cell_x) - min_x] = row.n_records

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")
    norm = LogNorm(vmin=1, vmax=max(int(grid["n_records"].max()), 1))

    cell_m = cell_km * 1000
    extent = [
        min_x * cell_m,
        (max_x + 1) * cell_m,
        min_y * cell_m,
        (max_y + 1) * cell_m,
    ]

    fig, ax = plt.subplots(figsize=(18, 9))
    image = ax.imshow(
        arr,
        origin="lower",
        extent=extent,
        cmap="viridis",
        norm=norm,
        interpolation="nearest",
    )
    cbar = fig.colorbar(image, ax=ax, shrink=0.62)
    cbar.set_label("BOLD Fungi records per cell, log scale")
    ax.set_title(f"BOLD Fungi Sampling Records by {cell_km:g} km Equal-Area Cell", fontsize=16)
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(output_png, dpi=220)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--cell-km", type=float, default=100)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    cell_label = f"{args.cell_km:g}km".replace(".", "p")
    output_png = args.outdir / f"bold_global_fungi_grid_{cell_label}.png"
    output_csv = args.outdir / f"bold_global_fungi_grid_{cell_label}_counts.csv"

    print(f"Reading BOLD records: {args.input}")
    points = load_points(args.input)
    print(f"Records with usable coordinates: {len(points):,}")

    print(f"Binning to {args.cell_km:g} km equal-area cells.")
    grid = build_grid_counts(points, args.cell_km)
    print(f"Occupied cells: {len(grid):,}")
    print(f"Max records in one cell: {int(grid['n_records'].max()):,}")

    grid.drop(columns="geometry").sort_values("n_records", ascending=False).to_csv(
        output_csv, index=False
    )
    print(f"Wrote counts: {output_csv}")

    print("Rendering map.")
    plot_grid(grid, output_png, args.cell_km)
    print(f"Wrote map: {output_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
