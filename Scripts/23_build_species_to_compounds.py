#!/usr/bin/env python3
"""Build unified species → compound maps from LOTUS and COCONUT.

Step 3a: Parse each NP database into long-format (species, compound) pairs.
Step 3b: Deduplicate across sources by (species_name_lower, inchikey),
         producing species_compound_pairs.csv.
Step 3c: Aggregate per species, producing species_to_compounds.csv.

Outputs:
  Data/processed/discovery/natural_products/species_compound_pairs.csv
  Data/processed/discovery/natural_products/species_to_compounds.csv
  Output/audits/np_kingdom_disagreements.csv

Usage:
  python3 Scripts/23_build_species_to_compounds.py
  python3 Scripts/23_build_species_to_compounds.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")

DEFAULT_LOTUS = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "natural_products"
    / "lotus"
    / "260413_frozen_metadata.csv.gz"
)
DEFAULT_COCONUT = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "natural_products"
    / "coconut"
    / "coconut_csv-05-2026.zip"
)
DEFAULT_PAIRS_OUT = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "natural_products"
    / "species_compound_pairs.csv"
)
DEFAULT_SUMMARY_OUT = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "natural_products"
    / "species_to_compounds.csv"
)
DEFAULT_AUDIT_OUT = (
    PROJECT_ROOT / "Output" / "audits" / "np_kingdom_disagreements.csv"
)

INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def normalize_species(name: str) -> str:
    """Normalize a scientific name to 'Genus epithet' form.

    - Strip whitespace, collapse internal whitespace.
    - Title-case genus, lowercase epithet (standard binomial).
    - Skip common names (all-lowercase first word) and strain IDs.
    """
    name = " ".join(name.strip().split())
    if not name:
        return ""
    parts = name.split()
    if not parts[0][0].isupper():
        return ""
    if len(parts) == 1:
        return parts[0]
    genus = parts[0]
    # skip subgenus in parentheses: "Mycale (Carmia) microsigmatosa"
    rest_start = 1
    if rest_start < len(parts) and parts[rest_start].startswith("("):
        while rest_start < len(parts) and ")" not in parts[rest_start]:
            rest_start += 1
        rest_start += 1
    if rest_start >= len(parts):
        return genus
    epithet = parts[rest_start].lower()
    return f"{genus} {epithet}"


def extract_genus(species_name: str) -> str:
    if not species_name:
        return ""
    return species_name.split()[0]


KINGDOM_MAP = {
    "archaeplastida": "Plantae",
    "fungi": "Fungi",
    "metazoa": "Animalia",
    "viridiplantae": "Plantae",
    "plantae": "Plantae",
    "animalia": "Animalia",
}


def normalize_kingdom(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    return KINGDOM_MAP.get(raw.lower(), raw)


# ── LOTUS parser ─────────────────────────────────────────────────────


def parse_lotus(path: Path, max_rows: int | None = None) -> list[dict]:
    """Parse LOTUS metadata into long-format rows."""
    csv.field_size_limit(100_000_000)
    rows = []
    raw_count = 0
    skipped_no_name = 0
    skipped_no_ik = 0

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            raw_count += 1
            if max_rows and raw_count > max_rows:
                break

            ik = rec.get("structure_inchikey", "").strip()
            if not ik or not INCHIKEY_RE.match(ik):
                skipped_no_ik += 1
                continue

            sp = rec.get("organism_taxonomy_09species", "").strip()
            org = rec.get("organism_name", "").strip()
            name = sp or org
            name = normalize_species(name)
            if not name:
                skipped_no_name += 1
                continue

            genus = rec.get("organism_taxonomy_08genus", "").strip()
            if not genus:
                genus = extract_genus(name)

            kingdom = normalize_kingdom(
                rec.get("organism_taxonomy_02kingdom", "")
            )

            rows.append(
                {
                    "species_name": name,
                    "genus": genus,
                    "kingdom": kingdom,
                    "inchikey": ik,
                    "source": "lotus",
                }
            )

    print(f"LOTUS: scanned {raw_count:,} rows", flush=True)
    print(f"  kept {len(rows):,} (species, compound) mentions", flush=True)
    print(
        f"  skipped: {skipped_no_name:,} no usable name, "
        f"{skipped_no_ik:,} no valid InChIKey",
        flush=True,
    )
    return rows


# ── COCONUT parser ───────────────────────────────────────────────────


def parse_coconut(path: Path, max_rows: int | None = None) -> list[dict]:
    """Parse COCONUT CSV (inside zip) into long-format rows."""
    csv.field_size_limit(100_000_000)
    rows = []
    raw_count = 0
    skipped_no_org = 0
    skipped_no_ik = 0

    zf = zipfile.ZipFile(path)
    csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
    if not csv_names:
        raise FileNotFoundError(f"No CSV found inside {path}")
    csv_name = csv_names[0]

    with zf.open(csv_name) as raw:
        f = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
        reader = csv.DictReader(f)
        for rec in reader:
            raw_count += 1
            if max_rows and raw_count > max_rows:
                break

            ik = rec.get("standard_inchi_key", "").strip()
            if not ik or not INCHIKEY_RE.match(ik):
                skipped_no_ik += 1
                continue

            orgs_raw = rec.get("organisms", "").strip()
            if not orgs_raw:
                skipped_no_org += 1
                continue

            for org in orgs_raw.split("|"):
                name = normalize_species(org)
                if not name:
                    continue
                rows.append(
                    {
                        "species_name": name,
                        "genus": extract_genus(name),
                        "kingdom": "",
                        "inchikey": ik,
                        "source": "coconut",
                    }
                )

    print(f"COCONUT: scanned {raw_count:,} rows", flush=True)
    print(f"  kept {len(rows):,} (species, compound) mentions", flush=True)
    print(
        f"  skipped: {skipped_no_org:,} no organism, "
        f"{skipped_no_ik:,} no valid InChIKey",
        flush=True,
    )
    return rows


# ── Extra-source parser (generic CSV with species_name + inchikey) ───


def parse_extra(name: str, path: Path, max_rows: int | None = None) -> list[dict]:
    csv.field_size_limit(100_000_000)
    rows = []
    raw_count = 0

    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            raw_count += 1
            if max_rows and raw_count > max_rows:
                break
            sp = normalize_species(rec.get("species_name", ""))
            ik = rec.get("inchikey", "").strip()
            if not sp or not ik or not INCHIKEY_RE.match(ik):
                continue
            rows.append(
                {
                    "species_name": sp,
                    "genus": rec.get("genus", "") or extract_genus(sp),
                    "kingdom": normalize_kingdom(rec.get("kingdom", "")),
                    "inchikey": ik,
                    "source": name,
                }
            )

    print(f"{name}: scanned {raw_count:,} rows, kept {len(rows):,}", flush=True)
    return rows


# ── Dedup and aggregate ─────────────────────────────────────────────


def build_pairs(all_rows: list[dict]) -> pd.DataFrame:
    """Deduplicate (species_name_lower, inchikey) pairs, track source_set."""
    df = pd.DataFrame(all_rows)
    df["species_lower"] = df["species_name"].str.lower()

    # keep first non-empty value per group for genus and kingdom
    # and collect all sources
    def agg_group(g):
        genus_vals = g["genus"].loc[g["genus"] != ""]
        kingdom_vals = g["kingdom"].loc[g["kingdom"] != ""]
        species_vals = g["species_name"]
        return pd.Series(
            {
                "species_name": species_vals.iloc[0],
                "genus": genus_vals.iloc[0] if len(genus_vals) else "",
                "kingdom": kingdom_vals.iloc[0] if len(kingdom_vals) else "",
                "source_set": ",".join(sorted(g["source"].unique())),
            }
        )

    pairs = (
        df.groupby(["species_lower", "inchikey"], sort=False)
        .apply(agg_group, include_groups=False)
        .reset_index()
    )
    pairs.drop(columns=["species_lower"], inplace=True)
    return pairs


def audit_kingdom_disagreements(all_rows: list[dict], out_path: Path) -> int:
    """Find species where sources disagree on kingdom."""
    species_kingdoms: dict[str, dict[str, set]] = defaultdict(
        lambda: defaultdict(set)
    )
    for row in all_rows:
        k = row["kingdom"]
        if k:
            sp_lower = row["species_name"].lower()
            species_kingdoms[sp_lower][k].add(row["source"])

    conflicts = []
    for sp, kd in species_kingdoms.items():
        if len(kd) > 1:
            for k, sources in sorted(kd.items()):
                conflicts.append(
                    {
                        "species_name_lower": sp,
                        "kingdom": k,
                        "sources": ",".join(sorted(sources)),
                    }
                )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cdf = pd.DataFrame(conflicts)
    if len(cdf):
        cdf.to_csv(out_path, index=False)
    else:
        out_path.write_text("species_name_lower,kingdom,sources\n")
    print(
        f"Kingdom disagreements: {len(cdf)} rows "
        f"({len(set(c['species_name_lower'] for c in conflicts))} species)",
        flush=True,
    )
    return len(cdf)


def build_summary(pairs: pd.DataFrame) -> pd.DataFrame:
    """Aggregate pairs to per-species compound counts."""

    def count_source(g, src):
        return g.loc[g["source_set"].str.contains(src), "inchikey"].nunique()

    def agg_species(g):
        return pd.Series(
            {
                "genus": g["genus"].iloc[0],
                "kingdom": g["kingdom"].iloc[0],
                "n_compounds_lotus": count_source(g, "lotus"),
                "n_compounds_coconut": count_source(g, "coconut"),
                "n_unique_compounds_total": g["inchikey"].nunique(),
                "sources": ",".join(
                    sorted(
                        {
                            s
                            for ss in g["source_set"]
                            for s in ss.split(",")
                        }
                    )
                ),
            }
        )

    summary = (
        pairs.groupby(pairs["species_name"].str.lower(), sort=False)
        .apply(agg_species, include_groups=False)
        .reset_index()
    )
    summary.rename(columns={"species_name": "species_name_lower"}, inplace=True)

    # recover display-form species_name from pairs
    display = (
        pairs[["species_name"]]
        .assign(species_lower=pairs["species_name"].str.lower())
        .drop_duplicates(subset="species_lower")
        .set_index("species_lower")["species_name"]
    )
    summary["species_name"] = summary["species_name_lower"].map(display)
    summary.drop(columns=["species_name_lower"], inplace=True)

    col_order = [
        "species_name",
        "genus",
        "kingdom",
        "n_compounds_lotus",
        "n_compounds_coconut",
        "n_unique_compounds_total",
        "sources",
    ]
    summary = summary[col_order].sort_values(
        "n_unique_compounds_total", ascending=False
    )
    return summary


def print_report(all_rows: list[dict], pairs: pd.DataFrame, summary: pd.DataFrame):
    sources = sorted({r["source"] for r in all_rows})
    print("\n" + "=" * 65, flush=True)
    print("REPORT", flush=True)
    print("=" * 65, flush=True)

    print(f"\nPer-source raw mention counts:", flush=True)
    src_counter = Counter(r["source"] for r in all_rows)
    for s in sources:
        print(f"  {s}: {src_counter[s]:,} mentions", flush=True)

    print(f"\nPer-source unique species:", flush=True)
    src_species: dict[str, set] = defaultdict(set)
    for r in all_rows:
        src_species[r["source"]].add(r["species_name"].lower())
    for s in sources:
        print(f"  {s}: {len(src_species[s]):,}", flush=True)

    if len(sources) >= 2:
        s1, s2 = sources[0], sources[1]
        overlap_sp = src_species[s1] & src_species[s2]
        print(f"\nCross-source overlap:", flush=True)
        print(
            f"  Species in both {s1} and {s2}: {len(overlap_sp):,}",
            flush=True,
        )
        ik_sets: dict[str, set] = defaultdict(set)
        for r in all_rows:
            ik_sets[r["source"]].add(r["inchikey"])
        overlap_ik = ik_sets[s1] & ik_sets[s2]
        print(
            f"  Compounds (InChIKey) in both: {len(overlap_ik):,}",
            flush=True,
        )

    print(f"\nDeduplicated pairs: {len(pairs):,}", flush=True)
    print(f"Unique species in summary: {len(summary):,}", flush=True)

    print(f"\nKingdom breakdown (summary):", flush=True)
    kingdom_counts = summary["kingdom"].replace("", "(unknown)").value_counts()
    for k, c in kingdom_counts.items():
        print(f"  {k:<20s} {c:>8,} species", flush=True)

    print(
        f"\nCompound-count quantiles (n_unique_compounds_total):", flush=True
    )
    q = summary["n_unique_compounds_total"].describe(
        percentiles=[0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    )
    for label in ["mean", "50%", "75%", "90%", "95%", "99%", "max"]:
        print(f"  {label:>6s}: {q[label]:,.1f}", flush=True)
    print("=" * 65, flush=True)


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--lotus", type=Path, default=DEFAULT_LOTUS)
    parser.add_argument("--coconut", type=Path, default=DEFAULT_COCONUT)
    parser.add_argument(
        "--extra-source",
        nargs=2,
        action="append",
        metavar=("NAME", "PATH"),
        default=[],
        help="Additional source: --extra-source knapsack /path/to/file.csv",
    )
    parser.add_argument("--pairs-out", type=Path, default=DEFAULT_PAIRS_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_OUT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process first 100k rows per source only.",
    )
    args = parser.parse_args()

    max_rows = 100_000 if args.dry_run else None
    if args.dry_run:
        print("*** DRY RUN — 100k rows per source ***\n", flush=True)

    # ── Step 3a: parse sources ───────────────────────────────────────
    all_rows: list[dict] = []

    if args.lotus.exists():
        all_rows.extend(parse_lotus(args.lotus, max_rows))
    else:
        print(f"WARNING: LOTUS file not found: {args.lotus}", flush=True)

    if args.coconut.exists():
        all_rows.extend(parse_coconut(args.coconut, max_rows))
    else:
        print(f"WARNING: COCONUT file not found: {args.coconut}", flush=True)

    for name, path_str in args.extra_source:
        p = Path(path_str)
        if p.exists():
            all_rows.extend(parse_extra(name, p, max_rows))
        else:
            print(f"WARNING: extra source {name!r} not found: {p}", flush=True)

    if not all_rows:
        print("ERROR: no data parsed from any source.", flush=True)
        return 1

    # ── Step 3b: dedup pairs ─────────────────────────────────────────
    print(f"\nDeduplicating {len(all_rows):,} mentions ...", flush=True)
    pairs = build_pairs(all_rows)

    args.pairs_out.parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(args.pairs_out, index=False)
    print(f"Wrote pairs: {args.pairs_out} ({len(pairs):,} rows)", flush=True)

    # ── Kingdom audit ────────────────────────────────────────────────
    audit_kingdom_disagreements(all_rows, args.audit_out)

    # ── Step 3c: per-species summary ─────────────────────────────────
    summary = build_summary(pairs)

    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_out, index=False)
    print(
        f"Wrote summary: {args.summary_out} ({len(summary):,} rows)",
        flush=True,
    )

    # ── Report ───────────────────────────────────────────────────────
    print_report(all_rows, pairs, summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
