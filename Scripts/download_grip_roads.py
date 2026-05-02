#!/usr/bin/env python3
"""Download GRIP4 road density rasters.

GRIP4: Global Roads Inventory Project, version 4.
Pre-computed road density at 5 arcminutes (~8km) resolution.
Source: PBL Netherlands Environmental Assessment Agency.

Downloads the total road density raster (all road types combined).
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "grip"

# GRIP4 raster download URLs
BASE_URL = "https://dataportaal.pbl.nl/data/GRIP4"
RASTER_FILES = {
    "total": "GRIP4_density_total.zip",
    "highways": "GRIP4_density_tp1.zip",
    "primary": "GRIP4_density_tp2.zip",
    "secondary": "GRIP4_density_tp3.zip",
    "tertiary": "GRIP4_density_tp4.zip",
    "local": "GRIP4_density_tp5.zip",
}


def download_file(url: str, dest: Path, timeout: int = 120) -> bool:
    """Download a file."""
    try:
        print(f"  Downloading: {url}", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length", 0))
            with open(dest, "wb") as f:
                downloaded = 0
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        print(f"    {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB", end="\r", flush=True)
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
    parser.add_argument("--types", nargs="+", default=["total"],
                        choices=list(RASTER_FILES.keys()),
                        help="Road types to download. Default: total only.")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    print("GRIP4 Road Density Rasters", flush=True)
    print(f"Output: {args.outdir}", flush=True)
    print(f"Types: {args.types}", flush=True)
    print()

    downloaded = []
    failed = []

    for road_type in args.types:
        filename = RASTER_FILES[road_type]
        url = f"{BASE_URL}/{filename}"
        dest_zip = args.outdir / filename

        # Check for extracted file (may have different name inside zip)
        asc_name = filename.replace(".zip", ".asc")
        dest_asc = args.outdir / asc_name
        # Also check for files already extracted with any name
        existing_asc = list(args.outdir.glob(f"*{road_type}*.asc"))
        if existing_asc:
            dest_asc = existing_asc[0]

        if args.skip_existing and dest_asc.exists():
            print(f"Skipping (exists): {asc_name}", flush=True)
            downloaded.append(road_type)
            continue

        print(f"[{road_type}]", flush=True)

        if not download_file(url, dest_zip):
            failed.append(road_type)
            continue

        # Extract
        print(f"  Extracting...", flush=True)
        try:
            with zipfile.ZipFile(dest_zip, "r") as zf:
                zf.extractall(args.outdir)
            print(f"  Extracted: {asc_name}", flush=True)
            # Remove zip to save space
            dest_zip.unlink()
            downloaded.append(road_type)
        except Exception as e:
            print(f"  Extract failed: {e}", flush=True)
            failed.append(road_type)

    # Write metadata
    meta_path = args.outdir / "grip_download_metadata.txt"
    with open(meta_path, "w") as f:
        f.write("source: PBL GRIP4 (Global Roads Inventory Project)\n")
        f.write("url: https://www.globio.info/download-grip-dataset\n")
        f.write("resolution: 5 arcminutes (~8km)\n")
        f.write("units: meters of road per square kilometer\n")
        f.write(f"downloaded_types: {downloaded}\n")
    print(f"\nWrote metadata: {meta_path}", flush=True)

    print(f"\nSummary:", flush=True)
    print(f"  Downloaded: {len(downloaded)}", flush=True)
    print(f"  Failed: {len(failed)}", flush=True)

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
