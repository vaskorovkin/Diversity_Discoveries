#!/usr/bin/env python3
"""Download ACLED conflict events via API.

Requires a free ACLED account at https://acleddata.com/. Authenticate via the
ACLED dashboard to get a Bearer token (JSON with access_token field, valid 24h).

Pass the token via --token (the access_token string) or --token-file (path to
the JSON response). Downloads year-by-year for progress tracking.

Output: Data/raw/acled/acled_events_2005_2024.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "acled"

API_URL = "https://api.acleddata.com/acled/read"
YEAR_MIN = 2005
YEAR_MAX = 2024
PAGE_SIZE = 5000

OUTPUT_COLS = [
    "event_id_cnty",
    "event_date",
    "year",
    "event_type",
    "sub_event_type",
    "interaction",
    "region",
    "country",
    "iso3",
    "admin1",
    "location",
    "latitude",
    "longitude",
    "geo_precision",
    "fatalities",
]


def fetch_year(token: str, year: int) -> list[dict]:
    """Fetch all ACLED events for a single year, handling pagination."""
    rows: list[dict] = []
    page = 1

    while True:
        params = (
            f"?event_date={year}-01-01|{year}-12-31"
            f"&event_date_where=BETWEEN"
            f"&limit={PAGE_SIZE}&page={page}"
        )
        url = API_URL + params
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"    HTTP {e.code} on page {page} — {e.reason}")
            if e.code == 401:
                print("    Token expired or invalid. Get a new one from ACLED dashboard.")
            if e.code == 403:
                print("    Access denied. Check your ACLED account permissions.")
            raise

        if not payload.get("success", True):
            msg = payload.get("error", {}).get("message", "Unknown error")
            raise RuntimeError(f"ACLED API error: {msg}")

        data = payload.get("data", [])
        if not data:
            break

        rows.extend(data)
        count = payload.get("count", len(rows))
        print(f"    page {page}: {len(data)} events (total so far: {len(rows)}/{count})")

        if len(rows) >= int(count):
            break
        page += 1

    return rows


def resolve_token(args) -> str:
    """Get the access_token string from --token or --token-file."""
    if args.token:
        token = args.token.strip()
        if token.startswith("{"):
            obj = json.loads(token)
            return obj["access_token"]
        return token

    if args.token_file:
        text = args.token_file.read_text().strip()
        if text.startswith("{"):
            obj = json.loads(text)
            return obj["access_token"]
        return text

    raise ValueError("Provide --token or --token-file")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--token", help="ACLED Bearer access_token string")
    group.add_argument("--token-file", type=Path,
                       help="Path to JSON file with access_token")
    parser.add_argument("--start-year", type=int, default=YEAR_MIN)
    parser.add_argument("--end-year", type=int, default=YEAR_MAX)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--between-year-sleep", type=float, default=2.0,
                        help="Seconds between year downloads (default: 2)")
    args = parser.parse_args()

    token = resolve_token(args)
    print(f"Token: ...{token[-20:]}")

    args.outdir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []

    for year in range(args.start_year, args.end_year + 1):
        print(f"Downloading {year} ...", flush=True)
        year_rows = fetch_year(token, year)
        print(f"  {year}: {len(year_rows):,} events", flush=True)
        all_rows.extend(year_rows)

        if year < args.end_year:
            time.sleep(args.between_year_sleep)

    print(f"\nTotal events: {len(all_rows):,}")

    outpath = args.outdir / f"acled_events_{args.start_year}_{args.end_year}.csv"
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Written: {outpath}")

    years_present = sorted({int(r.get("year", 0)) for r in all_rows if r.get("year")})
    countries = {r.get("country") for r in all_rows if r.get("country")}
    fatalities = sum(int(r.get("fatalities", 0)) for r in all_rows)
    print(f"Years: {min(years_present)}-{max(years_present)}")
    print(f"Countries: {len(countries)}")
    print(f"Total fatalities: {fatalities:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
