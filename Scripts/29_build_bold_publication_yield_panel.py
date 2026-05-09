#!/usr/bin/env python3
"""Build BOLD specimen-cohort downstream publication-yield panel.

This is the corrected Option A outcome for causal downstream-publication
analysis. The unit is cell x BOLD collection year. Outcomes count distinct
PubMed publications linked to BOLD specimens collected in that cell-year within
fixed future windows:

    collection year t -> publications in [t, t + 3]
    collection year t -> publications in [t, t + 5]
    collection year t -> publications in [t, t + 10]

This differs from the broader publication-exposure panel built by
28_build_publication_cell_year_panel.py, which indexes outcomes by publication
year and includes GBIF dataset-level literature exposure. This script is
BOLD-only and uses accession-level PubMed links, so it is closer to
specimen-specific downstream output.

Inputs:
    Data/processed/bold/bold_minimal_records.csv
    Data/processed/discovery/publications/bold_accession_to_pubmed.csv
    Data/processed/discovery/publications/pubmed_id_to_metadata.csv

Output:
    Data/processed/discovery/publications/bold_pub_yield_cell_year_panel.csv
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
BOLD_LINKS_CSV = PUB_DIR / "bold_accession_to_pubmed.csv"
PUBMED_METADATA_CSV = PUB_DIR / "pubmed_id_to_metadata.csv"
OUTPUT_CSV = PUB_DIR / "bold_pub_yield_cell_year_panel.csv"
DEFAULT_WORK_DB = PUB_DIR / "bold_pub_yield_work.db"

ACCESSION_SPLIT_RE = re.compile(r"[|;,\s]+")
ACCESSION_VERSION_RE = re.compile(r"\.[0-9]+$")
ACCESSION_TOKEN_RE = re.compile(r"^[A-Z0-9_]{5,25}$")
WINDOWS = (3, 5, 10)
KINGDOMS = ("Animalia", "Plantae", "Fungi", "Bacteria")


def normalize_accession(value: object) -> str:
    token = ACCESSION_VERSION_RE.sub("", str(value or "").strip().upper())
    if not token:
        return ""
    if not ACCESSION_TOKEN_RE.match(token):
        return ""
    if not any(ch.isalpha() for ch in token):
        return ""
    if not any(ch.isdigit() for ch in token):
        return ""
    return token


def accession_tokens(value: object) -> list[str]:
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
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.I)
    text = re.sub(r"^doi:\s*", "", text, flags=re.I)
    return text.lower()


def publication_key(pmid: str, doi: object = "") -> str:
    doi_key = canonical_doi(doi)
    if doi_key:
        return "doi:" + doi_key
    return f"pubmed:{str(pmid).strip()}"


def normalize_kingdom(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if text in KINGDOMS:
        return text
    return "other"


def suffix(window: int) -> str:
    return f"0_{window}yr"


def base_columns() -> list[str]:
    out = ["bold_pub_total"]
    out.extend(f"bold_pub_{kingdom.lower()}" for kingdom in KINGDOMS)
    return out


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
        panel[f"bold_pub_complete_{suffix(window)}"] = (panel["year"] + window <= max_pub_year).astype(int)
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
        + [f"bold_pub_complete_{suffix(window)}" for window in WINDOWS]
    ]


def cell_ids_from_coords(lon: np.ndarray, lat: np.ndarray, transformer: Transformer, cell_km: float) -> np.ndarray:
    x, y = transformer.transform(lon, lat)
    cell_m = cell_km * 1000
    cell_x = np.floor(x / cell_m).astype(int)
    cell_y = np.floor(y / cell_m).astype(int)
    return np.char.add(np.char.add(cell_x.astype(str), "_"), cell_y.astype(str))


def load_pubmed_metadata(path: Path) -> tuple[dict[str, tuple[int, str]], int]:
    if not path.exists():
        raise SystemExit(f"Missing PubMed metadata: {path}. Run Scripts/20b_fetch_pubmed_metadata.py first.")
    out: dict[str, tuple[int, str]] = {}
    max_year = 0
    for chunk in pd.read_csv(path, dtype=str, chunksize=500_000):
        for row in chunk.to_dict("records"):
            pmid = str(row.get("pubmed_id", "") or "").strip()
            year = parse_year(row.get("year"))
            if not pmid or year is None:
                continue
            out[pmid] = (year, publication_key(pmid, row.get("doi", "")))
            max_year = max(max_year, year)
    if max_year == 0:
        raise SystemExit(f"No usable publication years found in {path}")
    print(f"Loaded PubMed metadata: {len(out):,} PMIDs; max publication year={max_year}.", flush=True)
    return out, max_year


def load_accession_publications(
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
        print(f"  BOLD link rows scanned: {rows:,}; accessions with PMID years: {len(out):,}", flush=True)
    final = {key: sorted(value) for key, value in out.items()}
    print(f"Loaded accession publication map: {len(final):,} accessions.", flush=True)
    return final


def init_work_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("DROP TABLE IF EXISTS yield_events")
    conn.execute(
        """
        CREATE TABLE yield_events (
            cell_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            window INTEGER NOT NULL,
            kingdom TEXT NOT NULL,
            pub_key TEXT NOT NULL,
            PRIMARY KEY (cell_id, year, window, kingdom, pub_key)
        )
        """
    )
    conn.commit()


def build_yield_events(
    conn: sqlite3.Connection,
    bold_csv: Path,
    accession_pubs: dict[str, list[tuple[int, str]]],
    land_cell_ids: set[str],
    transformer: Transformer,
    cell_km: float,
    start_year: int,
    end_year: int,
    chunksize: int,
    insert_batch_size: int,
) -> dict[str, int]:
    usecols = ["insdc_acs", "has_coord", "latitude", "longitude", "collection_year", "kingdom"]
    stats = {
        "rows_scanned": 0,
        "coordinate_year_rows": 0,
        "candidate_records_with_linked_accession": 0,
        "events_buffered": 0,
    }
    buffer: set[tuple[str, int, int, str, str]] = set()

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        conn.executemany(
            """
            INSERT OR IGNORE INTO yield_events
                (cell_id, year, window, kingdom, pub_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            sorted(buffer),
        )
        conn.commit()
        buffer = set()

    for i, chunk in enumerate(pd.read_csv(bold_csv, dtype=str, usecols=usecols, chunksize=chunksize), 1):
        stats["rows_scanned"] += len(chunk)
        years = pd.to_numeric(chunk["collection_year"], errors="coerce")
        sub = chunk.loc[
            (chunk["has_coord"].fillna("") == "1")
            & years.between(start_year, end_year)
        ].copy()
        if sub.empty:
            print(f"BOLD chunk {i:,}: {stats['rows_scanned']:,} rows scanned.", flush=True)
            continue

        sub_years = years.loc[sub.index].astype(int)
        lat = pd.to_numeric(sub["latitude"], errors="coerce")
        lon = pd.to_numeric(sub["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        sub = sub.loc[valid].copy()
        sub_years = sub_years.loc[sub.index].astype(int)
        if sub.empty:
            print(f"BOLD chunk {i:,}: {stats['rows_scanned']:,} rows scanned.", flush=True)
            continue

        cell_ids = cell_ids_from_coords(
            pd.to_numeric(sub["longitude"], errors="coerce").to_numpy(),
            pd.to_numeric(sub["latitude"], errors="coerce").to_numpy(),
            transformer,
            cell_km,
        )
        sub["cell_id"] = cell_ids
        sub["year"] = sub_years.to_numpy()
        sub = sub.loc[sub["cell_id"].isin(land_cell_ids)].copy()
        stats["coordinate_year_rows"] += len(sub)

        for rec in sub[["insdc_acs", "cell_id", "year", "kingdom"]].itertuples(index=False):
            accessions = [accession for accession in accession_tokens(rec.insdc_acs) if accession in accession_pubs]
            if not accessions:
                continue
            stats["candidate_records_with_linked_accession"] += 1
            collection_year = int(rec.year)
            kingdom = normalize_kingdom(rec.kingdom)
            for accession in accessions:
                for pub_year, pub_key in accession_pubs[accession]:
                    lag = pub_year - collection_year
                    if lag < 0:
                        continue
                    for window in WINDOWS:
                        if lag <= window:
                            buffer.add((str(rec.cell_id), collection_year, window, kingdom, pub_key))
            stats["events_buffered"] += len(buffer)
            if len(buffer) >= insert_batch_size:
                flush()

        flush()
        print(
            f"BOLD chunk {i:,}: {stats['rows_scanned']:,} rows scanned; "
            f"{stats['candidate_records_with_linked_accession']:,} records with linked accessions.",
            flush=True,
        )

    flush()
    return stats


def build_long_panel(conn: sqlite3.Connection) -> pd.DataFrame:
    queries = [
        """
        SELECT cell_id, year, window, kingdom, COUNT(DISTINCT pub_key) AS n_publications
        FROM yield_events
        GROUP BY cell_id, year, window, kingdom
        """,
        """
        SELECT cell_id, year, window, 'total' AS kingdom, COUNT(DISTINCT pub_key) AS n_publications
        FROM yield_events
        GROUP BY cell_id, year, window
        """,
    ]
    frames = [pd.read_sql_query(query, conn) for query in queries]
    if not frames:
        return pd.DataFrame(columns=["cell_id", "year", "window", "kingdom", "n_publications"])
    return pd.concat(frames, ignore_index=True)


def build_wide_panel(
    long: pd.DataFrame,
    land: pd.DataFrame,
    start_year: int,
    end_year: int,
    max_pub_year: int,
) -> pd.DataFrame:
    panel = build_zero_panel(land, start_year, end_year, max_pub_year)
    specs = [("bold_pub_total", "total")] + [
        (f"bold_pub_{kingdom.lower()}", kingdom) for kingdom in KINGDOMS
    ]
    for window in WINDOWS:
        win_suffix = suffix(window)
        for col, kingdom in specs:
            out_col = f"{col}_{win_suffix}"
            sub = long.loc[
                (long["window"] == window) & (long["kingdom"] == kingdom),
                ["cell_id", "year", "n_publications"],
            ].rename(columns={"n_publications": out_col})
            panel = panel.merge(sub, on=["cell_id", "year"], how="left")
            panel[out_col] = panel[out_col].fillna(0).astype(int)
            panel[f"any_{out_col}"] = (panel[out_col] > 0).astype(int)
            panel[f"log1p_{out_col}"] = np.log1p(panel[out_col])
    return panel


def write_summary(output_csv: Path, stats: list[tuple[str, object]]) -> None:
    path = output_csv.with_name(output_csv.stem + "_summary.csv")
    pd.DataFrame(stats, columns=["metric", "value"]).to_csv(path, index=False)
    print(f"Wrote summary: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bold-records", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--bold-links", type=Path, default=BOLD_LINKS_CSV)
    parser.add_argument("--pubmed-metadata", type=Path, default=PUBMED_METADATA_CSV)
    parser.add_argument("--land-cells", type=Path, default=LAND_CELLS_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
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
    pubmed_metadata, max_pub_year = load_pubmed_metadata(args.pubmed_metadata)
    accession_pubs = load_accession_publications(args.bold_links, pubmed_metadata, args.chunksize)

    args.work_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.work_db) as conn:
        init_work_db(conn)
        stream_stats = build_yield_events(
            conn=conn,
            bold_csv=args.bold_records,
            accession_pubs=accession_pubs,
            land_cell_ids=land_cell_ids,
            transformer=transformer,
            cell_km=args.cell_km,
            start_year=args.start_year,
            end_year=args.end_year,
            chunksize=args.chunksize,
            insert_batch_size=args.insert_batch_size,
        )
        event_count = conn.execute("SELECT COUNT(*) FROM yield_events").fetchone()[0]
        long = build_long_panel(conn)

    wide = build_wide_panel(long, land, args.start_year, args.end_year, max_pub_year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(args.output, index=False)
    print(f"Wrote BOLD publication-yield panel: {args.output} ({len(wide):,} rows)", flush=True)

    summary: list[tuple[str, object]] = [
        ("start_year", args.start_year),
        ("end_year", args.end_year),
        ("max_pub_year", max_pub_year),
        ("land_cells", len(land)),
        ("wide_rows", len(wide)),
        ("distinct_yield_events", event_count),
        ("elapsed_min", round((time.time() - started) / 60, 2)),
    ]
    summary.extend(stream_stats.items())
    for col in [c for c in wide.columns if c.startswith("bold_pub_") and not c.startswith("bold_pub_complete_")]:
        summary.append((col, int(wide[col].sum())))
        summary.append((f"cell_years_with_{col}", int((wide[col] > 0).sum())))
    write_summary(args.output, summary)

    if not args.keep_work_db:
        for suffix_text in ["", "-wal", "-shm"]:
            path = Path(str(args.work_db) + suffix_text)
            if path.exists():
                path.unlink()
        print(f"Removed work DB: {args.work_db}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
