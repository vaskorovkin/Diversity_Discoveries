#!/usr/bin/env python3
"""Download instructions and verification for IUCN Red List species range maps.

IUCN range maps are the gold standard for baseline species richness. They
require manual download from the IUCN Red List spatial data page (free account).

Download URL:
  https://www.iucnredlist.org/resources/spatial-data-download

Required datasets (shapefile or geodatabase format):
  1. MAMMALS — all assessed mammal species range polygons
  2. AMPHIBIANS — all assessed amphibian species range polygons
  3. REPTILES — all assessed reptile species range polygons (available since 2022)

Birds are maintained separately by BirdLife International:
  4. BIRDS — download from https://datazone.birdlife.org/species/requestdis
     (requires separate BirdLife data request, typically approved for research)

Alternative (if BirdLife request is pending):
  Use mammals + amphibians + reptiles only. These three taxa from IUCN provide
  good global richness coverage and are immediately downloadable.

Expected files after extraction (in Data/raw/iucn_ranges/):
  MAMMALS.shp (+ .shx, .dbf, .prj)     ~600 MB
  AMPHIBIANS.shp (+ .shx, .dbf, .prj)  ~300 MB
  REPTILES.shp (+ .shx, .dbf, .prj)    ~800 MB
  BOTW.gdb (BirdLife, if obtained)      ~5 GB

Also supports IUCN geodatabase format (.gdb) for each taxon.

This script verifies downloads and records metadata.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_DIR = PROJECT_ROOT / "Data" / "raw" / "iucn_ranges"

EXPECTED_TAXA = {
    "MAMMALS": {
        "exts": [".shp", ".gdb"],
        "source": "IUCN Red List",
        "url": "https://www.iucnredlist.org/resources/spatial-data-download",
    },
    "AMPHIBIANS": {
        "exts": [".shp", ".gdb"],
        "source": "IUCN Red List",
        "url": "https://www.iucnredlist.org/resources/spatial-data-download",
    },
    "REPTILES": {
        "exts": [".shp", ".gdb"],
        "source": "IUCN Red List",
        "url": "https://www.iucnredlist.org/resources/spatial-data-download",
    },
    "BOTW": {
        "exts": [".gdb", ".shp"],
        "source": "BirdLife International",
        "url": "https://datazone.birdlife.org/species/requestdis",
    },
}


def find_file(base_dir: Path, taxon: str, exts: list[str]) -> Path | None:
    for ext in exts:
        candidates = list(base_dir.rglob(f"*{taxon}*{ext}"))
        if not candidates:
            candidates = list(base_dir.rglob(f"*{taxon.lower()}*{ext}"))
        if candidates:
            return candidates[0]
    return None


def compute_sha256_partial(path: Path, max_bytes: int = 10_000_000) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        read = 0
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
            read += len(chunk)
            if read >= max_bytes:
                break
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR,
                        help="Directory containing IUCN range downloads")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    args.dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("IUCN Red List / BirdLife Species Range Maps")
    print("=" * 70)
    print()
    print("Manual download required:")
    print()
    print("IUCN (mammals, amphibians, reptiles):")
    print("  1. Register at https://www.iucnredlist.org/ (free)")
    print("  2. Go to https://www.iucnredlist.org/resources/spatial-data-download")
    print("  3. Download each taxonomic group (shapefile or geodatabase)")
    print(f"  4. Extract to: {args.dir}/")
    print()
    print("BirdLife (birds):")
    print("  1. Go to https://datazone.birdlife.org/species/requestdis")
    print("  2. Submit data request (state research purpose)")
    print("  3. Download BOTW (Birds of the World) geodatabase when approved")
    print(f"  4. Place in: {args.dir}/")
    print()

    found = {}
    missing = []

    for taxon, info in EXPECTED_TAXA.items():
        path = find_file(args.dir, taxon, info["exts"])
        if path:
            found[taxon] = path
            size_mb = path.stat().st_size / 1e6
            if path.is_dir():
                import os
                size_mb = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6
            print(f"  {taxon}: FOUND at {path.relative_to(args.dir)} ({size_mb:.0f} MB)")
        else:
            missing.append(taxon)
            print(f"  {taxon}: NOT FOUND (source: {info['source']})")

    print(f"\nFound: {len(found)}/{len(EXPECTED_TAXA)} taxonomic groups")

    if found:
        meta_path = args.dir / "iucn_ranges_download_metadata.txt"
        with open(meta_path, "w") as f:
            for taxon, path in found.items():
                f.write(f"taxon: {taxon}\n")
                f.write(f"path: {path}\n")
                f.write(f"source: {EXPECTED_TAXA[taxon]['source']}\n")
                f.write(f"size_bytes: {path.stat().st_size}\n")
                f.write("\n")
        print(f"\nWrote metadata: {meta_path}")

    if missing:
        print(f"\nMissing taxa: {', '.join(missing)}")
        print("Download and run this script again to verify.")
        if "BOTW" in missing and len(missing) == 1:
            print("\nNote: you can proceed with mammals+amphibians+reptiles only.")
            print("Run: python3 Scripts/aggregate_species_richness_100km.py")
            return 0
        return 1

    print("\nAll taxa found. Run aggregation:")
    print("  python3 Scripts/aggregate_species_richness_100km.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
