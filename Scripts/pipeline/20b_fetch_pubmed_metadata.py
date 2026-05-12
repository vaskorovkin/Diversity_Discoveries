#!/usr/bin/env python3
"""Fetch PubMed metadata for BOLD-linked PMIDs.

Input:
    Data/processed/discovery/publications/bold_accession_to_pubmed.csv

Output:
    Data/processed/discovery/publications/pubmed_id_to_metadata.csv

Cache:
    Data/processed/discovery/publications/pubmed_metadata_cache.db

The output supplies publication years for the BOLD accession-to-PubMed chain
before building the downstream publication cell-year panel.
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
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_utils import PROJECT_ROOT


PUB_DIR = PROJECT_ROOT / "Data" / "processed" / "discovery" / "publications"
INPUT_CSV = PUB_DIR / "bold_accession_to_pubmed.csv"
OUTPUT_CSV = PUB_DIR / "pubmed_id_to_metadata.csv"
DRYRUN_OUTPUT_CSV = PUB_DIR / "pubmed_id_to_metadata_dryrun.csv"
DEFAULT_CACHE_DB = PUB_DIR / "pubmed_metadata_cache.db"
DRYRUN_CACHE_DB = PUB_DIR / "pubmed_metadata_cache_dryrun.db"
DEFAULT_API_KEY_FILE = PROJECT_ROOT / "Data" / "raw" / "ncbi" / "api_key.txt"
DEFAULT_EMAIL = "vkorovkinv@gmail.com"
DEFAULT_TOOL = "diversity_discoveries"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
BACKOFF_DELAYS = [1, 2, 4, 8, 16]
OUTPUT_COLUMNS = [
    "pubmed_id",
    "year",
    "doi",
    "title",
    "journal",
    "pubdate",
    "epubdate",
    "source",
]


class RateLimiter:
    """Small thread-safe limiter for NCBI request starts."""

    def __init__(self, requests_per_second: float) -> None:
        self.interval = 1.0 / requests_per_second
        self.lock = threading.Lock()
        self.next_allowed = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            if now < self.next_allowed:
                time.sleep(self.next_allowed - now)
                now = time.monotonic()
            self.next_allowed = now + self.interval


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_api_key(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def extract_unique_pmids(input_csv: Path, limit_pmids: int | None, chunksize: int) -> list[str]:
    if not input_csv.exists():
        raise SystemExit(f"Input not found: {input_csv}")

    seen: set[str] = set()
    rows_seen = 0
    print(f"Extracting PMIDs from {input_csv}", flush=True)
    for i, chunk in enumerate(
        pd.read_csv(input_csv, dtype=str, usecols=["pubmed_id"], chunksize=chunksize),
        1,
    ):
        rows_seen += len(chunk)
        pmids = chunk["pubmed_id"].fillna("").str.strip()
        for pmid in pmids[pmids.ne("")].values:
            if pmid.isdigit():
                seen.add(str(int(pmid)))
                if limit_pmids is not None and len(seen) >= limit_pmids:
                    break
        print(
            f"  chunk {i:,}: {rows_seen:,} rows scanned; {len(seen):,} unique PMIDs",
            flush=True,
        )
        if limit_pmids is not None and len(seen) >= limit_pmids:
            break
    return sorted(seen, key=lambda x: int(x))


def init_cache(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pubmed_metadata (
            pubmed_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            year TEXT,
            doi TEXT,
            title TEXT,
            journal TEXT,
            pubdate TEXT,
            epubdate TEXT,
            source TEXT,
            raw_json TEXT,
            error_json TEXT
        )
        """
    )
    conn.commit()


def cached_pmids(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT pubmed_id FROM pubmed_metadata WHERE status = 'ok'")
    }


def parse_year(*values: str) -> str:
    for value in values:
        text = (value or "").strip()
        if len(text) >= 4 and text[:4].isdigit():
            year = int(text[:4])
            if 1500 <= year <= 2100:
                return str(year)
    return ""


def first_doi(record: dict[str, Any]) -> str:
    article_ids = record.get("articleids") or []
    if isinstance(article_ids, list):
        for item in article_ids:
            if not isinstance(item, dict):
                continue
            if str(item.get("idtype", "")).lower() == "doi":
                return str(item.get("value", "")).strip()
    return ""


def normalize_record(pmid: str, record: dict[str, Any]) -> dict[str, str]:
    pubdate = str(record.get("pubdate", "") or "")
    epubdate = str(record.get("epubdate", "") or "")
    sortpubdate = str(record.get("sortpubdate", "") or "")
    return {
        "pubmed_id": pmid,
        "year": parse_year(pubdate, epubdate, sortpubdate),
        "doi": first_doi(record),
        "title": str(record.get("title", "") or "").strip(),
        "journal": str(record.get("fulljournalname", "") or record.get("source", "") or "").strip(),
        "pubdate": pubdate.strip(),
        "epubdate": epubdate.strip(),
        "source": str(record.get("source", "") or "").strip(),
    }


def fetch_batch(
    pmids: list[str],
    api_key: str,
    email: str,
    tool: str,
    timeout: float,
    rate_limiter: RateLimiter,
) -> dict[str, dict[str, str]]:
    params = {
        "db": "pubmed",
        "retmode": "json",
        "id": ",".join(pmids),
        "email": email,
        "tool": tool,
    }
    if api_key:
        params["api_key"] = api_key
    url = ESUMMARY_URL + "?" + urllib.parse.urlencode(params)

    for attempt in range(len(BACKOFF_DELAYS) + 1):
        try:
            rate_limiter.wait()
            with urllib.request.urlopen(url, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read()
            if status != 200:
                raise RuntimeError(f"NCBI HTTP {status}: {body[:500]!r}")
            payload = json.loads(body.decode("utf-8"))
            result = payload.get("result", {})
            out: dict[str, dict[str, str]] = {}
            for pmid in pmids:
                record = result.get(pmid)
                if isinstance(record, dict):
                    out[pmid] = normalize_record(pmid, record)
            return out
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            retryable = True
            if isinstance(exc, urllib.error.HTTPError):
                retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= len(BACKOFF_DELAYS):
                raise RuntimeError(f"PubMed esummary failed for batch starting {pmids[0]}: {exc}") from exc
            delay = BACKOFF_DELAYS[attempt] + random.uniform(0, 0.25)
            print(
                f"  request retry {attempt + 1}/{len(BACKOFF_DELAYS)} "
                f"after {type(exc).__name__}: {exc}; sleeping {delay:.1f}s",
                flush=True,
            )
            time.sleep(delay)

    raise RuntimeError(f"PubMed esummary failed for batch starting {pmids[0]}")


def fetch_batch_result(
    batch_index: int,
    batch: list[str],
    api_key: str,
    email: str,
    tool: str,
    timeout: float,
    rate_limiter: RateLimiter,
) -> dict[str, object]:
    try:
        rows = fetch_batch(
            batch,
            api_key=api_key,
            email=email,
            tool=tool,
            timeout=timeout,
            rate_limiter=rate_limiter,
        )
        return {
            "batch_index": batch_index,
            "batch": batch,
            "rows": rows,
            "error": None,
        }
    except Exception as exc:
        return {
            "batch_index": batch_index,
            "batch": batch,
            "rows": {},
            "error": {"message": str(exc), "type": type(exc).__name__},
        }


def write_cache_rows(
    conn: sqlite3.Connection,
    rows: dict[str, dict[str, str]],
    requested_pmids: list[str],
) -> None:
    now = utc_now()
    for pmid in requested_pmids:
        row = rows.get(pmid)
        if row is None:
            conn.execute(
                """
                INSERT OR REPLACE INTO pubmed_metadata
                    (pubmed_id, status, fetched_at, error_json)
                VALUES (?, ?, ?, ?)
                """,
                (pmid, "missing", now, json.dumps({"message": "PMID absent from esummary result"})),
            )
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO pubmed_metadata
                (pubmed_id, status, fetched_at, year, doi, title, journal,
                 pubdate, epubdate, source, raw_json, error_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pmid,
                "ok",
                now,
                row["year"],
                row["doi"],
                row["title"],
                row["journal"],
                row["pubdate"],
                row["epubdate"],
                row["source"],
                json.dumps(row, ensure_ascii=False),
                None,
            ),
        )
    conn.commit()


def write_output(conn: sqlite3.Connection, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in conn.execute(
            """
            SELECT pubmed_id, year, doi, title, journal, pubdate, epubdate, source
            FROM pubmed_metadata
            WHERE status = 'ok'
            ORDER BY CAST(pubmed_id AS INTEGER)
            """
        ):
            writer.writerow(dict(zip(OUTPUT_COLUMNS, row)))
    tmp.replace(output)
    print(f"Wrote metadata CSV: {output}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--cache-db", type=Path, default=DEFAULT_CACHE_DB)
    parser.add_argument("--api-key-file", type=Path, default=DEFAULT_API_KEY_FILE)
    parser.add_argument("--email", type=str, default=DEFAULT_EMAIL)
    parser.add_argument("--tool", type=str, default=DEFAULT_TOOL)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    parser.add_argument("--request-timeout", type=float, default=30.0)
    parser.add_argument("--sleep", type=float, default=None)
    parser.add_argument("--requests-per-second", type=float, default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit-pmids", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--concat-only", action="store_true")
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.limit_pmids is not None and args.limit_pmids <= 0:
        parser.error("--limit-pmids must be positive")
    if args.request_timeout <= 0:
        parser.error("--request-timeout must be positive")
    if args.workers <= 0:
        parser.error("--workers must be positive")
    if args.requests_per_second is not None and args.requests_per_second <= 0:
        parser.error("--requests-per-second must be positive")

    api_key = read_api_key(args.api_key_file)
    sleep = args.sleep
    if sleep is None:
        sleep = 0.11 if api_key else 0.34
    requests_per_second = args.requests_per_second
    if requests_per_second is None:
        requests_per_second = min(9.0, 1.0 / sleep) if api_key else min(2.8, 1.0 / sleep)
    output = DRYRUN_OUTPUT_CSV if args.dry_run and args.output == OUTPUT_CSV else args.output
    cache_db = DRYRUN_CACHE_DB if args.dry_run and args.cache_db == DEFAULT_CACHE_DB else args.cache_db
    limit_pmids = args.limit_pmids
    if args.dry_run and limit_pmids is None:
        limit_pmids = 1_000

    print(
        f"NCBI API key {'loaded' if api_key else 'not found'}; "
        f"workers={args.workers:,}; shared request cap={requests_per_second:.2f} req/sec.",
        flush=True,
    )
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(cache_db) as conn:
        init_cache(conn)
        if not args.concat_only:
            pmids = extract_unique_pmids(args.input, limit_pmids, args.chunksize)
            done = set() if args.force_refresh else cached_pmids(conn)
            pending = [pmid for pmid in pmids if pmid not in done]
            print(
                f"Unique PMIDs: {len(pmids):,}; cached={len(done):,}; pending={len(pending):,}",
                flush=True,
            )
            started = time.time()
            batches = [
                pending[i : i + args.batch_size]
                for i in range(0, len(pending), args.batch_size)
            ]
            rate_limiter = RateLimiter(requests_per_second)
            errors = 0

            if args.workers == 1:
                iterator = (
                    fetch_batch_result(
                        batch_index,
                        batch,
                        api_key,
                        args.email,
                        args.tool,
                        args.request_timeout,
                        rate_limiter,
                    )
                    for batch_index, batch in enumerate(batches, 1)
                )
            else:
                executor = ThreadPoolExecutor(max_workers=args.workers)
                futures = [
                    executor.submit(
                        fetch_batch_result,
                        batch_index,
                        batch,
                        api_key,
                        args.email,
                        args.tool,
                        args.request_timeout,
                        rate_limiter,
                    )
                    for batch_index, batch in enumerate(batches, 1)
                ]
                iterator = (future.result() for future in as_completed(futures))

            try:
                pmids_done = 0
                for batches_done, result in enumerate(iterator, 1):
                    batch = result["batch"]
                    if result["error"] is None:
                        write_cache_rows(conn, result["rows"], batch)
                    else:
                        errors += 1
                        error = result["error"]
                        print(
                            f"WARNING: batch {result['batch_index']} failed: {error['message']}",
                            flush=True,
                        )
                    pmids_done += len(batch)
                    if batches_done % 25 == 0 or batches_done == len(batches):
                        elapsed = max(time.time() - started, 1)
                        rate = pmids_done / elapsed
                        remaining = len(pending) - pmids_done
                        eta_min = remaining / rate / 60 if rate else 0
                        print(
                            f"batches_done={batches_done:,} pmids_done={pmids_done:,} "
                            f"remaining={remaining:,} errors={errors:,} eta_min={eta_min:.1f}",
                            flush=True,
                        )
            finally:
                if args.workers != 1:
                    executor.shutdown(wait=True)
        write_output(conn, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
