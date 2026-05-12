#!/usr/bin/env python3
"""Download the LOTUS Initiative natural-products dataset (Zenodo frozen dump).

Source: Zenodo deposit 10.5281/zenodo.19360665, version v11 (published 2026-04-13),
which is the canonical bulk export of LOTUS data union'd from Wikidata. The
underlying data is CC0 (Wikidata policy); the Zenodo deposit metadata declares
CC-BY-4.0. Cite eLife 70780.

Two files are pulled:

  - 260413_frozen.csv.gz          ~21 MB
        Core triplets: (compound InChIKey, organism Wikidata QID,
        reference Wikidata QID).

  - 260413_frozen_metadata.csv.gz ~90 MB
        Enriched: structural descriptors, NPClassifier / ChemOnt chemical
        classes, biological taxonomy, literature references. This is the
        file used downstream for the species -> compound count map.

Outputs:
  Data/raw/natural_products/lotus/260413_frozen.csv.gz
  Data/raw/natural_products/lotus/260413_frozen_metadata.csv.gz
  Data/raw/natural_products/lotus/lotus_download_manifest.csv

Usage:
  python3 Scripts/download/22_download_lotus.py
  python3 Scripts/download/22_download_lotus.py --force   # re-download even if present
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
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "natural_products" / "lotus"

ZENODO_DOI = "10.5281/zenodo.19360665"
ZENODO_VERSION = "v11"
ZENODO_RECORD_URL = "https://zenodo.org/records/19360665"

# label -> (filename, source URL)
FILES = {
    "frozen": (
        "260413_frozen.csv.gz",
        "https://zenodo.org/records/19360665/files/260413_frozen.csv.gz",
    ),
    "frozen_metadata": (
        "260413_frozen_metadata.csv.gz",
        "https://zenodo.org/records/19360665/files/260413_frozen_metadata.csv.gz",
    ),
}


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
    with urllib.request.urlopen(request, timeout=timeout) as response, part.open("wb") as handle:
        total = int(response.headers.get("Content-Length", 0))
        chunk_size = 1024 * 1024
        next_log = 25 * 1024 * 1024
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
                    print(f"  Downloaded {downloaded / 1024 / 1024:,.0f} MB", flush=True)
                next_log += 25 * 1024 * 1024
    part.replace(output)
    elapsed = max(time.time() - started, 1e-9)
    print(
        f"Done: {output} ({downloaded / 1024 / 1024:,.1f} MB at "
        f"{downloaded / 1024 / 1024 / elapsed:,.1f} MB/s)",
        flush=True,
    )


def validate_gzip(path: Path) -> None:
    """Cheap integrity check: file starts with the gzip magic bytes."""
    with path.open("rb") as handle:
        head = handle.read(2)
    if head != b"\x1f\x8b":
        raise ValueError(f"Not a valid gzip file (bad magic bytes): {path}")


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "downloaded_utc",
        "dataset",
        "label",
        "doi",
        "version",
        "url",
        "local_file",
        "bytes",
        "sha256",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Wrote manifest: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--only",
        choices=sorted(FILES),
        help="Download only one of the labelled files (default: both).",
    )
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    labels = [args.only] if args.only else sorted(FILES)
    rows: list[dict[str, object]] = []
    now = datetime.now(timezone.utc).isoformat()

    for label in labels:
        filename, url = FILES[label]
        output = args.outdir / filename

        if output.exists() and not args.force:
            print(f"Exists, skipping (use --force to re-download): {output}", flush=True)
        else:
            download(url, output, timeout=args.timeout)

        validate_gzip(output)

        rows.append(
            {
                "downloaded_utc": now,
                "dataset": "lotus",
                "label": label,
                "doi": ZENODO_DOI,
                "version": ZENODO_VERSION,
                "url": url,
                "local_file": str(output.relative_to(PROJECT_ROOT)),
                "bytes": output.stat().st_size,
                "sha256": sha256(output),
            }
        )

    write_manifest(args.outdir / "lotus_download_manifest.csv", rows)
    print(f"Zenodo record: {ZENODO_RECORD_URL}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
