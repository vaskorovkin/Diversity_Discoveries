#!/usr/bin/env python3
"""Map global BOLD Fungi records by subnational admin-1 division.

The map uses only records with usable latitude/longitude. It spatially joins
those points to Natural Earth admin-1 polygons, counts records per polygon, and
saves both a PNG choropleth and a CSV of admin-1 counts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cartopy.io.shapereader as shpreader
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LogNorm


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_INPUT = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_global_fungi_minimal.tsv"
DEFAULT_OUTDIR = PROJECT_ROOT / "Output" / "maps"


def load_bold_points(path: Path) -> gpd.GeoDataFrame:
    usecols = [
        "processid",
        "specimenid",
        "record_id",
        "species",
        "country_ocean",
        "country_iso",
        "province_state",
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
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )


def load_admin1() -> gpd.GeoDataFrame:
    shp = shpreader.natural_earth(
        resolution="10m",
        category="cultural",
        name="admin_1_states_provinces",
    )
    admin = gpd.read_file(shp)
    admin = admin.to_crs("EPSG:4326")

    # Natural Earth schemas differ slightly across versions.
    keep = ["geometry"]
    for col in ["adm1_code", "name", "name_en", "admin", "iso_a2", "iso_3166_2"]:
        if col in admin.columns:
            keep.append(col)
    admin = admin[keep].copy()
    admin["admin1_id"] = admin.index.astype(str)
    return admin


def make_counts(points: gpd.GeoDataFrame, admin: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    joined = gpd.sjoin(
        points,
        admin[["admin1_id", "geometry"]],
        how="inner",
        predicate="within",
    )
    counts = joined.groupby("admin1_id").size().rename("n_records").reset_index()
    out = admin.merge(counts, on="admin1_id", how="left")
    out["n_records"] = out["n_records"].fillna(0).astype(int)
    return out


def plot_map(admin_counts: gpd.GeoDataFrame, output_png: Path) -> None:
    positive = admin_counts[admin_counts["n_records"] > 0].copy()

    fig, ax = plt.subplots(figsize=(18, 9))
    admin_counts.boundary.plot(ax=ax, linewidth=0.08, color="#d2d2d2")
    if not positive.empty:
        positive.plot(
            ax=ax,
            column="n_records",
            cmap="viridis",
            norm=LogNorm(vmin=1, vmax=max(positive["n_records"].max(), 1)),
            linewidth=0.03,
            edgecolor="#f2f2f2",
            legend=True,
            legend_kwds={"label": "BOLD Fungi records, log scale", "shrink": 0.62},
        )

    ax.set_title("BOLD Fungi Records by Subnational Division", fontsize=16)
    ax.set_axis_off()
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 85)
    fig.tight_layout()
    fig.savefig(output_png, dpi=220)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    output_png = args.outdir / "bold_global_fungi_admin1_map.png"
    output_csv = args.outdir / "bold_global_fungi_admin1_counts.csv"

    print(f"Reading BOLD records: {args.input}")
    points = load_bold_points(args.input)
    print(f"Records with usable coordinates: {len(points):,}")

    print("Loading Natural Earth admin-1 polygons.")
    admin = load_admin1()
    print(f"Admin-1 polygons: {len(admin):,}")

    print("Spatially joining records to admin-1 polygons.")
    admin_counts = make_counts(points, admin)
    mapped_records = int(admin_counts["n_records"].sum())
    mapped_polygons = int((admin_counts["n_records"] > 0).sum())
    print(f"Mapped records: {mapped_records:,}")
    print(f"Admin-1 divisions with at least one record: {mapped_polygons:,}")

    admin_counts.drop(columns="geometry").sort_values("n_records", ascending=False).to_csv(
        output_csv, index=False
    )
    print(f"Wrote counts: {output_csv}")

    print("Rendering map.")
    plot_map(admin_counts, output_png)
    print(f"Wrote map: {output_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
