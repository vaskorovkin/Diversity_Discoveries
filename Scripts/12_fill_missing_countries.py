#!/usr/bin/env python3
"""Fill missing country_final for the ~89 collectors without LLM resolution.

Strategy per status group:
  ORG        → map organization name to country via a hardcoded lookup table,
               fall back to most common inst/country on their BOLD records
  AMBIGUOUS  → find co-collectors (people who appear in the same collector
               string), look up resolved countries of those co-collectors
  UNRESOLVED → same co-collector approach, plus check the BOLD inst field

Reads:
    Data/processed/bold/bold_collector_affiliations_merged.csv
    Data/processed/bold/bold_minimal_records.csv

Writes:
    Data/processed/bold/bold_collector_affiliations_merged.csv  (updated in place)

Usage:
    python3 Scripts/12_fill_missing_countries.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

PROJ = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
BOLD_DIR = PROJ / "Data" / "processed" / "bold"
MINIMAL_CSV = BOLD_DIR / "bold_minimal_records.csv"

# Hardcoded ORG → country for organizations whose identity is obvious
ORG_COUNTRY = {
    "cbg collections staff": "CAN",
    "bio collections staff": "CAN",
    "bio collections": "CAN",
    "biobus 2008": "CAN",
    "biobus 2009": "CAN",
    "biobus 2010": "CAN",
    "biobus 2011": "CAN",
    "biobus 2012": "CAN",
    "biobus 2013": "CAN",
    "biobus 2014": "CAN",
    "biobus 2015": "CAN",
    "parks canada": "CAN",
    "parks canada staff": "CAN",
    "polar staff": "CAN",
    "cbh staff": "CAN",
    "heraty lab": "USA",
    "national ecological observatory network": "USA",
    "united states": "USA",
    "stone barns center": "USA",
    "icfc manu": "PER",
    "icfc wayqecha": "PER",
    "park rangers of parque exploradores": "PER",
    "binatang research center": "PNG",
    "gusaneros": "CRI",
    "park staff": "CRI",
    "palombar": "PRT",
    "ecoreg solutions": "ZAF",
    "african lion safari staff": "CAN",
    "local collector": "",
    "tdh/eyk/naa/baa": "",
}

# Known institution substrings → country
INST_COUNTRY = {
    "university of guelph": "CAN",
    "biodiversity institute of ontario": "CAN",
    "centre for biodiversity genomics": "CAN",
    "canadian centre for dna barcoding": "CAN",
    "agriculture and agri-food canada": "CAN",
    "canadian national collection": "CAN",
    "royal ontario museum": "CAN",
    "canadian museum of nature": "CAN",
    "parks canada": "CAN",
    "smithsonian": "USA",
    "national museum of natural history": "USA",
    "usda": "USA",
    "university of california": "USA",
    "texas a&m": "USA",
    "university of kentucky": "USA",
    "universidad de costa rica": "CRI",
    "area de conservacion guanacaste": "CRI",
    "inbio": "CRI",
    "south african national": "ZAF",
    "university of kwazulu": "ZAF",
    "stellenbosch": "ZAF",
    "csiro": "AUS",
    "australian museum": "AUS",
    "museum victoria": "AUS",
    "natural history museum": "GBR",
    "nhm london": "GBR",
    "wellcome sanger": "GBR",
    "museo argentino": "ARG",
    "inta": "ARG",
    "universidad de buenos aires": "ARG",
}


def inst_to_country(inst_str: str) -> str:
    low = inst_str.lower().strip()
    for pattern, cc in INST_COUNTRY.items():
        if pattern in low:
            return cc
    return ""


def main() -> int:
    merged = pd.read_csv(BOLD_DIR / "bold_collector_affiliations_merged.csv")
    merged["country_final"] = merged["country_final"].fillna("").astype(str)

    missing_mask = merged["country_final"] == ""
    missing_names = set(merged.loc[missing_mask, "name"].str.strip().str.lower())
    all_names = set(merged["name"].str.strip().str.lower())

    print(f"Total collectors: {len(merged)}")
    print(f"Missing country_final: {missing_mask.sum()}")
    print(f"Reading BOLD records: {MINIMAL_CSV}", flush=True)

    # --- Pass 1: scan BOLD for co-collectors and institutions ---
    # For each missing name, collect:
    #   co_collectors[name] = Counter of other people in the same collector string
    #   institutions[name] = Counter of inst values on their records
    co_collectors: dict[str, Counter] = defaultdict(Counter)
    institutions: dict[str, Counter] = defaultdict(Counter)
    total = 0

    for i, chunk in enumerate(
        pd.read_csv(MINIMAL_CSV, dtype=str,
                     usecols=["collectors", "inst"],
                     chunksize=500_000), 1
    ):
        total += len(chunk)
        mask = chunk["collectors"].notna()
        sub = chunk[mask]

        for _, row in sub.iterrows():
            coll_str = row["collectors"].strip()
            names_in_row = [n.strip().lower() for n in coll_str.split(",") if n.strip()]

            hits = [n for n in names_in_row if n in missing_names]
            if not hits:
                continue

            inst_val = str(row.get("inst", "")).strip()

            for name in hits:
                if inst_val and inst_val != "nan":
                    institutions[name][inst_val] += 1
                for other in names_in_row:
                    if other != name and other in all_names:
                        co_collectors[name][other] += 1

        print(f"  chunk {i}: {total:,} rows, "
              f"{len(institutions)} names with inst data, "
              f"{len(co_collectors)} names with co-collectors",
              flush=True)

    # --- Build lookup: name_lower → resolved country ---
    resolved = {}
    for _, row in merged.iterrows():
        cc = str(row["country_final"]).strip()
        if cc:
            resolved[row["name"].strip().lower()] = cc

    # --- Fill missing countries ---
    filled = 0
    details = []

    for idx in merged.index:
        if not missing_mask[idx]:
            continue

        name = merged.at[idx, "name"]
        name_lower = name.strip().lower()
        status = merged.at[idx, "status"]
        inferred_cc = ""
        method = ""

        # Method 1: ORG lookup table
        if status == "ORG":
            cc = ORG_COUNTRY.get(name_lower, "")
            if cc:
                inferred_cc = cc
                method = "org_lookup"

        # Method 2: BOLD institution field
        if not inferred_cc:
            inst_counts = institutions.get(name_lower, Counter())
            if inst_counts:
                top_inst = inst_counts.most_common(1)[0][0]
                cc = inst_to_country(top_inst)
                if cc:
                    inferred_cc = cc
                    method = f"bold_inst:{top_inst}"

        # Method 3: co-collector countries
        if not inferred_cc:
            coauthors = co_collectors.get(name_lower, Counter())
            if coauthors:
                cc_votes: Counter = Counter()
                for coauth, count in coauthors.most_common(20):
                    coauth_cc = resolved.get(coauth, "")
                    if coauth_cc:
                        cc_votes[coauth_cc] += count
                if cc_votes:
                    top_cc, top_n = cc_votes.most_common(1)[0]
                    total_n = sum(cc_votes.values())
                    share = top_n / total_n
                    if share >= 0.5:
                        inferred_cc = top_cc
                        top_coauths = ", ".join(
                            f"{c}({resolved.get(c,'')})"
                            for c, _ in coauthors.most_common(3)
                        )
                        method = f"co-collectors:{top_coauths}"

        if inferred_cc:
            merged.at[idx, "country_final"] = inferred_cc
            merged.at[idx, "review_notes"] = f"auto:{method}"
            filled += 1

        details.append({
            "number": merged.at[idx, "number"],
            "name": name,
            "status": status,
            "inferred": inferred_cc,
            "method": method,
            "top_inst": institutions.get(name_lower, Counter()).most_common(1)[0][0]
                if institutions.get(name_lower) else "",
            "n_coauthors": len(co_collectors.get(name_lower, Counter())),
        })

    # --- Report ---
    print(f"\n=== Filled {filled}/{missing_mask.sum()} missing countries ===\n")

    for d in details:
        flag = "OK" if d["inferred"] else "??"
        print(f"  [{flag}] {d['number']:3d}. {d['name'][:30]:<30s}  "
              f"{d['status']:11s}  → {d['inferred'] or '---':3s}  "
              f"inst={d['top_inst'][:35]}  "
              f"coauth={d['n_coauthors']}")

    still_missing = merged[merged["country_final"] == ""]
    print(f"\nStill missing: {len(still_missing)}")
    for _, r in still_missing.iterrows():
        print(f"  {r['number']:3d}. {r['name']} ({r['status']})")

    out = BOLD_DIR / "bold_collector_affiliations_merged.csv"
    merged.to_csv(out, index=False)
    print(f"\nWrote {out}")

    total_with = (merged["country_final"] != "").sum()
    print(f"Coverage: {total_with}/{len(merged)} ({100*total_with/len(merged):.1f}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
