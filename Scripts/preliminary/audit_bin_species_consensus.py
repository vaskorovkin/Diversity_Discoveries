#!/usr/bin/env python3
"""Audit BIN-level species coverage in BOLD minimal records.

Estimates the upper bound on BIN-consensus species-name recovery:
how many unnamed records sit in BINs where other records carry a
species name, and how many of those BINs have a clean (>=80%)
single-species consensus.

Streams bold_minimal_records.csv once in two passes:
  Pass 1: build per-BIN species vote tallies.
  Pass 2: classify every record against the BIN consensus.

Output:
  Output/audits/bin_species_consensus.csv
  (one row per source_group + a TOTAL row)

Usage:
  python3 Scripts/preliminary/audit_bin_species_consensus.py
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
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_INPUT = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_minimal_records.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "Output" / "audits" / "bin_species_consensus.csv"

CONSENSUS_THRESHOLD = 0.80


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=CONSENSUS_THRESHOLD)
    args = parser.parse_args()

    csv.field_size_limit(100_000_000)

    # ── Pass 1: build per-BIN species tallies ────────────────────────
    print("Pass 1: building per-BIN species tallies ...", flush=True)
    bin_species: dict[str, Counter] = defaultdict(Counter)
    n_pass1 = 0

    with args.input.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_pass1 += 1
            bin_uri = row.get("bin_uri", "").strip()
            species = row.get("species", "").strip()
            if bin_uri and species:
                bin_species[bin_uri][species] += 1
            if n_pass1 % 5_000_000 == 0:
                print(f"  pass 1: {n_pass1:,} rows, {len(bin_species):,} named BINs", flush=True)

    print(f"  pass 1 done: {n_pass1:,} rows, {len(bin_species):,} BINs with >=1 named record", flush=True)

    # precompute consensus status per BIN
    bin_consensus: dict[str, str | None] = {}
    for bin_uri, votes in bin_species.items():
        total = sum(votes.values())
        top_species, top_count = votes.most_common(1)[0]
        if top_count / total >= args.threshold:
            bin_consensus[bin_uri] = top_species
        else:
            bin_consensus[bin_uri] = None  # named but no consensus

    n_consensus_bins = sum(1 for v in bin_consensus.values() if v is not None)
    n_no_consensus_bins = sum(1 for v in bin_consensus.values() if v is None)
    print(f"  BINs with consensus (>={args.threshold:.0%}): {n_consensus_bins:,}", flush=True)
    print(f"  BINs named but no consensus: {n_no_consensus_bins:,}", flush=True)

    # ── Pass 2: classify every record ────────────────────────────────
    print("\nPass 2: classifying records ...", flush=True)

    fields = [
        "n_records",
        "n_with_species",
        "n_with_bin_uri",
        "n_named_with_bin",
        "n_unnamed_in_named_bin",
        "n_unnamed_in_consensus_bin",
        "n_unnamed_in_unnamed_bin",
        "n_unnamed_no_bin",
    ]
    group_stats: dict[str, dict[str, int]] = defaultdict(lambda: {f: 0 for f in fields})
    n_pass2 = 0

    with args.input.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_pass2 += 1
            sg = row.get("source_group", "").strip() or "(unknown)"
            species = row.get("species", "").strip()
            bin_uri = row.get("bin_uri", "").strip()

            gs = group_stats[sg]
            gs["n_records"] += 1

            has_species = bool(species)
            has_bin = bool(bin_uri)

            if has_species:
                gs["n_with_species"] += 1
            if has_bin:
                gs["n_with_bin_uri"] += 1

            if has_species and has_bin:
                gs["n_named_with_bin"] += 1
            elif not has_species:
                if has_bin:
                    if bin_uri in bin_species:
                        gs["n_unnamed_in_named_bin"] += 1
                        if bin_consensus.get(bin_uri) is not None:
                            gs["n_unnamed_in_consensus_bin"] += 1
                    else:
                        gs["n_unnamed_in_unnamed_bin"] += 1
                else:
                    gs["n_unnamed_no_bin"] += 1

            if n_pass2 % 5_000_000 == 0:
                print(f"  pass 2: {n_pass2:,} rows", flush=True)

    print(f"  pass 2 done: {n_pass2:,} rows", flush=True)

    # ── Build TOTAL row ──────────────────────────────────────────────
    total = {f: 0 for f in fields}
    for gs in group_stats.values():
        for f in fields:
            total[f] += gs[f]
    group_stats["TOTAL"] = total

    # ── Write output ─────────────────────────────────────────────────
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_fields = ["source_group"] + fields
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for sg in sorted(group_stats.keys(), key=lambda x: (x == "TOTAL", x)):
            row = {"source_group": sg}
            row.update(group_stats[sg])
            writer.writerow(row)

    print(f"\nWrote: {args.output}", flush=True)

    # ── Console summary ──────────────────────────────────────────────
    t = total
    unnamed = t["n_records"] - t["n_with_species"]
    print(f"\n{'='*70}", flush=True)
    print("BIN SPECIES CONSENSUS AUDIT", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"Total records:              {t['n_records']:>12,}", flush=True)
    print(f"  with species:             {t['n_with_species']:>12,}  ({100*t['n_with_species']/t['n_records']:.1f}%)", flush=True)
    print(f"  with bin_uri:             {t['n_with_bin_uri']:>12,}  ({100*t['n_with_bin_uri']/t['n_records']:.1f}%)", flush=True)
    print(f"  named + BIN:              {t['n_named_with_bin']:>12,}", flush=True)
    print(f"\nUnnamed records:            {unnamed:>12,}", flush=True)
    if unnamed > 0:
        print(f"  in named BIN:             {t['n_unnamed_in_named_bin']:>12,}  ({100*t['n_unnamed_in_named_bin']/unnamed:.1f}% of unnamed)", flush=True)
        print(f"    of which consensus BIN: {t['n_unnamed_in_consensus_bin']:>12,}  ({100*t['n_unnamed_in_consensus_bin']/unnamed:.1f}% of unnamed)", flush=True)
        print(f"  in unnamed-only BIN:      {t['n_unnamed_in_unnamed_bin']:>12,}  ({100*t['n_unnamed_in_unnamed_bin']/unnamed:.1f}% of unnamed)", flush=True)
        print(f"  no BIN at all:            {t['n_unnamed_no_bin']:>12,}  ({100*t['n_unnamed_no_bin']/unnamed:.1f}% of unnamed)", flush=True)
    print(f"\nRecoverable (consensus BIN, >={args.threshold:.0%}): {t['n_unnamed_in_consensus_bin']:,} records", flush=True)
    print(f"Genuinely unidentifiable (no BIN): {t['n_unnamed_no_bin']:,} records", flush=True)
    print(f"{'='*70}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
