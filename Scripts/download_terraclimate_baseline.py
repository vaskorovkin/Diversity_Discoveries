#!/usr/bin/env python3
"""Download TerraClimate baseline years (1981-2000) for proper anomaly calculation.

This supplements the main download_terraclimate.py which downloads 2001-2023.
Together they provide 1981-2023 for a proper 1981-2010 baseline climatology.
"""

from __future__ import annotations

import argparse
import hashlib
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "terraclimate"

BASE_URL = "https://climate.northwestknowledge.net/TERRACLIMATE-DATA"
VARIABLES = ["PDSI", "tmax", "ppt"]

# Baseline years not covered by main download
BASELINE_START = 1981
BASELINE_END = 2000


def download_file(url: str, dest: Path, timeout: int = 300) -> bool:
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
    parser.add_argument("--start-year", type=int, default=BASELINE_START)
    parser.add_argument("--end-year", type=int, default=BASELINE_END)
    parser.add_argument("--variables", nargs="+", default=VARIABLES)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--sleep", type=float, default=2.0)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    years = list(range(args.start_year, args.end_year + 1))
    print(f"Downloading TerraClimate BASELINE years: {args.variables}", flush=True)
    print(f"Years: {years[0]}-{years[-1]} (for 1981-2010 climatology)", flush=True)
    print(f"Output: {args.outdir}", flush=True)

    manifest_rows = []
    failed = []

    for var in args.variables:
        var_dir = args.outdir / var.lower()
        var_dir.mkdir(exist_ok=True)

        for year in years:
            filename = f"TerraClimate_{var}_{year}.nc"
            url = f"{BASE_URL}/{filename}"
            dest = var_dir / filename

            if args.skip_existing and dest.exists():
                print(f"Skipping (exists): {filename}", flush=True)
                manifest_rows.append({
                    "variable": var,
                    "year": year,
                    "filename": filename,
                    "status": "skipped",
                })
                continue

            print(f"[{var} {year}]", flush=True)
            success = download_file(url, dest)

            if success:
                manifest_rows.append({
                    "variable": var,
                    "year": year,
                    "filename": filename,
                    "status": "downloaded",
                })
            else:
                failed.append((var, year))
                manifest_rows.append({
                    "variable": var,
                    "year": year,
                    "filename": filename,
                    "status": "failed",
                })

            time.sleep(args.sleep)

    # Append to existing manifest
    manifest_path = args.outdir / "terraclimate_baseline_manifest.csv"
    with open(manifest_path, "w") as f:
        f.write("variable,year,filename,status\n")
        for row in manifest_rows:
            f.write(f"{row['variable']},{row['year']},{row['filename']},{row['status']}\n")
    print(f"\nWrote manifest: {manifest_path}", flush=True)

    print(f"\nSummary:", flush=True)
    print(f"  Variables: {len(args.variables)}", flush=True)
    print(f"  Years: {len(years)}", flush=True)
    print(f"  Total files: {len(args.variables) * len(years)}", flush=True)
    print(f"  Failed: {len(failed)}", flush=True)

    if failed:
        print(f"\nFailed downloads:", flush=True)
        for var, year in failed:
            print(f"  {var} {year}", flush=True)
        return 1

    print(f"\nNow run: python3 Scripts/aggregate_terraclimate_100km.py", flush=True)
    print(f"It will use 1981-2010 for baseline climatology.", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
