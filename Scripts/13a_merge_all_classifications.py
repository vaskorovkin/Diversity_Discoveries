#!/usr/bin/env python3
"""Merge original 633 + batch 1-5 LLM classifications into expanded affiliations.

Run BEFORE 13_build_foreign_collecting_panel.py (which reads the output).

Two-stage pipeline:
  Stage 1 (always): merge LLM outputs + detect local collectors
           → _expanded_prereview.csv
  Stage 2 (always): apply reviewed decisions (DISAGREE, ORG, hardcoded fixes)
           → _expanded.csv

Reads:
    collectors/bold_collector_affiliations_633_reviewed.csv
    collectors/bold_batch{1-5}_classifications_{gpt,claude}.csv
    collectors/bold_batch1_classifications_claude.txt
    collectors/bold_all_collector_individuals.csv
    collectors/bold_disagree_for_review[_with_judgements].csv
    collectors/bold_org_for_review_merged_pass1_pass2.csv (preferred)
      or bold_org_for_review[_with_org_judgements].csv (fallback)

Writes:
    collectors/bold_collector_affiliations_expanded_prereview.csv  (always)
    collectors/bold_collector_affiliations_expanded.csv            (always)

Usage:
    python3 Scripts/13a_merge_all_classifications.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

PROJ = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
COLLECTORS_DIR = PROJ / "Data" / "processed" / "bold" / "collectors"


# ---------------------------------------------------------------------------
# ISO3 → ISO2
# ---------------------------------------------------------------------------
ISO3_TO_ISO2 = {
    "ALB": "AL", "ARE": "AE", "ARG": "AR", "AUS": "AU", "AUT": "AT",
    "BEL": "BE", "BEN": "BJ", "BFA": "BF", "BGD": "BD", "BGR": "BG",
    "BIH": "BA", "BLR": "BY", "BLZ": "BZ", "BMU": "BM", "BOL": "BO", "BRA": "BR",
    "BTN": "BT", "CAN": "CA", "CHE": "CH", "CHL": "CL", "CHN": "CN",
    "CIV": "CI", "CMR": "CM", "COD": "CD", "COG": "CG", "COL": "CO",
    "CRI": "CR", "CUB": "CU", "CUW": "CW", "CZE": "CZ", "DEU": "DE", "DNK": "DK",
    "DOM": "DO", "DZA": "DZ", "ECU": "EC", "EGY": "EG", "ESP": "ES",
    "EST": "EE", "ETH": "ET", "FIN": "FI", "FRA": "FR", "FRO": "FO",
    "GAB": "GA", "GBR": "GB", "GEO": "GE", "GHA": "GH", "GIN": "GN",
    "GRC": "GR", "GTM": "GT", "GUM": "GU", "GUY": "GY", "HKG": "HK",
    "HND": "HN", "HRV": "HR", "HUN": "HU", "IDN": "ID", "IND": "IN",
    "IRL": "IE", "IRN": "IR", "IRQ": "IQ", "ISL": "IS", "ISR": "IL",
    "ITA": "IT", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KGZ": "KG",
    "KOR": "KR", "LBN": "LB", "LKA": "LK", "LTU": "LT", "LUX": "LU",
    "LVA": "LV", "MAR": "MA", "MDA": "MD", "MDG": "MG", "MEX": "MX",
    "MKD": "MK", "MLT": "MT", "MMR": "MM", "MNE": "ME", "MNG": "MN",
    "MOZ": "MZ", "MUS": "MU", "MWI": "MW", "MYS": "MY", "NAM": "NA",
    "NGA": "NG", "NIC": "NI", "NLD": "NL", "NOR": "NO", "NPL": "NP",
    "NZL": "NZ", "OMN": "OM", "PAK": "PK", "PAN": "PA", "PER": "PE",
    "PHL": "PH", "PNG": "PG", "POL": "PL", "PRI": "PR", "PRT": "PT",
    "PRY": "PY", "ROU": "RO", "RUS": "RU", "SAU": "SA", "SDN": "SD",
    "SEN": "SN", "SGP": "SG", "SRB": "RS", "SUR": "SR", "SVK": "SK",
    "SVN": "SI", "SWE": "SE", "SYC": "SC", "THA": "TH", "TTO": "TT",
    "TUN": "TN", "TUR": "TR", "TWN": "TW", "TZA": "TZ", "UGA": "UG",
    "UKR": "UA", "URY": "UY", "USA": "US", "VIR": "VI", "VNM": "VN", "XKX": "XK",
    "ZAF": "ZA", "ZMB": "ZM", "ZWE": "ZW",
}


def classify_cat(inst: str) -> str:
    inst = str(inst).strip()
    if "ORGANIZATION" in inst or inst in ("—", "\x97", ""):
        return "ORG"
    if "AMBIGUOUS" in inst:
        return "AMBIGUOUS"
    if "UNKNOWN" in inst:
        return "UNKNOWN"
    return "MATCHED"


def valid_country(s: str) -> bool:
    s = str(s).strip()
    return len(s) == 3 and s.isalpha() and s.upper() not in ("NAN", "---")


def parse_claude_batch1(path: Path) -> pd.DataFrame:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"(\d+)\.\s+(.+?)\s*\|\s*(.+?)\s*\|\s*(\S+)", line)
            if m:
                rows.append({
                    "number": int(m.group(1)),
                    "name": m.group(2).strip(),
                    "institution": m.group(3).strip(),
                    "country_iso3": m.group(4).strip(),
                })
    return pd.DataFrame(rows)


def load_batch(batch: int, source: str) -> pd.DataFrame:
    if batch == 1 and source == "claude":
        return parse_claude_batch1(
            COLLECTORS_DIR / "bold_batch1_classifications_claude.txt"
        )
    path = COLLECTORS_DIR / f"bold_batch{batch}_classifications_{source}.csv"
    return pd.read_csv(path, encoding="utf-8-sig")


def compute_orig_rank(batch: int, seq_number: int) -> int:
    if batch == 1:
        return seq_number
    offset = 2634 + (batch - 2) * 2000
    return offset + seq_number


def merge_pair(gpt_row: dict, claude_row: dict) -> dict:
    g_inst = str(gpt_row.get("institution", "")).strip()
    c_inst = str(claude_row.get("institution", "")).strip()
    g_cc = str(gpt_row.get("country_iso3", "")).strip()
    c_cc = str(claude_row.get("country_iso3", "")).strip()
    g_cc = g_cc if valid_country(g_cc) else ""
    c_cc = c_cc if valid_country(c_cc) else ""
    g_cat = classify_cat(g_inst)
    c_cat = classify_cat(c_inst)

    if g_cat == "ORG" or c_cat == "ORG":
        return {"status": "ORG", "institution_final": "ORGANIZATION",
                "country_final": ""}

    if g_cat == "MATCHED" and c_cat == "MATCHED":
        if g_cc and c_cc:
            if g_cc == c_cc:
                return {"status": "AGREED", "institution_final": g_inst,
                        "country_final": g_cc}
            else:
                return {"status": "DISAGREE", "institution_final": "",
                        "country_final": ""}
        elif g_cc:
            return {"status": "AGREED", "institution_final": g_inst,
                    "country_final": g_cc}
        elif c_cc:
            return {"status": "AGREED", "institution_final": c_inst,
                    "country_final": c_cc}
        else:
            return {"status": "AGREED", "institution_final": g_inst,
                    "country_final": ""}

    if g_cat == "MATCHED" and c_cat in ("UNKNOWN", "AMBIGUOUS"):
        return {"status": "GPT_ONLY", "institution_final": g_inst,
                "country_final": g_cc if g_cc else c_cc}

    if c_cat == "MATCHED" and g_cat in ("UNKNOWN", "AMBIGUOUS"):
        return {"status": "CLAUDE_ONLY", "institution_final": c_inst,
                "country_final": c_cc if c_cc else g_cc}

    if g_cat == "AMBIGUOUS" and c_cat == "AMBIGUOUS":
        return {"status": "AMBIGUOUS", "institution_final": "",
                "country_final": ""}

    if g_cc and c_cc:
        if g_cc == c_cc:
            return {"status": "UNRESOLVED_AGREED", "institution_final": "",
                    "country_final": g_cc}
        else:
            return {"status": "UNRESOLVED_DISAGREE", "institution_final": "",
                    "country_final": g_cc}
    cc = g_cc or c_cc
    if cc:
        return {"status": "UNRESOLVED_ONE", "institution_final": "",
                "country_final": cc}
    return {"status": "UNRESOLVED", "institution_final": "", "country_final": ""}


# ---------------------------------------------------------------------------
# ORG classification helpers
# ---------------------------------------------------------------------------

def classify_org_category(name: str) -> str:
    """Assign a sort-friendly category for the ORG review file."""
    low = name.lower().strip()
    if "et al" in low or "et. al" in low:
        return "1_et_al"
    if "/" in low or ":" in low:
        return "2_multi_person"
    if "local" in low:
        return "3_local"
    if "student" in low:
        return "4_students"
    return "5_other"


ORG_COUNTRY_AUTO = {
    "cbg collections": "CAN", "bio collections": "CAN", "biobus": "CAN",
    "parks canada": "CAN", "polar staff": "CAN", "cbh staff": "CAN",
    "african lion safari": "CAN", "boreal entomology": "CAN",
    "rouge nup": "CAN", "caisn network": "CAN",
    "pacific biological station": "CAN", "assiniboine park zoo": "CAN",
    "heraty lab": "USA", "national ecological observatory network": "USA",
    "neon technician": "USA", "united states": "USA",
    "stone barns": "USA", "maryland": "USA", "deepend consortium": "USA",
    "fim personnel": "USA", "epa ord staff": "USA",
    "gusaneros": "CRI", "park staff": "CRI", "park rangers": "CRI",
    "inbio": "CRI",
    "icfc manu": "PER", "icfc wayqecha": "PER",
    "binatang": "PNG", "palombar": "PRT", "ecoreg solutions": "ZAF",
    "tubaro": "ARG", "lijtmaer": "ARG",
    "primary school students": "AUS", "ps students": "AUS",
    "area school students": "AUS", "high school students": "AUS",
    "college students": "AUS", "shark bay school": "AUS",
    "state school students": "AUS", "catholic school": "AUS",
    "atmosphere (nz)": "NZL", "rv tangaroa": "NZL",
    "finnmarksprosjektet": "NOR", "lubw insektenmonitoring": "DEU",
    "campagne resicod": "FRA", "pruvost et al": "FRA",
    "parc amazonien de guyane": "FRA", "tropical deep sea benthos": "FRA",
    "biomonitoras": "GTM", "grupo biomonitores": "GTM",
}


def auto_classify_org(name: str) -> str:
    low = name.lower().strip()
    for pattern, cc in ORG_COUNTRY_AUTO.items():
        if pattern in low:
            return cc
    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # ---- Stage 1: Pure LLM merge (no manual input) ----

    # Load original 633 (reviewed version — preserves user's manual work)
    reviewed_path = COLLECTORS_DIR / "bold_collector_affiliations_633_reviewed.csv"
    orig = pd.read_csv(reviewed_path)
    orig["source"] = "original_633"
    print(f"Original pipeline (reviewed): {len(orig)} collectors")
    print(f"  Status: {dict(orig['status'].value_counts())}")

    # Record counts from allcoll
    allcoll = pd.read_csv(
        COLLECTORS_DIR / "bold_all_collector_individuals.csv",
        usecols=["rank", "collector_name", "record_count_total"],
    )
    allcoll_lookup = dict(
        zip(allcoll["collector_name"].str.strip().str.lower(),
            allcoll["record_count_total"])
    )

    # Process batches 1-5
    batch_rows = []
    for b in range(1, 6):
        gpt = load_batch(b, "gpt")
        claude = load_batch(b, "claude")
        if len(gpt) != len(claude):
            print(f"WARNING: batch {b} size mismatch: GPT={len(gpt)}, Claude={len(claude)}")

        for i in range(len(gpt)):
            g = gpt.iloc[i]
            c = claude.iloc[i]
            seq_num = int(g["number"])
            orig_rank = compute_orig_rank(b, seq_num)
            name = str(g["name"]).strip()
            merged = merge_pair(g.to_dict(), c.to_dict())
            rec_count = allcoll_lookup.get(name.lower(), 0)

            batch_rows.append({
                "number": orig_rank,
                "name": name,
                "record_count_total": rec_count,
                "institution_gpt": str(g.get("institution", "")).strip(),
                "country_gpt": str(g.get("country_iso3", "")).strip(),
                "institution_claude": str(c.get("institution", "")).strip(),
                "country_claude": str(c.get("country_iso3", "")).strip(),
                "institution_final": merged["institution_final"],
                "country_final": merged["country_final"],
                "status": merged["status"],
                "review_notes": "",
                "source": f"batch_{b}",
            })
        print(f"Batch {b}: {len(gpt)} rows loaded")

    batch_df = pd.DataFrame(batch_rows)

    # Deduplicate batches by name
    batch_df["name_lower"] = batch_df["name"].str.strip().str.lower()
    n_before = len(batch_df)
    batch_df = batch_df.drop_duplicates(subset="name_lower", keep="first")
    n_dupes = n_before - len(batch_df)
    print(f"\nDuplicates within batches removed: {n_dupes}")

    # Drop any overlap with original 633
    orig_names = set(orig["name"].str.strip().str.lower())
    overlap = batch_df[batch_df["name_lower"].isin(orig_names)]
    if len(overlap) > 0:
        print(f"WARNING: {len(overlap)} batch names overlap with original 633 — dropping")
        batch_df = batch_df[~batch_df["name_lower"].isin(orig_names)]
    batch_df = batch_df.drop(columns=["name_lower"])

    # Combine
    out_cols = ["number", "name", "record_count_total",
                "institution_gpt", "country_gpt",
                "institution_claude", "country_claude",
                "institution_final", "country_final",
                "status", "review_notes", "source"]
    combined = pd.concat([orig[out_cols], batch_df[out_cols]], ignore_index=True)
    print(f"\nCombined: {len(combined)} unique collectors")

    # ---- Detect and add local collector names ----
    LOCAL_PATTERN = re.compile(r'\blocal\b', re.IGNORECASE)

    local_mask = combined["name"].apply(lambda n: bool(LOCAL_PATTERN.search(str(n))))
    n_reclassified = local_mask.sum()
    combined.loc[local_mask, "status"] = "LOCAL_COLLECTOR"
    combined.loc[local_mask, "country_final"] = ""
    combined.loc[local_mask, "review_notes"] = "domestic by definition"

    existing_names = set(combined["name"].str.strip().str.lower())
    local_rows = []
    for _, row in allcoll.iterrows():
        name = str(row["collector_name"]).strip()
        if LOCAL_PATTERN.search(name) and name.lower() not in existing_names:
            local_rows.append({
                "number": int(row["rank"]),
                "name": name,
                "record_count_total": int(row["record_count_total"]),
                "institution_gpt": "",
                "country_gpt": "",
                "institution_claude": "",
                "country_claude": "",
                "institution_final": "",
                "country_final": "",
                "status": "LOCAL_COLLECTOR",
                "review_notes": "domestic by definition",
                "source": "local_collector",
            })
    if local_rows:
        local_df = pd.DataFrame(local_rows)
        combined = pd.concat([combined, local_df[out_cols]], ignore_index=True)
    print(f"Local collectors: {n_reclassified} reclassified + {len(local_rows)} new "
          f"= {n_reclassified + len(local_rows)} total")

    # Write pre-review version
    prereview_path = COLLECTORS_DIR / "bold_collector_affiliations_expanded_prereview.csv"
    combined.to_csv(prereview_path, index=False)
    print(f"Wrote pre-review → {prereview_path}")

    # ---- Stage 2: Apply decisions from reviewed files ----
    # The user edits the review files in place (or creates _with_judgements
    # variants). The script reads them back and applies decisions.
    # No manual concatenation needed.

    # Hardcoded resolutions for dual-affiliation and politically sensitive cases.
    # These cannot be expressed as a single ISO3 in the review file.
    DUAL_AFFILIATION_FIXES = {
        "m.kekkonen": ("CAN", "dual CAN;FIN — use primary (CBG/Guelph)"),
        "jen guyton": ("USA", "dual USA;MOZ — use primary (Princeton)"),
        "adrienne jochum": ("CHE", "dual CHE;DEU — use primary (Bern)"),
        "maarten j. m. christenhusz": ("AUS", "dual AUS;NLD — use primary (Curtin)"),
        "maarten j.m. christenhusz": ("AUS", "dual AUS;NLD — duplicate name variant"),
        "moises bernal": ("USA", "dual USA;PAN — use primary (Auburn)"),
        "thomas dahlgren": ("NOR", "dual NOR;SWE — use primary (NORCE)"),
        "m. erdmann": ("NZL", "dual NZL;USA — use primary (ReShark/Re:wild)"),
        "k. a. efetov": ("UKR", "Crimea — coded as Ukraine"),
        "norseman ii": ("NOR", "Norwegian research vessel — LLM returned invalid ARC"),
    }

    decision_lookup: dict[str, tuple[str, str]] = {}

    # Read DISAGREE review file
    # Supports both original (country_decision) and LLM-reviewed (verified_country_iso)
    disagree_reviewed = COLLECTORS_DIR / "bold_disagree_for_review_with_judgements.csv"
    disagree_original = COLLECTORS_DIR / "bold_disagree_for_review.csv"
    disagree_path = disagree_reviewed if disagree_reviewed.exists() else disagree_original

    if disagree_path.exists():
        dr = pd.read_csv(disagree_path, encoding="utf-8-sig")
        # Detect which column has the decision
        if "verified_country_iso" in dr.columns:
            cc_col, notes_col = "verified_country_iso", "verified_notes"
        else:
            cc_col, notes_col = "country_decision", "decision_notes"
        dr[cc_col] = dr[cc_col].fillna("").astype(str).str.strip()
        valid = dr[dr[cc_col].str.match(r"^[A-Z]{3}$", na=False)]
        for _, row in valid.iterrows():
            key = str(row["name"]).strip().lower()
            notes = str(row.get(notes_col, "")).strip()
            decision_lookup[key] = (row[cc_col], notes)
        print(f"  DISAGREE: {len(valid)} decisions from {disagree_path.name}")
    else:
        # First run — create template
        disagree = combined[
            (combined["status"] == "DISAGREE") & (combined["source"] != "original_633")
        ].copy()
        disagree["country_decision"] = ""
        disagree["decision_notes"] = ""
        disagree_original.parent.mkdir(parents=True, exist_ok=True)
        disagree.to_csv(disagree_original, index=False)
        print(f"  Created DISAGREE template → {disagree_original.name}")

    # Read ORG review file (prefer merged pass1+pass2 > pass1 only > template)
    org_merged = COLLECTORS_DIR / "bold_org_for_review_merged_pass1_pass2.csv"
    org_reviewed = COLLECTORS_DIR / "bold_org_for_review_with_org_judgements.csv"
    org_original = COLLECTORS_DIR / "bold_org_for_review.csv"
    if org_merged.exists():
        org_path = org_merged
    elif org_reviewed.exists():
        org_path = org_reviewed
    else:
        org_path = org_original

    if org_path.exists():
        orr = pd.read_csv(org_path)
        if "merged_country_decision" in orr.columns:
            cc_col, notes_col = "merged_country_decision", "merged_notes"
        elif "country_decision_run" in orr.columns:
            cc_col, notes_col = "country_decision_run", "decision_basis_run"
        else:
            cc_col, notes_col = "country_decision", "decision_notes"
        orr[cc_col] = orr[cc_col].fillna("").astype(str).str.strip()
        orr[cc_col] = orr[cc_col].apply(
            lambda s: s.split(";")[0].strip() if ";" in str(s) else s
        )
        valid = orr[orr[cc_col].str.match(r"^[A-Z]{3}$", na=False)]
        for _, row in valid.iterrows():
            key = str(row["name"]).strip().lower()
            notes = str(row.get(notes_col, "")).strip()
            decision_lookup[key] = (row[cc_col], notes)
        print(f"  ORG: {len(valid)} decisions from {org_path.name}")
    else:
        # First run — create template
        orgs = combined[
            (combined["status"] == "ORG") & (combined["source"] != "original_633")
        ].copy()
        orgs["auto_country"] = orgs["name"].apply(auto_classify_org)
        orgs["org_category"] = orgs["name"].apply(classify_org_category)
        orgs["country_decision"] = orgs["auto_country"]
        orgs["decision_notes"] = orgs["auto_country"].apply(
            lambda x: "auto" if x else ""
        )
        orgs = orgs.sort_values(
            ["org_category", "record_count_total"], ascending=[True, False]
        )
        orgs.to_csv(org_original, index=False)
        auto_n = (orgs["auto_country"] != "").sum()
        print(f"  Created ORG template → {org_original.name} ({auto_n} auto)")

    # Hardcoded fixes take precedence over file-based decisions
    decision_lookup.update(DUAL_AFFILIATION_FIXES)

    # Apply all decisions (skip local collectors — their country is per-record)
    applied = 0
    for idx in combined.index:
        if combined.at[idx, "status"] == "LOCAL_COLLECTOR":
            continue
        key = str(combined.at[idx, "name"]).strip().lower()
        if key in decision_lookup:
            cc, notes = decision_lookup[key]
            combined.at[idx, "country_final"] = cc
            combined.at[idx, "review_notes"] = f"reviewed: {notes}" if notes else "reviewed"
            if combined.at[idx, "status"] == "DISAGREE":
                combined.at[idx, "status"] = "REVIEWED"
            elif combined.at[idx, "status"] == "ORG":
                combined.at[idx, "status"] = "ORG_REVIEWED"
            applied += 1
    print(f"  Applied {applied} decisions total")

    expanded_path = COLLECTORS_DIR / "bold_collector_affiliations_expanded.csv"
    combined.to_csv(expanded_path, index=False)
    label = "post-review" if applied > 0 else "pre-review (no decisions yet)"
    print(f"Wrote {label} → {expanded_path}")

    # ---- Summary ----
    print("\n=== Status distribution ===")
    for s, cnt in combined["status"].value_counts().items():
        print(f"  {s:>22s}: {cnt:5d} ({100 * cnt / len(combined):.1f}%)")

    has_cc = combined["country_final"].fillna("").astype(str).str.strip() != ""
    print(f"\nWith country_final: {has_cc.sum()} / {len(combined)} "
          f"({100 * has_cc.sum() / len(combined):.1f}%)")

    unmapped = set(combined.loc[has_cc, "country_final"].unique()) - set(ISO3_TO_ISO2.keys())
    if unmapped:
        print(f"WARNING: ISO3 codes without ISO2 mapping: {sorted(unmapped)}")

    total_records = combined["record_count_total"].sum()
    matched_records = combined.loc[has_cc, "record_count_total"].sum()
    print(f"Record-weighted coverage: {matched_records:,.0f} / {total_records:,.0f} "
          f"({100 * matched_records / total_records:.1f}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
