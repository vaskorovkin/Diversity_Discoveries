#!/usr/bin/env python3
"""Count genus values in a BOLD TSV export."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()

    counts: Counter[str] = Counter()
    rows = 0
    with args.input.open("r", newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if "genus" not in (reader.fieldnames or []):
            raise RuntimeError(f"No genus column found in {args.input}")
        for row in reader:
            rows += 1
            genus = (row.get("genus") or "").strip() or "<blank>"
            counts[genus] += 1

    print(f"Rows: {rows:,}")
    print(f"Genera: {len(counts):,}")
    print("")
    print("Top genera:")
    for genus, count in counts.most_common(args.top):
        print(f"{genus}\t{count}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["genus", "records"])
            writer.writerows(counts.most_common())
        print("")
        print(f"Wrote: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
