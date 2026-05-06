#!/usr/bin/env python3
"""Merge all 5 LLM classification batches, add BOLD inst data, audit agreements.

Non-invasive diagnostic script. Reads batch files and bold_minimal_records.csv,
writes a single audit CSV and prints summary statistics.

For each of the 9,358 new collector names (beyond the original 633):
  - Merges GPT and Claude classifications
  - Checks for duplicate names across batches
  - Looks up the most common BOLD `inst` field for each name
  - Compares BOLD inst against LLM country assignments

Reads:
    Data/processed/bold/collectors/bold_batch{1-5}_classifications_{gpt,claude}.csv
    Data/processed/bold/collectors/bold_batch1_classifications_claude.txt
    Data/processed/bold/collectors/bold_all_collector_individuals.csv
    Data/processed/bold/bold_minimal_records.csv

Writes:
    Data/processed/bold/collectors/audit_batch_classifications.csv

Usage:
    python3 Scripts/16_audit_batch_classifications.py
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

PROJ = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
CDIR = PROJ / "Data" / "processed" / "bold" / "collectors"
MINIMAL_CSV = PROJ / "Data" / "processed" / "bold" / "bold_minimal_records.csv"


def parse_claude_txt(path: Path) -> pd.DataFrame:
    """Parse pipe-delimited Claude batch 1 txt into a DataFrame."""
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or not line[0].isdigit():
            continue
        num_rest = line.split(".", 1)
        num = int(num_rest[0].strip())
        parts = num_rest[1].split("|")
        name = parts[0].strip() if len(parts) > 0 else ""
        inst = parts[1].strip() if len(parts) > 1 else ""
        cc = parts[2].strip() if len(parts) > 2 else "---"
        rows.append({"number": num, "name": name, "institution": inst, "country_iso3": cc})
    return pd.DataFrame(rows)


def classify(inst: str) -> str:
    inst = str(inst).strip()
    if inst == "ORGANIZATION":
        return "ORG"
    if inst == "AMBIGUOUS":
        return "AMBIGUOUS"
    if inst == "UNKNOWN":
        return "UNKNOWN"
    return "MATCHED"


def main() -> int:
    started = time.time()

    # ---------------------------------------------------------------
    # 1. Load the rank-to-name mapping for sequential-numbered batches
    # ---------------------------------------------------------------
    indiv = pd.read_csv(CDIR / "bold_all_collector_individuals.csv",
                        usecols=["rank", "collector_name"])
    rank_to_name = dict(zip(indiv["rank"], indiv["collector_name"]))

    # ---------------------------------------------------------------
    # 2. Load and unify all 5 batches
    # ---------------------------------------------------------------
    rows = []

    for b in range(1, 6):
        gpt = pd.read_csv(CDIR / f"bold_batch{b}_classifications_gpt.csv")
        if b == 1:
            claude = parse_claude_txt(CDIR / "bold_batch1_classifications_claude.txt")
        else:
            claude = pd.read_csv(CDIR / f"bold_batch{b}_classifications_claude.csv")

        merged = gpt.merge(claude, on="number", suffixes=("_gpt", "_claude"))

        for _, r in merged.iterrows():
            seq_num = int(r["number"])

            if b == 1:
                orig_rank = seq_num
            else:
                # Batches 2-5: sequential 1-N maps to ranks starting after batch 1
                # Batch 1 covers ranks 203-2634 (2000 names, non-contiguous from indiv)
                # Batch 2 starts at rank 2635, batch 3 at 4635, etc.
                offset = 2634 + (b - 2) * 2000
                orig_rank = offset + seq_num

            name_gpt = str(r["name_gpt"]).strip()
            name_claude = str(r["name_claude"]).strip()
            name = name_gpt if name_gpt else name_claude

            inst_gpt = str(r["institution_gpt"]).strip()
            inst_claude = str(r["institution_claude"]).strip()
            cc_gpt = str(r["country_iso3_gpt"]).strip()
            cc_claude = str(r["country_iso3_claude"]).strip()
            if cc_gpt == "nan":
                cc_gpt = "---"
            if cc_claude == "nan":
                cc_claude = "---"

            cat_gpt = classify(inst_gpt)
            cat_claude = classify(inst_claude)

            # Determine status
            if cat_gpt == "ORG" or cat_claude == "ORG":
                status = "ORG"
            elif cat_gpt == "MATCHED" and cat_claude == "MATCHED":
                if cc_gpt != "---" and cc_claude != "---":
                    status = "AGREED" if cc_gpt == cc_claude else "DISAGREE"
                elif cc_gpt != "---" or cc_claude != "---":
                    status = "AGREED"
                else:
                    status = "AGREED"
            elif cat_gpt == "MATCHED":
                status = "GPT_ONLY"
            elif cat_claude == "MATCHED":
                status = "CLAUDE_ONLY"
            elif cat_gpt == "AMBIGUOUS" and cat_claude == "AMBIGUOUS":
                status = "AMBIGUOUS"
            else:
                status = "UNRESOLVED"

            # Best country guess
            if status == "DISAGREE":
                best_cc = ""
            elif cc_gpt != "---" and cc_gpt:
                best_cc = cc_gpt
            elif cc_claude != "---" and cc_claude:
                best_cc = cc_claude
            else:
                best_cc = ""

            rows.append({
                "batch": b,
                "seq_number": seq_num,
                "orig_rank": orig_rank,
                "name": name,
                "name_lower": name.lower().strip(),
                "institution_gpt": inst_gpt,
                "country_gpt": cc_gpt,
                "institution_claude": inst_claude,
                "country_claude": cc_claude,
                "cat_gpt": cat_gpt,
                "cat_claude": cat_claude,
                "status": status,
                "best_cc": best_cc,
                "bold_inst": "",
                "bold_inst_count": 0,
                "bold_inst_country": "",
                "inst_vs_agree": "",
            })

    df = pd.DataFrame(rows)
    print(f"Loaded {len(df)} names from 5 batches")

    # ---------------------------------------------------------------
    # 3. Check duplicates
    # ---------------------------------------------------------------
    dup_names = df[df.duplicated("name_lower", keep=False)]
    n_dup = dup_names["name_lower"].nunique()
    print(f"Duplicate names across batches: {n_dup}")
    if n_dup > 0 and n_dup <= 20:
        for name, grp in dup_names.groupby("name_lower"):
            batches_str = ",".join(str(b) for b in grp["batch"])
            print(f"  {name}: batches {batches_str}")

    # ---------------------------------------------------------------
    # 4. Scan BOLD for inst values per collector name
    # ---------------------------------------------------------------
    target_names = set(df["name_lower"])
    inst_counts: dict[str, Counter] = defaultdict(Counter)

    print(f"\nScanning {MINIMAL_CSV} for inst values...", flush=True)
    total = 0
    for i, chunk in enumerate(
        pd.read_csv(MINIMAL_CSV, dtype=str,
                     usecols=["collectors", "inst"],
                     chunksize=500_000), 1
    ):
        total += len(chunk)
        mask = chunk["collectors"].notna() & chunk["inst"].notna()
        sub = chunk[mask]

        for _, row in sub.iterrows():
            coll_str = str(row["collectors"]).strip()
            inst_val = str(row["inst"]).strip()
            if not inst_val or inst_val == "nan":
                continue
            names_in_row = [n.strip().lower() for n in coll_str.split(",") if n.strip()]
            for name in names_in_row:
                if name in target_names:
                    inst_counts[name][inst_val] += 1

        if i % 5 == 0:
            print(f"  chunk {i}: {total:,} rows, {len(inst_counts)} names with inst",
                  flush=True)

    print(f"  Done: {total:,} rows scanned, {len(inst_counts)} names have BOLD inst data")

    # ---------------------------------------------------------------
    # 5. Attach BOLD inst to each row
    # ---------------------------------------------------------------
    for idx in df.index:
        name_low = df.at[idx, "name_lower"]
        counts = inst_counts.get(name_low)
        if counts:
            top_inst, top_count = counts.most_common(1)[0]
            df.at[idx, "bold_inst"] = top_inst
            df.at[idx, "bold_inst_count"] = top_count

    has_inst = (df["bold_inst"] != "").sum()
    print(f"\nNames with BOLD inst: {has_inst}/{len(df)} ({100*has_inst/len(df):.1f}%)")

    # ---------------------------------------------------------------
    # 6. Compare BOLD inst vs LLM countries
    # ---------------------------------------------------------------
    # For each row with both a BOLD inst and LLM countries, check if
    # the BOLD inst text matches what the LLMs said.
    # We don't try to map inst→country here; instead we flag cases
    # where the inst text contains a country-associated keyword.

    # Build a simple keyword→ISO3 lookup for comparison
    INST_KEYWORDS = {
        "guelph": "CAN", "ontario": "CAN", "canada": "CAN", "canadian": "CAN",
        "cbg": "CAN", "biodiversity institute of ontario": "CAN",
        "smithsonian": "USA", "usda": "USA", "united states": "USA",
        "california": "USA", "texas": "USA", "florida": "USA", "harvard": "USA",
        "cornell": "USA", "michigan": "USA", "illinois": "USA",
        "american museum": "USA", "yale": "USA",
        "natural history museum, london": "GBR", "nhm london": "GBR",
        "oxford": "GBR", "cambridge university": "GBR", "kew": "GBR",
        "edinburgh": "GBR", "cardiff": "GBR", "sanger": "GBR",
        "british museum": "GBR", "imperial college": "GBR",
        "csiro": "AUS", "australian museum": "AUS", "museum victoria": "AUS",
        "queensland": "AUS", "western australia": "AUS",
        "museo argentino": "ARG", "inta": "ARG", "buenos aires": "ARG",
        "conicet": "ARG",
        "south african": "ZAF", "sanbi": "ZAF", "iziko": "ZAF",
        "stellenbosch": "ZAF", "pretoria": "ZAF", "kwazulu": "ZAF",
        "inbio": "CRI", "costa rica": "CRI", "acg": "CRI",
        "naturalis": "NLD", "leiden": "NLD", "wageningen": "NLD",
        "amsterdam": "NLD",
        "museum fur naturkunde": "DEU", "senckenberg": "DEU",
        "zoologische staatssammlung": "DEU", "bavarian": "DEU",
        "bonn": "DEU", "hamburg": "DEU", "munich": "DEU",
        "mnhn": "FRA", "museum national": "FRA", "montpellier": "FRA",
        "paris": "FRA", "ird": "FRA",
        "tokyo": "JPN", "kyoto": "JPN", "osaka": "JPN", "hokkaido": "JPN",
        "chinese academy": "CHN", "beijing": "CHN", "kunming": "CHN",
        "swedish museum": "SWE", "lund": "SWE", "uppsala": "SWE",
        "station linne": "SWE",
        "helsinki": "FIN", "turku": "FIN", "oulu": "FIN",
        "oslo": "NOR", "bergen": "NOR", "trondheim": "NOR", "ntnu": "NOR",
        "nibio": "NOR",
        "copenhagen": "DNK", "aarhus": "DNK",
        "moscow": "RUS", "saint petersburg": "RUS",
        "sao paulo": "BRA", "rio de janeiro": "BRA", "inpa": "BRA",
        "mexico": "MEX", "unam": "MEX",
        "university of porto": "PRT", "lisbon": "PRT",
        "zurich": "CHE", "bern": "CHE", "basel": "CHE", "geneva": "CHE",
        "vienna": "AUT", "graz": "AUT", "innsbruck": "AUT",
        "warsaw": "POL", "krakow": "POL", "poznan": "POL",
        "prague": "CZE", "brno": "CZE", "ostrava": "CZE",
        "national museum of kenya": "KEN", "nairobi": "KEN",
        "rome": "ITA", "milan": "ITA", "florence": "ITA", "torino": "ITA",
        "brussels": "BEL", "ghent": "BEL", "antwerp": "BEL",
        "makerere": "UGA",
        "cape town": "ZAF", "johannesburg": "ZAF",
        "singapore": "SGP",
        "hebrew university": "ISR", "tel aviv": "ISR",
        "new zealand": "NZL", "auckland": "NZL", "wellington": "NZL",
        "national taiwan": "TWN", "taipei": "TWN",
        "seoul": "KOR", "korea": "KOR",
        "abu dhabi": "ARE", "dubai": "ARE",
        "cairo": "EGY",
        "lima": "PER",
        "bogota": "COL",
        "santiago": "CHL",
        "panama": "PAN",
        "luxembourg": "LUX",
    }

    def inst_to_country(inst_str: str) -> str:
        low = inst_str.lower()
        for kw, cc in INST_KEYWORDS.items():
            if kw in low:
                return cc
        return ""

    confirmed = 0
    contradicted = 0
    broke_tie = 0
    filled_unknown = 0

    for idx in df.index:
        bold_inst = df.at[idx, "bold_inst"]
        if not bold_inst:
            continue

        bold_cc = inst_to_country(bold_inst)
        df.at[idx, "bold_inst_country"] = bold_cc
        if not bold_cc:
            continue

        status = df.at[idx, "status"]
        cc_gpt = df.at[idx, "country_gpt"]
        cc_claude = df.at[idx, "country_claude"]
        best_cc = df.at[idx, "best_cc"]

        if status == "AGREED" and best_cc:
            if bold_cc == best_cc:
                df.at[idx, "inst_vs_agree"] = "CONFIRMS"
                confirmed += 1
            else:
                df.at[idx, "inst_vs_agree"] = f"CONTRADICTS({bold_cc})"
                contradicted += 1
        elif status == "DISAGREE":
            if bold_cc == cc_gpt:
                df.at[idx, "inst_vs_agree"] = "SUPPORTS_GPT"
                broke_tie += 1
            elif bold_cc == cc_claude:
                df.at[idx, "inst_vs_agree"] = "SUPPORTS_CLAUDE"
                broke_tie += 1
            else:
                df.at[idx, "inst_vs_agree"] = f"NEITHER({bold_cc})"
        elif status in ("GPT_ONLY", "CLAUDE_ONLY"):
            if bold_cc == best_cc:
                df.at[idx, "inst_vs_agree"] = "CONFIRMS"
                confirmed += 1
            else:
                df.at[idx, "inst_vs_agree"] = f"CONTRADICTS({bold_cc})"
                contradicted += 1
        elif status in ("UNRESOLVED", "AMBIGUOUS"):
            df.at[idx, "inst_vs_agree"] = f"FILLS({bold_cc})"
            filled_unknown += 1

    # ---------------------------------------------------------------
    # 7. Report
    # ---------------------------------------------------------------
    print("\n=== STATUS SUMMARY ===")
    for s, cnt in df["status"].value_counts().items():
        print(f"  {s:15s}: {cnt:5d} ({100*cnt/len(df):.1f}%)")

    print(f"\n=== BOLD INST vs LLM COUNTRY ===")
    has_bold_cc = (df["bold_inst_country"] != "").sum()
    print(f"  Names with BOLD inst:            {has_inst}")
    print(f"  Names with mappable BOLD inst:   {has_bold_cc}")
    print(f"  CONFIRMS agreement:              {confirmed}")
    print(f"  CONTRADICTS agreement:           {contradicted}")
    print(f"  Breaks tie on DISAGREE:          {broke_tie}")
    print(f"  Fills UNRESOLVED/AMBIGUOUS:      {filled_unknown}")

    # Detail on contradictions
    contras = df[df["inst_vs_agree"].str.startswith("CONTRADICTS", na=False)]
    if len(contras) > 0:
        print(f"\n=== CONTRADICTIONS ({len(contras)}) ===")
        for _, r in contras.head(30).iterrows():
            print(f"  B{r['batch']} #{r['orig_rank']:5d}  {r['name'][:28]:<28s}  "
                  f"LLM:{r['best_cc']:3s}  BOLD_inst:{r['bold_inst_country']:3s}  "
                  f"inst=\"{r['bold_inst'][:40]}\"")

    # Detail on DISAGREE with tie-break
    ties = df[df["inst_vs_agree"].str.startswith("SUPPORTS", na=False)]
    if len(ties) > 0:
        print(f"\n=== DISAGREE TIE-BREAKS ({len(ties)}) ===")
        for _, r in ties.head(30).iterrows():
            winner = "GPT" if "GPT" in r["inst_vs_agree"] else "Claude"
            print(f"  B{r['batch']} #{r['orig_rank']:5d}  {r['name'][:28]:<28s}  "
                  f"GPT:{r['country_gpt']:3s}  Claude:{r['country_claude']:3s}  "
                  f"BOLD→{r['bold_inst_country']:3s} ({winner})  "
                  f"inst=\"{r['bold_inst'][:35]}\"")

    # DISAGREE with no tie-break
    neither = df[df["inst_vs_agree"].str.startswith("NEITHER", na=False)]
    if len(neither) > 0:
        print(f"\n=== DISAGREE, BOLD INST MATCHES NEITHER ({len(neither)}) ===")
        for _, r in neither.head(20).iterrows():
            print(f"  B{r['batch']} #{r['orig_rank']:5d}  {r['name'][:28]:<28s}  "
                  f"GPT:{r['country_gpt']:3s}  Claude:{r['country_claude']:3s}  "
                  f"BOLD→{r['bold_inst_country']:3s}  "
                  f"inst=\"{r['bold_inst'][:35]}\"")

    # Fills
    fills = df[df["inst_vs_agree"].str.startswith("FILLS", na=False)]
    if len(fills) > 0:
        print(f"\n=== UNRESOLVED/AMBIGUOUS FILLED BY BOLD INST ({len(fills)}) ===")
        for _, r in fills.head(20).iterrows():
            print(f"  B{r['batch']} #{r['orig_rank']:5d}  {r['name'][:28]:<28s}  "
                  f"→ {r['bold_inst_country']:3s}  "
                  f"inst=\"{r['bold_inst'][:45]}\"")
        print(f"  ... ({len(fills)} total)")

    # Summary of DISAGREE rows
    disagree_total = (df["status"] == "DISAGREE").sum()
    disagree_with_inst = df[(df["status"] == "DISAGREE") & (df["bold_inst"] != "")]
    disagree_resolved = df[(df["status"] == "DISAGREE") & (df["inst_vs_agree"].str.startswith("SUPPORTS", na=False))]
    print(f"\n=== DISAGREE SUMMARY ===")
    print(f"  Total DISAGREE:          {disagree_total}")
    print(f"  With BOLD inst:          {len(disagree_with_inst)}")
    print(f"  Resolved by BOLD inst:   {len(disagree_resolved)}")
    print(f"  Remaining to review:     {disagree_total - len(disagree_resolved)}")

    # ---------------------------------------------------------------
    # 8. Save
    # ---------------------------------------------------------------
    out = CDIR / "audit_batch_classifications.csv"
    df.to_csv(out, index=False)
    elapsed = time.time() - started
    print(f"\nWrote {len(df)} rows to {out}")
    print(f"Time: {elapsed:.0f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
