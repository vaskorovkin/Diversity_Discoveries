#!/usr/bin/env python3
"""Download NOAA IBTrACS tropical-cyclone track data.

Default download is the official "since1980" CSV from NOAA/NCEI IBTrACS v04r01.

Outputs:
  Data/raw/ibtracs/ibtracs_since1980_list_v04r01.csv
  Data/raw/ibtracs/ibtracs_download_manifest.csv
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
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "ibtracs"

VERSION = "v04r01"
DATASET_URLS = {
    "since1980": (
        "https://www.ncei.noaa.gov/data/"
        "international-best-track-archive-for-climate-stewardship-ibtracs/"
        f"{VERSION}/access/csv/ibtracs.since1980.list.{VERSION}.csv"
    ),
    "all": (
        "https://www.ncei.noaa.gov/data/"
        "international-best-track-archive-for-climate-stewardship-ibtracs/"
        f"{VERSION}/access/csv/ibtracs.ALL.list.{VERSION}.csv"
    ),
    "last3years": (
        "https://www.ncei.noaa.gov/data/"
        "international-best-track-archive-for-climate-stewardship-ibtracs/"
        f"{VERSION}/access/csv/ibtracs.last3years.list.{VERSION}.csv"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_stem(dataset: str) -> str:
    return f"ibtracs_{dataset}_list_{VERSION}"


def download(url: str, output: Path, timeout: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_suffix(output.suffix + ".part")
    if part.exists():
        part.unlink()

    print(f"Downloading: {url}", flush=True)
    print(f"To: {output}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Diversity_Discoveries/replication"})
    downloaded = 0
    started = time.time()
    with urllib.request.urlopen(request, timeout=timeout) as response, part.open("wb") as handle:
        total = int(response.headers.get("Content-Length", 0))
        chunk_size = 1024 * 1024
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if downloaded % (25 * 1024 * 1024) < chunk_size:
                if total > 0:
                    pct = 100 * downloaded / total
                    print(f"Downloaded {downloaded / 1024 / 1024:,.0f} MB ({pct:.1f}%)", flush=True)
                else:
                    print(f"Downloaded {downloaded / 1024 / 1024:,.0f} MB", flush=True)
    part.replace(output)
    elapsed = max(time.time() - started, 1e-9)
    print(
        f"Done: {output} ({downloaded / 1024 / 1024:,.1f} MB at "
        f"{downloaded / 1024 / 1024 / elapsed:,.1f} MB/s)",
        flush=True,
    )


def validate_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        header = handle.readline().strip()
        units = handle.readline().strip()
    if not header.startswith("SID,SEASON,NUMBER,BASIN"):
        raise ValueError(f"Unexpected IBTrACS header in {path}")
    if "degrees_north" not in units:
        raise ValueError(f"Unexpected IBTrACS units row in {path}")


def write_manifest(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "downloaded_utc",
                "dataset",
                "url",
                "local_file",
                "bytes",
                "sha256",
            ],
        )
        writer.writeheader()
        writer.writerow(row)
    print(f"Wrote manifest: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASET_URLS), default="since1980")
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = dataset_stem(args.dataset)
    output = args.outdir / f"{stem}.csv"

    if output.exists() and not args.force:
        print(f"Output exists, skipping: {output}", flush=True)
    else:
        download(DATASET_URLS[args.dataset], output, timeout=args.timeout)

    validate_csv(output)

    row = {
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "url": DATASET_URLS[args.dataset],
        "local_file": str(output.relative_to(PROJECT_ROOT)),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
    }
    write_manifest(args.outdir / "ibtracs_download_manifest.csv", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
