#!/usr/bin/env python3
"""Link BOLD GenBank/INSDC accessions to PubMed IDs through NCBI Entrez.

Input:
    Data/processed/bold/bold_minimal_records.csv

Primary output:
    Data/processed/discovery/publications/bold_accession_to_pubmed.csv

Resume-safe batch chunks:
    Data/processed/discovery/publications/chunks/bold_link_batch_<NNNNN>.csv

The requested API path is Entrez E-utilities epost + elink
(`dbfrom=nuccore`, `db=pubmed`). In practice, elink can be either collapsed at
the posted-batch level or falsely empty for accession-string inputs, so it is
not sufficient for source-specific attribution. This script supports the
requested epost + elink screen, but production runs can use
`--skip-elink-screen` and rely directly on GenBank flat-file efetch for final
per-accession PUBMED references. It never expands a collapsed batch into a
cartesian product.
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
import http.client
import os
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Sequence
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline_utils import MINIMAL_CSV, PROJECT_ROOT


PUB_DIR = PROJECT_ROOT / "Data" / "processed" / "discovery" / "publications"
CHUNK_DIRNAME = "chunks"
DRYRUN_CHUNK_DIRNAME = "chunks_dryrun"
FINAL_CSV_NAME = "bold_accession_to_pubmed.csv"
DEFAULT_API_KEY_FILE = PROJECT_ROOT / "Data" / "raw" / "ncbi" / "api_key.txt"
DEFAULT_EMAIL = "vkorovkinv@gmail.com"
DEFAULT_TOOL = "diversity_discoveries"

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EPOST_URL = f"{EUTILS}/epost.fcgi"
ELINK_URL = f"{EUTILS}/elink.fcgi"
EFETCH_URL = f"{EUTILS}/efetch.fcgi"

CHUNK_HEADER = ["accession", "pubmed_id", "query_date"]
CHUNK_FILENAME_RE = re.compile(r"bold_link_batch_(\d+)\.csv$")
ACCESSION_SPLIT_RE = re.compile(r"[|;,\s]+")
ACCESSION_VERSION_RE = re.compile(r"\.[0-9]+$")
ACCESSION_TOKEN_RE = re.compile(r"^[A-Z0-9_]{5,25}$")
BACKOFF_DELAYS = [1, 2, 4, 8, 16]
EXCLUDED_SOURCE_GROUPS = {"diptera_cecidomyiidae_costa_rica_capped"}
ACCESSION_PREFIXES = ("NZ_",)
DEFAULT_EFETCH_BATCH_SIZE = 100
DEFAULT_REQUEST_TIMEOUT = 45
FAILURE_HEADER = [
    "run_started",
    "batch_index",
    "subbatch_index",
    "accession_count",
    "accessions",
    "reason",
]
REPAIR_REMAINING_NAME = "bold_pubmed_efetch_failures_remaining.csv"


def normalize_accession(value: str) -> str:
    token = ACCESSION_VERSION_RE.sub("", value.strip().upper())
    if not token:
        return ""
    if not ACCESSION_TOKEN_RE.match(token):
        return ""
    if not any(ch.isalpha() for ch in token):
        return ""
    if not any(ch.isdigit() for ch in token):
        return ""
    return token


def accession_aliases(accession: str) -> set[str]:
    token = normalize_accession(accession)
    if not token:
        return set()
    aliases = {token}
    for prefix in ACCESSION_PREFIXES:
        if token.startswith(prefix):
            aliases.add(token[len(prefix):])
        else:
            aliases.add(prefix + token)
    return {alias for alias in aliases if normalize_accession(alias)}


def extract_unique_accessions(
    input_csv: Path,
    chunksize: int = 1_000_000,
    max_unique_accessions: int | None = None,
) -> list[str]:
    if not input_csv.exists():
        raise SystemExit(f"Input not found: {input_csv}")

    seen: set[str] = set()
    rows_seen = 0
    tokens_seen = 0
    tokens_discarded = 0

    print(f"Extracting accessions from {input_csv}", flush=True)
    for i, chunk in enumerate(
        pd.read_csv(
            input_csv,
            dtype=str,
            usecols=["source_group", "insdc_acs"],
            chunksize=chunksize,
        ),
        1,
    ):
        chunk = chunk[~chunk["source_group"].fillna("").isin(EXCLUDED_SOURCE_GROUPS)]
        for cell in chunk["insdc_acs"].fillna("").values:
            if not cell:
                continue
            for raw_token in ACCESSION_SPLIT_RE.split(cell):
                if not raw_token:
                    continue
                tokens_seen += 1
                token = normalize_accession(raw_token)
                if token:
                    seen.add(token)
                else:
                    tokens_discarded += 1
                if max_unique_accessions is not None and len(seen) >= max_unique_accessions:
                    break
            if max_unique_accessions is not None and len(seen) >= max_unique_accessions:
                break

        rows_seen += len(chunk)
        print(
            f"  chunk {i}: {rows_seen:,} eligible rows scanned; "
            f"{len(seen):,} unique accessions",
            flush=True,
        )
        if max_unique_accessions is not None and len(seen) >= max_unique_accessions:
            print(
                f"Stopping early after collecting {len(seen):,} unique accessions.",
                flush=True,
            )
            break

    if tokens_seen:
        pct = 100 * tokens_discarded / tokens_seen
        print(
            f"Parsed {tokens_seen:,} accession tokens; discarded "
            f"{tokens_discarded:,} ({pct:.2f}%) as malformed.",
            flush=True,
        )
    print(
        "Excluded source_groups from linkage: "
        + ", ".join(sorted(EXCLUDED_SOURCE_GROUPS)),
        flush=True,
    )
    return sorted(seen)


def covered_accessions(chunk_dir: Path) -> set[str]:
    covered: set[str] = set()
    for path in sorted(chunk_dir.glob("bold_link_batch_*.csv")):
        try:
            df = pd.read_csv(path, dtype=str, usecols=["accession"])
        except Exception as exc:
            print(f"WARNING: could not read existing chunk {path}: {exc}", flush=True)
            continue
        covered.update(df["accession"].dropna().map(normalize_accession))
    covered.discard("")
    return covered


def existing_batch_indices(chunk_dir: Path) -> set[int]:
    indices: set[int] = set()
    for path in chunk_dir.glob("bold_link_batch_*.csv"):
        match = CHUNK_FILENAME_RE.match(path.name)
        if match:
            indices.add(int(match.group(1)))
    return indices


class ThreadSafeLog:
    def __init__(self, fh) -> None:
        self.fh = fh
        self.lock = threading.Lock()

    def write(self, text: str) -> int:
        with self.lock:
            written = self.fh.write(text)
            self.fh.flush()
            return written

    def flush(self) -> None:
        with self.lock:
            self.fh.flush()


class ThreadSafeCsv:
    def __init__(self, fh) -> None:
        self.fh = fh
        self.writer = csv.writer(fh)
        self.lock = threading.Lock()

    def writerow(self, row: Sequence[str | int]) -> None:
        with self.lock:
            self.writer.writerow(row)
            self.fh.flush()


def write_chunk_atomic(chunk_path: Path, rows: list[tuple[str, str]], query_date: str) -> None:
    tmp_path = chunk_path.with_suffix(chunk_path.suffix + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CHUNK_HEADER)
        for accession, pubmed_id in rows:
            writer.writerow([accession, pubmed_id, query_date])
    os.replace(tmp_path, chunk_path)


def read_chunk_rows(chunk_path: Path) -> list[dict[str, str]]:
    with chunk_path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_chunk_dicts_atomic(chunk_path: Path, rows: list[dict[str, str]]) -> None:
    tmp_path = chunk_path.with_suffix(chunk_path.suffix + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CHUNK_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "accession": normalize_accession(row.get("accession", "")),
                    "pubmed_id": (row.get("pubmed_id") or "").strip(),
                    "query_date": (row.get("query_date") or "").strip(),
                }
            )
    os.replace(tmp_path, chunk_path)


def post_form_with_backoff(
    url: str,
    params: Sequence[tuple[str, str]],
    log_fh,
    batch_index: int,
    label: str,
    sleep_per_request: float,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
) -> bytes | None:
    for attempt in range(len(BACKOFF_DELAYS) + 1):
        try:
            body = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
            request = urllib.request.Request(url, data=body, method="POST")
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                payload = response.read()
                time.sleep(sleep_per_request)
                if response.status == 200:
                    return payload
                transient = response.status == 429 or 500 <= response.status < 600
                log_fh.write(
                    f"batch={batch_index} {label} attempt={attempt} "
                    f"status={response.status}\n"
                )
                log_fh.flush()
                if not transient:
                    return None
        except urllib.error.HTTPError as exc:
            time.sleep(sleep_per_request)
            transient = exc.code == 429 or 500 <= exc.code < 600
            log_fh.write(
                f"batch={batch_index} {label} attempt={attempt} "
                f"httperror={exc.code}\n"
            )
            log_fh.flush()
            if not transient:
                return None
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as exc:
            time.sleep(sleep_per_request)
            partial = getattr(exc, "partial", b"")
            if partial:
                partial_bytes = bytes(partial)
                if partial_bytes.lstrip().startswith(b"<"):
                    log_fh.write(
                        f"batch={batch_index} {label} attempt={attempt} "
                        f"neterror={type(exc).__name__}:using_partial_xml "
                        f"bytes={len(partial_bytes)}\n"
                    )
                    log_fh.flush()
                    return partial_bytes
                preview = partial_bytes[:200].decode("utf-8", errors="replace").replace("\n", " ")
                log_fh.write(
                    f"batch={batch_index} {label} attempt={attempt} "
                    f"neterror={type(exc).__name__}:partial_nonxml "
                    f"bytes={len(partial_bytes)} preview={preview}\n"
                )
                log_fh.flush()
            log_fh.write(
                f"batch={batch_index} {label} attempt={attempt} "
                f"neterror={type(exc).__name__}:{exc}\n"
            )
            log_fh.flush()

        if attempt >= len(BACKOFF_DELAYS):
            log_fh.write(f"batch={batch_index} {label} failed_after_retries\n")
            log_fh.flush()
            return None

        delay = BACKOFF_DELAYS[attempt] + random.uniform(0, 0.25)
        time.sleep(delay)

    return None


def parse_xml(payload: bytes, log_fh, batch_index: int, label: str) -> ET.Element | None:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        log_fh.write(f"batch={batch_index} {label} xml_parse_error={exc}\n")
        log_fh.flush()
        return None

    errors = [node.text.strip() for node in root.findall(".//ERROR") if node.text]
    if errors:
        log_fh.write(f"batch={batch_index} {label} ncbi_error={' | '.join(errors)}\n")
        log_fh.flush()
    return root


def parse_epost(payload: bytes, log_fh, batch_index: int) -> tuple[str, str] | None:
    root = parse_xml(payload, log_fh, batch_index, "epost")
    if root is None:
        return None
    query_key = root.findtext(".//QueryKey")
    webenv = root.findtext(".//WebEnv")
    if not query_key or not webenv:
        log_fh.write(f"batch={batch_index} epost missing_query_key_or_webenv\n")
        log_fh.flush()
        return None
    return query_key, webenv


def linkset_pmids(linkset: ET.Element) -> set[str]:
    pmids: set[str] = set()
    for linkset_db in linkset.findall("./LinkSetDb"):
        db_to = (linkset_db.findtext("./DbTo") or "").strip().lower()
        if db_to and db_to != "pubmed":
            continue
        for node in linkset_db.findall("./Link/Id"):
            if node.text and node.text.strip().isdigit():
                pmids.add(node.text.strip())
    return pmids


def parse_elink_mapping(
    payload: bytes,
    batch: list[str],
    log_fh,
    batch_index: int,
    label: str,
) -> tuple[dict[str, set[str]] | None, str]:
    """Return (mapping, status).

    `mapping is None` means elink returned a valid response but not one that
    can be assigned to individual source accessions without ambiguity.
    """
    root = parse_xml(payload, log_fh, batch_index, label)
    if root is None:
        return None, "parse_error"

    linksets = root.findall(".//LinkSet")
    if not linksets:
        return {accession: set() for accession in batch}, "no_linksets"

    batch_set = set(batch)
    mapping: dict[str, set[str]] = {}

    if len(linksets) == 1:
        source_ids = [
            normalize_accession(node.text or "")
            for node in linksets[0].findall("./IdList/Id")
        ]
        source_ids = [sid for sid in source_ids if sid]
        if len(source_ids) == 1 and source_ids[0] in batch_set:
            mapping[source_ids[0]] = linkset_pmids(linksets[0])
            return mapping, "single_source"
        if len(batch) == 1:
            mapping[batch[0]] = linkset_pmids(linksets[0])
            return mapping, "single_batch_item"
        return None, "collapsed_linkset"

    for i, linkset in enumerate(linksets):
        source_ids = [
            normalize_accession(node.text or "")
            for node in linkset.findall("./IdList/Id")
        ]
        source_ids = [sid for sid in source_ids if sid]

        accession = ""
        if len(source_ids) == 1 and source_ids[0] in batch_set:
            accession = source_ids[0]
        elif len(linksets) == len(batch):
            accession = batch[i]

        if not accession:
            return None, "ambiguous_linkset"
        mapping.setdefault(accession, set()).update(linkset_pmids(linkset))

    return mapping, "mapped_linksets"


def parse_elink_batch_pmids(payload: bytes, log_fh, batch_index: int, label: str) -> set[str] | None:
    root = parse_xml(payload, log_fh, batch_index, label)
    if root is None:
        return None
    pmids: set[str] = set()
    for linkset in root.findall(".//LinkSet"):
        pmids.update(linkset_pmids(linkset))
    return pmids


def common_params(email: str, tool: str, api_key: str) -> list[tuple[str, str]]:
    params = [("email", email), ("tool", tool)]
    if api_key:
        params.append(("api_key", api_key))
    return params


def epost_params(batch: list[str], email: str, tool: str, api_key: str) -> list[tuple[str, str]]:
    return [
        ("db", "nuccore"),
        ("id", ",".join(batch)),
        *common_params(email, tool, api_key),
    ]


def elink_history_params(
    query_key: str,
    webenv: str,
    email: str,
    tool: str,
    api_key: str,
) -> list[tuple[str, str]]:
    return [
        ("dbfrom", "nuccore"),
        ("db", "pubmed"),
        ("cmd", "neighbor"),
        ("query_key", query_key),
        ("WebEnv", webenv),
        ("linkname", "nuccore_pubmed"),
        *common_params(email, tool, api_key),
    ]


def efetch_params(batch: list[str], email: str, tool: str, api_key: str) -> list[tuple[str, str]]:
    return [
        ("db", "nuccore"),
        ("id", ",".join(batch)),
        ("rettype", "gb"),
        ("retmode", "text"),
        *common_params(email, tool, api_key),
    ]


def parse_genbank_pubmed_mapping(payload: bytes | str) -> tuple[dict[str, set[str]], int, int]:
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
    else:
        text = payload

    mapping: dict[str, set[str]] = {}
    current_accession = ""
    current_pmids: set[str] = set()
    records_seen = 0

    def flush_record() -> None:
        nonlocal current_accession, current_pmids, records_seen
        if current_accession:
            records_seen += 1
            for alias in accession_aliases(current_accession):
                mapping.setdefault(alias, set()).update(current_pmids)
        current_accession = ""
        current_pmids = set()

    for line in text.splitlines():
        if line.startswith("LOCUS "):
            flush_record()
            parts = line.split()
            if len(parts) >= 2:
                current_accession = normalize_accession(parts[1])
            continue
        if not current_accession:
            continue
        if line.startswith("ACCESSION"):
            parts = line.split()
            if len(parts) >= 2:
                accession = normalize_accession(parts[1])
                if accession:
                    current_accession = accession
            continue
        stripped = line.lstrip()
        if stripped.startswith("PUBMED"):
            parts = stripped.split()
            if len(parts) >= 2 and parts[1].isdigit():
                current_pmids.add(parts[1])
            continue
        if line.startswith("//"):
            flush_record()

    flush_record()
    pmid_count = len({pmid for pmids in mapping.values() for pmid in pmids})
    return mapping, records_seen, pmid_count


def rows_from_mapping(batch: list[str], mapping: dict[str, set[str]]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for accession in batch:
        pmids = sorted(mapping.get(accession, set()), key=lambda value: int(value))
        if pmids:
            rows.extend((accession, pmid) for pmid in pmids)
        else:
            rows.append((accession, ""))
    return rows


def fetch_genbank_pubmed_mapping(
    batch: list[str],
    batch_index: int,
    email: str,
    tool: str,
    api_key: str,
    sleep_per_request: float,
    log_fh,
    efetch_batch_size: int = DEFAULT_EFETCH_BATCH_SIZE,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    failure_writer: ThreadSafeCsv | None = None,
    run_started: str = "",
) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    records_seen_total = 0
    pmid_values: set[str] = set()
    failed_subbatches = 0
    failed_accessions = 0

    groups = [
        batch[i : i + efetch_batch_size]
        for i in range(0, len(batch), efetch_batch_size)
    ]
    for group_index, group in enumerate(groups, 1):
        label = "efetch_genbank"
        if len(groups) > 1:
            label = f"efetch_genbank_{group_index:03d}"
        payload = post_form_with_backoff(
            EFETCH_URL,
            efetch_params(group, email, tool, api_key),
            log_fh,
            batch_index,
            label,
            sleep_per_request,
            request_timeout=request_timeout,
        )
        if payload is None:
            failed_subbatches += 1
            failed_accessions += len(group)
            log_fh.write(
                f"batch={batch_index} {label}_skipped_after_retries "
                f"accessions={len(group)}\n"
            )
            log_fh.flush()
            if failure_writer is not None:
                failure_writer.writerow(
                    [
                        run_started,
                        batch_index,
                        group_index,
                        len(group),
                        ";".join(group),
                        f"{label}_failed_after_retries",
                    ]
                )
            continue
        group_mapping, records_seen, pmid_count = parse_genbank_pubmed_mapping(payload)
        records_seen_total += records_seen
        for accession, pmids in group_mapping.items():
            mapping.setdefault(accession, set()).update(pmids)
            pmid_values.update(pmids)
        if len(groups) > 1:
            log_fh.write(
                f"batch={batch_index} {label}_parsed "
                f"records={records_seen} mapping_keys={len(group_mapping)} "
                f"pmid_values={pmid_count}\n"
            )
            log_fh.flush()

    log_fh.write(
        f"batch={batch_index} efetch_genbank_parsed "
        f"records={records_seen_total} mapping_keys={len(mapping)} "
        f"pmid_values={len(pmid_values)} "
        f"failed_subbatches={failed_subbatches} failed_accessions={failed_accessions}\n"
    )
    log_fh.flush()
    return mapping


def resolve_collapsed_linkset_mapping(
    batch: list[str],
    linked_payload: bytes,
    batch_index: int,
    email: str,
    tool: str,
    api_key: str,
    sleep_per_request: float,
    log_fh,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    failure_writer: ThreadSafeCsv | None = None,
    run_started: str = "",
) -> dict[str, set[str]] | None:
    pmids = parse_elink_batch_pmids(linked_payload, log_fh, batch_index, "elink_history")
    if pmids is None:
        return None
    if not pmids:
        return {accession: set() for accession in batch}

    log_fh.write(
        f"batch={batch_index} elink_history_collapsed_pmids={len(pmids)}; "
        "resolving_per_accession_with_efetch_genbank\n"
    )
    log_fh.flush()
    return fetch_genbank_pubmed_mapping(
        batch=batch,
        batch_index=batch_index,
        email=email,
        tool=tool,
        api_key=api_key,
        sleep_per_request=sleep_per_request,
        log_fh=log_fh,
        request_timeout=request_timeout,
        failure_writer=failure_writer,
        run_started=run_started,
    )


def process_batch(
    batch: list[str],
    batch_index: int,
    chunk_path: Path,
    email: str,
    tool: str,
    api_key: str,
    sleep_per_request: float,
    log_fh,
    efetch_batch_size: int = DEFAULT_EFETCH_BATCH_SIZE,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    failure_writer: ThreadSafeCsv | None = None,
    run_started: str = "",
    skip_elink_screen: bool = False,
) -> tuple[int, int, bool]:
    """Process one batch and return (rows_written, pmid_rows, chunk_written)."""
    mapping: dict[str, set[str]] | None = None
    if skip_elink_screen:
        log_fh.write(f"batch={batch_index} skip_elink_screen using_efetch_for_per_accession_pubmed\n")
        log_fh.flush()
    else:
        posted = post_form_with_backoff(
            EPOST_URL,
            epost_params(batch, email, tool, api_key),
            log_fh,
            batch_index,
            "epost",
            sleep_per_request,
            request_timeout=request_timeout,
        )
        if posted is None:
            log_fh.write(f"batch={batch_index} epost_failed_continuing_with_efetch\n")
            log_fh.flush()
        else:
            history = parse_epost(posted, log_fh, batch_index)
            if history is None:
                log_fh.write(f"batch={batch_index} epost_unusable_continuing_with_efetch\n")
                log_fh.flush()
            else:
                query_key, webenv = history
                linked = post_form_with_backoff(
                    ELINK_URL,
                    elink_history_params(query_key, webenv, email, tool, api_key),
                    log_fh,
                    batch_index,
                    "elink_history",
                    sleep_per_request,
                    request_timeout=request_timeout,
                )
                if linked is None:
                    log_fh.write(f"batch={batch_index} elink_failed_continuing_with_efetch\n")
                    log_fh.flush()
                else:
                    mapping, status = parse_elink_mapping(
                        linked, batch, log_fh, batch_index, "elink_history"
                    )
                    if mapping is None:
                        log_fh.write(
                            f"batch={batch_index} elink_history_unmappable status={status}; "
                            "using_efetch_for_per_accession_pubmed\n"
                        )
                        log_fh.flush()
                    else:
                        linked_accessions = sum(1 for pmids in mapping.values() if pmids)
                        log_fh.write(
                            f"batch={batch_index} elink_history_status={status} "
                            f"elink_accessions_with_pmids={linked_accessions}; "
                            "using_efetch_for_per_accession_pubmed\n"
                        )
                        log_fh.flush()

    efetch_mapping = fetch_genbank_pubmed_mapping(
        batch=batch,
        batch_index=batch_index,
        email=email,
        tool=tool,
        api_key=api_key,
        sleep_per_request=sleep_per_request,
        log_fh=log_fh,
        efetch_batch_size=efetch_batch_size,
        request_timeout=request_timeout,
        failure_writer=failure_writer,
        run_started=run_started,
    )
    mapping = efetch_mapping

    rows = rows_from_mapping(batch, mapping)
    query_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    write_chunk_atomic(chunk_path, rows, query_date)
    pmid_rows = sum(1 for _, pmid in rows if pmid)
    return len(rows), pmid_rows, True


def concat_chunks(chunk_dir: Path, final_csv: Path) -> None:
    files = sorted(chunk_dir.glob("bold_link_batch_*.csv"))
    if not files:
        print(f"No chunk files found in {chunk_dir}; nothing to concatenate.", flush=True)
        return

    print(f"Concatenating {len(files):,} chunk files -> {final_csv}", flush=True)
    final_csv.parent.mkdir(parents=True, exist_ok=True)

    seen: set[tuple[str, str]] = set()
    rows_in = 0
    rows_out = 0
    with final_csv.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(CHUNK_HEADER)
        for path in files:
            with path.open("r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    accession = normalize_accession(row.get("accession", ""))
                    pubmed_id = (row.get("pubmed_id") or "").strip()
                    query_date = (row.get("query_date") or "").strip()
                    if not accession:
                        continue
                    rows_in += 1
                    key = (accession, pubmed_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    writer.writerow([accession, pubmed_id, query_date])
                    rows_out += 1

    accessions_total = len({accession for accession, _ in seen})
    accessions_linked = len({accession for accession, pmid in seen if pmid})
    print(
        f"Read {rows_in:,} rows; wrote {rows_out:,} unique rows. "
        f"Accessions: {accessions_total:,}; with PMID: {accessions_linked:,}.",
        flush=True,
    )


def load_failure_groups(failures_path: Path) -> list[tuple[int, int, list[str], str]]:
    if not failures_path.exists():
        raise SystemExit(f"Failure file not found: {failures_path}")

    groups: list[tuple[int, int, list[str], str]] = []
    seen: set[tuple[int, int, tuple[str, ...]]] = set()
    with failures_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            batch_index = int(row.get("batch_index") or 0)
            subbatch_index = int(row.get("subbatch_index") or 0)
            accessions = [
                normalize_accession(token)
                for token in (row.get("accessions") or "").split(";")
            ]
            accessions = [accession for accession in accessions if accession]
            if not batch_index or not accessions:
                continue
            key = (batch_index, subbatch_index, tuple(accessions))
            if key in seen:
                continue
            seen.add(key)
            groups.append((batch_index, subbatch_index, accessions, row.get("reason") or ""))
    return groups


def patch_chunk_with_mapping(
    chunk_path: Path,
    accessions: list[str],
    mapping: dict[str, set[str]],
    query_date: str,
) -> tuple[int, int]:
    rows = read_chunk_rows(chunk_path)
    target_accessions = set(accessions)
    pmid_by_accession = {
        accession: sorted(mapping.get(accession, set()), key=lambda value: int(value))
        for accession in accessions
    }

    patched_rows: list[dict[str, str]] = []
    removed_blank_rows = 0
    added_pmid_rows = 0
    seen_target_accessions: set[str] = set()

    for row in rows:
        accession = normalize_accession(row.get("accession", ""))
        if accession not in target_accessions:
            patched_rows.append(row)
            continue

        seen_target_accessions.add(accession)
        pmids = pmid_by_accession.get(accession, [])
        if not pmids:
            patched_rows.append(row)
            continue

        if not (row.get("pubmed_id") or "").strip():
            removed_blank_rows += 1
        else:
            patched_rows.append(row)
            continue

        for pmid in pmids:
            patched_rows.append(
                {"accession": accession, "pubmed_id": pmid, "query_date": query_date}
            )
            added_pmid_rows += 1

    missing_from_chunk = target_accessions - seen_target_accessions
    for accession in sorted(missing_from_chunk):
        pmids = pmid_by_accession.get(accession, [])
        if pmids:
            for pmid in pmids:
                patched_rows.append(
                    {"accession": accession, "pubmed_id": pmid, "query_date": query_date}
                )
                added_pmid_rows += 1
        else:
            patched_rows.append(
                {"accession": accession, "pubmed_id": "", "query_date": query_date}
            )

    write_chunk_dicts_atomic(chunk_path, patched_rows)
    return removed_blank_rows, added_pmid_rows


def repair_failed_efetches(
    failures_path: Path,
    remaining_failures_path: Path,
    chunk_dir: Path,
    final_csv: Path,
    email: str,
    tool: str,
    api_key: str,
    sleep_per_request: float,
    log_path: Path,
    workers: int,
    efetch_batch_size: int,
    request_timeout: float,
) -> None:
    groups = load_failure_groups(failures_path)
    if not groups:
        print(f"No failure groups found in {failures_path}.", flush=True)
        concat_chunks(chunk_dir, final_csv)
        return

    groups_by_batch: dict[int, list[tuple[int, list[str], str]]] = defaultdict(list)
    for batch_index, subbatch_index, accessions, reason in groups:
        groups_by_batch[batch_index].append((subbatch_index, accessions, reason))
    batch_items = sorted(groups_by_batch.items())

    print(
        f"Repairing {len(groups):,} failed efetch groups "
        f"({sum(len(group[2]) for group in groups):,} accessions) "
        f"across {len(batch_items):,} chunk files.",
        flush=True,
    )
    started_iso = datetime.now(timezone.utc).isoformat()
    started_mono = time.monotonic()
    query_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    remaining_rows: list[list[str | int]] = []
    repaired_groups = 0
    repaired_accessions = 0
    removed_blank_rows = 0
    added_pmid_rows = 0

    with log_path.open("a", encoding="utf-8") as log_fh:
        log = ThreadSafeLog(log_fh)
        log.write(
            f"\n=== repair started {started_iso} groups={len(groups)} "
            f"workers={workers} efetch_batch_size={efetch_batch_size} "
            f"request_timeout={request_timeout}s source={failures_path} ===\n"
        )

        def repair_one(item: tuple[int, list[tuple[int, list[str], str]]]):
            batch_index, batch_groups = item
            batch_mapping: dict[str, set[str]] = {}
            remaining_by_group: list[tuple[int, list[str], str]] = []
            recovered_pmids = 0

            for subbatch_index, accessions, reason in batch_groups:
                mapping = fetch_genbank_pubmed_mapping(
                    batch=accessions,
                    batch_index=batch_index,
                    email=email,
                    tool=tool,
                    api_key=api_key,
                    sleep_per_request=sleep_per_request,
                    log_fh=log,
                    efetch_batch_size=efetch_batch_size,
                    request_timeout=request_timeout,
                    failure_writer=None,
                    run_started=started_iso,
                )
                for accession, pmids in mapping.items():
                    batch_mapping.setdefault(accession, set()).update(pmids)
                    recovered_pmids += len(pmids)
                remaining = [
                    accession for accession in accessions if accession not in mapping
                ]
                if remaining:
                    log.write(
                        f"batch={batch_index} repair_remaining_missing_records="
                        f"{len(remaining)} subbatch={subbatch_index}\n"
                    )
                    remaining_by_group.append((subbatch_index, remaining, reason))

            accessions = sorted(
                {
                    accession
                    for _, group_accessions, _ in batch_groups
                    for accession in group_accessions
                }
            )
            chunk_path = chunk_dir / f"bold_link_batch_{batch_index:05d}.csv"
            removed, added = patch_chunk_with_mapping(
                chunk_path=chunk_path,
                accessions=accessions,
                mapping=batch_mapping,
                query_date=query_date,
            )
            return (
                batch_index,
                len(batch_groups),
                accessions,
                remaining_by_group,
                recovered_pmids,
                removed,
                added,
            )

        if workers == 1:
            iterator = (repair_one(item) for item in batch_items)
        else:
            executor = ThreadPoolExecutor(max_workers=workers)
            futures = [executor.submit(repair_one, item) for item in batch_items]
            iterator = (future.result() for future in as_completed(futures))

        try:
            for completed, result in enumerate(iterator, 1):
                (
                    batch_index,
                    groups_in_batch,
                    accessions,
                    remaining_by_group,
                    recovered_pmids,
                    removed,
                    added,
                ) = result
                repaired_groups += groups_in_batch
                remaining_accessions = sum(len(group[1]) for group in remaining_by_group)
                repaired_accessions += len(accessions) - remaining_accessions
                removed_blank_rows += removed
                added_pmid_rows += added
                for subbatch_index, remaining, reason in remaining_by_group:
                    remaining_rows.append(
                        [
                            started_iso,
                            batch_index,
                            subbatch_index,
                            len(remaining),
                            ";".join(remaining),
                            f"repair_remaining_after_{reason}",
                        ]
                    )
                if completed % 25 == 0 or completed == len(batch_items):
                    elapsed = time.monotonic() - started_mono
                    rate = completed / elapsed if elapsed > 0 else 0.0
                    left = len(batch_items) - completed
                    eta = left / rate if rate > 0 else 0.0
                    print(
                        f"repair_chunks_done={completed:,} chunks_remaining={left:,} "
                        f"elapsed_min={elapsed/60:.1f} eta_min={eta/60:.1f} "
                        f"groups_repaired={repaired_groups:,} "
                        f"accessions_repaired={repaired_accessions:,} "
                        f"pmid_rows_added={added_pmid_rows:,}",
                        flush=True,
                    )
                    log.write(
                        f"repair_progress chunks_done={completed} "
                        f"remaining={left} recovered_pmids={recovered_pmids}\n"
                    )
        finally:
            if workers != 1:
                executor.shutdown(wait=True)

        finished_iso = datetime.now(timezone.utc).isoformat()
        log.write(
            f"=== repair finished {finished_iso} groups={repaired_groups} "
            f"accessions_repaired={repaired_accessions} "
            f"blank_rows_removed={removed_blank_rows} "
            f"pmid_rows_added={added_pmid_rows} "
            f"remaining_groups={len(remaining_rows)} ===\n"
        )

    with remaining_failures_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(FAILURE_HEADER)
        writer.writerows(remaining_rows)

    print(
        f"Repair complete. Repaired accessions: {repaired_accessions:,}; "
        f"PMID rows added: {added_pmid_rows:,}; "
        f"remaining failed groups: {len(remaining_rows):,}.",
        flush=True,
    )
    print(f"Remaining failures written to {remaining_failures_path}", flush=True)
    concat_chunks(chunk_dir, final_csv)


def load_api_key(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    return text.splitlines()[0].strip() if text else ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", type=Path, default=MINIMAL_CSV)
    parser.add_argument("--out-dir", type=Path, default=PUB_DIR)
    parser.add_argument("--api-key-file", type=Path, default=DEFAULT_API_KEY_FILE)
    parser.add_argument("--email", type=str, default=DEFAULT_EMAIL)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel batch workers for full/resume runs (default 1).")
    parser.add_argument("--efetch-batch-size", type=int, default=DEFAULT_EFETCH_BATCH_SIZE,
                        help="Accessions per GenBank efetch request inside each chunk (default 100).")
    parser.add_argument("--request-timeout", type=float, default=DEFAULT_REQUEST_TIMEOUT,
                        help="Seconds before each NCBI request times out (default 45).")
    parser.add_argument(
        "--skip-elink-screen",
        action="store_true",
        help="Skip epost/elink pre-checks and use GenBank efetch as the direct linkage source.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concat-only", action="store_true")
    parser.add_argument(
        "--repair-failures",
        action="store_true",
        help="Refetch groups listed in bold_pubmed_efetch_failures.csv and patch existing chunks.",
    )
    parser.add_argument(
        "--failures-file",
        type=Path,
        default=None,
        help="CSV of failed efetch groups to repair (default: standard failures CSV).",
    )
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.workers <= 0:
        parser.error("--workers must be positive")
    if args.efetch_batch_size <= 0:
        parser.error("--efetch-batch-size must be positive")
    if args.request_timeout <= 0:
        parser.error("--request-timeout must be positive")
    if args.dry_run and args.workers != 1:
        print("WARNING: --dry-run forces --workers 1.", flush=True)
        args.workers = 1

    api_key = load_api_key(args.api_key_file)
    rate_per_second = 10.0 if api_key else 3.0
    sleep_per_request = 1.0 / rate_per_second
    if api_key:
        print(f"NCBI API key loaded from {args.api_key_file}; using 10 req/sec.", flush=True)
    else:
        print(
            f"WARNING: no NCBI API key found at {args.api_key_file}; "
            "falling back to 3 req/sec.",
            flush=True,
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir = args.out_dir / (DRYRUN_CHUNK_DIRNAME if args.dry_run else CHUNK_DIRNAME)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    final_csv = args.out_dir / FINAL_CSV_NAME
    failures_path = args.out_dir / (
        "link_dryrun_efetch_failures.csv" if args.dry_run else "bold_pubmed_efetch_failures.csv"
    )
    if args.failures_file is not None:
        failures_path = args.failures_file
    remaining_failures_path = args.out_dir / (
        "link_dryrun_efetch_failures_remaining.csv" if args.dry_run else REPAIR_REMAINING_NAME
    )
    log_path = args.out_dir / ("link_dryrun.log" if args.dry_run else "link.log")

    if args.repair_failures:
        if args.dry_run:
            final_csv = args.out_dir / "bold_accession_to_pubmed_dryrun.csv"
        repair_failed_efetches(
            failures_path=failures_path,
            remaining_failures_path=remaining_failures_path,
            chunk_dir=chunk_dir,
            final_csv=final_csv,
            email=args.email,
            tool=DEFAULT_TOOL,
            api_key=api_key,
            sleep_per_request=sleep_per_request,
            log_path=log_path,
            workers=args.workers,
            efetch_batch_size=args.efetch_batch_size,
            request_timeout=args.request_timeout,
        )
        return 0

    if args.concat_only:
        if args.dry_run:
            print("WARNING: --dry-run --concat-only will concatenate dry-run chunks.", flush=True)
            final_csv = args.out_dir / "bold_accession_to_pubmed_dryrun.csv"
        concat_chunks(chunk_dir, final_csv)
        return 0

    accessions = extract_unique_accessions(
        args.input,
        max_unique_accessions=100 if args.dry_run else None,
    )
    if args.dry_run:
        print(f"--dry-run: limiting to first {len(accessions):,} accessions.", flush=True)

    existing_indices = existing_batch_indices(chunk_dir)
    covered = covered_accessions(chunk_dir)
    pending = [accession for accession in accessions if accession not in covered]
    print(f"Existing chunks: {len(covered):,} covered accessions in {chunk_dir}", flush=True)
    print(f"Pending accessions: {len(pending):,}", flush=True)

    if not pending:
        print("Nothing to do; all requested accessions are already covered.", flush=True)
        if not args.dry_run:
            concat_chunks(chunk_dir, final_csv)
        return 0

    all_batches: list[tuple[int, list[str], Path]] = []
    for offset in range(0, len(accessions), args.batch_size):
        batch_index = (offset // args.batch_size) + 1
        chunk_path = chunk_dir / f"bold_link_batch_{batch_index:05d}.csv"
        if batch_index in existing_indices or chunk_path.exists():
            continue
        batch = [accession for accession in accessions[offset : offset + args.batch_size] if accession not in covered]
        if not batch:
            continue
        all_batches.append((batch_index, batch, chunk_path))

    n_batches = len(all_batches)

    started_iso = datetime.now(timezone.utc).isoformat()
    started_mono = time.monotonic()
    batches_written = 0
    accessions_processed = 0
    rows_written = 0
    pmids_returned = 0

    failures_needs_header = not failures_path.exists() or failures_path.stat().st_size == 0
    with log_path.open("a", encoding="utf-8") as log_fh, failures_path.open(
        "a", newline="", encoding="utf-8"
    ) as failures_fh:
        log = ThreadSafeLog(log_fh)
        if failures_needs_header:
            csv.writer(failures_fh).writerow(FAILURE_HEADER)
            failures_fh.flush()
        failures = ThreadSafeCsv(failures_fh)
        log.write(
            f"\n=== run started {started_iso} pending={len(pending)} "
            f"batches={n_batches} batch_size={args.batch_size} "
            f"workers={args.workers} rate={rate_per_second}rps "
            f"request_timeout={args.request_timeout}s "
            f"skip_elink_screen={'yes' if args.skip_elink_screen else 'no'} "
            f"failures={failures_path} "
            f"key={'yes' if api_key else 'no'} ===\n"
        )

        def run_one(item: tuple[int, list[str], Path]) -> tuple[int, int, int, int, bool]:
            batch_index, batch, chunk_path = item
            n_rows, n_pmids, chunk_written = process_batch(
                batch=batch,
                batch_index=batch_index,
                chunk_path=chunk_path,
                email=args.email,
                tool=DEFAULT_TOOL,
                api_key=api_key,
                sleep_per_request=sleep_per_request,
                log_fh=log,
                efetch_batch_size=args.efetch_batch_size,
                request_timeout=args.request_timeout,
                failure_writer=failures,
                run_started=started_iso,
                skip_elink_screen=args.skip_elink_screen,
            )
            return batch_index, len(batch) if chunk_written else 0, n_rows, n_pmids, chunk_written

        completed = 0
        if args.workers == 1:
            iterator = (run_one(item) for item in all_batches)
        else:
            executor = ThreadPoolExecutor(max_workers=args.workers)
            futures = [executor.submit(run_one, item) for item in all_batches]
            iterator = (future.result() for future in as_completed(futures))

        try:
            for batch_index, n_accessions, n_rows, n_pmids, chunk_written in iterator:
                completed += 1
                if chunk_written:
                    batches_written += 1
                    accessions_processed += n_accessions
                    rows_written += n_rows
                    pmids_returned += n_pmids
                else:
                    log.write(f"batch={batch_index} no_chunk_written\n")

                if completed % 100 == 0 or completed == n_batches:
                    elapsed = time.monotonic() - started_mono
                    batches_per_second = completed / elapsed if elapsed > 0 else 0.0
                    remaining = n_batches - completed
                    eta = remaining / batches_per_second if batches_per_second > 0 else 0.0
                    print(
                        f"batches_done={completed:,} batches_remaining={remaining:,} "
                        f"elapsed_min={elapsed/60:.1f} eta_min={eta/60:.1f} "
                        f"accessions_processed={accessions_processed:,} "
                        f"pmids_returned={pmids_returned:,}",
                        flush=True,
                    )
        finally:
            if args.workers != 1:
                executor.shutdown(wait=True)

        finished_iso = datetime.now(timezone.utc).isoformat()
        log.write(
            f"=== run finished {finished_iso} batches_written={batches_written} "
            f"accessions_processed={accessions_processed} rows_written={rows_written} "
            f"pmids_returned={pmids_returned} ===\n"
        )

    elapsed = time.monotonic() - started_mono
    print(f"Run complete in {elapsed/60:.1f} min.", flush=True)
    print(f"Chunks written this run: {batches_written:,}", flush=True)
    print(f"Accessions processed this run: {accessions_processed:,}", flush=True)
    print(f"Rows written this run: {rows_written:,}", flush=True)
    print(f"PMID links returned this run: {pmids_returned:,}", flush=True)

    if args.dry_run:
        print(f"--dry-run: chunks are in {chunk_dir}; skipping concatenation.", flush=True)
    else:
        concat_chunks(chunk_dir, final_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
