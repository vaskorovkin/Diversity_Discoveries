#!/usr/bin/env python3
"""Create subnational/admin-1 BOLD count maps."""

from __future__ import annotations

import argparse
import csv
import time
from collections import Counter
from pathlib import Path

import cartopy.io.shapereader as shpreader
import geopandas as gpd
import matplotlib
from matplotlib.colors import LogNorm

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from pipeline_utils import EQUAL_AREA_CRS, PROCESSED_BOLD, EXHIBIT_MAPS, MINIMAL_CSV, clean, ensure_output_dirs, lognorm_or_none


def load_admin1() -> gpd.GeoDataFrame:
    shp = shpreader.natural_earth(resolution="10m", category="cultural", name="admin_1_states_provinces")
    admin = gpd.read_file(shp).to_crs("EPSG:4326")
    keep = ["geometry"]
    for col in ["adm1_code", "name", "name_en", "admin", "iso_a2", "iso_3166_2"]:
        if col in admin.columns:
            keep.append(col)
    admin = admin[keep].copy()
    admin["admin1_id"] = admin.index.astype(str)
    admin_equal_area = admin.to_crs(EQUAL_AREA_CRS)
    admin["area_km2"] = admin_equal_area.geometry.area / 1_000_000
    return admin


def count_admin1(input_path: Path, admin: gpd.GeoDataFrame, chunksize: int) -> tuple[Counter, Counter]:
    all_counts = Counter()
    chordata_counts = Counter()
    total = 0
    mapped = 0
    started = time.time()
    admin_small = admin[["admin1_id", "geometry"]]

    for chunk_index, chunk in enumerate(pd.read_csv(input_path, dtype=str, chunksize=chunksize), 1):
        sub = chunk[chunk["has_coord"].fillna("") == "1"].copy()
        sub["latitude"] = pd.to_numeric(sub["latitude"], errors="coerce")
        sub["longitude"] = pd.to_numeric(sub["longitude"], errors="coerce")
        sub = sub[sub["latitude"].between(-90, 90) & sub["longitude"].between(-180, 180)].copy()
        if not sub.empty:
            points = gpd.GeoDataFrame(
                sub,
                geometry=gpd.points_from_xy(sub["longitude"], sub["latitude"]),
                crs="EPSG:4326",
            )
            joined = gpd.sjoin(points, admin_small, how="inner", predicate="within")
            for admin1_id, count in joined.groupby("admin1_id").size().items():
                all_counts[str(admin1_id)] += int(count)
            chordata = joined[joined["phylum"].fillna("") == "Chordata"]
            for admin1_id, count in chordata.groupby("admin1_id").size().items():
                chordata_counts[str(admin1_id)] += int(count)
            mapped += len(joined)
        total += len(chunk)
        elapsed = max(time.time() - started, 1)
        print(
            f"chunk {chunk_index:,}: {total:,} rows scanned; {mapped:,} mapped to admin-1 "
            f"({total / elapsed:,.0f} rows/sec)",
            flush=True,
        )
    return all_counts, chordata_counts


def write_counts(admin: gpd.GeoDataFrame, counts: Counter, path: Path) -> gpd.GeoDataFrame:
    out = admin.copy()
    out["record_count"] = out["admin1_id"].map(lambda x: counts.get(str(x), 0)).astype(int)
    out["records_per_10000_km2"] = 0.0
    valid_area = out["area_km2"] > 0
    out.loc[valid_area, "records_per_10000_km2"] = (
        out.loc[valid_area, "record_count"] / out.loc[valid_area, "area_km2"] * 10_000
    )
    out.drop(columns="geometry").sort_values("record_count", ascending=False).to_csv(path, index=False)
    print(f"Wrote counts: {path}", flush=True)
    return out


def lognorm_for_series(values: pd.Series) -> LogNorm | None:
    positive = values[values > 0]
    if positive.empty:
        return None
    return LogNorm(vmin=float(positive.min()), vmax=float(positive.max()))


def plot_admin(admin_counts: gpd.GeoDataFrame, output: Path, title: str, value_col: str, legend_label: str) -> None:
    positive = admin_counts[admin_counts[value_col] > 0].copy()
    fig, ax = plt.subplots(figsize=(18, 9))
    admin_counts.boundary.plot(ax=ax, linewidth=0.06, color="#d0d0d0")
    if not positive.empty:
        norm = lognorm_or_none(int(positive[value_col].max())) if value_col == "record_count" else lognorm_for_series(positive[value_col])
        positive.plot(
            ax=ax,
            column=value_col,
            cmap="viridis",
            norm=norm,
            linewidth=0.02,
            edgecolor="#f2f2f2",
            legend=True,
            legend_kwds={"label": legend_label, "shrink": 0.62},
        )
    ax.set_title(title)
    ax.set_axis_off()
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 85)
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)
    print(f"Wrote map: {output}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--chunksize", type=int, default=300_000)
    args = parser.parse_args()

    ensure_output_dirs()
    print("Loading Natural Earth admin-1 polygons.", flush=True)
    admin = load_admin1()
    print(f"Admin-1 polygons: {len(admin):,}", flush=True)

    all_counts, chordata_counts = count_admin1(args.input, admin, args.chunksize)
    all_admin = write_counts(admin, all_counts, PROCESSED_BOLD / "bold_admin1_counts_all.csv")
    chordata_admin = write_counts(admin, chordata_counts, PROCESSED_BOLD / "bold_admin1_counts_chordata.csv")
    plot_admin(
        all_admin,
        EXHIBIT_MAPS / "map_world_all_observations_admin1.png",
        "BOLD observations by subnational division",
        "record_count",
        "record count, log scale",
    )
    plot_admin(
        chordata_admin,
        EXHIBIT_MAPS / "map_world_chordata_admin1.png",
        "BOLD Chordata observations by subnational division",
        "record_count",
        "record count, log scale",
    )
    plot_admin(
        all_admin,
        EXHIBIT_MAPS / "map_world_all_observations_admin1_per_10000km2.png",
        "BOLD observations per 10,000 square km by subnational division",
        "records_per_10000_km2",
        "records per 10,000 square km, log scale",
    )
    plot_admin(
        chordata_admin,
        EXHIBIT_MAPS / "map_world_chordata_admin1_per_10000km2.png",
        "BOLD Chordata observations per 10,000 square km by subnational division",
        "records_per_10000_km2",
        "records per 10,000 square km, log scale",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
