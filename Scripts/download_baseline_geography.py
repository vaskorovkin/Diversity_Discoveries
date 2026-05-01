#!/usr/bin/env python3
"""Download baseline geography inputs used by the BOLD 100 km overlays.

This script fetches the raw, external geography files needed for:

1. RESOLVE 2017 ecoregion / biome / realm overlay.
2. CEPF / Conservation International biodiversity-hotspot overlay.

It intentionally does not download WDPA/Protected Planet because that dataset
requires a separate user download and terms workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
OUTDIR = PROJECT_ROOT / "Data" / "raw" / "baseline_geography"

RESOLVE_URL = "https://storage.googleapis.com/teow2016/Ecoregions2017.zip"
RESOLVE_ZIP = OUTDIR / "resolve_ecoregions" / "Ecoregions2017.zip"
RESOLVE_REQUIRED = [
    OUTDIR / "resolve_ecoregions" / "Ecoregions2017.shp",
    OUTDIR / "resolve_ecoregions" / "Ecoregions2017.dbf",
    OUTDIR / "resolve_ecoregions" / "Ecoregions2017.shx",
    OUTDIR / "resolve_ecoregions" / "Ecoregions2017.prj",
]

CEPF_URL = (
    "https://services.arcgis.com/nzS0F0zdNLvs7nc8/arcgis/rest/services/"
    "Terrestrial_biodiversity_hotspots/FeatureServer/0/query?"
    "where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson"
)
CEPF_GEOJSON = OUTDIR / "cepf_hotspots.geojson"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, output: Path, force: bool, timeout: int) -> bool:
    if output.exists() and not force:
        print(f"exists, skipping: {output}", flush=True)
        return False

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".part")
    if tmp.exists():
        tmp.unlink()

    request = urllib.request.Request(url, headers={"User-Agent": "Diversity_Discoveries/replication"})
    print(f"Downloading: {url}", flush=True)
    print(f"To: {output}", flush=True)
    start = time.time()
    downloaded = 0
    with urllib.request.urlopen(request, timeout=timeout) as response, tmp.open("wb") as f:
        shutil.copyfileobj(response, f, length=1024 * 1024)
        downloaded = tmp.stat().st_size
    tmp.replace(output)
    elapsed = max(time.time() - start, 1e-9)
    print(f"Downloaded {downloaded / 1024 / 1024:,.1f} MB ({downloaded / 1024 / 1024 / elapsed:,.1f} MB/s)", flush=True)
    return True


def write_metadata(path: Path, records: list[dict[str, object]]) -> None:
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Wrote metadata: {path}", flush=True)


def resolve_record() -> dict[str, object]:
    return {
        "dataset": "RESOLVE Ecoregions 2017",
        "source_url": RESOLVE_URL,
        "local_file": str(RESOLVE_ZIP.relative_to(PROJECT_ROOT)),
        "sha256": sha256(RESOLVE_ZIP),
        "bytes": RESOLVE_ZIP.stat().st_size,
        "extracted_files": [str(p.relative_to(PROJECT_ROOT)) for p in RESOLVE_REQUIRED if p.exists()],
        "notes": "Global terrestrial ecoregions, biomes, realms, and NNH fields; CC-BY 4.0.",
    }


def cepf_record() -> dict[str, object]:
    return {
        "dataset": "CEPF / Conservation International Biodiversity Hotspots",
        "source_url": CEPF_URL,
        "local_file": str(CEPF_GEOJSON.relative_to(PROJECT_ROOT)),
        "sha256": sha256(CEPF_GEOJSON),
        "bytes": CEPF_GEOJSON.stat().st_size,
        "notes": "GeoJSON query from public ArcGIS FeatureServer; 36 terrestrial biodiversity hotspots.",
    }


def download_resolve(force: bool, timeout: int) -> None:
    download(RESOLVE_URL, RESOLVE_ZIP, force=force, timeout=timeout)
    missing = [p for p in RESOLVE_REQUIRED if not p.exists()]
    if missing or force:
        print(f"Extracting: {RESOLVE_ZIP}", flush=True)
        with zipfile.ZipFile(RESOLVE_ZIP) as zf:
            zf.extractall(RESOLVE_ZIP.parent)
    missing = [p for p in RESOLVE_REQUIRED if not p.exists()]
    if missing:
        raise FileNotFoundError("RESOLVE zip did not produce required files: " + ", ".join(str(p) for p in missing))


def download_cepf(force: bool, timeout: int) -> None:
    download(CEPF_URL, CEPF_GEOJSON, force=force, timeout=timeout)
    text = CEPF_GEOJSON.read_text(errors="replace")
    if '"FeatureCollection"' not in text:
        raise ValueError(f"CEPF download does not look like GeoJSON: {CEPF_GEOJSON}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=["all", "resolve", "cepf"],
        default="all",
        help="Dataset to download.",
    )
    parser.add_argument("--force", action="store_true", help="Re-download even when local files exist.")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=OUTDIR / "baseline_geography_download_metadata.json",
    )
    args = parser.parse_args()

    records: list[dict[str, object]] = []
    if args.only in {"all", "resolve"}:
        download_resolve(force=args.force, timeout=args.timeout)
        records.append(resolve_record())
    if args.only in {"all", "cepf"}:
        download_cepf(force=args.force, timeout=args.timeout)
        records.append(cepf_record())

    write_metadata(args.metadata, records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
