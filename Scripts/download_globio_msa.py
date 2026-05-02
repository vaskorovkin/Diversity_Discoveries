#!/usr/bin/env python3
"""Download GLOBIO4 MSA (Mean Species Abundance) rasters.

GLOBIO4 MSA represents local terrestrial biodiversity intactness (0-1 scale).
Available for overall, plants, and warm-blooded vertebrates (birds+mammals).

Source: PBL Netherlands, Schipper et al. (2020)
Resolution: 10 arcseconds (~300m)
Year: 2015 baseline
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "globio"

BASE_URL = "https://dataportaal.pbl.nl/downloads/GLOBIO/Schipper_etal_2020/2015"

MSA_FILES = {
    "overall": {
        "filename": "Globio4_TerrestrialMSA_10sec_2015.zip",
        "size_mb": 6000,
        "description": "Overall MSA (all taxa)",
    },
    "plants": {
        "filename": "Globio4_TerrestrialMSA_plants_10sec_2015.zip",
        "size_mb": 900,
        "description": "Plants MSA only",
    },
    "vertebrates": {
        "filename": "Globio4_TerrestrialMSA_wbvert_10sec_2015.zip",
        "size_mb": 6000,
        "description": "Warm-blooded vertebrates (birds + mammals)",
    },
}


def download_file(url: str, dest: Path, timeout: int = 600) -> bool:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--types", nargs="+", default=["plants"],
                        choices=list(MSA_FILES.keys()),
                        help="MSA types to download. Default: plants only (~900MB). Use 'overall' for full MSA (~6GB).")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-extract", action="store_true", help="Skip extraction after download.")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    print("GLOBIO4 MSA (Mean Species Abundance) Download", flush=True)
    print(f"Output: {args.outdir}", flush=True)
    print(f"Types: {args.types}", flush=True)
    print()

    for msa_type in args.types:
        info = MSA_FILES[msa_type]
        filename = info["filename"]
        url = f"{BASE_URL}/{filename}"
        dest_zip = args.outdir / filename

        print(f"[{msa_type}] {info['description']} (~{info['size_mb']} MB)", flush=True)

        # Check for extracted file
        tif_name = filename.replace(".zip", ".tif")
        dest_tif = args.outdir / tif_name

        if args.skip_existing and (dest_tif.exists() or dest_zip.exists()):
            print(f"  Skipping (exists)", flush=True)
            continue

        if not download_file(url, dest_zip):
            return 1

        if not args.no_extract:
            print(f"  Extracting...", flush=True)
            try:
                with zipfile.ZipFile(dest_zip, "r") as zf:
                    zf.extractall(args.outdir)
                # Find extracted tif
                extracted = list(args.outdir.glob("*.tif"))
                print(f"  Extracted: {[f.name for f in extracted]}", flush=True)
            except Exception as e:
                print(f"  Extract failed: {e}", flush=True)
                return 1

    # Write metadata
    meta_path = args.outdir / "globio_download_metadata.txt"
    with open(meta_path, "w") as f:
        f.write("source: PBL GLOBIO4 (Schipper et al. 2020)\n")
        f.write("url: https://www.globio.info/globio-data-downloads\n")
        f.write("resolution: 10 arcseconds (~300m)\n")
        f.write("year: 2015\n")
        f.write("units: Mean Species Abundance (0-1 scale, 1 = pristine)\n")
        f.write(f"downloaded_types: {args.types}\n")
    print(f"\nWrote metadata: {meta_path}", flush=True)

    print(f"\nDone. Now run: python3 Scripts/aggregate_globio_msa_100km.py", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
