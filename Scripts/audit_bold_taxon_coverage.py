#!/usr/bin/env python3
"""Audit local BOLD downloads against the intended taxon coverage plan.

This is a local file/manifest audit. It does not query BOLD. The four oversized
Diptera families are reported as intentionally excluded because they still need
a separate split strategy.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
BOLD_DIR = PROJECT_ROOT / "Data" / "raw" / "bold"
AUDIT_DIR = PROJECT_ROOT / "Output" / "audits"

EXCLUDED_DIPTERA = {"Cecidomyiidae", "Chironomidae", "Phoridae", "Sciaridae"}

BROAD_DOWNLOADS = [
    ("kingdom", "Fungi", "bold_global_fungi"),
    ("kingdom", "Plantae", "bold_global_plantae"),
    ("phylum", "Mollusca", "bold_global_mollusca"),
    ("phylum", "Chordata", "bold_global_chordata"),
]

ANIMAL_PHYLA = [
    "Annelida",
    "Cnidaria",
    "Echinodermata",
    "Nematoda",
    "Platyhelminthes",
    "Porifera",
    "Rotifera",
    "Bryozoa",
    "Nemertea",
    "Tardigrada",
    "Onychophora",
    "Acanthocephala",
    "Brachiopoda",
    "Chaetognatha",
    "Ctenophora",
    "Entoprocta",
    "Gastrotricha",
    "Hemichordata",
    "Kinorhyncha",
    "Phoronida",
    "Priapulida",
    "Xenacoelomorpha",
]

SMALL_INSECT_ORDERS = [
    "Psocodea",
    "Orthoptera",
    "Trichoptera",
    "Thysanoptera",
    "Blattodea",
    "Ephemeroptera",
    "Neuroptera",
    "Odonata",
    "Plecoptera",
]

NON_INSECT_ARTHROPODS_AND_MICROBES = [
    "Araneae",
    "Acari",
    "Scorpiones",
    "Opiliones",
    "Pseudoscorpiones",
    "Decapoda",
    "Amphipoda",
    "Isopoda",
    "Copepoda",
    "Ostracoda",
    "Chilopoda",
    "Diplopoda",
    "Symphyla",
    "Pauropoda",
    "Pycnogonida",
    "Xiphosura",
    "Chromista",
    "Protozoa",
    "Archaea",
    "Bacteria",
]

FAMILY_GROUPS = [
    ("Coleoptera", BOLD_DIR / "coleoptera_by_family", "coleoptera"),
    ("Hemiptera", BOLD_DIR / "hemiptera_by_family", "hemiptera"),
    ("Hymenoptera", BOLD_DIR / "hymenoptera_by_family", "hymenoptera"),
    ("Lepidoptera", BOLD_DIR / "lepidoptera_by_family", "lepidoptera"),
    ("Diptera", BOLD_DIR / "diptera_by_family", "diptera"),
]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_by(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        if row.get(key):
            latest[row[key]] = row
    return latest


def read_summary_json(stem: str) -> tuple[str, str]:
    path = BOLD_DIR / f"{stem}_summary.json"
    if not path.exists():
        return "", ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = str(payload.get("counts", {}).get("specimens", ""))
    coord = payload.get("coord", {})
    records_with_coordinates = ""
    if isinstance(coord, dict):
        try:
            records_with_coordinates = str(sum(int(v) for v in coord.values()))
        except (TypeError, ValueError):
            records_with_coordinates = ""
    return records, records_with_coordinates


def output_status(path: Path) -> tuple[bool, bool, int]:
    part = Path(str(path) + ".part")
    exists = path.exists()
    part_exists = part.exists()
    size = path.stat().st_size if exists else 0
    return exists, part_exists, size


def row(
    group: str,
    rank: str,
    taxon: str,
    expected_records_hint: str,
    records_v5_summary: str,
    records_with_coordinates: str,
    status: str,
    output_path: Path | None,
    issue: str,
    note: str = "",
) -> dict[str, object]:
    exists = False
    part_exists = False
    size = 0
    if output_path is not None:
        exists, part_exists, size = output_status(output_path)
    return {
        "group": group,
        "rank": rank,
        "taxon": taxon,
        "expected_records_hint": expected_records_hint,
        "records_v5_summary": records_v5_summary,
        "records_with_coordinates": records_with_coordinates,
        "status": status,
        "output_exists": int(exists),
        "partial_exists": int(part_exists),
        "output_size_bytes": size,
        "issue": issue,
        "note": note,
        "output_path": str(output_path.relative_to(PROJECT_ROOT)) if output_path else "",
    }


def audit_broad(rows: list[dict[str, object]]) -> None:
    for rank, taxon, stem in BROAD_DOWNLOADS:
        records, coord = read_summary_json(stem)
        path = BOLD_DIR / f"{stem}_records.tsv"
        exists, part_exists, _ = output_status(path)
        issue = "ok_downloaded" if exists and not part_exists else "missing_file"
        if part_exists:
            issue = "partial_file"
        rows.append(row("broad", rank, taxon, records, records, coord, "downloaded", path, issue))


def audit_animal_phyla(rows: list[dict[str, object]]) -> None:
    outdir = BOLD_DIR / "animals_except_acm"
    summary = latest_by(read_csv(outdir / "bold_animals_except_acm_summary.csv"), "phylum")
    for phylum in ANIMAL_PHYLA:
        srow = summary.get(phylum, {})
        records = srow.get("records", "")
        coord = srow.get("records_with_coordinates", "")
        path = outdir / f"bold_global_{slug(phylum)}_records.tsv"
        exists, part_exists, _ = output_status(path)
        if str(records) == "0":
            issue = "ok_empty_in_bold_v5"
            status = "empty"
            path_for_row: Path | None = path
        else:
            issue = "ok_downloaded" if exists and not part_exists else "missing_file"
            if part_exists:
                issue = "partial_file"
            status = "downloaded"
            path_for_row = path
        rows.append(row("animals_except_acm", "phylum", phylum, records, records, coord, status, path_for_row, issue))


def audit_small_insect_orders(rows: list[dict[str, object]]) -> None:
    outdir = BOLD_DIR / "insect_orders_small"
    summary = latest_by(read_csv(outdir / "bold_insect_orders_small_summary.csv"), "order")
    for order in SMALL_INSECT_ORDERS:
        srow = summary.get(order, {})
        records = srow.get("records", "")
        coord = srow.get("records_with_coordinates", "")
        path = outdir / f"bold_global_{slug(order)}_records.tsv"
        exists, part_exists, _ = output_status(path)
        issue = "ok_downloaded" if exists and not part_exists else "missing_file"
        if str(records) == "0":
            issue = "ok_empty_in_bold_v5"
        if part_exists:
            issue = "partial_file"
        rows.append(row("small_insect_orders", "order", order, records, records, coord, "downloaded", path, issue))


def audit_non_insect_arthropods_and_microbes(rows: list[dict[str, object]]) -> None:
    outdir = BOLD_DIR / "non_insect_arthropods_and_microbes"
    summary = latest_by(read_csv(outdir / "non_insect_arthropods_and_microbes_summary.csv"), "group")
    for taxon in NON_INSECT_ARTHROPODS_AND_MICROBES:
        srow = summary.get(taxon, {})
        records = srow.get("records", "")
        coord = srow.get("records_with_coordinates", "")
        status = srow.get("status", "")
        path = outdir / f"bold_global_{slug(taxon)}_records.tsv"
        exists, part_exists, _ = output_status(path)
        if status == "empty" or str(records) == "0":
            issue = "ok_empty_in_bold_v5"
        else:
            issue = "ok_downloaded" if exists and not part_exists else "missing_file"
        if part_exists:
            issue = "partial_file"
        rows.append(row("non_insect_arthropods_and_microbes", "mixed", taxon, records, records, coord, status, path, issue))


def audit_family_group(
    rows: list[dict[str, object]],
    group: str,
    outdir: Path,
    prefix: str,
) -> None:
    manifest = read_csv(outdir / f"{prefix}_family_manifest.csv")
    summary = latest_by(read_csv(outdir / f"{prefix}_family_download_summary.csv"), "family")
    failed = latest_by(read_csv(outdir / f"{prefix}_family_failed_downloads.csv"), "family")
    for mrow in manifest:
        family = mrow["family"]
        records_hint = mrow.get("records_v4_taxbrowser", "")
        path = outdir / f"bold_global_{prefix}_family_{slug(family)}_records.tsv"
        if group == "Diptera" and family in EXCLUDED_DIPTERA:
            rows.append(
                row(
                    group,
                    "family",
                    family,
                    records_hint,
                    "",
                    "",
                    "excluded_over_cap",
                    None,
                    "excluded_over_cap",
                    "Known over 1M; still needs split strategy.",
                )
            )
            continue

        srow = summary.get(family, {})
        records_v5 = srow.get("records_v5_summary", "")
        coord = srow.get("records_with_coordinates", "")
        status = srow.get("status", "")
        exists, part_exists, _ = output_status(path)
        fail = failed.get(family, {})

        if status == "empty" or records_v5 == "0":
            issue = "ok_empty_in_bold_v5"
            note = "v4 taxonomy browser had records, but BOLD v5 summary returned 0." if records_hint not in ("", "0") else ""
        elif exists and not part_exists:
            issue = "ok_downloaded"
            note = ""
            if fail:
                issue = "ok_downloaded_stale_failed_log"
                note = f"Earlier failed log says: {fail.get('error', '')}"
        else:
            issue = "missing_file"
            note = ""
            if fail:
                note = f"Failed log says: {fail.get('error', '')}"
        if part_exists:
            issue = "partial_file"

        rows.append(row(group, "family", family, records_hint, records_v5, coord, status, path, issue, note))


def write_outputs(rows: list[dict[str, object]]) -> tuple[Path, Path]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = AUDIT_DIR / "bold_taxon_coverage_audit.csv"
    md_path = AUDIT_DIR / "bold_taxon_coverage_audit.md"

    fieldnames = [
        "group",
        "rank",
        "taxon",
        "expected_records_hint",
        "records_v5_summary",
        "records_with_coordinates",
        "status",
        "output_exists",
        "partial_exists",
        "output_size_bytes",
        "issue",
        "note",
        "output_path",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(str(r["issue"]) for r in rows)
    by_group_issue = Counter((str(r["group"]), str(r["issue"])) for r in rows)
    problem_rows = [
        r
        for r in rows
        if r["issue"] not in {"ok_downloaded", "ok_empty_in_bold_v5", "excluded_over_cap"}
    ]
    missing_rows = [r for r in rows if r["issue"] in {"missing_file", "partial_file"}]

    lines = [
        "# BOLD taxon coverage audit",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "This is a local audit of the intended BOLD coverage plan. It does not query BOLD.",
        "The four oversized Diptera families are intentionally excluded: "
        + ", ".join(sorted(EXCLUDED_DIPTERA))
        + ".",
        "",
        "## Issue counts",
        "",
        "| Issue | Count |",
        "|---|---:|",
    ]
    for issue, count in sorted(counts.items()):
        lines.append(f"| {issue} | {count} |")

    lines.extend(["", "## Group by issue", "", "| Group | Issue | Count |", "|---|---|---:|"])
    for (group, issue), count in sorted(by_group_issue.items()):
        lines.append(f"| {group} | {issue} | {count} |")

    lines.extend(["", "## Missing or partial files", "", "| Group | Rank | Taxon | Issue | Note |", "|---|---|---|---|---|"])
    if missing_rows:
        for r in missing_rows:
            lines.append(f"| {r['group']} | {r['rank']} | {r['taxon']} | {r['issue']} | {r['note']} |")
    else:
        lines.append("| none |  |  |  |  |")

    stale_rows = [r for r in rows if r["issue"] == "ok_downloaded_stale_failed_log"]
    lines.extend(["", "## Downloaded but still listed in failed logs", "", "| Group | Taxon | Note |", "|---|---|---|"])
    if stale_rows:
        for r in stale_rows:
            lines.append(f"| {r['group']} | {r['taxon']} | {r['note']} |")
    else:
        lines.append("| none |  |  |")

    zero_rows = [r for r in rows if r["issue"] == "ok_empty_in_bold_v5" and r["expected_records_hint"] not in ("", "0")]
    lines.extend(["", "## V4 listed records but BOLD v5 summary is zero", "", "| Group | Taxon | V4 hint |", "|---|---|---:|"])
    if zero_rows:
        for r in zero_rows:
            lines.append(f"| {r['group']} | {r['taxon']} | {r['expected_records_hint']} |")
    else:
        lines.append("| none |  |  |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def main() -> int:
    rows: list[dict[str, object]] = []
    audit_broad(rows)
    audit_animal_phyla(rows)
    audit_small_insect_orders(rows)
    audit_non_insect_arthropods_and_microbes(rows)
    for group, outdir, prefix in FAMILY_GROUPS:
        audit_family_group(rows, group, outdir, prefix)
    csv_path, md_path = write_outputs(rows)
    counts = Counter(str(r["issue"]) for r in rows)
    print(f"Audited taxa: {len(rows)}")
    for issue, count in sorted(counts.items()):
        print(f"{issue}: {count}")
    print(f"CSV: {csv_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
