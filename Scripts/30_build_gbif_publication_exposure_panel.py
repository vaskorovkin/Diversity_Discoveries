#!/usr/bin/env python3
"""Build GBIF cohort-timed dataset-publication exposure panel.

This is the corrected-timing GBIF companion to the BOLD publication-yield
panel. The unit is cell x GBIF occurrence collection year. Outcomes count
distinct GBIF Literature API records linked to the occurrence dataset_key
within fixed future windows:

    collection year t -> dataset-linked publications in [t, t + 3]
    collection year t -> dataset-linked publications in [t, t + 5]
    collection year t -> dataset-linked publications in [t, t + 10]

Important caveat: GBIF Literature API links publications to datasets, not to
individual specimens/occurrences. Every occurrence cohort from a linked dataset
inherits the dataset publication links. These outcomes are therefore
cohort-timed dataset-citing publication exposure, not specimen-specific
downstream publication yield.

Inputs:
    Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv
    Data/processed/discovery/publications/gbif_dataset_to_pubs.csv

Output:
    Data/processed/discovery/publications/gbif_pub_exposure_cell_year_panel.csv
"""

from __future__ import annotations

import argparse
import math
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline_utils import EQUAL_AREA_CRS, LAND_CELLS_CSV, PROJECT_ROOT


PUB_DIR = PROJECT_ROOT / "Data" / "processed" / "discovery" / "publications"
GBIF_MINIMAL_CSV = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal.csv"
)
GBIF_PUBS_CSV = PUB_DIR / "gbif_dataset_to_pubs.csv"
OUTPUT_CSV = PUB_DIR / "gbif_pub_exposure_cell_year_panel.csv"

WINDOWS = (3, 5, 10)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def parse_year(value: object) -> int | None:
    text = "" if value is None else str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        year = int(text[:4])
        if 1500 <= year <= 2100:
            return year
    return None


def canonical_doi(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.I)
    text = re.sub(r"^doi:\s*", "", text, flags=re.I)
    return text.lower()


def publication_key(pub_id: object, doi: object = "") -> str:
    doi_key = canonical_doi(doi)
    if doi_key:
        return "doi:" + doi_key
    return f"gbif:{str(pub_id or '').strip()}"


def suffix(window: int) -> str:
    return f"0_{window}yr"


def valid_dataset_key(value: object) -> str:
    key = str(value or "").strip().lower()
    if UUID_RE.match(key):
        return key
    return ""


def load_land_cells(path: Path) -> pd.DataFrame:
    land = pd.read_csv(path, dtype={"cell_id": str, "iso_a3": str})
    required = {"cell_id", "cell_x", "cell_y", "centroid_lon", "centroid_lat", "continent", "country", "iso_a3"}
    missing = sorted(required - set(land.columns))
    if missing:
        raise ValueError(f"Land-cell file missing columns: {missing}")
    return land


def build_zero_panel(land: pd.DataFrame, start_year: int, end_year: int, max_pub_year: int) -> pd.DataFrame:
    years = np.arange(start_year, end_year + 1, dtype=int)
    panel = land.loc[land.index.repeat(len(years))].copy()
    panel["year"] = np.tile(years, len(land))
    country = panel["country"].fillna("")
    continent = panel["continent"].fillna("")
    panel["drop_rich_region_flag"] = (
        continent.isin(["Europe", "North America"]) | country.isin(["Australia", "New Zealand"])
    ).astype(int)
    for window in WINDOWS:
        panel[f"gbif_pub_complete_{suffix(window)}"] = (panel["year"] + window <= max_pub_year).astype(int)
    return panel[
        [
            "cell_id",
            "cell_x",
            "cell_y",
            "year",
            "centroid_lon",
            "centroid_lat",
            "continent",
            "country",
            "iso_a3",
            "drop_rich_region_flag",
        ]
        + [f"gbif_pub_complete_{suffix(window)}" for window in WINDOWS]
    ]


def cell_ids_from_coords(lon: np.ndarray, lat: np.ndarray, transformer: Transformer, cell_km: float) -> np.ndarray:
    x, y = transformer.transform(lon, lat)
    cell_m = cell_km * 1000
    cell_x = np.floor(x / cell_m).astype(int)
    cell_y = np.floor(y / cell_m).astype(int)
    return np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))


def load_dataset_publications(
    path: Path,
    max_publication_year: int | None,
    chunksize: int,
) -> tuple[dict[str, list[tuple[int, str]]], int]:
    if not path.exists():
        raise SystemExit(f"Missing GBIF dataset-publication file: {path}. Run Scripts/21_link_gbif_datasets_to_publications.py first.")
    out: dict[str, set[tuple[int, str]]] = {}
    max_seen_year = 0
    max_used_year = 0
    rows = 0
    for chunk in pd.read_csv(path, dtype=str, chunksize=chunksize):
        rows += len(chunk)
        for rec in chunk.to_dict("records"):
            dataset_key = valid_dataset_key(rec.get("dataset_key"))
            pub_id = str(rec.get("pub_id", "") or "").strip()
            year = parse_year(rec.get("year"))
            if not dataset_key or not pub_id or year is None:
                continue
            max_seen_year = max(max_seen_year, year)
            if max_publication_year is not None and year > max_publication_year:
                continue
            out.setdefault(dataset_key, set()).add((year, publication_key(pub_id, rec.get("doi", ""))))
            max_used_year = max(max_used_year, year)
        print(f"  GBIF publication rows scanned: {rows:,}; datasets with usable pubs: {len(out):,}", flush=True)
    if max_used_year == 0:
        raise SystemExit(f"No usable GBIF publication years found in {path}")
    final = {key: sorted(value) for key, value in out.items()}
    print(
        f"Loaded GBIF dataset publication map: {len(final):,} datasets; "
        f"max seen year={max_seen_year}; max used year={max_used_year}.",
        flush=True,
    )
    return final, max_used_year


def build_dataset_cohorts(
    gbif_csv: Path,
    linked_dataset_keys: set[str],
    land_cell_ids: set[str],
    transformer: Transformer,
    cell_km: float,
    start_year: int,
    end_year: int,
    chunksize: int,
) -> tuple[set[tuple[str, str, int]], dict[str, int]]:
    usecols = ["dataset_key", "has_coord", "latitude", "longitude", "year"]
    stats = {
        "rows_scanned": 0,
        "coordinate_year_rows": 0,
        "rows_with_linked_dataset": 0,
        "invalid_dataset_key_rows": 0,
    }
    cohorts: set[tuple[str, str, int]] = set()

    for i, chunk in enumerate(pd.read_csv(gbif_csv, dtype=str, usecols=usecols, chunksize=chunksize), 1):
        stats["rows_scanned"] += len(chunk)
        years = pd.to_numeric(chunk["year"], errors="coerce")
        sub = chunk.loc[
            (chunk["has_coord"].fillna("") == "1")
            & years.between(start_year, end_year)
        ].copy()
        if sub.empty:
            print(f"GBIF chunk {i:,}: {stats['rows_scanned']:,} rows scanned.", flush=True)
            continue

        sub_years = years.loc[sub.index].astype(int)
        lat = pd.to_numeric(sub["latitude"], errors="coerce")
        lon = pd.to_numeric(sub["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        sub = sub.loc[valid].copy()
        sub_years = sub_years.loc[sub.index].astype(int)
        if sub.empty:
            print(f"GBIF chunk {i:,}: {stats['rows_scanned']:,} rows scanned.", flush=True)
            continue

        dataset_keys = sub["dataset_key"].map(valid_dataset_key)
        stats["invalid_dataset_key_rows"] += int((dataset_keys == "").sum())
        linked = dataset_keys.isin(linked_dataset_keys)
        sub = sub.loc[linked].copy()
        sub_years = sub_years.loc[sub.index].astype(int)
        dataset_keys = dataset_keys.loc[sub.index]
        stats["rows_with_linked_dataset"] += len(sub)
        if sub.empty:
            print(f"GBIF chunk {i:,}: {stats['rows_scanned']:,} rows scanned; no linked datasets.", flush=True)
            continue

        cell_ids = cell_ids_from_coords(
            pd.to_numeric(sub["longitude"], errors="coerce").to_numpy(),
            pd.to_numeric(sub["latitude"], errors="coerce").to_numpy(),
            transformer,
            cell_km,
        )
        temp = pd.DataFrame(
            {
                "dataset_key": dataset_keys.to_numpy(),
                "cell_id": cell_ids,
                "year": sub_years.to_numpy(),
            }
        )
        temp = temp.loc[temp["cell_id"].isin(land_cell_ids)].drop_duplicates()
        stats["coordinate_year_rows"] += len(temp)
        cohorts.update((str(r.dataset_key), str(r.cell_id), int(r.year)) for r in temp.itertuples(index=False))

        print(
            f"GBIF chunk {i:,}: {stats['rows_scanned']:,} rows scanned; "
            f"{stats['rows_with_linked_dataset']:,} linked-dataset rows.",
            flush=True,
        )

    return cohorts, stats


def build_exposure_long(
    cohorts: set[tuple[str, str, int]],
    dataset_pubs: dict[str, list[tuple[int, str]]],
) -> tuple[pd.DataFrame, dict[str, int]]:
    stats = {
        "dataset_cohorts": 0,
        "dataset_cohorts_with_publication_window": 0,
        "distinct_exposure_events": 0,
    }
    pub_to_id: dict[str, int] = {}
    dataset_pub_ids: dict[str, list[tuple[int, int]]] = {}
    cohorts_by_year: dict[int, list[tuple[str, str]]] = defaultdict(list)
    rows: list[dict[str, object]] = []

    def pub_id(pub_key: str) -> int:
        existing = pub_to_id.get(pub_key)
        if existing is not None:
            return existing
        new_id = len(pub_to_id) + 1
        pub_to_id[pub_key] = new_id
        return new_id

    for dataset_key, pubs in dataset_pubs.items():
        dataset_pub_ids[dataset_key] = [(pub_year, pub_id(pub_key)) for pub_year, pub_key in pubs]

    for dataset_key, cell_id, collection_year in cohorts:
        cohorts_by_year[int(collection_year)].append((dataset_key, cell_id))

    for collection_year in sorted(cohorts_by_year):
        cell_window_pubs: dict[tuple[str, int], set[int]] = defaultdict(set)
        for dataset_key, cell_id in cohorts_by_year[collection_year]:
            stats["dataset_cohorts"] += 1
            matched = False
            for pub_year, compact_pub_id in dataset_pub_ids.get(dataset_key, []):
                lag = pub_year - int(collection_year)
                if lag < 0:
                    continue
                for window in WINDOWS:
                    if lag <= window:
                        cell_window_pubs[(str(cell_id), window)].add(compact_pub_id)
                        matched = True
            if matched:
                stats["dataset_cohorts_with_publication_window"] += 1
            if stats["dataset_cohorts"] % 100_000 == 0:
                print(
                    f"  expanded {stats['dataset_cohorts']:,} dataset cohorts; "
                    f"{stats['dataset_cohorts_with_publication_window']:,} with future pubs.",
                    flush=True,
                )

        stats["distinct_exposure_events"] += sum(len(pub_ids) for pub_ids in cell_window_pubs.values())
        rows.extend(
            {
                "cell_id": cell_id,
                "year": collection_year,
                "window": window,
                "n_publications": len(pub_ids),
            }
            for (cell_id, window), pub_ids in cell_window_pubs.items()
        )
        if cell_window_pubs:
            print(
                f"  year={collection_year}: {len(cell_window_pubs):,} nonzero cell-window groups; "
                f"{stats['distinct_exposure_events']:,} distinct exposure events so far.",
                flush=True,
            )

    stats["unique_publication_keys"] = len(pub_to_id)
    return pd.DataFrame(rows, columns=["cell_id", "year", "window", "n_publications"]), stats


def build_wide_panel(
    long: pd.DataFrame,
    land: pd.DataFrame,
    start_year: int,
    end_year: int,
    max_pub_year: int,
) -> pd.DataFrame:
    panel = build_zero_panel(land, start_year, end_year, max_pub_year)
    for window in WINDOWS:
        win_suffix = suffix(window)
        source_col = f"gbif_pub_total_{win_suffix}"
        sub = long.loc[
            long["window"] == window,
            ["cell_id", "year", "n_publications"],
        ].rename(columns={"n_publications": source_col})
        panel = panel.merge(sub, on=["cell_id", "year"], how="left")
        panel[source_col] = panel[source_col].fillna(0).astype(int)
        panel[f"gbif_pub_plantae_{win_suffix}"] = panel[source_col]
        for col in [source_col, f"gbif_pub_plantae_{win_suffix}"]:
            panel[f"any_{col}"] = (panel[col] > 0).astype(int)
            panel[f"log1p_{col}"] = np.log1p(panel[col])
    return panel


def write_summary(output_csv: Path, stats: list[tuple[str, object]]) -> None:
    path = output_csv.with_name(output_csv.stem + "_summary.csv")
    pd.DataFrame(stats, columns=["metric", "value"]).to_csv(path, index=False)
    print(f"Wrote summary: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gbif-records", type=Path, default=GBIF_MINIMAL_CSV)
    parser.add_argument("--gbif-pubs", type=Path, default=GBIF_PUBS_CSV)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--cell-km", type=float, default=100)
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--max-publication-year",
        type=int,
        default=date.today().year - 1,
        help="Highest publication year to use. Defaults to last complete calendar year.",
    )
    parser.add_argument("--chunksize", type=int, default=500_000)
    args = parser.parse_args()

    started = time.time()
    land = load_land_cells(args.land_cells)
    land_cell_ids = set(land["cell_id"].astype(str))
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    dataset_pubs, max_pub_year = load_dataset_publications(
        args.gbif_pubs,
        args.max_publication_year,
        args.chunksize,
    )

    cohorts, cohort_stats = build_dataset_cohorts(
        gbif_csv=args.gbif_records,
        linked_dataset_keys=set(dataset_pubs),
        land_cell_ids=land_cell_ids,
        transformer=transformer,
        cell_km=args.cell_km,
        start_year=args.start_year,
        end_year=args.end_year,
        chunksize=args.chunksize,
    )
    cohort_count = len(cohorts)
    print(f"Unique GBIF dataset-cell-year cohorts: {cohort_count:,}", flush=True)
    long, event_stats = build_exposure_long(cohorts, dataset_pubs)
    event_count = event_stats["distinct_exposure_events"]

    wide = build_wide_panel(long, land, args.start_year, args.end_year, max_pub_year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(args.output, index=False)
    print(f"Wrote GBIF publication-exposure panel: {args.output} ({len(wide):,} rows)", flush=True)

    summary: list[tuple[str, object]] = [
        ("start_year", args.start_year),
        ("end_year", args.end_year),
        ("max_pub_year", max_pub_year),
        ("max_publication_year_arg", args.max_publication_year),
        ("land_cells", len(land)),
        ("wide_rows", len(wide)),
        ("dataset_publication_keys", len(dataset_pubs)),
        ("dataset_cohorts", cohort_count),
        ("distinct_exposure_events", event_count),
        ("elapsed_min", round((time.time() - started) / 60, 2)),
    ]
    summary.extend(cohort_stats.items())
    summary.extend(event_stats.items())
    for col in [c for c in wide.columns if c.startswith("gbif_pub_") and not c.startswith("gbif_pub_complete_")]:
        summary.append((col, int(wide[col].sum())))
        summary.append((f"cell_years_with_{col}", int((wide[col] > 0).sum())))
    write_summary(args.output, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
