#!/usr/bin/env python3
"""Append BOLD v4 genus splits for oversized Diptera families.

The largest Diptera families exceed the BOLD 1M-record query cap, so they need
to be split below family. This script uses the legacy BOLD v4 taxonomy browser
to scrape child genera and appends the counts to bold_taxon_size_notes.txt.
"""

from __future__ import annotations

import csv
import html
import re
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
OUTDIR = PROJECT_ROOT / "Output" / "audits"
FAMILY_SPLITS = OUTDIR / "bold_v4_insect_order_family_splits.csv"
TARGET_FAMILIES = ["Cecidomyiidae", "Chironomidae", "Phoridae", "Sciaridae"]
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/json,*/*"}


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read().decode("utf-8", errors="replace")


def load_target_taxids() -> dict[str, str]:
    with FAMILY_SPLITS.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    taxids = {}
    for row in rows:
        if row["order"] == "Diptera" and row["family"] in TARGET_FAMILIES:
            taxids[row["family"]] = row["taxid"]
    missing = [family for family in TARGET_FAMILIES if family not in taxids]
    if missing:
        raise RuntimeError(f"Missing target families in {FAMILY_SPLITS}: {missing}")
    return taxids


def parse_genera(family: str, taxid: str) -> list[dict[str, object]]:
    url = f"https://v4.boldsystems.org/index.php/Taxbrowser_Taxonpage?taxid={taxid}"
    text = get_text(url)
    section = re.search(r"Genera \(\d+\).*?</ol>", text, flags=re.S)
    if not section:
        raise RuntimeError(f"Could not find Genera section for {family}")

    rows = []
    for genus_taxid, genus, count in re.findall(
        r'href="\?taxid=(\d+)">([^<\[]+?) \[(\d+)\]</a>',
        section.group(0),
    ):
        rows.append(
            {
                "order": "Diptera",
                "family": family,
                "genus": html.unescape(genus.strip()),
                "taxid": genus_taxid,
                "records_v4_taxbrowser": int(count),
            }
        )
    return sorted(rows, key=lambda row: int(row["records_v4_taxbrowser"]), reverse=True)


def compact_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return str(value)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    taxids = load_target_taxids()
    all_rows = []
    for family in TARGET_FAMILIES:
        rows = parse_genera(family, taxids[family])
        print(f"{family}: {len(rows)} genera")
        all_rows.extend(rows)

    csv_path = OUTDIR / "bold_v4_diptera_large_family_genus_splits.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["order", "family", "genus", "taxid", "records_v4_taxbrowser"],
        )
        writer.writeheader()
        writer.writerows(all_rows)

    txt_path = PROJECT_ROOT / "bold_taxon_size_notes.txt"
    lines = [
        "",
        "",
        "Genus splits for oversized Diptera families",
        "==========================================",
        "",
        "Source note: these genus-level counts come from the legacy BOLD v4",
        "taxonomy browser child-genus lists. They are used to plan downloads",
        "for Diptera families above the 1M-record BOLD Portal query cap and",
        "can differ from BOLD v5 summary counts.",
        f"Full CSV: {csv_path.relative_to(PROJECT_ROOT)}",
        "",
    ]
    for family in TARGET_FAMILIES:
        rows = [row for row in all_rows if row["family"] == family]
        total = sum(int(row["records_v4_taxbrowser"]) for row in rows)
        lines.extend(
            [
                f"{family} genera",
                "-" * (len(family) + 7),
                "",
                f"Genera listed: {len(rows)}; summed genus records: {total:,}.",
                "",
                "| Genus | Records |",
                "|---|---:|",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row['genus']} | {compact_count(int(row['records_v4_taxbrowser']))} |"
            )
        lines.append("")

    with txt_path.open("a", encoding="utf-8") as output:
        output.write("\n".join(lines))
        output.write("\n")

    print(f"Wrote CSV: {csv_path}")
    print(f"Appended: {txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
