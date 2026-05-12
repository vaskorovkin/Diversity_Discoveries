#!/usr/bin/env python3
"""Build cell-year panel of foreign vs domestic collecting.

For each BOLD record with geocoordinates and a collector field, matches
collector names against the affiliation file to determine whether the
collector is foreign (home country != collecting country) or domestic.

Outputs both integer record counts (categorical, mutually exclusive) and
fractional score sums (splitting mixed-collector records proportionally).

Foreign collectors are further split into regional (same continent) and
distant (different continent).

Aggregates to the same 100 km equal-area grid used by the main pipeline.

Reads:
    Data/processed/bold/collectors/bold_collector_affiliations_expanded.csv
    Data/processed/bold/bold_minimal_records.csv
    Data/regressors/baseline_geography/resolve_ecoregions_100km_cells.csv

Writes:
    Data/processed/bold/collectors/bold_foreign_collecting_cell_year_panel.csv

Usage:
    python3 Scripts/preliminary/13_build_foreign_collecting_panel.py
"""


from __future__ import annotations


from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _path in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

PROJ = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
BOLD_DIR = PROJ / "Data" / "processed" / "bold"
MINIMAL_CSV = BOLD_DIR / "bold_minimal_records.csv"
AFFILIATIONS_CSV = BOLD_DIR / "collectors" / "bold_collector_affiliations_expanded.csv"
RESOLVE_CSV = PROJ / "Data" / "regressors" / "baseline_geography" / "resolve_ecoregions_100km_cells.csv"
EQUAL_AREA_CRS = "EPSG:6933"
CELL_M = 100_000
YEAR_MIN = 2005
YEAR_MAX = 2025

# Affiliations use ISO3; BOLD country_iso uses ISO2
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


def build_continent_lookup() -> dict[str, str]:
    """ISO2 → continent, derived from RESOLVE ecoregions."""
    df = pd.read_csv(RESOLVE_CSV, usecols=["iso_a3", "continent"])
    df = df.dropna(subset=["iso_a3", "continent"])
    iso3_cont = (
        df.groupby("iso_a3")["continent"]
        .agg(lambda x: x.mode().iloc[0])
        .to_dict()
    )
    lookup = {}
    for iso3, cont in iso3_cont.items():
        iso2 = ISO3_TO_ISO2.get(iso3)
        if iso2:
            lookup[iso2] = cont
    return lookup


def build_collector_lookup() -> tuple[dict[str, str], set[str]]:
    """Returns (name_lower -> home ISO2, set of local collector names).

    Local collectors (status=LOCAL_COLLECTOR) have no fixed home country --
    they are domestic by definition, so the collecting country is used at
    match time.
    """
    df = pd.read_csv(AFFILIATIONS_CSV)
    df["country_final"] = df["country_final"].fillna("").astype(str)
    df["status"] = df["status"].fillna("").astype(str)
    lookup = {}
    local_names: set[str] = set()
    unmapped = set()
    for _, row in df.iterrows():
        name_lower = row["name"].strip().lower()
        if row["status"].strip() == "LOCAL_COLLECTOR":
            local_names.add(name_lower)
            continue
        cc3 = row["country_final"].strip()
        if cc3:
            cc2 = ISO3_TO_ISO2.get(cc3)
            if cc2:
                lookup[name_lower] = cc2
            else:
                unmapped.add(cc3)
    if unmapped:
        print(f"WARNING: no ISO2 mapping for: {unmapped}")
    return lookup, local_names


def main() -> int:
    started = time.time()

    continent_lookup = build_continent_lookup()
    print(f"Continent lookup: {len(continent_lookup)} countries mapped")

    collector_home, local_collectors = build_collector_lookup()
    print(f"Collector lookup: {len(collector_home)} names with home country")
    print(f"Local collectors: {len(local_collectors)} names (domestic by definition)")

    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)

    # Accumulators per (cell_id, year)
    acc_total = defaultdict(int)
    acc_with_collectors = defaultdict(int)
    acc_classified = defaultdict(int)
    acc_unclassified = defaultdict(int)

    acc_domestic_records = defaultdict(int)
    acc_regional_records = defaultdict(int)
    acc_distant_records = defaultdict(int)
    acc_collab_records = defaultdict(int)

    acc_domestic_score = defaultdict(float)
    acc_regional_score = defaultdict(float)
    acc_distant_score = defaultdict(float)

    acc_foreign_collectors = defaultdict(set)
    acc_domestic_collectors = defaultdict(set)

    total_rows = 0
    total_geocoded = 0
    total_with_collector = 0
    total_matched = 0

    for i, chunk in enumerate(
        pd.read_csv(MINIMAL_CSV, dtype=str,
                     usecols=["latitude", "longitude", "has_coord",
                              "collection_year", "collectors", "country_iso"],
                     chunksize=500_000), 1
    ):
        total_rows += len(chunk)

        geo = chunk[chunk["has_coord"].fillna("") == "1"].copy()
        if geo.empty:
            print(f"  chunk {i}: {total_rows:,} rows (no geocoded)", flush=True)
            continue

        lat = pd.to_numeric(geo["latitude"], errors="coerce")
        lon = pd.to_numeric(geo["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        geo = geo[valid]
        lat = lat[valid].to_numpy()
        lon = lon[valid].to_numpy()

        if len(geo) == 0:
            print(f"  chunk {i}: {total_rows:,} rows (no valid coords)", flush=True)
            continue

        x, y = transformer.transform(lon, lat)
        cell_x = np.floor(x / CELL_M).astype(int)
        cell_y = np.floor(y / CELL_M).astype(int)

        years_raw = geo["collection_year"].fillna("").to_numpy()
        collectors_raw = geo["collectors"].fillna("").to_numpy()
        country_iso_raw = geo["country_iso"].fillna("").to_numpy()

        total_geocoded += len(geo)
        chunk_matched = 0

        for j in range(len(geo)):
            yr_str = str(years_raw[j]).strip()
            if len(yr_str) < 4 or not yr_str[:4].isdigit():
                continue
            yr = int(yr_str[:4])
            if yr < YEAR_MIN or yr > YEAR_MAX:
                continue

            cell_id = f"{cell_x[j]}_{cell_y[j]}"
            key = (cell_id, yr)
            acc_total[key] += 1

            coll_str = str(collectors_raw[j]).strip()
            if not coll_str:
                continue
            acc_with_collectors[key] += 1
            total_with_collector += 1

            collecting_country = str(country_iso_raw[j]).strip()

            names = [n.strip().lower() for n in coll_str.split(",") if n.strip()]
            matched_homes = []
            matched_names_for_cell = []
            for name in names:
                home = collector_home.get(name)
                if home:
                    matched_homes.append(home)
                    matched_names_for_cell.append((name, home))
                elif name in local_collectors and collecting_country:
                    matched_homes.append(collecting_country)
                    matched_names_for_cell.append((name, collecting_country))

            if not matched_homes:
                acc_unclassified[key] += 1
                continue

            total_matched += 1
            chunk_matched += 1
            acc_classified[key] += 1

            if not collecting_country:
                continue

            collecting_cont = continent_lookup.get(collecting_country, "")

            n_dom = 0
            n_reg = 0
            n_dist = 0
            has_domestic = False
            has_foreign = False

            for home in matched_homes:
                if home == collecting_country:
                    n_dom += 1
                    has_domestic = True
                else:
                    has_foreign = True
                    home_cont = continent_lookup.get(home, "")
                    if home_cont and collecting_cont and home_cont == collecting_cont:
                        n_reg += 1
                    else:
                        n_dist += 1

            n_total = n_dom + n_reg + n_dist

            # Fractional scores
            acc_domestic_score[key] += n_dom / n_total
            acc_regional_score[key] += n_reg / n_total
            acc_distant_score[key] += n_dist / n_total

            # Categorical (hierarchy: distant > regional > domestic)
            if n_dist > 0:
                acc_distant_records[key] += 1
            elif n_reg > 0:
                acc_regional_records[key] += 1
            else:
                acc_domestic_records[key] += 1

            # Collaboration: both domestic and foreign on same record
            if has_domestic and has_foreign:
                acc_collab_records[key] += 1

            # Unique collector names
            for name, home in matched_names_for_cell:
                if home != collecting_country:
                    acc_foreign_collectors[key].add(name)
                else:
                    acc_domestic_collectors[key].add(name)

        print(f"  chunk {i}: {total_rows:,} rows, "
              f"{total_geocoded:,} geocoded, "
              f"{chunk_matched:,} matched this chunk",
              flush=True)

    # Build output dataframe
    all_keys = sorted(set(acc_total.keys()))
    rows = []
    for key in all_keys:
        cell_id, year = key

        rows.append({
            "cell_id": cell_id,
            "year": year,
            "records_total": acc_total[key],
            "records_with_collectors": acc_with_collectors.get(key, 0),
            "records_classified": acc_classified.get(key, 0),
            "records_unclassified": acc_unclassified.get(key, 0),
            "records_domestic": acc_domestic_records.get(key, 0),
            "records_foreign_regional": acc_regional_records.get(key, 0),
            "records_foreign_distant": acc_distant_records.get(key, 0),
            "records_collab": acc_collab_records.get(key, 0),
            "domestic_score_sum": round(acc_domestic_score.get(key, 0.0), 4),
            "regional_score_sum": round(acc_regional_score.get(key, 0.0), 4),
            "distant_score_sum": round(acc_distant_score.get(key, 0.0), 4),
            "n_collectors_foreign": len(acc_foreign_collectors.get(key, set())),
            "n_collectors_domestic": len(acc_domestic_collectors.get(key, set())),
        })

    df = pd.DataFrame(rows)
    out = BOLD_DIR / "collectors" / "bold_foreign_collecting_cell_year_panel.csv"
    df.to_csv(out, index=False)

    elapsed = time.time() - started
    print(f"\nWrote {len(df):,} cell-year rows to {out}")
    print(f"Time: {elapsed:.0f}s")
    print(f"\nSummary:")
    print(f"  Total BOLD rows:            {total_rows:,}")
    print(f"  Geocoded:                   {total_geocoded:,}")
    print(f"  With collector field:       {total_with_collector:,}")
    print(f"  Classified (>=1 match):     {total_matched:,}")
    print(f"  Cell-year observations:     {len(df):,}")

    classified = df["records_classified"].sum()
    dom = df["records_domestic"].sum()
    reg = df["records_foreign_regional"].sum()
    dist = df["records_foreign_distant"].sum()
    collab = df["records_collab"].sum()
    scored = df["domestic_score_sum"].sum() + df["regional_score_sum"].sum() + df["distant_score_sum"].sum()

    if classified > 0:
        print(f"\n  Classified records:         {classified:,}")
        print(f"    Domestic:                 {dom:,} ({100*dom/classified:.1f}%)")
        print(f"    Foreign regional:         {reg:,} ({100*reg/classified:.1f}%)")
        print(f"    Foreign distant:          {dist:,} ({100*dist/classified:.1f}%)")
        print(f"    Collaborations (dom+for): {collab:,} ({100*collab/classified:.1f}%)")

    if scored > 0:
        dom_s = df["domestic_score_sum"].sum()
        reg_s = df["regional_score_sum"].sum()
        dist_s = df["distant_score_sum"].sum()
        print(f"\n  Fractional scores (sum to classified w/ country):")
        print(f"    Domestic score:           {dom_s:,.1f} ({100*dom_s/scored:.1f}%)")
        print(f"    Regional score:           {reg_s:,.1f} ({100*reg_s/scored:.1f}%)")
        print(f"    Distant score:            {dist_s:,.1f} ({100*dist_s/scored:.1f}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
