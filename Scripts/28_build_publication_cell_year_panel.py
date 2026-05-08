#!/usr/bin/env python3
"""Build the unified Option A publication-linked cell-year panel.

Inputs:
    Data/processed/bold/bold_minimal_records.csv
    Data/processed/discovery/publications/bold_accession_to_pubmed.csv
    Data/processed/discovery/publications/pubmed_id_to_metadata.csv
    Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv
    Data/processed/discovery/publications/gbif_dataset_to_pubs.csv

Outputs:
    Data/processed/discovery/publications/pubs_cell_year_panel_long.csv
    Data/processed/discovery/publications/pubs_cell_year_panel.csv

The BOLD branch joins records to publications through exploded/normalized
`insdc_acs` accessions, not through process IDs. The GBIF branch is
dataset-level attribution: occurrences inherit GBIF dataset-citing
publication links, so GBIF publication counts are dataset publication exposure
rather than direct specimen citations.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline_utils import EQUAL_AREA_CRS, LAND_CELLS_CSV, MINIMAL_CSV, PROJECT_ROOT


PUB_DIR = PROJECT_ROOT / "Data" / "processed" / "discovery" / "publications"
GBIF_MINIMAL_CSV = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal.csv"
)
BOLD_LINKS_CSV = PUB_DIR / "bold_accession_to_pubmed.csv"
PUBMED_METADATA_CSV = PUB_DIR / "pubmed_id_to_metadata.csv"
GBIF_PUBS_CSV = PUB_DIR / "gbif_dataset_to_pubs.csv"
LONG_OUTPUT_CSV = PUB_DIR / "pubs_cell_year_panel_long.csv"
WIDE_OUTPUT_CSV = PUB_DIR / "pubs_cell_year_panel.csv"
DEFAULT_WORK_DB = PUB_DIR / "publication_cell_year_work.db"

ACCESSION_SPLIT_RE = re.compile(r"[|;,\s]+")
ACCESSION_VERSION_RE = re.compile(r"\.[0-9]+$")
ACCESSION_TOKEN_RE = re.compile(r"^[A-Z0-9_]{5,25}$")
KINGDOM_ORDER = ["Animalia", "Plantae", "Fungi", "Bacteria", "other_blank"]
WIDE_SPECS = [
    ("pubs_total", "all", "all"),
    ("pubs_bold", "bold", "all"),
    ("pubs_gbif", "gbif", "all"),
    ("pubs_animalia", "all", "Animalia"),
    ("pubs_plantae", "all", "Plantae"),
    ("pubs_fungi", "all", "Fungi"),
    ("pubs_bacteria", "all", "Bacteria"),
    ("pubs_other_blank", "all", "other_blank"),
    ("pubs_bold_animalia", "bold", "Animalia"),
    ("pubs_bold_plantae", "bold", "Plantae"),
    ("pubs_bold_fungi", "bold", "Fungi"),
    ("pubs_bold_bacteria", "bold", "Bacteria"),
    ("pubs_bold_other_blank", "bold", "other_blank"),
    ("pubs_gbif_plantae", "gbif", "Plantae"),
]


def normalize_accession(value: str) -> str:
    token = ACCESSION_VERSION_RE.sub("", str(value).strip().upper())
    if not token:
        return ""
    if not ACCESSION_TOKEN_RE.match(token):
        return ""
    if not any(ch.isalpha() for ch in token):
        return ""
    if not any(ch.isdigit() for ch in token):
        return ""
    return token


def accession_tokens(value: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in ACCESSION_SPLIT_RE.split(str(value or "")):
        token = normalize_accession(raw)
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


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
    text = "" if value is None else str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.I)
    text = re.sub(r"^doi:\s*", "", text, flags=re.I)
    return text.lower()


def publication_key(prefix: str, identifier: str, doi: object = "") -> str:
    doi_key = canonical_doi(doi)
    if doi_key:
        return "doi:" + doi_key
    return f"{prefix}:{str(identifier).strip()}"


def normalize_kingdom(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if text in {"Animalia", "Plantae", "Fungi", "Bacteria"}:
        return text
    return "other_blank"


def load_land_cells(path: Path) -> pd.DataFrame:
    land = pd.read_csv(path, dtype={"cell_id": str, "iso_a3": str})
    required = {"cell_id", "cell_x", "cell_y", "centroid_lon", "centroid_lat", "continent", "country", "iso_a3"}
    missing = sorted(required - set(land.columns))
    if missing:
        raise ValueError(f"Land-cell file missing columns: {missing}")
    return land


def build_zero_panel(land: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    years = np.arange(start_year, end_year + 1, dtype=int)
    panel = land.loc[land.index.repeat(len(years))].copy()
    panel["year"] = np.tile(years, len(land))
    country = panel["country"].fillna("")
    continent = panel["continent"].fillna("")
    panel["drop_rich_region_flag"] = (
        continent.isin(["Europe", "North America"]) | country.isin(["Australia", "New Zealand"])
    ).astype(int)
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
    ]


def cell_ids_from_coords(lon: np.ndarray, lat: np.ndarray, transformer: Transformer, cell_km: float) -> np.ndarray:
    x, y = transformer.transform(lon, lat)
    cell_m = cell_km * 1000
    cell_x = np.floor(x / cell_m).astype(int)
    cell_y = np.floor(y / cell_m).astype(int)
    return np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))


def load_pubmed_metadata(path: Path, start_year: int, end_year: int) -> dict[str, tuple[int, str]]:
    if not path.exists():
        raise SystemExit(
            f"Missing PubMed metadata: {path}. Run Scripts/20b_fetch_pubmed_metadata.py first."
        )
    out: dict[str, tuple[int, str]] = {}
    for chunk in pd.read_csv(path, dtype=str, chunksize=500_000):
        for row in chunk.itertuples(index=False):
            data = row._asdict()
            pmid = str(data.get("pubmed_id", "") or "").strip()
            year = parse_year(data.get("year"))
            if not pmid or year is None or not (start_year <= year <= end_year):
                continue
            out[pmid] = (year, publication_key("pubmed", pmid, data.get("doi", "")))
    print(f"Loaded PubMed metadata for {len(out):,} PMIDs in year window.", flush=True)
    return out


def load_bold_accession_publications(
    links_csv: Path,
    pmid_metadata: dict[str, tuple[int, str]],
    chunksize: int,
) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, set[tuple[int, str]]] = defaultdict(set)
    rows = 0
    for chunk in pd.read_csv(links_csv, dtype=str, usecols=["accession", "pubmed_id"], chunksize=chunksize):
        rows += len(chunk)
        chunk = chunk.dropna(subset=["accession", "pubmed_id"])
        for accession, pmid in zip(chunk["accession"], chunk["pubmed_id"]):
            pmid = str(pmid).strip()
            if not pmid or pmid not in pmid_metadata:
                continue
            accession = normalize_accession(accession)
            if accession:
                out[accession].add(pmid_metadata[pmid])
        print(f"  BOLD link rows scanned: {rows:,}; accessions with in-window PMIDs: {len(out):,}", flush=True)
    final = {key: sorted(value) for key, value in out.items()}
    print(f"Loaded BOLD accession publication map: {len(final):,} accessions.", flush=True)
    return final


def load_gbif_dataset_publications(
    gbif_pubs_csv: Path,
    start_year: int,
    end_year: int,
    chunksize: int,
) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, set[tuple[int, str]]] = defaultdict(set)
    rows = 0
    for chunk in pd.read_csv(gbif_pubs_csv, dtype=str, chunksize=chunksize):
        rows += len(chunk)
        for rec in chunk.to_dict("records"):
            dataset_key = str(rec.get("dataset_key", "") or "").strip()
            pub_id = str(rec.get("pub_id", "") or "").strip()
            year = parse_year(rec.get("year"))
            if not dataset_key or not pub_id or year is None or not (start_year <= year <= end_year):
                continue
            out[dataset_key].add((year, publication_key("gbif", pub_id, rec.get("doi", ""))))
        print(f"  GBIF publication rows scanned: {rows:,}; datasets with in-window pubs: {len(out):,}", flush=True)
    final = {key: sorted(value) for key, value in out.items()}
    print(f"Loaded GBIF dataset publication map: {len(final):,} datasets.", flush=True)
    return final


def init_work_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("DROP TABLE IF EXISTS bold_acc_cells")
    conn.execute("DROP TABLE IF EXISTS gbif_dataset_cells")
    conn.execute("DROP TABLE IF EXISTS publication_events")
    conn.execute(
        """
        CREATE TABLE bold_acc_cells (
            accession TEXT NOT NULL,
            cell_id TEXT NOT NULL,
            kingdom TEXT NOT NULL,
            PRIMARY KEY (accession, cell_id, kingdom)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gbif_dataset_cells (
            dataset_key TEXT NOT NULL,
            cell_id TEXT NOT NULL,
            PRIMARY KEY (dataset_key, cell_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE publication_events (
            cell_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            source TEXT NOT NULL,
            kingdom TEXT NOT NULL,
            pub_key TEXT NOT NULL,
            PRIMARY KEY (cell_id, year, source, kingdom, pub_key)
        )
        """
    )
    conn.commit()


def insert_many(conn: sqlite3.Connection, sql: str, rows: set[tuple[str, ...]], label: str) -> None:
    if not rows:
        return
    conn.executemany(sql, sorted(rows))
    conn.commit()
    print(f"  inserted {len(rows):,} unique {label}", flush=True)


def build_bold_accession_cells(
    conn: sqlite3.Connection,
    bold_csv: Path,
    accession_pubs: dict[str, list[tuple[int, str]]],
    land_cell_ids: set[str],
    transformer: Transformer,
    cell_km: float,
    chunksize: int,
) -> None:
    usecols = ["insdc_acs", "has_coord", "latitude", "longitude", "kingdom"]
    rows_seen = 0
    for i, chunk in enumerate(pd.read_csv(bold_csv, dtype=str, usecols=usecols, chunksize=chunksize), 1):
        rows_seen += len(chunk)
        sub = chunk.loc[chunk["has_coord"].fillna("") == "1"].copy()
        if sub.empty:
            continue
        lat = pd.to_numeric(sub["latitude"], errors="coerce")
        lon = pd.to_numeric(sub["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        sub = sub.loc[valid].copy()
        if sub.empty:
            continue
        cell_ids = cell_ids_from_coords(
            pd.to_numeric(sub["longitude"], errors="coerce").to_numpy(),
            pd.to_numeric(sub["latitude"], errors="coerce").to_numpy(),
            transformer,
            cell_km,
        )
        sub["cell_id"] = cell_ids
        sub = sub.loc[sub["cell_id"].isin(land_cell_ids)]
        records: set[tuple[str, str, str]] = set()
        for rec in sub[["insdc_acs", "cell_id", "kingdom"]].itertuples(index=False):
            kingdom = normalize_kingdom(rec.kingdom)
            for accession in accession_tokens(rec.insdc_acs):
                if accession in accession_pubs:
                    records.add((accession, str(rec.cell_id), kingdom))
        insert_many(
            conn,
            "INSERT OR IGNORE INTO bold_acc_cells(accession, cell_id, kingdom) VALUES (?, ?, ?)",
            records,
            "BOLD accession-cell rows",
        )
        print(f"BOLD chunk {i:,}: {rows_seen:,} rows scanned.", flush=True)


def build_gbif_dataset_cells(
    conn: sqlite3.Connection,
    gbif_csv: Path,
    dataset_pubs: dict[str, list[tuple[int, str]]],
    land_cell_ids: set[str],
    transformer: Transformer,
    cell_km: float,
    chunksize: int,
) -> None:
    usecols = ["dataset_key", "has_coord", "latitude", "longitude"]
    rows_seen = 0
    dataset_keys_with_pubs = set(dataset_pubs)
    for i, chunk in enumerate(pd.read_csv(gbif_csv, dtype=str, usecols=usecols, chunksize=chunksize), 1):
        rows_seen += len(chunk)
        sub = chunk.loc[
            (chunk["has_coord"].fillna("") == "1")
            & (chunk["dataset_key"].fillna("").isin(dataset_keys_with_pubs))
        ].copy()
        if sub.empty:
            continue
        lat = pd.to_numeric(sub["latitude"], errors="coerce")
        lon = pd.to_numeric(sub["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        sub = sub.loc[valid].copy()
        if sub.empty:
            continue
        cell_ids = cell_ids_from_coords(
            pd.to_numeric(sub["longitude"], errors="coerce").to_numpy(),
            pd.to_numeric(sub["latitude"], errors="coerce").to_numpy(),
            transformer,
            cell_km,
        )
        sub["cell_id"] = cell_ids
        sub = sub.loc[sub["cell_id"].isin(land_cell_ids)]
        records = {
            (str(dataset_key), str(cell_id))
            for dataset_key, cell_id in zip(sub["dataset_key"], sub["cell_id"])
        }
        insert_many(
            conn,
            "INSERT OR IGNORE INTO gbif_dataset_cells(dataset_key, cell_id) VALUES (?, ?)",
            records,
            "GBIF dataset-cell rows",
        )
        print(f"GBIF chunk {i:,}: {rows_seen:,} rows scanned.", flush=True)


def populate_events(
    conn: sqlite3.Connection,
    accession_pubs: dict[str, list[tuple[int, str]]],
    dataset_pubs: dict[str, list[tuple[int, str]]],
    batch_size: int,
) -> None:
    buffer: list[tuple[str, int, str, str, str]] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        conn.executemany(
            """
            INSERT OR IGNORE INTO publication_events
                (cell_id, year, source, kingdom, pub_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            buffer,
        )
        conn.commit()
        buffer = []

    n = 0
    for accession, cell_id, kingdom in conn.execute("SELECT accession, cell_id, kingdom FROM bold_acc_cells"):
        for year, pub_key in accession_pubs.get(accession, []):
            buffer.append((cell_id, int(year), "bold", kingdom, pub_key))
        n += 1
        if len(buffer) >= batch_size:
            flush()
    flush()
    print(f"Expanded BOLD accession-cell rows: {n:,}", flush=True)

    n = 0
    for dataset_key, cell_id in conn.execute("SELECT dataset_key, cell_id FROM gbif_dataset_cells"):
        for year, pub_key in dataset_pubs.get(dataset_key, []):
            buffer.append((cell_id, int(year), "gbif", "Plantae", pub_key))
        n += 1
        if len(buffer) >= batch_size:
            flush()
    flush()
    print(f"Expanded GBIF dataset-cell rows: {n:,}", flush=True)


def build_long_panel(conn: sqlite3.Connection) -> pd.DataFrame:
    queries = [
        "SELECT cell_id, year, source, kingdom, COUNT(DISTINCT pub_key) AS n_publications FROM publication_events GROUP BY cell_id, year, source, kingdom",
        "SELECT cell_id, year, source, 'all' AS kingdom, COUNT(DISTINCT pub_key) AS n_publications FROM publication_events GROUP BY cell_id, year, source",
        "SELECT cell_id, year, 'all' AS source, kingdom, COUNT(DISTINCT pub_key) AS n_publications FROM publication_events GROUP BY cell_id, year, kingdom",
        "SELECT cell_id, year, 'all' AS source, 'all' AS kingdom, COUNT(DISTINCT pub_key) AS n_publications FROM publication_events GROUP BY cell_id, year",
    ]
    frames = [pd.read_sql_query(query, conn) for query in queries]
    long = pd.concat(frames, ignore_index=True)
    long["any_publications"] = (long["n_publications"] > 0).astype(int)
    long["log1p_publications"] = np.log1p(long["n_publications"])
    return long.sort_values(["cell_id", "year", "source", "kingdom"])


def build_wide_panel(long: pd.DataFrame, land: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    panel = build_zero_panel(land, start_year, end_year)
    for col, source, kingdom in WIDE_SPECS:
        sub = long.loc[(long["source"] == source) & (long["kingdom"] == kingdom), ["cell_id", "year", "n_publications"]]
        sub = sub.rename(columns={"n_publications": col})
        panel = panel.merge(sub, on=["cell_id", "year"], how="left")
        panel[col] = panel[col].fillna(0).astype(int)
        panel[f"any_{col}"] = (panel[col] > 0).astype(int)
        panel[f"log1p_{col}"] = np.log1p(panel[col])
    return panel


def write_summary(path: Path, stats: list[tuple[str, object]]) -> None:
    pd.DataFrame(stats, columns=["metric", "value"]).to_csv(path, index=False)
    print(f"Wrote summary: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bold-records", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--bold-links", type=Path, default=BOLD_LINKS_CSV)
    parser.add_argument("--pubmed-metadata", type=Path, default=PUBMED_METADATA_CSV)
    parser.add_argument("--gbif-records", type=Path, default=GBIF_MINIMAL_CSV)
    parser.add_argument("--gbif-pubs", type=Path, default=GBIF_PUBS_CSV)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--long-output", type=Path, default=LONG_OUTPUT_CSV)
    parser.add_argument("--wide-output", type=Path, default=WIDE_OUTPUT_CSV)
    parser.add_argument("--work-db", type=Path, default=DEFAULT_WORK_DB)
    parser.add_argument("--cell-km", type=float, default=100)
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--chunksize", type=int, default=500_000)
    parser.add_argument("--insert-batch-size", type=int, default=100_000)
    parser.add_argument("--keep-work-db", action="store_true")
    args = parser.parse_args()

    started = time.time()
    land = load_land_cells(args.land_cells)
    land_cell_ids = set(land["cell_id"].astype(str))
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)

    pubmed_metadata = load_pubmed_metadata(args.pubmed_metadata, args.start_year, args.end_year)
    accession_pubs = load_bold_accession_publications(args.bold_links, pubmed_metadata, args.chunksize)
    dataset_pubs = load_gbif_dataset_publications(args.gbif_pubs, args.start_year, args.end_year, args.chunksize)

    args.work_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.work_db) as conn:
        init_work_db(conn)
        build_bold_accession_cells(
            conn,
            args.bold_records,
            accession_pubs,
            land_cell_ids,
            transformer,
            args.cell_km,
            args.chunksize,
        )
        build_gbif_dataset_cells(
            conn,
            args.gbif_records,
            dataset_pubs,
            land_cell_ids,
            transformer,
            args.cell_km,
            args.chunksize,
        )
        populate_events(conn, accession_pubs, dataset_pubs, args.insert_batch_size)
        event_count = conn.execute("SELECT COUNT(*) FROM publication_events").fetchone()[0]
        long = build_long_panel(conn)

    args.long_output.parent.mkdir(parents=True, exist_ok=True)
    long.to_csv(args.long_output, index=False)
    print(f"Wrote long panel: {args.long_output} ({len(long):,} rows)", flush=True)

    wide = build_wide_panel(long, land, args.start_year, args.end_year)
    wide.to_csv(args.wide_output, index=False)
    print(f"Wrote wide panel: {args.wide_output} ({len(wide):,} rows)", flush=True)

    summary = args.wide_output.with_name(args.wide_output.stem + "_summary.csv")
    stats: list[tuple[str, object]] = [
        ("start_year", args.start_year),
        ("end_year", args.end_year),
        ("land_cells", len(land)),
        ("wide_rows", len(wide)),
        ("long_rows", len(long)),
        ("distinct_publication_events", event_count),
        ("elapsed_min", round((time.time() - started) / 60, 2)),
    ]
    for col, _, _ in WIDE_SPECS:
        stats.append((col, int(wide[col].sum())))
        stats.append((f"cell_years_with_{col}", int((wide[col] > 0).sum())))
    write_summary(summary, stats)

    if not args.keep_work_db:
        for suffix in ["", "-wal", "-shm"]:
            path = Path(str(args.work_db) + suffix)
            if path.exists():
                path.unlink()
        print(f"Removed work DB: {args.work_db}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
