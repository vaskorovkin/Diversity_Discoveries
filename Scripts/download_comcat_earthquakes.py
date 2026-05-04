#!/usr/bin/env python3
"""Download global earthquake events from the USGS ComCat/FDSN event service.

Defaults:
  - eventtype=earthquake
  - 2005-2025
  - min magnitude 4.5
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "comcat"
BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query.csv"
DEFAULT_START_YEAR = 2005
DEFAULT_END_YEAR = 2025
DEFAULT_MIN_MAG = 4.5
DEFAULT_LIMIT = 20_000

OUTPUT_COLS = [
    "time",
    "latitude",
    "longitude",
    "depth",
    "mag",
    "magType",
    "nst",
    "gap",
    "dmin",
    "rms",
    "net",
    "id",
    "updated",
    "place",
    "type",
    "horizontalError",
    "depthError",
    "magError",
    "magNst",
    "status",
    "locationSource",
    "magSource",
]


def slug_mag(value: float) -> str:
    return str(value).replace(".", "p")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_page(year: int, offset: int, limit: int, min_magnitude: float, timeout: int) -> list[dict[str, str]]:
    params = {
        "starttime": f"{year}-01-01",
        "endtime": f"{year}-12-31",
        "eventtype": "earthquake",
        "minmagnitude": f"{min_magnitude:g}",
        "orderby": "time-asc",
        "limit": str(limit),
        "offset": str(offset),
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "Diversity_Discoveries/replication"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def write_manifest(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "downloaded_utc",
                "start_year",
                "end_year",
                "min_magnitude",
                "local_file",
                "bytes",
                "sha256",
            ],
        )
        writer.writeheader()
        writer.writerow(row)
    print(f"Wrote manifest: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--min-magnitude", type=float, default=DEFAULT_MIN_MAG)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--between-page-sleep", type=float, default=0.5)
    parser.add_argument("--between-year-sleep", type=float, default=1.0)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"comcat_earthquakes_{args.start_year}_{args.end_year}_"
        f"m{slug_mag(args.min_magnitude)}"
    )
    output = args.outdir / f"{stem}.csv"

    all_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for year in range(args.start_year, args.end_year + 1):
        print(f"Downloading {year} ...", flush=True)
        page = 1
        offset = 1
        kept_year_rows = 0
        while True:
            rows = fetch_page(
                year=year,
                offset=offset,
                limit=args.limit,
                min_magnitude=args.min_magnitude,
                timeout=args.timeout,
            )
            n_rows = len(rows)
            print(f"  year {year} page {page}: {n_rows:,} rows", flush=True)
            if not rows:
                break
            for row in rows:
                quake_id = row.get("id", "")
                if quake_id and quake_id in seen_ids:
                    continue
                if quake_id:
                    seen_ids.add(quake_id)
                all_rows.append(row)
                kept_year_rows += 1
            if n_rows < args.limit:
                break
            page += 1
            offset += args.limit
            time.sleep(args.between_page_sleep)
        print(f"  {year}: kept {kept_year_rows:,} rows", flush=True)
        if year < args.end_year:
            time.sleep(args.between_year_sleep)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Written: {output}", flush=True)

    row = {
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "min_magnitude": args.min_magnitude,
        "local_file": str(output.relative_to(PROJECT_ROOT)),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
    }
    write_manifest(args.outdir / "comcat_download_manifest.csv", row)
    print(f"Total rows: {len(all_rows):,}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
