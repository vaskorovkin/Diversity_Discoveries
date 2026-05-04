#!/usr/bin/env python3
"""Create exhibit tables with BOLD observation counts."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import pandas as pd

from pipeline_utils import EXHIBIT_TABLES, MINIMAL_CSV, ensure_output_dirs, iter_minimal_chunks, write_simple_latex_table


def aggregate_chunks(input_path: Path, chunksize: int) -> pd.DataFrame:
    """Read minimal CSV in chunks and return one row per record with needed cols."""
    chunks: list[pd.DataFrame] = []
    total_rows = 0
    started = time.time()
    cols = ["kingdom", "phylum", "class_name", "order", "family", "genus", "species",
            "country_ocean", "has_coord", "collection_year"]

    for chunk_index, chunk in enumerate(iter_minimal_chunks(input_path, chunksize), 1):
        chunks.append(chunk[cols].copy())
        total_rows += len(chunk)
        elapsed = max(time.time() - started, 1)
        print(f"chunk {chunk_index:,}: {total_rows:,} rows ({total_rows / elapsed:,.0f} rows/sec)", flush=True)

    return pd.concat(chunks, ignore_index=True)


def build_kingdom_table(df: pd.DataFrame) -> pd.DataFrame:
    kingdom = df["kingdom"].fillna("").str.strip().replace("", "Unknown")
    has_coord = df["has_coord"].fillna("") == "1"
    cyear = pd.to_numeric(df["collection_year"], errors="coerce")
    country = df["country_ocean"].fillna("").str.strip()
    species = df["species"].fillna("").str.strip()

    g = pd.DataFrame({
        "kingdom": kingdom,
        "has_coord": has_coord.astype(int),
        "country": country,
        "species": species,
        "cyear": cyear,
    })

    agg = g.groupby("kingdom", sort=False).agg(
        record_count=("has_coord", "size"),
        records_with_coordinates=("has_coord", "sum"),
        unique_countries=("country", lambda x: x[x != ""].nunique()),
        unique_species=("species", lambda x: x[x != ""].nunique()),
        first_collection_year=("cyear", "min"),
        last_collection_year=("cyear", "max"),
    ).reset_index()

    total = agg["record_count"].sum()
    agg["record_share_percent"] = (100 * agg["record_count"] / total).round(2)
    agg["share_with_coordinates"] = (100 * agg["records_with_coordinates"] / agg["record_count"]).round(2)
    agg["first_collection_year"] = agg["first_collection_year"].astype("Int64").astype(str).replace("<NA>", "")
    agg["last_collection_year"] = agg["last_collection_year"].astype("Int64").astype(str).replace("<NA>", "")

    agg = agg.sort_values("record_count", ascending=False)
    return agg[["kingdom", "record_count", "record_share_percent",
                "records_with_coordinates", "share_with_coordinates",
                "unique_countries", "unique_species",
                "first_collection_year", "last_collection_year"]]


def build_animalia_class_table(df: pd.DataFrame) -> pd.DataFrame:
    animalia = df[df["kingdom"].fillna("").str.strip() == "Animalia"].copy()
    class_name = animalia["class_name"].fillna("").str.strip().replace("", "Unknown")
    has_coord = (animalia["has_coord"].fillna("") == "1").astype(int)
    country = animalia["country_ocean"].fillna("").str.strip()
    species = animalia["species"].fillna("").str.strip()
    order = animalia["order"].fillna("").str.strip()
    family = animalia["family"].fillna("").str.strip()

    g = pd.DataFrame({
        "class": class_name.values,
        "has_coord": has_coord.values,
        "country": country.values,
        "species": species.values,
        "order": order.values,
        "family": family.values,
    })

    agg = g.groupby("class", sort=False).agg(
        record_count=("has_coord", "size"),
        records_with_coordinates=("has_coord", "sum"),
        unique_countries=("country", lambda x: x[x != ""].nunique()),
        unique_orders=("order", lambda x: x[x != ""].nunique()),
        unique_families=("family", lambda x: x[x != ""].nunique()),
        unique_species=("species", lambda x: x[x != ""].nunique()),
    ).reset_index()

    total = agg["record_count"].sum()
    agg["record_share_percent"] = (100 * agg["record_count"] / total).round(2)
    agg["share_with_coordinates"] = (100 * agg["records_with_coordinates"] / agg["record_count"]).round(2)

    agg = agg.sort_values("record_count", ascending=False)
    return agg[["class", "record_count", "record_share_percent",
                "records_with_coordinates", "share_with_coordinates",
                "unique_countries", "unique_orders", "unique_families", "unique_species"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--outdir", type=Path, default=EXHIBIT_TABLES)
    parser.add_argument("--chunksize", type=int, default=500_000)
    args = parser.parse_args()

    ensure_output_dirs()
    args.outdir.mkdir(parents=True, exist_ok=True)

    print(f"Reading minimal records: {args.input}", flush=True)
    df = aggregate_chunks(args.input, args.chunksize)
    print(f"Total rows loaded: {len(df):,}", flush=True)

    started = time.time()
    kingdom_df = build_kingdom_table(df)
    kingdom_csv = args.outdir / "table_observations_by_kingdom.csv"
    kingdom_df.to_csv(kingdom_csv, index=False)
    print(f"Wrote: {kingdom_csv} ({time.time() - started:.1f}s)", flush=True)

    started = time.time()
    animalia_df = build_animalia_class_table(df)
    animalia_csv = args.outdir / "table_animalia_by_class.csv"
    animalia_df.to_csv(animalia_csv, index=False)
    print(f"Wrote: {animalia_csv} ({time.time() - started:.1f}s)", flush=True)

    write_simple_latex_table(
        kingdom_csv,
        args.outdir / "table_observations_by_kingdom.tex",
        "BOLD observations by kingdom",
        "tab:bold_observations_by_kingdom",
    )
    write_simple_latex_table(
        animalia_csv,
        args.outdir / "table_animalia_by_class.tex",
        "BOLD Animalia observations by class",
        "tab:bold_animalia_by_class",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
