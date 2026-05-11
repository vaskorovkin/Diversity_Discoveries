#!/usr/bin/env python3
"""Download monthly CHIRPS GeoTIFFs for quarterly precipitation panels."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "chirps_monthly"
BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"
DEFAULT_START_YEAR = 1981
DEFAULT_END_YEAR = 2025


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
                        print(
                            f"    {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({pct:.0f}%)",
                            end="\r",
                            flush=True,
                        )
        print(f"    Done: {dest.name} ({downloaded / 1e6:.1f} MB)          ", flush=True)
        return True
    except Exception as exc:
        print(f"    Failed: {exc}", flush=True)
        if dest.exists():
            dest.unlink()
        return False


def gunzip(src: Path, dest: Path) -> None:
    with gzip.open(src, "rb") as fin, open(dest, "wb") as fout:
        shutil.copyfileobj(fin, fout)


def sha256(path: Path) -> str:
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
    parser.add_argument("--keep-gz", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.25)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    failed = []

    print("Downloading CHIRPS monthly precipitation", flush=True)
    print(f"Years: {args.start_year}-{args.end_year}", flush=True)
    print(f"Output: {args.outdir}", flush=True)

    for year in range(args.start_year, args.end_year + 1):
        for month in range(1, 13):
            tif_name = f"chirps-v2.0.{year}.{month:02d}.tif"
            gz_name = f"{tif_name}.gz"
            tif_path = args.outdir / tif_name
            gz_path = args.outdir / gz_name

            if args.skip_existing and tif_path.exists():
                print(f"Skipping (exists): {tif_name}", flush=True)
                manifest_rows.append((year, month, tif_name, str(tif_path), "skipped", ""))
                continue

            print(f"[{year}-{month:02d}]", flush=True)
            ok = download_file(f"{BASE_URL}/{gz_name}", gz_path)
            if not ok:
                failed.append((year, month))
                manifest_rows.append((year, month, tif_name, str(tif_path), "failed", ""))
                continue

            gunzip(gz_path, tif_path)
            if not args.keep_gz:
                gz_path.unlink()
            manifest_rows.append((year, month, tif_name, str(tif_path), "downloaded", sha256(tif_path)))
            time.sleep(args.sleep)

    manifest_path = args.outdir / "chirps_monthly_download_manifest.csv"
    with open(manifest_path, "w") as f:
        f.write("year,month,filename,path,status,sha256\n")
        for row in manifest_rows:
            f.write(",".join(map(str, row)) + "\n")
    print(f"\nWrote manifest: {manifest_path}", flush=True)
    print(f"Failed downloads: {len(failed)}", flush=True)

    if failed:
        for year, month in failed:
            print(f"  {year}-{month:02d}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
