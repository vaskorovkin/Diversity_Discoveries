#!/usr/bin/env python3
"""Summarize BOLD v4 taxonomy-browser family splits for selected insect orders.

The current BOLD Portal summary endpoint does not aggregate by family. The v4
taxonomy browser page exposes child-family counts in the form "Family [count]".
These counts are taxonomy-browser specimen counts and can differ from BOLD v5
Portal summary counts used elsewhere in the project.
"""

from __future__ import annotations

import csv
import html
import re
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
OUTDIR = PROJECT_ROOT / "Output" / "audits"
ORDERS = ["Diptera", "Hymenoptera", "Lepidoptera", "Coleoptera", "Hemiptera"]
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/json,*/*"}


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


def find_order_taxid(order: str) -> str:
    url = "https://v4.boldsystems.org/index.php/API_Tax/TaxonSearch?" + urllib.parse.urlencode(
        {"taxName": order}
    )
    text = get_text(url)
    match = re.search(r'"taxid"\s*:\s*(\d+).*?"taxon"\s*:\s*"' + re.escape(order) + r'"', text)
    if not match:
        raise RuntimeError(f"Could not find BOLD taxid for {order}")
    return match.group(1)


def parse_families(order: str, taxid: str) -> list[dict[str, object]]:
    url = f"https://v4.boldsystems.org/index.php/Taxbrowser_Taxonpage?taxid={taxid}"
    text = get_text(url)
    section = re.search(r"Families \(\d+\).*?</ol>", text, flags=re.S)
    if not section:
        raise RuntimeError(f"Could not find Families section for {order}")

    rows = []
    for taxid_child, family, count in re.findall(
        r'href="\?taxid=(\d+)">([^<\[]+?) \[(\d+)\]</a>',
        section.group(0),
    ):
        rows.append(
            {
                "order": order,
                "family": html.unescape(family.strip()),
                "taxid": taxid_child,
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
    all_rows = []
    for order in ORDERS:
        taxid = find_order_taxid(order)
        rows = parse_families(order, taxid)
        print(f"{order}: {len(rows)} families")
        all_rows.extend(rows)

    csv_path = OUTDIR / "bold_v4_insect_order_family_splits.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["order", "family", "taxid", "records_v4_taxbrowser"],
        )
        writer.writeheader()
        writer.writerows(all_rows)

    txt_path = PROJECT_ROOT / "bold_taxon_size_notes.txt"
    lines = [
        "",
        "",
        "Family splits for large insect orders",
        "====================================",
        "",
        "Source note: these family-level counts come from the legacy BOLD v4",
        "taxonomy browser child-family lists, because the current BOLD Portal",
        "summary endpoint does not aggregate by family. These are taxonomy-browser",
        "specimen counts and can differ from the BOLD v5 summary counts above.",
        f"Full CSV: {csv_path.relative_to(PROJECT_ROOT)}",
        "",
    ]
    for order in ORDERS:
        rows = [row for row in all_rows if row["order"] == order]
        total = sum(int(row["records_v4_taxbrowser"]) for row in rows)
        lines.extend(
            [
                f"{order} families",
                "-" * (len(order) + 9),
                "",
                f"Families listed: {len(rows)}; summed family records: {total:,}.",
                "",
                "| Family | Records |",
                "|---|---:|",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row['family']} | {compact_count(int(row['records_v4_taxbrowser']))} |"
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
