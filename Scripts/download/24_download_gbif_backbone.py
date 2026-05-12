#!/usr/bin/env python3
"""Download the GBIF Backbone Taxonomy (Darwin Core Archive).

Source: https://hosted-datasets.gbif.org/datasets/backbone/current/
GBIF Backbone Taxonomy — ~10M names with synonym→accepted mappings,
incorporating WCVP (plants), Index Fungorum (fungi), Catalogue of Life.
No authentication required.

The zip contains a Darwin Core Archive with Taxon.tsv as the main file
(tab-separated: taxonID, acceptedNameUsageID, canonicalName,
taxonomicStatus, kingdom, genus, specificEpithet, etc.).

Outputs:
  Data/raw/gbif/backbone/backbone.zip   (~926 MB)
  Data/raw/gbif/backbone/gbif_backbone_download_manifest.csv

Usage:
  python3 Scripts/download/24_download_gbif_backbone.py
  python3 Scripts/download/24_download_gbif_backbone.py --force
"""


from __future__ import annotations


from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
for _path in (SCRIPTS_ROOT / "_shared", SCRIPTS_ROOT / "download"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import argparse
import csv
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "gbif" / "backbone"

BACKBONE_URL = (
    "https://hosted-datasets.gbif.org/datasets/backbone/current/backbone.zip"
)
BACKBONE_FILENAME = "backbone.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, output: Path, timeout: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_suffix(output.suffix + ".part")
    if part.exists():
        part.unlink()

    print(f"Downloading: {url}", flush=True)
    print(f"To: {output}", flush=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "Diversity_Discoveries/replication"}
    )
    downloaded = 0
    started = time.time()
    with urllib.request.urlopen(request, timeout=timeout) as response, part.open(
        "wb"
    ) as handle:
        total = int(response.headers.get("Content-Length", 0))
        chunk_size = 1024 * 1024
        next_log = 50 * 1024 * 1024
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if downloaded >= next_log:
                if total > 0:
                    pct = 100 * downloaded / total
                    print(
                        f"  Downloaded {downloaded / 1024 / 1024:,.0f} MB ({pct:.1f}%)",
                        flush=True,
                    )
                else:
                    print(
                        f"  Downloaded {downloaded / 1024 / 1024:,.0f} MB",
                        flush=True,
                    )
                next_log += 50 * 1024 * 1024
    part.replace(output)
    elapsed = max(time.time() - started, 1e-9)
    print(
        f"Done: {output} ({downloaded / 1024 / 1024:,.1f} MB at "
        f"{downloaded / 1024 / 1024 / elapsed:,.1f} MB/s)",
        flush=True,
    )


def validate_zip(path: Path) -> None:
    with path.open("rb") as handle:
        head = handle.read(4)
    if head[:2] != b"PK":
        raise ValueError(f"Not a valid ZIP file (bad magic bytes): {path}")


def preview_contents(path: Path) -> None:
    import zipfile

    with zipfile.ZipFile(path) as zf:
        print("\nArchive contents:", flush=True)
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            size_mb = info.file_size / 1024 / 1024
            print(f"  {info.filename:<40s} {size_mb:>10,.1f} MB", flush=True)


def write_manifest(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "downloaded_utc",
        "dataset",
        "url",
        "local_file",
        "bytes",
        "sha256",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
    print(f"Wrote manifest: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    output = args.outdir / BACKBONE_FILENAME

    if output.exists() and not args.force:
        print(
            f"Exists, skipping (use --force to re-download): {output}",
            flush=True,
        )
    else:
        download(BACKBONE_URL, output, timeout=args.timeout)

    validate_zip(output)
    preview_contents(output)

    row = {
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "gbif_backbone",
        "url": BACKBONE_URL,
        "local_file": str(output.relative_to(PROJECT_ROOT)),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
    }
    write_manifest(args.outdir / "gbif_backbone_download_manifest.csv", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
