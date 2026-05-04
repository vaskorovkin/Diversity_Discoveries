#!/usr/bin/env python3
"""Submit GBIF plant download requests and optionally poll/download them.

Creates two GBIF Darwin Core Archive requests:
1. Plantae preserved/material records with coordinates, years 2005-2025
2. Plantae human observations with coordinates, years 2005-2025

GBIF authentication uses your GBIF username and password, not an API key.

Typical usage:
    python3 Scripts/request_gbif_plantae_downloads.py \
        --gbif-username YOUR_USERNAME \
        --gbif-password-file /path/to/gbif_password.txt \
        --notification-email YOU@example.com

Submit only, no polling:
    python3 Scripts/request_gbif_plantae_downloads.py \
        --gbif-username YOUR_USERNAME \
        --gbif-password-file /path/to/gbif_password.txt \
        --notification-email YOU@example.com \
        --submit-only
"""

from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_OUTDIR = PROJECT_ROOT / "Data" / "raw" / "gbif" / "plantae"
GBIF_REQUEST_URL = "https://api.gbif.org/v1/occurrence/download/request"
GBIF_STATUS_URL = "https://api.gbif.org/v1/occurrence/download"
PLANTAE_TAXON_KEY = "6"


def build_preserved_predicate(start_year: int, end_year: int) -> dict:
    return {
        "type": "and",
        "predicates": [
            {"type": "equals", "key": "TAXON_KEY", "value": PLANTAE_TAXON_KEY},
            {"type": "equals", "key": "HAS_COORDINATE", "value": "true"},
            {"type": "greaterThanOrEquals", "key": "YEAR", "value": str(start_year)},
            {"type": "lessThanOrEquals", "key": "YEAR", "value": str(end_year)},
            {
                "type": "in",
                "key": "BASIS_OF_RECORD",
                "values": ["PRESERVED_SPECIMEN", "MATERIAL_SAMPLE"],
            },
        ],
    }


def build_human_observation_predicate(start_year: int, end_year: int) -> dict:
    return {
        "type": "and",
        "predicates": [
            {"type": "equals", "key": "TAXON_KEY", "value": PLANTAE_TAXON_KEY},
            {"type": "equals", "key": "HAS_COORDINATE", "value": "true"},
            {"type": "greaterThanOrEquals", "key": "YEAR", "value": str(start_year)},
            {"type": "lessThanOrEquals", "key": "YEAR", "value": str(end_year)},
            {"type": "equals", "key": "BASIS_OF_RECORD", "value": "HUMAN_OBSERVATION"},
        ],
    }


def build_request_payload(
    creator: str,
    notification_email: str,
    predicate: dict,
) -> dict:
    return {
        "creator": creator,
        "notificationAddresses": [notification_email],
        "sendNotification": True,
        "format": "DWCA",
        "predicate": predicate,
    }


def auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def post_download_request(username: str, password: str, payload: dict) -> str:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(GBIF_REQUEST_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", auth_header(username, password))
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8").strip()


def fetch_status(download_key: str) -> dict:
    url = f"{GBIF_STATUS_URL}/{download_key}"
    with urllib.request.urlopen(url, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_zip(download_key: str, outpath: Path) -> None:
    url = f"https://api.gbif.org/v1/occurrence/download/request/{download_key}.zip"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=600) as resp, outpath.open("wb") as handle:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def stem_for(kind: str, start_year: int, end_year: int) -> str:
    return f"gbif_plantae_{kind}_dwca_{start_year}_{end_year}"


def resolve_password(password: str | None, password_file: Path | None) -> str:
    if password_file is not None:
        return password_file.read_text(encoding="utf-8").strip()
    if password is not None:
        return password
    raise ValueError("Provide --gbif-password or --gbif-password-file")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gbif-username", required=True, help="GBIF username, not email.")
    parser.add_argument("--gbif-password", default=None, help="GBIF password.")
    parser.add_argument("--gbif-password-file", type=Path, default=None, help="Text file containing only the GBIF password.")
    parser.add_argument("--notification-email", required=True, help="Email for GBIF completion notice.")
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--submit-only", action="store_true", help="Submit requests and stop.")
    parser.add_argument("--poll-interval", type=int, default=120, help="Seconds between GBIF status checks.")
    parser.add_argument("--max-polls", type=int, default=180, help="Maximum number of poll attempts per request.")
    args = parser.parse_args()
    password = resolve_password(args.gbif_password, args.gbif_password_file)

    args.outdir.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("preserved_material", build_preserved_predicate(args.start_year, args.end_year)),
        ("human_observation", build_human_observation_predicate(args.start_year, args.end_year)),
    ]

    submitted: list[tuple[str, str, Path]] = []

    for kind, predicate in jobs:
        stem = stem_for(kind, args.start_year, args.end_year)
        payload = build_request_payload(args.gbif_username, args.notification_email, predicate)
        json_path = args.outdir / f"{stem}_request.json"
        write_json(json_path, payload)
        print(f"Wrote request JSON: {json_path}", flush=True)
        print(f"Submitting GBIF request: {kind}", flush=True)
        try:
            key = post_download_request(args.gbif_username, password, payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GBIF request failed for {kind}: HTTP {exc.code} {exc.reason}\n{body}") from exc
        print(f"  download key: {key}", flush=True)
        key_path = args.outdir / f"{stem}_download_key.txt"
        key_path.write_text(key + "\n", encoding="utf-8")
        submitted.append((kind, key, args.outdir / f"{stem}.zip"))

    if args.submit_only:
        print("Submitted both requests. Use the download keys or your email to fetch results later.", flush=True)
        return 0

    for kind, key, zip_path in submitted:
        print(f"\nPolling GBIF request: {kind} ({key})", flush=True)
        status = None
        for attempt in range(1, args.max_polls + 1):
            status = fetch_status(key)
            state = status.get("status", "")
            print(f"  poll {attempt}: {state}", flush=True)
            if state == "SUCCEEDED":
                break
            if state in {"KILLED", "CANCELLED", "FAILED"}:
                raise RuntimeError(f"GBIF download {key} ended with status {state}")
            time.sleep(args.poll_interval)

        if not status or status.get("status") != "SUCCEEDED":
            raise RuntimeError(f"GBIF download {key} did not succeed within polling limit")

        print(f"Downloading ZIP to: {zip_path}", flush=True)
        download_zip(key, zip_path)
        print(f"  wrote: {zip_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
