#!/usr/bin/env python3
"""Merge GPT and Claude collector affiliation guesses into one file.

Reads:
    Data/processed/bold/bold_collectors_affiliations_gpt.csv
    Data/processed/bold/bold_collectors_affiliations_claude.csv
    Data/processed/bold/bold_top500_collector_individuals.csv

Writes:
    Data/processed/bold/bold_collector_affiliations_merged.csv

Columns in output:
    number, name, record_count_total,
    institution_gpt, country_gpt, institution_claude, country_claude,
    institution_final, country_final, status, notes

Status values:
    AGREED       - both LLMs gave same country (or same institution after normalization)
    GPT_ONLY     - GPT matched, Claude said UNKNOWN/AMBIGUOUS
    CLAUDE_ONLY  - Claude matched, GPT said UNKNOWN/AMBIGUOUS
    DISAGREE     - both gave answers but they conflict → needs manual review
    ORG          - both flagged as organization/team
    UNRESOLVED   - neither matched
    AMBIGUOUS    - single-word name, can't identify

Usage:
    python3 Scripts/11_merge_collector_affiliations.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

PROJ = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
BOLD_DIR = PROJ / "Data" / "processed" / "bold"


def classify(inst: str) -> str:
    inst = str(inst).strip()
    if "ORGANIZATION" in inst or inst in ("—", "\x97", ""):
        return "ORG"
    if "AMBIGUOUS" in inst:
        return "AMBIGUOUS"
    if "UNKNOWN" in inst:
        return "UNKNOWN"
    return "MATCHED"


def norm_inst(s: str) -> str:
    s = str(s).lower().strip()
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    for old, new in [
        ("south african national biodiversity institute", "sanbi"),
        ("south african national parks", "sanparks"),
        ("museo argentino de ciencias naturales bernardino rivadavia", "macn"),
        ("museo argentino de ciencias naturales", "macn"),
        ("norwegian university of science and technology", "ntnu"),
        ("ntnu university museum", "ntnu"),
        ("university of california riverside", "uc riverside"),
        ("university of california san diego", "uc san diego"),
        ("uc san diego", "ucsd"),
        ("saint joseph university of beirut", "usj beirut"),
        ("saint joseph university beirut", "usj beirut"),
        ("i.i. schmalhausen institute of zoology", "schmalhausen institute"),
        ("schmalhausen institute of zoology nas ukraine", "schmalhausen institute"),
        ("new guinea binatang research center", "binatang research center"),
    ]:
        s = s.replace(old, new)
    return s


def valid_country(s: str) -> bool:
    s = str(s).strip()
    return len(s) == 3 and s.isalpha() and s.upper() != "NAN"


def main() -> int:
    gpt = pd.read_csv(BOLD_DIR / "bold_collectors_affiliations_gpt.csv", encoding="cp1252")
    claude = pd.read_csv(BOLD_DIR / "bold_collectors_affiliations_claude.csv", encoding="cp1252")
    indiv = pd.read_csv(BOLD_DIR / "bold_top500_collector_individuals.csv")

    gpt.columns = [re.sub(r"[^\x00-\x7f]", "", c).strip().rstrip(":") for c in gpt.columns]
    claude.columns = [re.sub(r"[^\x00-\x7f]", "", c).strip().rstrip(":") for c in claude.columns]

    gpt["cat"] = gpt["institution"].apply(classify)
    claude["cat"] = claude["institution"].apply(classify)

    rows = []
    for i in range(len(gpt)):
        g = gpt.iloc[i]
        c = claude.iloc[i]
        num = int(g["number"])

        rec_match = indiv[indiv["rank"] == num]
        rec_count = int(rec_match["record_count_total"].iloc[0]) if len(rec_match) > 0 else 0

        g_inst = str(g["institution"]).strip()
        c_inst = str(c["institution"]).strip()
        g_cc = str(g["country_iso3"]).strip() if valid_country(str(g["country_iso3"])) else ""
        c_cc = str(c["country_iso3"]).strip() if valid_country(str(c["country_iso3"])) else ""
        g_cat = g["cat"]
        c_cat = c["cat"]

        # Determine status and final values
        if g_cat == "ORG" and c_cat == "ORG":
            status = "ORG"
            final_inst = "ORGANIZATION"
            final_cc = ""
        elif g_cat == "ORG" or c_cat == "ORG":
            status = "ORG"
            final_inst = "ORGANIZATION"
            final_cc = ""
        elif g_cat == "MATCHED" and c_cat == "MATCHED":
            if g_cc == c_cc and g_cc:
                if norm_inst(g_inst) == norm_inst(c_inst):
                    status = "AGREED"
                else:
                    status = "AGREED"
                final_inst = g_inst
                final_cc = g_cc
            elif g_cc and c_cc and g_cc != c_cc:
                status = "DISAGREE"
                final_inst = ""
                final_cc = ""
            elif g_cc and not c_cc:
                status = "AGREED"
                final_inst = g_inst
                final_cc = g_cc
            elif c_cc and not g_cc:
                status = "AGREED"
                final_inst = c_inst
                final_cc = c_cc
            else:
                status = "AGREED"
                final_inst = g_inst
                final_cc = g_cc
        elif g_cat == "MATCHED" and c_cat in ("UNKNOWN", "AMBIGUOUS"):
            status = "GPT_ONLY"
            final_inst = g_inst
            final_cc = g_cc if g_cc else c_cc
        elif c_cat == "MATCHED" and g_cat in ("UNKNOWN", "AMBIGUOUS"):
            status = "CLAUDE_ONLY"
            final_inst = c_inst
            final_cc = c_cc if c_cc else g_cc
        elif g_cat == "AMBIGUOUS" and c_cat == "AMBIGUOUS":
            status = "AMBIGUOUS"
            final_inst = ""
            final_cc = ""
        elif g_cat == "UNKNOWN" and c_cat == "UNKNOWN":
            # Claude often gives country even when institution is UNKNOWN
            status = "UNRESOLVED"
            final_inst = ""
            final_cc = c_cc if c_cc else g_cc
        elif g_cat == "AMBIGUOUS" and c_cat == "UNKNOWN":
            status = "UNRESOLVED"
            final_inst = ""
            final_cc = c_cc if c_cc else ""
        elif g_cat == "UNKNOWN" and c_cat == "AMBIGUOUS":
            status = "UNRESOLVED"
            final_inst = ""
            final_cc = g_cc if g_cc else ""
        else:
            status = "UNRESOLVED"
            final_inst = ""
            final_cc = ""

        rows.append({
            "number": num,
            "name": str(g["name"]),
            "record_count_total": rec_count,
            "institution_gpt": g_inst,
            "country_gpt": g_cc,
            "institution_claude": c_inst,
            "country_claude": c_cc,
            "institution_final": final_inst,
            "country_final": final_cc,
            "status": status,
            "review_notes": "",
        })

    df = pd.DataFrame(rows)
    out = BOLD_DIR / "bold_collector_affiliations_merged.csv"
    df.to_csv(out, index=False)

    print(f"Wrote {len(df)} rows to {out}")
    print()
    print("=== Status summary ===")
    for s, cnt in df["status"].value_counts().items():
        print(f"  {s:15s}: {cnt:4d} ({100*cnt/len(df):.1f}%)")
    print()
    disagree = df[df["status"] == "DISAGREE"]
    print(f"=== DISAGREE rows needing manual review: {len(disagree)} ===")
    for _, r in disagree.iterrows():
        print(f"  {r['number']:3d}. {r['name'][:30]:<30s}  "
              f"GPT:{r['country_gpt']:3s} ({str(r['institution_gpt'])[:30]})  "
              f"Claude:{r['country_claude']:3s} ({str(r['institution_claude'])[:30]})")

    unresolved = df[df["status"] == "UNRESOLVED"]
    with_cc = unresolved[unresolved["country_final"] != ""]
    print(f"\n=== UNRESOLVED: {len(unresolved)} total, {len(with_cc)} have country from Claude ===")
    print(f"=== AMBIGUOUS (single-word names): {(df['status']=='AMBIGUOUS').sum()} ===")
    print(f"=== ORG: {(df['status']=='ORG').sum()} ===")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
