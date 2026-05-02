#!/usr/bin/env python3
"""Download World Bank GDP per capita (current US$) for all countries, 2001-2024.

Source: World Bank World Development Indicators (WDI).
Indicator: NY.GDP.PCAP.CD (GDP per capita, current US$).
Uses the World Bank Indicators API v2 (JSON format, no key required).

Two-step approach: first fetches the country list to exclude aggregates,
then queries the indicator for real countries only.

Output: Data/regressors/worldbank/worldbank_gdp_pcap_panel.csv
  Columns: iso_a3, country_name, year, gdp_pcap_current_usd
"""

from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "regressors" / "worldbank"

INDICATOR = "NY.GDP.PCAP.CD"
YEAR_MIN = 2001
YEAR_MAX = 2024
PER_PAGE = 500

BASE_API = "https://api.worldbank.org/v2"


def fetch_country_codes() -> list[str]:
    """Return ISO3 codes for real countries (not aggregates)."""
    url = f"{BASE_API}/country?format=json&per_page={PER_PAGE}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return [c["id"] for c in payload[1] if c["region"]["id"] != "NA"]


def fetch_indicator(country_codes: list[str]) -> list[dict]:
    """Fetch indicator data for given countries, all pages.

    Batches country codes to avoid URL-length limits.
    """
    BATCH = 50
    records: list[dict] = []

    for i in range(0, len(country_codes), BATCH):
        batch = country_codes[i : i + BATCH]
        codes_str = ";".join(batch)
        base_url = (
            f"{BASE_API}/country/{codes_str}/indicator/{INDICATOR}"
            f"?date={YEAR_MIN}:{YEAR_MAX}&format=json&per_page={PER_PAGE}"
        )
        page = 1
        total_pages = 1
        while page <= total_pages:
            url = f"{base_url}&page={page}"
            print(f"  Batch {i // BATCH + 1}, page {page}/{total_pages} ...")
            with urllib.request.urlopen(url, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            total_pages = payload[0]["pages"]
            data = payload[1] if len(payload) > 1 and payload[1] else []
            records.extend(data)
            page += 1

    return records


def parse_records(records: list[dict]) -> list[dict]:
    """Parse API records into flat rows, dropping nulls."""
    rows: list[dict] = []
    for r in records:
        val = r.get("value")
        if val is None:
            continue
        rows.append({
            "iso_a3": r["countryiso3code"],
            "country_name": r["country"]["value"],
            "year": int(r["date"]),
            "gdp_pcap_current_usd": round(float(val), 2),
        })
    return rows


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Download World Bank GDP per capita panel"
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTDIR,
        help="Output directory",
    )
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    print("Fetching country list ...")
    country_codes = fetch_country_codes()
    print(f"  {len(country_codes)} countries (excluding aggregates)")

    print(f"Downloading WDI indicator {INDICATOR} ({YEAR_MIN}-{YEAR_MAX}) ...")
    records = fetch_indicator(country_codes)
    print(f"  Raw records: {len(records)}")

    rows = parse_records(records)
    rows.sort(key=lambda r: (r["iso_a3"], r["year"]))
    print(f"  Parsed rows (country-year, non-null): {len(rows)}")

    countries = {r["iso_a3"] for r in rows}
    years = {r["year"] for r in rows}
    print(f"  Countries: {len(countries)}, Years: {min(years)}-{max(years)}")

    outpath = args.outdir / "worldbank_gdp_pcap_panel.csv"
    with open(outpath, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["iso_a3", "country_name", "year", "gdp_pcap_current_usd"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Written: {outpath} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
