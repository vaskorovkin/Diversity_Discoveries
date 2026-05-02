#!/usr/bin/env python3
"""Download CHIRPS precipitation data for climate anomaly regressors.

Downloads annual precipitation totals from CHIRPS (Climate Hazards Group
InfraRed Precipitation with Station data).

CHIRPS: ~5km (0.05°) resolution, quasi-global (50°S-50°N), 1981-present.
Source: UCSB Climate Hazards Center via direct download.
"""

from __future__ import annotations

import argparse
import hashlib
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "chirps"

# CHIRPS annual data URL (GeoTIFF format)
# Annual totals are easier to work with than daily/monthly
BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_annual/tifs"

DEFAULT_START_YEAR = 1981  # For baseline climatology
DEFAULT_END_YEAR = 2023


def download_file(url: str, dest: Path, timeout: int = 300) -> bool:
    """Download a file with progress indication."""
    try:
        print(f"  Downloading: {url}", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = 100 * downloaded / total
                        print(f"    {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({pct:.0f}%)", end="\r", flush=True)

            print(f"    Done: {dest.name} ({downloaded / 1e6:.1f} MB)          ", flush=True)
        return True
    except Exception as e:
        print(f"    Failed: {e}", flush=True)
        if dest.exists():
            dest.unlink()
        return False


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    years = list(range(args.start_year, args.end_year + 1))
    print(f"Downloading CHIRPS annual precipitation", flush=True)
    print(f"Years: {years[0]}-{years[-1]}", flush=True)
    print(f"Output: {args.outdir}", flush=True)

    manifest_rows = []
    failed = []

    for year in years:
        # CHIRPS annual file naming: chirps-v2.0.2020.tif
        filename = f"chirps-v2.0.{year}.tif"
        url = f"{BASE_URL}/{filename}"
        dest = args.outdir / filename

        if args.skip_existing and dest.exists():
            print(f"Skipping (exists): {filename}", flush=True)
            manifest_rows.append({
                "year": year,
                "filename": filename,
                "path": str(dest),
                "status": "skipped",
                "sha256": "",
            })
            continue

        print(f"[{year}]", flush=True)
        success = download_file(url, dest)

        if success:
            sha = compute_sha256(dest)
            manifest_rows.append({
                "year": year,
                "filename": filename,
                "path": str(dest),
                "status": "downloaded",
                "sha256": sha,
            })
        else:
            failed.append(year)
            manifest_rows.append({
                "year": year,
                "filename": filename,
                "path": str(dest),
                "status": "failed",
                "sha256": "",
            })

        time.sleep(args.sleep)

    # Write manifest
    manifest_path = args.outdir / "chirps_download_manifest.csv"
    with open(manifest_path, "w") as f:
        f.write("year,filename,path,status,sha256\n")
        for row in manifest_rows:
            f.write(f"{row['year']},{row['filename']},{row['path']},{row['status']},{row['sha256']}\n")
    print(f"\nWrote manifest: {manifest_path}", flush=True)

    print(f"\nSummary:", flush=True)
    print(f"  Years: {len(years)}", flush=True)
    print(f"  Failed: {len(failed)}", flush=True)

    if failed:
        print(f"\nFailed downloads:", flush=True)
        for year in failed:
            print(f"  {year}", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
