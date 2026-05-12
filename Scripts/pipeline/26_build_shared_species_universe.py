#!/usr/bin/env python3
"""Build the shared species universe from BOLD and GBIF Plantae.

The universe is the union of all species observable in our sampling data
(BOLD + GBIF), with NP-DB compound flags attached.  Species that exist
only in LOTUS/COCONUT but never in BOLD/GBIF are excluded — they cannot
enter cell-year regressions.

BOLD records without a species name are recovered via BIN consensus:
  Pass 1 — build per-BIN plurality species (top species wins).
  Pass 2 — unnamed records in a named BIN get the plurality species,
            tagged with the BIN's concordance rate.

Inputs:
  Data/processed/bold/bold_minimal_records.csv
  Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv
  Data/processed/discovery/natural_products/species_to_compounds.csv

Outputs:
  Data/processed/discovery/shared/shared_species_universe.csv
  Data/processed/discovery/shared/bin_consensus_lookup.csv

Usage:
  python3 Scripts/pipeline/26_build_shared_species_universe.py
  python3 Scripts/pipeline/26_build_shared_species_universe.py --dry-run
"""


from __future__ import annotations


from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _path in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")

DEFAULT_BOLD = (
    PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_minimal_records.csv"
)
DEFAULT_GBIF = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal.csv"
)
DEFAULT_NP = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "natural_products"
    / "species_to_compounds.csv"
)
DEFAULT_LAND_CELLS = (
    PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_grid100_land_cells.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "shared"
    / "shared_species_universe.csv"
)
DEFAULT_BIN_LOOKUP = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "shared"
    / "bin_consensus_lookup.csv"
)

EQUAL_AREA_CRS = "EPSG:6933"
CELL_M = 100_000


def clean(val: object) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    return str(val).strip()


def normalize_species(raw: str) -> str:
    raw = " ".join(raw.strip().split()).lower()
    return raw


# ── Cell assignment (matches 06_build_cell_year_panel.py) ────────────

_transformer = None


def get_transformer():
    global _transformer
    if _transformer is None:
        _transformer = Transformer.from_crs(
            "EPSG:4326", EQUAL_AREA_CRS, always_xy=True
        )
    return _transformer


def assign_cells(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    t = get_transformer()
    x, y = t.transform(lons, lats)
    cx = np.floor(x / CELL_M).astype(int)
    cy = np.floor(y / CELL_M).astype(int)
    return np.char.add(np.char.add(cx.astype(str), "_"), cy.astype(str))


# ── BOLD BIN consensus (pass 1) ─────────────────────────────────────


def build_bin_consensus(
    path: Path, max_rows: int | None, progress_every: int = 5_000_000
) -> dict[str, tuple[str, str, str, float]]:
    """Return {bin_uri: (plurality_species, kingdom, genus, concordance)}.

    Streams the BOLD minimal CSV once, tallying species votes per BIN.
    """
    csv.field_size_limit(100_000_000)
    bin_species: dict[str, Counter] = defaultdict(Counter)
    bin_kingdom: dict[str, Counter] = defaultdict(Counter)
    bin_genus: dict[str, Counter] = defaultdict(Counter)
    n = 0

    print("BOLD pass 1: building BIN consensus ...", flush=True)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n += 1
            if max_rows and n > max_rows:
                break
            bin_uri = clean(row.get("bin_uri", ""))
            species = clean(row.get("species", ""))
            if bin_uri and species and len(species.split()) >= 2:
                sp = normalize_species(species)
                bin_species[bin_uri][sp] += 1
                k = clean(row.get("kingdom", ""))
                if k:
                    bin_kingdom[bin_uri][k] += 1
                g = clean(row.get("genus", ""))
                if g:
                    bin_genus[bin_uri][g] += 1
            if n % progress_every == 0:
                print(
                    f"  pass 1: {n:,} rows, {len(bin_species):,} named BINs",
                    flush=True,
                )

    lookup: dict[str, tuple[str, str, str, float]] = {}
    for bin_uri, votes in bin_species.items():
        total = sum(votes.values())
        top_sp, top_count = votes.most_common(1)[0]
        concordance = top_count / total
        kingdom = ""
        if bin_kingdom[bin_uri]:
            kingdom = bin_kingdom[bin_uri].most_common(1)[0][0]
        genus = ""
        if bin_genus[bin_uri]:
            genus = bin_genus[bin_uri].most_common(1)[0][0]
        lookup[bin_uri] = (top_sp, kingdom, genus, concordance)

    print(
        f"  pass 1 done: {n:,} rows scanned, "
        f"{len(lookup):,} BINs with plurality species",
        flush=True,
    )
    return lookup


# ── BOLD streamer (pass 2) ───────────────────────────────────────────


def stream_bold(
    path: Path,
    land_cells: set[str],
    species_data: dict[str, dict],
    bin_lookup: dict[str, tuple[str, str, str, float]],
    max_rows: int | None,
    progress_every: int = 2_000_000,
) -> dict[str, int]:
    csv.field_size_limit(100_000_000)
    stats = {
        "scanned": 0,
        "with_species_direct": 0,
        "with_species_bin": 0,
        "with_coord": 0,
        "in_land": 0,
    }

    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        batch_sp: list[str] = []
        batch_lat: list[float] = []
        batch_lon: list[float] = []
        batch_size = 500_000

        def flush_batch():
            if not batch_sp:
                return
            lats = np.array(batch_lat)
            lons = np.array(batch_lon)
            cells = assign_cells(lats, lons)
            for sp, cell in zip(batch_sp, cells):
                if cell in land_cells:
                    stats["in_land"] += 1
                    species_data[sp]["cells"].add(cell)
            batch_sp.clear()
            batch_lat.clear()
            batch_lon.clear()

        for row in reader:
            stats["scanned"] += 1
            if max_rows and stats["scanned"] > max_rows:
                break

            sp_raw = clean(row.get("species", ""))
            kingdom_raw = clean(row.get("kingdom", ""))
            genus_raw = clean(row.get("genus", ""))
            bin_uri = clean(row.get("bin_uri", ""))

            # direct species name
            if sp_raw and len(sp_raw.split()) >= 2:
                sp = normalize_species(sp_raw)
                stats["with_species_direct"] += 1
            # BIN consensus fallback
            elif bin_uri and bin_uri in bin_lookup:
                sp, kingdom_raw, genus_raw, _conc = bin_lookup[bin_uri]
                stats["with_species_bin"] += 1
            else:
                continue

            if not sp:
                continue

            rec = species_data[sp]
            rec["n_records_bold"] += 1
            if not rec["kingdom"] and kingdom_raw:
                rec["kingdom"] = kingdom_raw
            if not rec["genus"] and genus_raw:
                rec["genus"] = genus_raw

            lat_s = clean(row.get("latitude", ""))
            lon_s = clean(row.get("longitude", ""))
            if lat_s and lon_s:
                try:
                    lat = float(lat_s)
                    lon = float(lon_s)
                except ValueError:
                    continue
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    stats["with_coord"] += 1
                    batch_sp.append(sp)
                    batch_lat.append(lat)
                    batch_lon.append(lon)
                    if len(batch_sp) >= batch_size:
                        flush_batch()

            if stats["scanned"] % progress_every == 0:
                print(
                    f"  BOLD pass 2: {stats['scanned']:,} rows, "
                    f"{len(species_data):,} species",
                    flush=True,
                )

        flush_batch()

    total_sp = stats["with_species_direct"] + stats["with_species_bin"]
    print(
        f"BOLD pass 2: scanned {stats['scanned']:,}, "
        f"with species {total_sp:,} "
        f"(direct {stats['with_species_direct']:,} + "
        f"BIN consensus {stats['with_species_bin']:,}), "
        f"with coord {stats['with_coord']:,}, "
        f"in land cells {stats['in_land']:,}",
        flush=True,
    )
    return stats


# ── GBIF Plantae streamer ───────────────────────────────────────────


def stream_gbif(
    path: Path,
    land_cells: set[str],
    species_data: dict[str, dict],
    max_rows: int | None,
    progress_every: int = 2_000_000,
) -> dict[str, int]:
    csv.field_size_limit(100_000_000)
    stats = {"scanned": 0, "with_species": 0, "with_coord": 0, "in_land": 0}

    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        batch_sp: list[str] = []
        batch_lat: list[float] = []
        batch_lon: list[float] = []
        batch_size = 500_000

        def flush_batch():
            if not batch_sp:
                return
            lats = np.array(batch_lat)
            lons = np.array(batch_lon)
            cells = assign_cells(lats, lons)
            for sp, cell in zip(batch_sp, cells):
                if cell in land_cells:
                    stats["in_land"] += 1
                    species_data[sp]["cells"].add(cell)
            batch_sp.clear()
            batch_lat.clear()
            batch_lon.clear()

        for row in reader:
            stats["scanned"] += 1
            if max_rows and stats["scanned"] > max_rows:
                break

            sp_raw = clean(row.get("species", ""))
            if not sp_raw or len(sp_raw.split()) < 2:
                continue
            sp = normalize_species(sp_raw)
            if not sp:
                continue
            stats["with_species"] += 1

            rec = species_data[sp]
            rec["n_records_gbif_pm"] += 1
            if not rec["kingdom"]:
                rec["kingdom"] = clean(row.get("kingdom", ""))
            if not rec["genus"]:
                rec["genus"] = clean(row.get("genus", ""))

            lat_s = clean(row.get("latitude", ""))
            lon_s = clean(row.get("longitude", ""))
            if lat_s and lon_s:
                try:
                    lat = float(lat_s)
                    lon = float(lon_s)
                except ValueError:
                    continue
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    stats["with_coord"] += 1
                    batch_sp.append(sp)
                    batch_lat.append(lat)
                    batch_lon.append(lon)
                    if len(batch_sp) >= batch_size:
                        flush_batch()

            if stats["scanned"] % progress_every == 0:
                print(
                    f"  GBIF: {stats['scanned']:,} rows, "
                    f"{len(species_data):,} species",
                    flush=True,
                )

        flush_batch()

    print(
        f"GBIF: scanned {stats['scanned']:,}, "
        f"with species {stats['with_species']:,}, "
        f"with coord {stats['with_coord']:,}, "
        f"in land cells {stats['in_land']:,}",
        flush=True,
    )
    return stats


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--bold", type=Path, default=DEFAULT_BOLD)
    parser.add_argument("--gbif", type=Path, default=DEFAULT_GBIF)
    parser.add_argument("--np-summary", type=Path, default=DEFAULT_NP)
    parser.add_argument("--land-cells", type=Path, default=DEFAULT_LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bin-lookup-out", type=Path, default=DEFAULT_BIN_LOOKUP)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process first 500k rows per source.",
    )
    args = parser.parse_args()

    max_rows = 500_000 if args.dry_run else None
    if args.dry_run:
        print("*** DRY RUN — 500k rows per source ***\n", flush=True)

    # ── Load land cells ──────────────────────────────────────────────
    land = pd.read_csv(args.land_cells, dtype={"cell_id": str})
    land_cell_ids = set(land["cell_id"])
    print(f"Land cells loaded: {len(land_cell_ids):,}", flush=True)

    # ── Load NP summary ──────────────────────────────────────────────
    np_summary = pd.read_csv(args.np_summary)
    np_summary["species_lower"] = (
        np_summary["species_name"].str.lower().str.strip()
    )
    np_lookup = dict(
        zip(
            np_summary["species_lower"],
            np_summary["n_unique_compounds_total"],
        )
    )
    print(f"NP species loaded: {len(np_lookup):,}", flush=True)

    # ── BOLD pass 1: BIN consensus ───────────────────────────────────
    print(flush=True)
    bin_lookup = build_bin_consensus(args.bold, max_rows)

    # ── Persist BIN consensus lookup ────────────────────────────────
    args.bin_lookup_out.parent.mkdir(parents=True, exist_ok=True)
    with args.bin_lookup_out.open("w", newline="", encoding="utf-8") as bf:
        bw = csv.DictWriter(
            bf,
            fieldnames=[
                "bin_uri",
                "consensus_species",
                "kingdom",
                "genus",
                "concordance",
                "is_strict",
            ],
        )
        bw.writeheader()
        for bin_uri, (sp, kingdom, genus, conc) in sorted(bin_lookup.items()):
            bw.writerow(
                {
                    "bin_uri": bin_uri,
                    "consensus_species": sp,
                    "kingdom": kingdom,
                    "genus": genus,
                    "concordance": f"{conc:.4f}",
                    "is_strict": 1 if conc >= 0.80 else 0,
                }
            )
    print(
        f"Wrote BIN consensus lookup: {args.bin_lookup_out} "
        f"({len(bin_lookup):,} BINs, "
        f"{sum(1 for _, _, _, c in bin_lookup.values() if c >= 0.80):,} strict)",
        flush=True,
    )

    # ── Stream BOLD (pass 2) + GBIF ──────────────────────────────────
    species_data: dict[str, dict] = defaultdict(
        lambda: {
            "kingdom": "",
            "genus": "",
            "n_records_bold": 0,
            "n_records_gbif_pm": 0,
            "cells": set(),
        }
    )

    print("\nStreaming BOLD (pass 2 with BIN consensus) ...", flush=True)
    bold_stats = stream_bold(
        args.bold, land_cell_ids, species_data, bin_lookup, max_rows
    )

    print("\nStreaming GBIF Plantae ...", flush=True)
    gbif_stats = stream_gbif(args.gbif, land_cell_ids, species_data, max_rows)

    # ── Build output DataFrame ───────────────────────────────────────
    rows = []
    for sp, rec in species_data.items():
        bold = rec["n_records_bold"]
        gbif = rec["n_records_gbif_pm"]
        if bold > gbif:
            priority = "bold"
        elif gbif > bold:
            priority = "gbif_pm"
        else:
            priority = "both"

        in_np = 1 if sp in np_lookup else 0
        n_compounds = np_lookup.get(sp, "")

        rows.append(
            {
                "species_name": sp,
                "genus": rec["genus"],
                "kingdom": rec["kingdom"],
                "n_records_bold": bold,
                "n_records_gbif_pm": gbif,
                "cells_present": len(rec["cells"]),
                "source_priority": priority,
                "in_np_db": in_np,
                "n_unique_compounds": n_compounds,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["n_records_bold", "n_records_gbif_pm", "species_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"\nWrote: {args.output} ({len(df):,} rows)", flush=True)

    # ── Report ───────────────────────────────────────────────────────
    print("\n" + "=" * 65, flush=True)
    print("SHARED SPECIES UNIVERSE — REPORT", flush=True)
    print("=" * 65, flush=True)

    print(f"\nTotal unique species: {len(df):,}", flush=True)

    print(f"\nBOLD species identification:", flush=True)
    print(
        f"  Direct from record:  {bold_stats['with_species_direct']:>10,}",
        flush=True,
    )
    print(
        f"  Via BIN consensus:   {bold_stats['with_species_bin']:>10,}",
        flush=True,
    )

    print(f"\nKingdom breakdown:", flush=True)
    kc = df["kingdom"].replace("", "(unknown)").value_counts()
    for k, c in kc.items():
        print(f"  {k:<20s} {c:>9,}", flush=True)

    bold_only = (
        (df["n_records_bold"] > 0) & (df["n_records_gbif_pm"] == 0)
    ).sum()
    gbif_only = (
        (df["n_records_bold"] == 0) & (df["n_records_gbif_pm"] > 0)
    ).sum()
    in_both = (
        (df["n_records_bold"] > 0) & (df["n_records_gbif_pm"] > 0)
    ).sum()
    print(f"\nSource breakdown:", flush=True)
    print(f"  BOLD only:   {bold_only:>9,}", flush=True)
    print(f"  GBIF only:   {gbif_only:>9,}", flush=True)
    print(f"  Both:        {in_both:>9,}", flush=True)

    np_match = (df["in_np_db"] == 1).sum()
    print(f"\nNP-DB coverage:", flush=True)
    print(
        f"  Species with in_np_db=1: {np_match:,} / {len(df):,} "
        f"({100*np_match/len(df):.1f}%)",
        flush=True,
    )

    if np_match > 0:
        np_sub = df.loc[df["in_np_db"] == 1]
        np_kingdom = (
            np_sub["kingdom"].replace("", "(unknown)").value_counts()
        )
        print(f"  NP-matched kingdom breakdown:", flush=True)
        for k, c in np_kingdom.items():
            print(f"    {k:<20s} {c:>8,}", flush=True)

    print("=" * 65, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
