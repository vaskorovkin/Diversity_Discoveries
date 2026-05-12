#!/usr/bin/env python3
"""Link GBIF Plantae dataset keys to GBIF Literature API records.

Input:
    Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv

Cache:
    Data/processed/discovery/publications/gbif_literature_cache.db

Output:
    Data/processed/discovery/publications/gbif_dataset_to_pubs.csv

API endpoint:
    https://api.gbif.org/v1/literature/search?gbifDatasetKey=<dataset_key>

Important caveat:
    This is dataset-level attribution. GBIF Literature API records cite GBIF
    datasets, not individual specimens. Downstream joins should therefore
    interpret inherited links as dataset-citing publication exposure. They are
    noisier than BOLD accession-to-PubMed links and should not be described as
    direct specimen citations.

Usage:
    python3 Scripts/pipeline/21_link_gbif_datasets_to_publications.py --dry-run
    python3 Scripts/pipeline/21_link_gbif_datasets_to_publications.py
    python3 Scripts/pipeline/21_link_gbif_datasets_to_publications.py --limit-datasets 100
    python3 Scripts/pipeline/21_link_gbif_datasets_to_publications.py --force-refresh
    python3 Scripts/pipeline/21_link_gbif_datasets_to_publications.py --dry-run --max-pages-per-dataset 5
    python3 Scripts/pipeline/21_link_gbif_datasets_to_publications.py --workers 4 --sleep 0.5
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
import json
import random
import sqlite3
import subprocess
import time
import urllib.parse
import uuid
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_utils import PROJECT_ROOT


GBIF_MINIMAL_CSV = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal.csv"
)
PUB_DIR = PROJECT_ROOT / "Data" / "processed" / "discovery" / "publications"
DEFAULT_CACHE_DB = PUB_DIR / "gbif_literature_cache.db"
DRYRUN_CACHE_DB = PUB_DIR / "gbif_literature_cache_dryrun.db"
DEFAULT_OUTPUT = PUB_DIR / "gbif_dataset_to_pubs.csv"
DRYRUN_OUTPUT = PUB_DIR / "gbif_dataset_to_pubs_dryrun.csv"

GBIF_LITERATURE_URL = "https://api.gbif.org/v1/literature/search"
DEFAULT_USER_AGENT = "diversity_discoveries/1.0 (mailto:vkorovkinv@gmail.com)"
CACHE_VERSION = "gbif_literature_search_gbifDatasetKey_v3_full_pages"
OUTPUT_COLUMNS = [
    "dataset_key",
    "pub_id",
    "doi",
    "year",
    "title",
    "source_url",
    "literature_type",
    "journal",
    "authors",
    "dataset_occurrence_count",
]
BACKOFF_DELAYS = [1, 2, 4, 8, 16]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_dataset_counts(input_csv: Path, limit_datasets: int | None = None) -> Counter[str]:
    """Return occurrence counts by non-empty dataset_key."""
    if not input_csv.exists():
        raise SystemExit(f"Input not found: {input_csv}")

    counts: Counter[str] = Counter()
    for chunk in pd.read_csv(
        input_csv,
        usecols=["dataset_key"],
        dtype=str,
        chunksize=1_000_000,
    ):
        keys = chunk["dataset_key"].fillna("").str.strip()
        for dataset_key, n in keys[keys.ne("")].value_counts().items():
            counts[str(dataset_key)] += int(n)
        if limit_datasets is not None and len(counts) >= limit_datasets:
            # Keep deterministic order by count key sorting later; this only
            # avoids scanning the whole 6.7GB file in dry runs.
            break
    return counts


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (TypeError, ValueError):
        return False
    return True


def init_cache(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_literature_cache (
            dataset_key TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            page_size INTEGER NOT NULL,
            total INTEGER,
            pages_json TEXT,
            error_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO cache_meta(key, value) VALUES (?, ?)",
        ("last_initialized_utc", utc_now()),
    )
    current_version = conn.execute(
        "SELECT value FROM cache_meta WHERE key = ?",
        ("script_cache_version",),
    ).fetchone()
    if current_version is None or current_version[0] != CACHE_VERSION:
        conn.execute("DELETE FROM dataset_literature_cache")
        conn.execute(
            "INSERT OR REPLACE INTO cache_meta(key, value) VALUES (?, ?)",
            ("script_cache_version", CACHE_VERSION),
        )
        conn.execute(
            "INSERT OR REPLACE INTO cache_meta(key, value) VALUES (?, ?)",
            ("cache_invalidated_utc", utc_now()),
        )
    conn.commit()


def get_cached_pages(conn: sqlite3.Connection, dataset_key: str) -> list[dict[str, Any]] | None:
    row = conn.execute(
        """
        SELECT status, pages_json
        FROM dataset_literature_cache
        WHERE dataset_key = ?
        """,
        (dataset_key,),
    ).fetchone()
    if row is None:
        return None
    status, pages_json = row
    if status != "ok":
        return None
    if not pages_json:
        return []
    return json.loads(pages_json)


def write_cache(
    conn: sqlite3.Connection,
    dataset_key: str,
    status: str,
    page_size: int,
    total: int | None,
    pages: list[dict[str, Any]] | None,
    error: dict[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO dataset_literature_cache
            (dataset_key, status, fetched_at, page_size, total, pages_json, error_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_key,
            status,
            utc_now(),
            page_size,
            total,
            compact_json(pages) if pages is not None else None,
            compact_json(error) if error is not None else None,
        ),
    )
    conn.commit()


def request_json(
    params: dict[str, str | int],
    user_agent: str,
    sleep: float,
    timeout: float,
) -> dict[str, Any]:
    url = GBIF_LITERATURE_URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(len(BACKOFF_DELAYS) + 1):
        try:
            proc = subprocess.run(
                [
                    "curl",
                    "-L",
                    "-sS",
                    "--max-time",
                    str(timeout),
                    "-H",
                    "Accept: application/json",
                    "-H",
                    f"User-Agent: {user_agent}",
                    "-w",
                    "\n%{http_code}",
                    url,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout + 5,
            )
            if sleep > 0:
                time.sleep(sleep)

            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or f"curl exited {proc.returncode}")

            body, _, status_text = proc.stdout.rpartition("\n")
            status = int(status_text.strip() or "0")
            if status == 200:
                if not body.strip():
                    return {"count": 0, "endOfRecords": True, "results": []}
                return json.loads(body)
            retryable = status == 429 or 500 <= status < 600
            if not retryable or attempt >= len(BACKOFF_DELAYS):
                raise RuntimeError(f"GBIF HTTP {status} for {url}; response={body[:500]}")
            delay = BACKOFF_DELAYS[attempt] + random.uniform(0, 0.25)
            time.sleep(delay)
        except (json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired) as exc:
            if attempt >= len(BACKOFF_DELAYS):
                raise RuntimeError(f"GBIF request failed for {url}: {exc}") from exc
            delay = BACKOFF_DELAYS[attempt] + random.uniform(0, 0.25)
            print(
                f"  request retry {attempt + 1}/{len(BACKOFF_DELAYS)} "
                f"after {type(exc).__name__}: {exc}; sleeping {delay:.1f}s",
                flush=True,
            )
            time.sleep(delay)

    raise RuntimeError(f"GBIF request failed for {url}")


def fetch_dataset_literature(
    dataset_key: str,
    page_size: int,
    sleep: float,
    user_agent: str,
    request_timeout: float,
    max_pages: int | None = None,
    page_progress_every: int = 10,
) -> tuple[list[dict[str, Any]], int | None]:
    pages: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None

    while True:
        page = request_json(
            {
                "gbifDatasetKey": dataset_key,
                "limit": page_size,
                "offset": offset,
            },
            user_agent=user_agent,
            sleep=sleep,
            timeout=request_timeout,
        )
        pages.append(page)
        total = page.get("count", total)
        results = page.get("results") or []
        page_n = len(pages)
        if page_progress_every > 0 and (
            page_n == 1 or page_n % page_progress_every == 0
        ):
            total_text = f"{int(total):,}" if total is not None else "unknown"
            print(
                f"  {dataset_key}: pages={page_n:,} offset={offset:,} "
                f"results_this_page={len(results):,} total={total_text}",
                flush=True,
            )
        if max_pages is not None and page_n >= max_pages:
            print(
                f"  {dataset_key}: stopping after --max-pages-per-dataset={max_pages:,}",
                flush=True,
            )
            break
        end_of_records = bool(page.get("endOfRecords"))
        if end_of_records or not results:
            break
        offset += page_size
        if total is not None and offset >= int(total):
            break
    return pages, total


def first_nonempty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, dict)):
            if value:
                return compact_json(value)
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def extract_doi(record: dict[str, Any]) -> str:
    direct = first_nonempty(record.get("doi"))
    if direct:
        return direct
    identifiers = record.get("identifiers") or record.get("identifier")
    if isinstance(identifiers, list):
        for item in identifiers:
            if isinstance(item, dict):
                scheme = str(item.get("scheme") or item.get("type") or "").lower()
                value = first_nonempty(item.get("identifier"), item.get("value"))
                if "doi" in scheme and value:
                    return value
            elif isinstance(item, str) and "10." in item:
                return item.strip()
    return ""


def extract_authors(record: dict[str, Any]) -> str:
    authors = record.get("authors") or record.get("author")
    if isinstance(authors, list):
        pieces: list[str] = []
        for author in authors:
            if isinstance(author, dict):
                pieces.append(first_nonempty(author.get("name"), author.get("lastName")))
            else:
                pieces.append(str(author))
        return "; ".join(piece for piece in pieces if piece)
    return first_nonempty(authors)


def normalize_publication(
    dataset_key: str,
    dataset_occurrence_count: int,
    record: dict[str, Any],
) -> dict[str, str | int]:
    return {
        "dataset_key": dataset_key,
        "pub_id": first_nonempty(
            record.get("id"),
            record.get("key"),
            record.get("identifier"),
            record.get("uuid"),
        ),
        "doi": extract_doi(record),
        "year": first_nonempty(
            record.get("year"),
            record.get("publishedYear"),
            record.get("publicationYear"),
        ),
        "title": first_nonempty(record.get("title")),
        "source_url": first_nonempty(
            record.get("source"),
            record.get("url"),
            record.get("websites"),
            record.get("homepage"),
        ),
        "literature_type": first_nonempty(record.get("type"), record.get("literatureType")),
        "journal": first_nonempty(
            record.get("journal"),
            record.get("sourceTitle"),
            record.get("publisher"),
        ),
        "authors": extract_authors(record),
        "dataset_occurrence_count": dataset_occurrence_count,
    }


def pages_to_rows(
    dataset_key: str,
    dataset_occurrence_count: int,
    pages: Iterable[dict[str, Any]],
) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    seen: set[tuple[str, str, str]] = set()
    for page in pages:
        for record in page.get("results") or []:
            if not isinstance(record, dict):
                continue
            row = normalize_publication(dataset_key, dataset_occurrence_count, record)
            key = (str(row["dataset_key"]), str(row["pub_id"]), str(row["doi"]))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def fetch_dataset_result(
    position: int,
    total_datasets: int,
    dataset_key: str,
    dataset_occurrence_count: int,
    page_size: int,
    sleep: float,
    user_agent: str,
    request_timeout: float,
    max_pages: int | None,
    page_progress_every: int,
) -> dict[str, Any]:
    """Fetch and normalize one dataset. SQLite writes stay in the main thread."""
    print(f"dataset {position:,}/{total_datasets:,}: {dataset_key}", flush=True)
    try:
        pages, total = fetch_dataset_literature(
            dataset_key=dataset_key,
            page_size=page_size,
            sleep=sleep,
            user_agent=user_agent,
            request_timeout=request_timeout,
            max_pages=max_pages,
            page_progress_every=page_progress_every,
        )
        return {
            "dataset_key": dataset_key,
            "status": "ok",
            "page_size": page_size,
            "total": total,
            "pages": pages,
            "rows": pages_to_rows(dataset_key, dataset_occurrence_count, pages),
            "error": None,
        }
    except Exception as exc:
        return {
            "dataset_key": dataset_key,
            "status": "error",
            "page_size": page_size,
            "total": None,
            "pages": None,
            "rows": [],
            "error": {"message": str(exc), "type": type(exc).__name__},
        }


def write_rows(output: Path, rows: list[dict[str, str | int]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    tmp.replace(output)
    print(f"Wrote {len(rows):,} publication rows -> {output}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=GBIF_MINIMAL_CSV)
    parser.add_argument("--cache-db", type=Path, default=DEFAULT_CACHE_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-datasets", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--request-timeout", type=float, default=20.0)
    parser.add_argument("--max-pages-per-dataset", type=int, default=None)
    parser.add_argument("--page-progress-every", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--user-agent", type=str, default=DEFAULT_USER_AGENT)
    args = parser.parse_args()

    if args.page_size <= 0:
        parser.error("--page-size must be positive")
    if args.limit_datasets is not None and args.limit_datasets <= 0:
        parser.error("--limit-datasets must be positive")
    if args.sleep < 0:
        parser.error("--sleep must be non-negative")
    if args.request_timeout <= 0:
        parser.error("--request-timeout must be positive")
    if args.max_pages_per_dataset is not None and args.max_pages_per_dataset <= 0:
        parser.error("--max-pages-per-dataset must be positive")
    if args.page_progress_every < 0:
        parser.error("--page-progress-every must be non-negative")
    if args.workers <= 0:
        parser.error("--workers must be positive")

    limit = args.limit_datasets
    if args.dry_run and limit is None:
        limit = 25
    max_pages = args.max_pages_per_dataset
    if args.dry_run and max_pages is None:
        max_pages = 5
    output = DRYRUN_OUTPUT if args.dry_run and args.output == DEFAULT_OUTPUT else args.output
    cache_db = DRYRUN_CACHE_DB if args.dry_run and args.cache_db == DEFAULT_CACHE_DB else args.cache_db

    print(f"Reading dataset keys from {args.input}", flush=True)
    dataset_counts = build_dataset_counts(args.input, limit_datasets=limit)
    dataset_keys = sorted(dataset_counts)
    if limit is not None:
        dataset_keys = dataset_keys[:limit]
    malformed_keys = [dataset_key for dataset_key in dataset_keys if not is_uuid(dataset_key)]
    if malformed_keys:
        sample = ", ".join(malformed_keys[:10])
        more = "" if len(malformed_keys) <= 10 else f", ... +{len(malformed_keys)-10:,} more"
        print(
            f"Skipping malformed non-UUID dataset_key values: {len(malformed_keys):,} "
            f"({sample}{more})",
            flush=True,
        )
    dataset_keys = [dataset_key for dataset_key in dataset_keys if is_uuid(dataset_key)]
    print(f"Dataset keys to query: {len(dataset_keys):,}", flush=True)
    if args.dry_run:
        print(f"--dry-run: output will be {output}", flush=True)
        print(f"--dry-run: cache will be {cache_db}", flush=True)

    cache_db.parent.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, str | int]] = []
    fetched = 0
    cached = 0
    errors = 0
    pending: list[tuple[int, str]] = []

    with sqlite3.connect(cache_db) as conn:
        init_cache(conn)
        for i, dataset_key in enumerate(dataset_keys, 1):
            pages = None if args.force_refresh else get_cached_pages(conn, dataset_key)
            if pages is None:
                pending.append((i, dataset_key))
            else:
                cached += 1
                all_rows.extend(
                    pages_to_rows(
                        dataset_key,
                        dataset_counts[dataset_key],
                        pages,
                    )
                )

        if cached:
            print(f"Using cached datasets: {cached:,}", flush=True)
        print(
            f"Datasets pending API fetch: {len(pending):,}; workers={args.workers:,}",
            flush=True,
        )

        def handle_result(result: dict[str, Any]) -> None:
            nonlocal fetched, errors
            dataset_key = result["dataset_key"]
            if result["status"] == "ok":
                write_cache(
                    conn,
                    dataset_key=dataset_key,
                    status="ok",
                    page_size=result["page_size"],
                    total=result["total"],
                    pages=result["pages"],
                    error=None,
                )
                fetched += 1
                all_rows.extend(result["rows"])
            else:
                write_cache(
                    conn,
                    dataset_key=dataset_key,
                    status="error",
                    page_size=result["page_size"],
                    total=None,
                    pages=None,
                    error=result["error"],
                )
                print(
                    f"WARNING: {dataset_key} failed: {result['error']['message']}",
                    flush=True,
                )
                errors += 1

        if args.workers == 1:
            for completed, (position, dataset_key) in enumerate(pending, 1):
                result = fetch_dataset_result(
                    position=position,
                    total_datasets=len(dataset_keys),
                    dataset_key=dataset_key,
                    dataset_occurrence_count=dataset_counts[dataset_key],
                    page_size=args.page_size,
                    sleep=args.sleep,
                    user_agent=args.user_agent,
                    request_timeout=args.request_timeout,
                    max_pages=max_pages,
                    page_progress_every=args.page_progress_every,
                )
                handle_result(result)
                if completed % 100 == 0 or completed == len(pending):
                    done = cached + completed
                    print(
                        f"datasets_done={done:,} remaining={len(dataset_keys)-done:,} "
                        f"rows_so_far={len(all_rows):,} fetched={fetched:,} "
                        f"cached={cached:,} errors={errors:,}",
                        flush=True,
                    )
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = [
                    executor.submit(
                        fetch_dataset_result,
                        position,
                        len(dataset_keys),
                        dataset_key,
                        dataset_counts[dataset_key],
                        args.page_size,
                        args.sleep,
                        args.user_agent,
                        args.request_timeout,
                        max_pages,
                        args.page_progress_every,
                    )
                    for position, dataset_key in pending
                ]
                for completed, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    handle_result(result)
                    if completed % 100 == 0 or completed == len(pending):
                        done = cached + completed
                        print(
                            f"datasets_done={done:,} remaining={len(dataset_keys)-done:,} "
                            f"rows_so_far={len(all_rows):,} fetched={fetched:,} "
                            f"cached={cached:,} errors={errors:,}",
                            flush=True,
                        )

    write_rows(output, all_rows)
    print(
        f"Complete. Datasets: {len(dataset_keys):,}; fetched={fetched:,}; "
        f"cached={cached:,}; errors={errors:,}; publication rows={len(all_rows):,}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
