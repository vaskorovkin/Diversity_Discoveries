#!/usr/bin/env python3
"""Download instructions and verification for gROADS v1 (Global Roads).

gROADS requires manual download from NASA SEDAC (requires free Earthdata login).

Download URL:
https://sedac.ciesin.columbia.edu/data/set/groads-global-roads-open-access-v1/data-download

Select: "Global Roads Open Access Data Set, v1 (1980 – 2010): Global"
Format: Shapefile (gdb also available but larger)

Expected files after extraction:
- gROADS-v1-global.shp (+ .shx, .dbf, .prj)
- Total size: ~4 GB uncompressed

This script verifies the download and records metadata.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_GROADS_DIR = PROJECT_ROOT / "Data" / "raw" / "groads"
EXPECTED_SHAPEFILE = "gROADS-v1-global.shp"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--groads-dir", type=Path, default=DEFAULT_GROADS_DIR)
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing download.")
    args = parser.parse_args()

    args.groads_dir.mkdir(parents=True, exist_ok=True)

    shapefile = args.groads_dir / EXPECTED_SHAPEFILE

    print("=" * 70)
    print("gROADS v1 (Global Roads Open Access Data Set)")
    print("=" * 70)
    print()
    print("Manual download required from NASA SEDAC:")
    print()
    print("1. Go to: https://sedac.ciesin.columbia.edu/data/set/groads-global-roads-open-access-v1/data-download")
    print()
    print("2. Log in with NASA Earthdata credentials (free registration)")
    print()
    print("3. Select:")
    print("   - Data Set: Global Roads Open Access Data Set, v1 (1980 – 2010)")
    print("   - Geographic Coverage: Global")
    print("   - Format: Shapefile")
    print()
    print("4. Download and extract to:")
    print(f"   {args.groads_dir}/")
    print()
    print(f"Expected file: {shapefile}")
    print()

    if shapefile.exists():
        print("Status: FOUND")
        size_mb = shapefile.stat().st_size / 1e6
        print(f"Size: {size_mb:.1f} MB")

        # Check for companion files
        companions = [".shx", ".dbf", ".prj"]
        missing = [ext for ext in companions if not shapefile.with_suffix(ext).exists()]
        if missing:
            print(f"Warning: missing companion files: {missing}")
        else:
            print("Companion files (.shx, .dbf, .prj): OK")

        # Compute hash
        print("Computing SHA256 (may take a minute)...")
        sha = compute_sha256(shapefile)
        print(f"SHA256: {sha}")

        # Write metadata
        meta_path = args.groads_dir / "groads_download_metadata.txt"
        with open(meta_path, "w") as f:
            f.write(f"source: NASA SEDAC gROADS v1\n")
            f.write(f"url: https://sedac.ciesin.columbia.edu/data/set/groads-global-roads-open-access-v1\n")
            f.write(f"file: {shapefile.name}\n")
            f.write(f"size_bytes: {shapefile.stat().st_size}\n")
            f.write(f"sha256: {sha}\n")
        print(f"Wrote metadata: {meta_path}")

        return 0
    else:
        print("Status: NOT FOUND")
        print()
        print("Please download manually and run this script again to verify.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
