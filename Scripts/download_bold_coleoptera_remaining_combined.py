#!/usr/bin/env python3
"""Download currently missing Coleoptera families as one combined BOLD query.

This reads the Coleoptera family manifest, removes families that already have
completed family-level TSV files, and sends one semicolon-separated BOLD query
for the remaining families.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
from pathlib import Path

from download_bold_fungi import (
    API_BASE,
    MAX_RECORDS_PER_QUERY,
    PROJECT_ROOT,
    SUMMARY_FIELDS,
    api_get_json,
    download_stream,
    write_json,
)


DEFAULT_FAMILY_DIR = PROJECT_ROOT / "Data" / "raw" / "bold" / "coleoptera_by_family"
DEFAULT_STEM = "bold_global_coleoptera_remaining_combined"
FAMILY_NAME_RE = re.compile(r"^[A-Za-z]+idae$")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def read_manifest(path: Path) -> list[str]:
    import csv

    with path.open("r", newline="", encoding="utf-8") as f:
        return [row["family"] for row in csv.DictReader(f) if row.get("family")]


def missing_families(family_dir: Path, manifest_path: Path) -> list[str]:
    families = read_manifest(manifest_path)
    missing = []
    for family in families:
        expected = family_dir / f"bold_global_coleoptera_family_{slug(family)}_records.tsv"
        if not expected.exists():
            missing.append(family)
    return missing


def combined_query(families: list[str]) -> str:
    return ";".join(f"tax:family:{family}" for family in families)


def split_standard_families(families: list[str]) -> tuple[list[str], list[str]]:
    standard = []
    skipped = []
    for family in families:
        if FAMILY_NAME_RE.match(family):
            standard.append(family)
        else:
            skipped.append(family)
    return standard, skipped


def summarize_query(query: str, timeout: int) -> dict:
    return api_get_json(
        "/summary",
        {"query": query, "fields": SUMMARY_FIELDS},
        timeout=timeout,
    )


def is_422(exc: BaseException) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code == 422


def find_valid_families(families: list[str], timeout: int) -> tuple[list[str], list[str]]:
    """Return valid and invalid family terms using recursive 422 bisection."""
    if not families:
        return [], []
    query = combined_query(families)
    try:
        summarize_query(query, timeout)
        return families, []
    except urllib.error.HTTPError as exc:
        if not is_422(exc):
            raise
        if len(families) == 1:
            return [], families

    middle = len(families) // 2
    left_valid, left_invalid = find_valid_families(families[:middle], timeout)
    right_valid, right_invalid = find_valid_families(families[middle:], timeout)
    return left_valid + right_valid, left_invalid + right_invalid


def split_valid_chunks(families: list[str], timeout: int) -> list[tuple[list[str], dict]]:
    """Split families into the fewest recursively validated chunks.

    A 422 on the full list, followed by zero invalid single-family terms, means
    BOLD is rejecting the combined query size/complexity. In that case the best
    we can do is split into larger valid subqueries.
    """
    if not families:
        return []
    try:
        summary = summarize_query(combined_query(families), timeout)
        return [(families, summary)]
    except urllib.error.HTTPError as exc:
        if not is_422(exc):
            raise
        if len(families) == 1:
            raise

    middle = len(families) // 2
    return (
        split_valid_chunks(families[:middle], timeout)
        + split_valid_chunks(families[middle:], timeout)
    )


def summary_counts(summary: dict) -> tuple[int, int, float]:
    n_records = int(summary.get("counts", {}).get("specimens", 0) or 0)
    n_coord = sum(int(v) for v in summary.get("coord", {}).values())
    coord_share = 100 * n_coord / n_records if n_records else 0.0
    return n_records, n_coord, coord_share


def download_query(
    query: str,
    summary: dict,
    output_path: Path,
    query_path: Path,
    fmt: str,
    timeout: int,
    force: bool,
) -> None:
    if output_path.exists() and not force:
        print(f"Output exists, skipping: {output_path}")
        return

    n_records, n_coord, coord_share = summary_counts(summary)
    print(f"Combined query: {n_records:,} records; {n_coord:,} coords ({coord_share:.1f}%)")
    if n_records == 0:
        return
    if n_records > MAX_RECORDS_PER_QUERY:
        raise RuntimeError(
            f"Combined query exceeds {MAX_RECORDS_PER_QUERY:,}-record cap; split further"
        )

    query_payload = api_get_json(
        "/query",
        {"query": query, "extent": "full"},
        timeout=timeout,
    )
    write_json(query_path, query_payload)
    query_id = query_payload.get("query_id")
    if not query_id:
        raise RuntimeError(f"No query_id returned: {json.dumps(query_payload)}")

    download_url = (
        f"{API_BASE}/documents/{urllib.parse.quote(query_id, safe='')}/download"
        f"?{urllib.parse.urlencode({'format': fmt})}"
    )
    print(f"Downloading to: {output_path}")
    download_stream(download_url, output_path, timeout=timeout)
    print(f"Done: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-dir", type=Path, default=DEFAULT_FAMILY_DIR)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--stem", default=DEFAULT_STEM)
    parser.add_argument("--format", default="tsv", choices=["tsv", "json", "dwc"])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--include-nonstandard",
        action="store_true",
        help="Include taxonomy-browser buckets such as unclassified Coleoptera.",
    )
    parser.add_argument(
        "--no-auto-drop-invalid",
        action="store_true",
        help="Do not diagnose and drop BOLD terms that produce HTTP 422.",
    )
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    family_dir = args.family_dir
    manifest_path = args.manifest or family_dir / "coleoptera_family_manifest.csv"
    family_dir.mkdir(parents=True, exist_ok=True)

    all_missing = missing_families(family_dir, manifest_path)
    families, skipped = split_standard_families(all_missing)
    if args.include_nonstandard:
        families = all_missing
        skipped = []
    query = combined_query(families)
    print(f"Missing manifest rows: {len(all_missing)}")
    print(f"Families in combined query: {len(families)}")
    if skipped:
        skipped_path = family_dir / f"{args.stem}_skipped_nonstandard.txt"
        skipped_path.write_text("\n".join(skipped) + "\n", encoding="utf-8")
        print(f"Skipped nonstandard taxonomy-browser buckets: {len(skipped)}")
        print(f"Skipped list: {skipped_path}")
    if not families:
        print("Nothing to download.")
        return 0

    families_path = family_dir / f"{args.stem}_families.txt"
    families_path.write_text("\n".join(families) + "\n", encoding="utf-8")
    write_json(
        family_dir / f"{args.stem}_query_terms.json",
        {"families": families, "skipped": skipped, "query": query},
    )

    chunks = None
    try:
        chunks = [(families, summarize_query(query, args.timeout))]
    except urllib.error.HTTPError as exc:
        if not is_422(exc) or args.no_auto_drop_invalid:
            raise
        print("Combined query returned HTTP 422; diagnosing invalid family terms.")
        valid, invalid = find_valid_families(families, args.timeout)
        invalid_path = family_dir / f"{args.stem}_invalid_bold_terms.txt"
        invalid_path.write_text("\n".join(invalid) + "\n", encoding="utf-8")
        print(f"Invalid BOLD family terms dropped: {len(invalid)}")
        print(f"Invalid list: {invalid_path}")
        families = valid
        query = combined_query(families)
        families_path.write_text("\n".join(families) + "\n", encoding="utf-8")
        write_json(
            family_dir / f"{args.stem}_query_terms.json",
            {"families": families, "skipped": skipped, "invalid": invalid, "query": query},
        )
        if not families:
            print("No valid families remain after 422 diagnosis.")
            return 1
        print(f"Families in repaired combined query: {len(families)}")
        try:
            chunks = [(families, summarize_query(query, args.timeout))]
        except urllib.error.HTTPError as repaired_exc:
            if not is_422(repaired_exc):
                raise
            print(
                "BOLD still rejects the full valid-family query; splitting into "
                "larger valid combined chunks."
            )
            chunks = split_valid_chunks(families, args.timeout)

    assert chunks is not None
    chunk_payload = []
    for index, (chunk_families, summary) in enumerate(chunks, start=1):
        chunk_query = combined_query(chunk_families)
        n_records, n_coord, coord_share = summary_counts(summary)
        chunk_payload.append(
            {
                "part": index,
                "families": chunk_families,
                "query": chunk_query,
                "records": n_records,
                "records_with_coordinates": n_coord,
                "coordinate_coverage_percent": f"{coord_share:.1f}",
            }
        )
    write_json(family_dir / f"{args.stem}_chunks.json", {"chunks": chunk_payload})

    print(f"Valid combined chunks: {len(chunks)}")
    if len(chunks) == 1:
        write_json(family_dir / f"{args.stem}_summary.json", chunks[0][1])
    else:
        for index, (_, summary) in enumerate(chunks, start=1):
            write_json(family_dir / f"{args.stem}_part{index:02d}_summary.json", summary)

    if args.summary_only:
        return 0

    for index, (chunk_families, summary) in enumerate(chunks, start=1):
        chunk_query = combined_query(chunk_families)
        if len(chunks) == 1:
            output_path = family_dir / f"{args.stem}_records.{args.format}"
            query_path = family_dir / f"{args.stem}_query.json"
        else:
            output_path = family_dir / f"{args.stem}_part{index:02d}_records.{args.format}"
            query_path = family_dir / f"{args.stem}_part{index:02d}_query.json"
            print(f"Chunk {index}/{len(chunks)}: {len(chunk_families)} families")
        download_query(
            chunk_query,
            summary,
            output_path,
            query_path,
            args.format,
            args.timeout,
            args.force,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
