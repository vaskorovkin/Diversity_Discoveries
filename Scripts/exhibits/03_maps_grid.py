#!/usr/bin/env python3
"""Create 100 km equal-area grid maps and grid-count data."""

from __future__ import annotations

import argparse
import csv
import time
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cartopy.io.shapereader as shpreader
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from pyproj import Transformer

from exhibit_utils import (
    EQUAL_AREA_CRS,
    EXHIBIT_DATA,
    EXHIBIT_MAPS,
    GRID_COUNTS_CSV,
    MINIMAL_CSV,
    clean,
    ensure_exhibit_dirs,
    finite_float,
    iter_minimal_chunks,
    lognorm_or_none,
)


def load_land_outline() -> gpd.GeoDataFrame:
    shp = shpreader.natural_earth(resolution="110m", category="physical", name="land")
    return gpd.read_file(shp).to_crs(EQUAL_AREA_CRS)


def build_grid_counts(input_path: Path, cell_km: float, chunksize: int) -> tuple[Counter, Counter]:
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    cell_m = cell_km * 1000
    all_counts = Counter()
    kingdom_counts = Counter()
    total = 0
    coord_total = 0
    started = time.time()

    print(f"Reading minimal records: {input_path}", flush=True)
    for chunk_index, chunk in enumerate(iter_minimal_chunks(input_path, chunksize), 1):
        for _, row in chunk.iterrows():
            if clean(row.get("has_coord")) != "1":
                continue
            lon = finite_float(row.get("longitude"))
            lat = finite_float(row.get("latitude"))
            if lon is None or lat is None:
                continue
            x, y = transformer.transform(lon, lat)
            cell_x = int(np.floor(x / cell_m))
            cell_y = int(np.floor(y / cell_m))
            cell = (cell_x, cell_y)
            kingdom = clean(row.get("kingdom")) or "Unknown"
            all_counts[cell] += 1
            kingdom_counts[(cell_x, cell_y, kingdom)] += 1
            coord_total += 1
        total += len(chunk)
        elapsed = max(time.time() - started, 1)
        print(
            f"chunk {chunk_index:,}: {total:,} rows scanned; "
            f"{coord_total:,} coordinate rows binned ({total / elapsed:,.0f} rows/sec)",
            flush=True,
        )
    return all_counts, kingdom_counts


def write_grid_counts(path: Path, all_counts: Counter, kingdom_counts: Counter, cell_km: float) -> None:
    transformer = Transformer.from_crs(EQUAL_AREA_CRS, "EPSG:4326", always_xy=True)
    cell_m = cell_km * 1000
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "cell_id",
                "cell_x",
                "cell_y",
                "centroid_lon",
                "centroid_lat",
                "kingdom",
                "record_count",
            ],
        )
        writer.writeheader()
        for (cell_x, cell_y, kingdom), count in sorted(kingdom_counts.items()):
            lon, lat = transformer.transform((cell_x + 0.5) * cell_m, (cell_y + 0.5) * cell_m)
            writer.writerow(
                {
                    "cell_id": f"{cell_x}_{cell_y}",
                    "cell_x": cell_x,
                    "cell_y": cell_y,
                    "centroid_lon": f"{lon:.6f}",
                    "centroid_lat": f"{lat:.6f}",
                    "kingdom": kingdom,
                    "record_count": count,
                }
            )

    all_path = path.with_name(path.stem + "_all.csv")
    with all_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cell_id", "cell_x", "cell_y", "record_count"])
        writer.writeheader()
        for (cell_x, cell_y), count in sorted(all_counts.items()):
            writer.writerow({"cell_id": f"{cell_x}_{cell_y}", "cell_x": cell_x, "cell_y": cell_y, "record_count": count})
    print(f"Wrote grid kingdom counts: {path}", flush=True)
    print(f"Wrote grid all-counts: {all_path}", flush=True)


def plot_grid(
    counts: dict[tuple[int, int], int],
    output: Path,
    title: str,
    cell_km: float,
    land_outline: gpd.GeoDataFrame | None = None,
) -> None:
    if not counts:
        print(f"No counts to plot for {output}", flush=True)
        return
    xs = [k[0] for k in counts]
    ys = [k[1] for k in counts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    arr = np.full((max_y - min_y + 1, max_x - min_x + 1), np.nan)
    for (cell_x, cell_y), count in counts.items():
        if count > 0:
            arr[cell_y - min_y, cell_x - min_x] = count

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")
    norm = lognorm_or_none(max(counts.values()))
    cell_m = cell_km * 1000
    extent = [min_x * cell_m, (max_x + 1) * cell_m, min_y * cell_m, (max_y + 1) * cell_m]

    fig, ax = plt.subplots(figsize=(18, 9))
    image = ax.imshow(arr, origin="lower", extent=extent, cmap=cmap, norm=norm, interpolation="nearest")
    if land_outline is not None:
        land_outline.boundary.plot(ax=ax, linewidth=0.28, color="#777777", alpha=0.9)
    cbar = fig.colorbar(image, ax=ax, shrink=0.62)
    cbar.set_label("record count, log scale")
    ax.set_title(title)
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)
    print(f"Wrote map: {output}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--cell-km", type=float, default=100)
    parser.add_argument("--chunksize", type=int, default=500_000)
    args = parser.parse_args()

    ensure_exhibit_dirs()
    cell_label = f"{args.cell_km:g}km".replace(".", "p")
    grid_csv = EXHIBIT_DATA / f"bold_grid{cell_label}_counts_by_kingdom.csv"

    all_counts, kingdom_counts = build_grid_counts(args.input, args.cell_km, args.chunksize)
    write_grid_counts(grid_csv, all_counts, kingdom_counts, args.cell_km)
    if args.cell_km == 100:
        write_grid_counts(GRID_COUNTS_CSV, all_counts, kingdom_counts, args.cell_km)

    chordata_counts = defaultdict(int)
    # Chordata is a phylum, so use the minimal CSV directly for this map.
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    cell_m = args.cell_km * 1000
    scanned = 0
    print("Binning Chordata for separate map.", flush=True)
    for chunk in iter_minimal_chunks(args.input, args.chunksize):
        sub = chunk[(chunk["phylum"].fillna("") == "Chordata") & (chunk["has_coord"].fillna("") == "1")]
        for _, row in sub.iterrows():
            lon = finite_float(row.get("longitude"))
            lat = finite_float(row.get("latitude"))
            if lon is None or lat is None:
                continue
            x, y = transformer.transform(lon, lat)
            chordata_counts[(int(np.floor(x / cell_m)), int(np.floor(y / cell_m)))] += 1
        scanned += len(chunk)
        print(f"  scanned {scanned:,} rows for Chordata", flush=True)

    print("Loading Natural Earth land outlines for grid maps.", flush=True)
    land_outline = load_land_outline()

    plot_grid(
        dict(all_counts),
        EXHIBIT_MAPS / f"map_world_all_observations_grid_{cell_label}.png",
        f"BOLD observations by {args.cell_km:g} km equal-area cell",
        args.cell_km,
        land_outline,
    )
    plot_grid(
        dict(chordata_counts),
        EXHIBIT_MAPS / f"map_world_chordata_grid_{cell_label}.png",
        f"BOLD Chordata observations by {args.cell_km:g} km equal-area cell",
        args.cell_km,
        land_outline,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
