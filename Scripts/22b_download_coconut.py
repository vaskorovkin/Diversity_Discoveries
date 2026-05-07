#!/usr/bin/env python3
"""Download the COCONUT 2.0 natural-products CSV export.

Source: https://coconut.naturalproducts.net/download
COCONUT 2.0 (Sorokina et al., NAR 2025) — 695K unique natural-product
structures with organism annotations. CC-BY-4.0.

The full CSV export includes annotation data (organism, geolocations,
literature references) beyond structural descriptors.

Outputs:
  Data/raw/natural_products/coconut/coconut_csv-05-2026.zip
  Data/raw/natural_products/coconut/coconut_download_manifest.csv

Usage:
  python3 Scripts/22b_download_coconut.py
  python3 Scripts/22b_download_coconut.py --force
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "natural_products" / "coconut"

COCONUT_URL = (
    "https://coconut.s3.uni-jena.de/prod/downloads/2026-05/coconut_csv-05-2026.zip"
)
COCONUT_FILENAME = "coconut_csv-05-2026.zip"


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


def validate_zip(path: Path) -> None:
    with path.open("rb") as handle:
        head = handle.read(4)
    if head[:2] != b"PK":
        raise ValueError(f"Not a valid ZIP file (bad magic bytes): {path}")


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
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    output = args.outdir / COCONUT_FILENAME

    if output.exists() and not args.force:
        print(f"Exists, skipping (use --force to re-download): {output}", flush=True)
    else:
        download(COCONUT_URL, output, timeout=args.timeout)

    validate_zip(output)

    row = {
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "coconut",
        "url": COCONUT_URL,
        "local_file": str(output.relative_to(PROJECT_ROOT)),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
    }
    write_manifest(args.outdir / "coconut_download_manifest.csv", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
