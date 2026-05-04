#!/usr/bin/env python3
"""Build a person-level collector file from top raw BOLD collector strings.

Input:
    Data/processed/bold/bold_top500_collectors.csv

Output:
    Data/processed/bold/bold_top500_collector_individuals.csv

The input file contains raw collector strings, many of which include multiple
people (for example: "D.Janzen, W.Hallwachs, J.A.Solano"). This script splits
those strings into person-level tokens and aggregates record counts across all
collector strings where the same person appears.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_utils import PROCESSED_BOLD


DEFAULT_INPUT = PROCESSED_BOLD / "bold_top500_collectors.csv"
DEFAULT_OUTPUT = PROCESSED_BOLD / "bold_top500_collector_individuals.csv"

NON_PERSON_PATTERNS = [
    re.compile(r"(?i)\b(?:team|program|survey|project|collection|museum|herbarium|institute|university)\b"),
    re.compile(r"(?i)\b(?:unknown|anonymous|not available|no voucher|n/?a)\b"),
]


def clean_token(token: str) -> str:
    token = re.sub(r"\s+", " ", (token or "").strip())
    token = token.strip(" ,;:|/")
    token = re.sub(r"\s+\.$", "", token)
    return token


def looks_like_person(token: str) -> bool:
    if not token:
        return False
    if any(pat.search(token) for pat in NON_PERSON_PATTERNS):
        return False
    if token.isupper() and len(token) <= 10:
        return False
    if re.fullmatch(r"[A-Z0-9 .'\-]+", token) and len(token.split()) == 1 and "." not in token:
        return False
    return bool(re.search(r"[A-Za-z]", token))


def split_collectors(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []

    normalized = raw.replace("&", ",").replace(";", ",")
    normalized = re.sub(r"\s+\band\b\s+", ",", normalized, flags=re.I)
    tokens = [clean_token(part) for part in normalized.split(",")]
    tokens = [token for token in tokens if looks_like_person(token)]

    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-n", type=int, default=500, help="Use only the first N rows of the raw collector file.")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Missing input file: {args.input}")

    total_records_with_people = 0
    individual_counts: Counter[str] = Counter()
    raw_string_count: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    n_rows_used = 0

    with args.input.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for i, row in enumerate(reader, 1):
            if i > args.top_n:
                break
            n_rows_used += 1
            raw_collector = (row.get("collector") or "").strip()
            record_count = int(float(row.get("record_count") or 0))
            people = split_collectors(raw_collector)
            if not people:
                continue
            total_records_with_people += record_count
            for person in people:
                individual_counts[person] += record_count
                raw_string_count[person] += 1
                if len(examples[person]) < 3 and raw_collector not in examples[person]:
                    examples[person].append(raw_collector)

    ranked = individual_counts.most_common()
    total_individual_weight = sum(individual_counts.values())
    cumulative = 0.0
    rows: list[dict[str, object]] = []
    for rank, (person, count) in enumerate(ranked, 1):
        share = count / total_individual_weight if total_individual_weight else 0.0
        cumulative += share
        rows.append(
            {
                "rank": rank,
                "collector_name": person,
                "record_count_total": count,
                "record_share_among_split_people": round(share, 6),
                "cumulative_share_among_split_people": round(cumulative, 6),
                "raw_collector_string_count": raw_string_count[person],
                "example_collector_strings": " | ".join(examples[person]),
                "affiliation_guess": "",
                "country_iso3": "",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "collector_name",
        "record_count_total",
        "record_share_among_split_people",
        "cumulative_share_among_split_people",
        "raw_collector_string_count",
        "example_collector_strings",
        "affiliation_guess",
        "country_iso3",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Read: {args.input}", flush=True)
    print(f"Top raw collector rows used: {n_rows_used}", flush=True)
    print(f"Unique split individuals: {len(rows):,}", flush=True)
    print(f"Raw record total in split rows: {total_records_with_people:,}", flush=True)
    print(f"Individual-weight total: {total_individual_weight:,}", flush=True)
    print(f"Wrote: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
