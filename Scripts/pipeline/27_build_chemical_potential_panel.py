#!/usr/bin/env python3
"""Build cell × year chemical-potential panel from specimen records.

For each cell-year, counts how many NP-bearing species (and compounds)
are reachable from the sampled specimens, using name resolution and
BIN consensus to maximize species identification.

Inputs:
  Data/processed/bold/bold_minimal_records.csv
  Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv
  Data/processed/discovery/natural_products/species_to_compounds.csv
  Data/processed/discovery/natural_products/species_compound_pairs.csv
  Data/processed/discovery/shared/species_name_resolution.csv
  Data/processed/discovery/shared/bin_consensus_lookup.csv
  Data/processed/bold/bold_grid100_land_cells.csv

Output:
  Data/processed/discovery/natural_products/cell_year_chemical_potential.csv

Usage:
  python3 Scripts/pipeline/27_build_chemical_potential_panel.py
  python3 Scripts/pipeline/27_build_chemical_potential_panel.py --dry-run
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
from collections import defaultdict
from pathlib import Path

import numpy as np
from pyproj import Transformer

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")

DEFAULT_BOLD = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_minimal_records.csv"
DEFAULT_GBIF = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal.csv"
)
DEFAULT_NP_SUMMARY = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "natural_products"
    / "species_to_compounds.csv"
)
DEFAULT_NP_PAIRS = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "natural_products"
    / "species_compound_pairs.csv"
)
DEFAULT_RESOLUTION = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "shared"
    / "species_name_resolution.csv"
)
DEFAULT_BIN_LOOKUP = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "shared"
    / "bin_consensus_lookup.csv"
)
DEFAULT_LAND_CELLS = (
    PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_grid100_land_cells.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "natural_products"
    / "cell_year_chemical_potential.csv"
)

EQUAL_AREA_CRS = "EPSG:6933"
CELL_M = 100_000
YEAR_MIN = 2005
YEAR_MAX = 2025


def clean(val: object) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    return str(val).strip()


# ── Cell assignment (matches 06_build_cell_year_panel.py) ───────────

_transformer = None


def get_transformer():
    global _transformer
    if _transformer is None:
        _transformer = Transformer.from_crs(
            "EPSG:4326", EQUAL_AREA_CRS, always_xy=True
        )
    return _transformer


def assign_cell(lat: float, lon: float) -> str:
    t = get_transformer()
    x, y = t.transform(lon, lat)
    cx = int(math.floor(x / CELL_M))
    cy = int(math.floor(y / CELL_M))
    return f"{cx}_{cy}"


def assign_cells_batch(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    t = get_transformer()
    x, y = t.transform(lons, lats)
    cx = np.floor(x / CELL_M).astype(int)
    cy = np.floor(y / CELL_M).astype(int)
    return np.char.add(np.char.add(cx.astype(str), "_"), cy.astype(str))


# ── Data structures ─────────────────────────────────────────────────

class CellYearAccum:
    __slots__ = (
        "n_records",
        "species_all",
        "species_strict",
        "species_no_fuzzy",
        "species_no_bin",
        "species_named_only",
    )

    def __init__(self):
        self.n_records = 0
        self.species_all: set[str] = set()
        self.species_strict: set[str] = set()
        self.species_no_fuzzy: set[str] = set()
        self.species_no_bin: set[str] = set()
        self.species_named_only: set[str] = set()


# ── Main ────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--bold", type=Path, default=DEFAULT_BOLD)
    parser.add_argument("--gbif", type=Path, default=DEFAULT_GBIF)
    parser.add_argument("--np-summary", type=Path, default=DEFAULT_NP_SUMMARY)
    parser.add_argument("--np-pairs", type=Path, default=DEFAULT_NP_PAIRS)
    parser.add_argument("--resolution", type=Path, default=DEFAULT_RESOLUTION)
    parser.add_argument("--bin-lookup", type=Path, default=DEFAULT_BIN_LOOKUP)
    parser.add_argument("--land-cells", type=Path, default=DEFAULT_LAND_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", help="500k rows per source.")
    args = parser.parse_args()

    csv.field_size_limit(100_000_000)
    max_rows = 500_000 if args.dry_run else None
    if args.dry_run:
        print("*** DRY RUN — 500k rows per source ***\n", flush=True)

    # ── (1) Load NP species set with compound IDs ───────────────────
    print("Loading name resolution ...", flush=True)
    name_res: dict[str, tuple[str, str]] = {}
    with args.resolution.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            inp = row["input_name"].strip()
            rn = row["resolved_name"].strip()
            method = row["resolution_method"].strip()
            name_res[inp] = (rn if rn else inp, method)
    print(f"  {len(name_res):,} resolution entries", flush=True)

    print("Loading NP compound pairs ...", flush=True)
    species_compounds: dict[str, set[str]] = defaultdict(set)
    with args.np_pairs.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sp = row["species_name"].strip().lower()
            ik = row["inchikey"].strip()
            resolved, _method = name_res.get(sp, (sp, ""))
            species_compounds[resolved].add(ik)
    print(f"  {len(species_compounds):,} resolved NP species with compound sets", flush=True)

    print("Loading NP summary ...", flush=True)
    np_kingdom: dict[str, str] = {}
    with args.np_summary.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sp = row["species_name"].strip().lower()
            resolved, _method = name_res.get(sp, (sp, ""))
            k = row.get("kingdom", "").strip()
            if resolved not in np_kingdom and k:
                np_kingdom[resolved] = k

    np_species_set = set(species_compounds.keys())
    print(f"  NP species set: {len(np_species_set):,}", flush=True)

    # ── Load BIN consensus lookup ───────────────────────────────────
    print("Loading BIN consensus lookup ...", flush=True)
    bin_lookup: dict[str, tuple[str, bool]] = {}
    with args.bin_lookup.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sp = row["consensus_species"].strip().lower()
            is_strict = row["is_strict"].strip() == "1"
            bin_lookup[row["bin_uri"].strip()] = (sp, is_strict)
    print(f"  {len(bin_lookup):,} BINs loaded", flush=True)

    # ── Load land cells ─────────────────────────────────────────────
    print("Loading land cells ...", flush=True)
    land_cells: set[str] = set()
    with args.land_cells.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            land_cells.add(row["cell_id"].strip())
    print(f"  {len(land_cells):,} land cells", flush=True)

    # ── (2) Stream BOLD ─────────────────────────────────────────────
    print("\nStreaming BOLD ...", flush=True)
    bold_accum: dict[tuple[str, int], CellYearAccum] = defaultdict(CellYearAccum)
    bold_stats = {
        "scanned": 0,
        "with_species_direct": 0,
        "with_species_bin": 0,
        "with_species_bin_strict": 0,
        "no_species": 0,
        "no_coord": 0,
        "no_year": 0,
        "not_land": 0,
        "kept": 0,
    }

    batch_sp: list[str] = []
    batch_method: list[str] = []
    batch_bin_recovered: list[bool] = []
    batch_bin_strict: list[bool] = []
    batch_lat: list[float] = []
    batch_lon: list[float] = []
    batch_year: list[int] = []
    BATCH_SIZE = 500_000

    def flush_bold_batch():
        if not batch_sp:
            return
        cells = assign_cells_batch(np.array(batch_lat), np.array(batch_lon))
        for i in range(len(batch_sp)):
            cell = cells[i]
            if cell not in land_cells:
                bold_stats["not_land"] += 1
                continue
            bold_stats["kept"] += 1
            yr = batch_year[i]
            sp = batch_sp[i]
            method = batch_method[i]
            is_bin = batch_bin_recovered[i]
            is_strict = batch_bin_strict[i]

            acc = bold_accum[(cell, yr)]
            acc.n_records += 1
            acc.species_all.add(sp)
            if not is_bin or is_strict:
                acc.species_strict.add(sp)
            if method != "name_match_fuzzy":
                acc.species_no_fuzzy.add(sp)
            if not is_bin:
                acc.species_no_bin.add(sp)
            if not is_bin and method != "name_match_fuzzy":
                acc.species_named_only.add(sp)
        batch_sp.clear()
        batch_method.clear()
        batch_bin_recovered.clear()
        batch_bin_strict.clear()
        batch_lat.clear()
        batch_lon.clear()
        batch_year.clear()

    with args.bold.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bold_stats["scanned"] += 1
            if max_rows and bold_stats["scanned"] > max_rows:
                break

            year_s = clean(row.get("collection_year", ""))
            if not year_s:
                bold_stats["no_year"] += 1
                continue
            try:
                year = int(year_s)
            except ValueError:
                bold_stats["no_year"] += 1
                continue
            if year < YEAR_MIN or year > YEAR_MAX:
                bold_stats["no_year"] += 1
                continue

            sp_raw = clean(row.get("species", ""))
            bin_uri = clean(row.get("bin_uri", ""))
            bin_recovered = False
            bin_strict = False

            if sp_raw and len(sp_raw.split()) >= 2:
                input_name = sp_raw.lower()
                bold_stats["with_species_direct"] += 1
            elif bin_uri and bin_uri in bin_lookup:
                input_name, bin_strict = bin_lookup[bin_uri]
                bin_recovered = True
                bold_stats["with_species_bin"] += 1
                if bin_strict:
                    bold_stats["with_species_bin_strict"] += 1
            else:
                bold_stats["no_species"] += 1
                continue

            resolved, method = name_res.get(input_name, (input_name, "unresolved"))

            lat_s = clean(row.get("latitude", ""))
            lon_s = clean(row.get("longitude", ""))
            if not lat_s or not lon_s:
                bold_stats["no_coord"] += 1
                continue
            try:
                lat = float(lat_s)
                lon = float(lon_s)
            except ValueError:
                bold_stats["no_coord"] += 1
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                bold_stats["no_coord"] += 1
                continue

            batch_sp.append(resolved)
            batch_method.append(method)
            batch_bin_recovered.append(bin_recovered)
            batch_bin_strict.append(bin_strict)
            batch_lat.append(lat)
            batch_lon.append(lon)
            batch_year.append(year)
            if len(batch_sp) >= BATCH_SIZE:
                flush_bold_batch()

            if bold_stats["scanned"] % 5_000_000 == 0:
                print(
                    f"  BOLD: {bold_stats['scanned']:,} scanned, "
                    f"{bold_stats['kept']:,} kept",
                    flush=True,
                )

    flush_bold_batch()
    print(
        f"  BOLD done: {bold_stats['scanned']:,} scanned, "
        f"{bold_stats['kept']:,} kept in land cells, "
        f"{len(bold_accum):,} cell-years",
        flush=True,
    )
    print(
        f"    direct species: {bold_stats['with_species_direct']:,}, "
        f"BIN recovered: {bold_stats['with_species_bin']:,} "
        f"(strict: {bold_stats['with_species_bin_strict']:,}), "
        f"no species: {bold_stats['no_species']:,}, "
        f"no coord: {bold_stats['no_coord']:,}, "
        f"no year: {bold_stats['no_year']:,}",
        flush=True,
    )

    # ── (3) Stream GBIF Plantae ─────────────────────────────────────
    print("\nStreaming GBIF Plantae ...", flush=True)
    gbif_accum: dict[tuple[str, int], CellYearAccum] = defaultdict(CellYearAccum)
    gbif_stats = {
        "scanned": 0,
        "with_species": 0,
        "no_species": 0,
        "no_coord": 0,
        "no_year": 0,
        "not_land": 0,
        "kept": 0,
    }

    gbatch_sp: list[str] = []
    gbatch_method: list[str] = []
    gbatch_lat: list[float] = []
    gbatch_lon: list[float] = []
    gbatch_year: list[int] = []

    def flush_gbif_batch():
        if not gbatch_sp:
            return
        cells = assign_cells_batch(np.array(gbatch_lat), np.array(gbatch_lon))
        for i in range(len(gbatch_sp)):
            cell = cells[i]
            if cell not in land_cells:
                gbif_stats["not_land"] += 1
                continue
            gbif_stats["kept"] += 1
            yr = gbatch_year[i]
            sp = gbatch_sp[i]
            method = gbatch_method[i]

            acc = gbif_accum[(cell, yr)]
            acc.n_records += 1
            acc.species_all.add(sp)
            acc.species_strict.add(sp)
            if method != "name_match_fuzzy":
                acc.species_no_fuzzy.add(sp)
            acc.species_no_bin.add(sp)
            if method != "name_match_fuzzy":
                acc.species_named_only.add(sp)
        gbatch_sp.clear()
        gbatch_method.clear()
        gbatch_lat.clear()
        gbatch_lon.clear()
        gbatch_year.clear()

    with args.gbif.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gbif_stats["scanned"] += 1
            if max_rows and gbif_stats["scanned"] > max_rows:
                break

            year_s = clean(row.get("year", ""))
            if not year_s:
                gbif_stats["no_year"] += 1
                continue
            try:
                year = int(year_s)
            except ValueError:
                gbif_stats["no_year"] += 1
                continue
            if year < YEAR_MIN or year > YEAR_MAX:
                gbif_stats["no_year"] += 1
                continue

            sp_raw = clean(row.get("species", ""))
            if not sp_raw or len(sp_raw.split()) < 2:
                gbif_stats["no_species"] += 1
                continue
            gbif_stats["with_species"] += 1
            input_name = sp_raw.lower()
            resolved, method = name_res.get(input_name, (input_name, "unresolved"))

            lat_s = clean(row.get("latitude", ""))
            lon_s = clean(row.get("longitude", ""))
            if not lat_s or not lon_s:
                gbif_stats["no_coord"] += 1
                continue
            try:
                lat = float(lat_s)
                lon = float(lon_s)
            except ValueError:
                gbif_stats["no_coord"] += 1
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                gbif_stats["no_coord"] += 1
                continue

            gbatch_sp.append(resolved)
            gbatch_method.append(method)
            gbatch_lat.append(lat)
            gbatch_lon.append(lon)
            gbatch_year.append(year)
            if len(gbatch_sp) >= BATCH_SIZE:
                flush_gbif_batch()

            if gbif_stats["scanned"] % 5_000_000 == 0:
                print(
                    f"  GBIF: {gbif_stats['scanned']:,} scanned, "
                    f"{gbif_stats['kept']:,} kept",
                    flush=True,
                )

    flush_gbif_batch()
    print(
        f"  GBIF done: {gbif_stats['scanned']:,} scanned, "
        f"{gbif_stats['kept']:,} kept in land cells, "
        f"{len(gbif_accum):,} cell-years",
        flush=True,
    )

    # ── (5) Aggregate to output rows ────────────────────────────────
    print("\nAggregating to cell × year × source_group ...", flush=True)

    all_cell_years = set(bold_accum.keys()) | set(gbif_accum.keys())
    print(f"  Unique cell-years: {len(all_cell_years):,}", flush=True)

    def compute_row(
        cell_id: str,
        year: int,
        source_group: str,
        species_all: set[str],
        species_strict: set[str],
        species_no_fuzzy: set[str],
        species_no_bin: set[str],
        species_named_only: set[str],
        n_records: int,
    ) -> dict:
        np_all = species_all & np_species_set
        np_strict = species_strict & np_species_set
        np_no_fuzzy = species_no_fuzzy & np_species_set
        np_no_bin = species_no_bin & np_species_set
        np_named = species_named_only & np_species_set

        n_sampled = len(species_all)
        n_np = len(np_all)

        compounds_union: set[str] = set()
        n_compounds_total = 0
        n_anim = 0
        n_plant = 0
        n_fungi = 0
        for sp in np_all:
            cset = species_compounds.get(sp, set())
            compounds_union |= cset
            n_compounds_total += len(cset)
            k = np_kingdom.get(sp, "")
            if k == "Animalia":
                n_anim += 1
            elif k == "Plantae":
                n_plant += 1
            elif k == "Fungi":
                n_fungi += 1

        return {
            "cell_id": cell_id,
            "year": year,
            "source_group": source_group,
            "n_records": n_records,
            "n_species_sampled": n_sampled,
            "n_species_with_compounds": n_np,
            "n_compounds_total": n_compounds_total,
            "n_unique_compounds": len(compounds_union),
            "share_np_species": f"{n_np / n_sampled:.6f}" if n_sampled else "0",
            "n_animalia_with_compounds": n_anim,
            "n_plantae_with_compounds": n_plant,
            "n_fungi_with_compounds": n_fungi,
            "n_species_with_compounds_strict": len(np_strict),
            "n_species_with_compounds_no_fuzzy": len(np_no_fuzzy),
            "n_species_with_compounds_no_bin": len(np_no_bin),
            "n_species_with_compounds_named_only": len(np_named),
        }

    out_rows: list[dict] = []
    for cell_id, year in sorted(all_cell_years):
        ba = bold_accum.get((cell_id, year))
        ga = gbif_accum.get((cell_id, year))

        if ba:
            out_rows.append(
                compute_row(
                    cell_id, year, "bold",
                    ba.species_all, ba.species_strict,
                    ba.species_no_fuzzy, ba.species_no_bin,
                    ba.species_named_only, ba.n_records,
                )
            )

        if ga:
            out_rows.append(
                compute_row(
                    cell_id, year, "gbif_plantae",
                    ga.species_all, ga.species_strict,
                    ga.species_no_fuzzy, ga.species_no_bin,
                    ga.species_named_only, ga.n_records,
                )
            )

        # combined: union species sets, sum records
        c_all: set[str] = set()
        c_strict: set[str] = set()
        c_no_fuzzy: set[str] = set()
        c_no_bin: set[str] = set()
        c_named: set[str] = set()
        c_records = 0
        if ba:
            c_all |= ba.species_all
            c_strict |= ba.species_strict
            c_no_fuzzy |= ba.species_no_fuzzy
            c_no_bin |= ba.species_no_bin
            c_named |= ba.species_named_only
            c_records += ba.n_records
        if ga:
            c_all |= ga.species_all
            c_strict |= ga.species_strict
            c_no_fuzzy |= ga.species_no_fuzzy
            c_no_bin |= ga.species_no_bin
            c_named |= ga.species_named_only
            c_records += ga.n_records

        out_rows.append(
            compute_row(
                cell_id, year, "combined",
                c_all, c_strict, c_no_fuzzy, c_no_bin, c_named,
                c_records,
            )
        )

    # ── Write output ────────────────────────────────────────────────
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cell_id",
        "year",
        "source_group",
        "n_records",
        "n_species_sampled",
        "n_species_with_compounds",
        "n_compounds_total",
        "n_unique_compounds",
        "share_np_species",
        "n_animalia_with_compounds",
        "n_plantae_with_compounds",
        "n_fungi_with_compounds",
        "n_species_with_compounds_strict",
        "n_species_with_compounds_no_fuzzy",
        "n_species_with_compounds_no_bin",
        "n_species_with_compounds_named_only",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    print(f"\nWrote: {args.output} ({len(out_rows):,} rows)", flush=True)

    # ── Report ──────────────────────────────────────────────────────
    print("\n" + "=" * 70, flush=True)
    print("CHEMICAL POTENTIAL PANEL — REPORT", flush=True)
    print("=" * 70, flush=True)

    for sg in ["bold", "gbif_plantae", "combined"]:
        sg_rows = [r for r in out_rows if r["source_group"] == sg]
        n_cy = len(sg_rows)
        np_vals = [r["n_species_with_compounds"] for r in sg_rows]
        np_arr = np.array(np_vals, dtype=float)
        has_np = sum(1 for v in np_vals if v > 0)

        print(f"\n  {sg}: {n_cy:,} cell-years", flush=True)
        if n_cy > 0:
            print(
                f"    n_species_with_compounds: "
                f"mean={np_arr.mean():.2f}, "
                f"median={np.median(np_arr):.1f}, "
                f"p90={np.percentile(np_arr, 90):.1f}, "
                f"max={np_arr.max():.0f}",
                flush=True,
            )
            print(
                f"    cell-years with >0 NP species: "
                f"{has_np:,} ({100 * has_np / n_cy:.1f}%)",
                flush=True,
            )
            # kingdom breakdown
            for kname, col in [
                ("Animalia", "n_animalia_with_compounds"),
                ("Plantae", "n_plantae_with_compounds"),
                ("Fungi", "n_fungi_with_compounds"),
            ]:
                has_k = sum(1 for r in sg_rows if r[col] > 0)
                print(
                    f"    cell-years with >0 {kname} NP: "
                    f"{has_k:,} ({100 * has_k / n_cy:.1f}%)",
                    flush=True,
                )

    # BIN-recovery contribution
    combined_rows = [r for r in out_rows if r["source_group"] == "combined"]
    if combined_rows:
        deltas_bin = [
            r["n_species_with_compounds"] - r["n_species_with_compounds_no_bin"]
            for r in combined_rows
        ]
        deltas_fuzzy = [
            r["n_species_with_compounds"] - r["n_species_with_compounds_no_fuzzy"]
            for r in combined_rows
        ]
        print(f"\n  BIN-recovery contribution (combined):", flush=True)
        print(
            f"    mean delta (all vs no_bin): "
            f"{np.mean(deltas_bin):.3f} species/cell-year",
            flush=True,
        )
        print(f"\n  Fuzzy-match contribution (combined):", flush=True)
        print(
            f"    mean delta (all vs no_fuzzy): "
            f"{np.mean(deltas_fuzzy):.3f} species/cell-year",
            flush=True,
        )

    # Sanity: dropped records
    bold_total = bold_stats["scanned"]
    bold_no_handle = bold_stats["no_species"]
    gbif_total = gbif_stats["scanned"]
    gbif_no_handle = gbif_stats["no_species"]
    print(f"\n  Sanity — records dropped (no taxonomic handle):", flush=True)
    if bold_total > 0:
        print(
            f"    BOLD: {bold_no_handle:,} / {bold_total:,} "
            f"({100 * bold_no_handle / bold_total:.1f}%)",
            flush=True,
        )
    if gbif_total > 0:
        print(
            f"    GBIF: {gbif_no_handle:,} / {gbif_total:,} "
            f"({100 * gbif_no_handle / gbif_total:.1f}%)",
            flush=True,
        )

    print("=" * 70, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
