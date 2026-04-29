#!/usr/bin/env python3
"""Create a Stata-friendly minimal table from the global BOLD Fungi TSV."""

from __future__ import annotations

import csv
import re
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
INPUT = PROJECT_ROOT / "Data" / "raw" / "bold" / "bold_global_fungi_records.tsv"
OUTPUT = PROJECT_ROOT / "Data" / "processed" / "bold" / "bold_global_fungi_minimal.tsv"

KEEP = [
    "processid",
    "sampleid",
    "record_id",
    "specimenid",
    "taxid",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
    "identification",
    "identification_rank",
    "collection_date_start",
    "collection_date_end",
    "country/ocean",
    "country_iso",
    "province/state",
    "region",
    "site",
    "coord",
    "elev",
    "habitat",
    "nuc_basecount",
    "insdc_acs",
    "marker_code",
    "sequence_run_site",
    "sequence_upload_date",
    "geopol_denorm.country_iso3",
    "marker_count",
]

OUT_HEADER = [
    "processid",
    "sampleid",
    "record_id",
    "specimenid",
    "taxid",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
    "identification",
    "identification_rank",
    "collection_date_start",
    "collection_date_end",
    "country_ocean",
    "country_iso",
    "province_state",
    "region",
    "site",
    "latitude",
    "longitude",
    "coord_raw",
    "elev",
    "habitat",
    "nuc_basecount",
    "insdc_acs",
    "marker_code",
    "sequence_run_site",
    "sequence_upload_date",
    "country_iso3",
    "marker_count",
]

COORD_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_coord(value: str) -> tuple[str, str]:
    parts = COORD_RE.findall(value or "")
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", ""


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    n_in = 0
    n_out = 0
    n_coord = 0

    with INPUT.open("r", encoding="utf-8", newline="") as src:
        reader = csv.reader(src, delimiter="\t")
        header = next(reader)
        index = {name: i for i, name in enumerate(header)}

        with OUTPUT.open("w", encoding="utf-8", newline="") as dst:
            writer = csv.writer(dst, delimiter="\t", lineterminator="\n")
            writer.writerow(OUT_HEADER)

            for row in reader:
                n_in += 1

                def get(name: str) -> str:
                    i = index.get(name)
                    if i is None or i >= len(row):
                        return ""
                    return row[i]

                coord = get("coord")
                lat, lon = parse_coord(coord)
                if lat and lon:
                    n_coord += 1

                writer.writerow(
                    [
                        get("processid"),
                        get("sampleid"),
                        get("record_id"),
                        get("specimenid"),
                        get("taxid"),
                        get("kingdom"),
                        get("phylum"),
                        get("class"),
                        get("order"),
                        get("family"),
                        get("genus"),
                        get("species"),
                        get("identification"),
                        get("identification_rank"),
                        get("collection_date_start"),
                        get("collection_date_end"),
                        get("country/ocean"),
                        get("country_iso"),
                        get("province/state"),
                        get("region"),
                        get("site"),
                        lat,
                        lon,
                        coord,
                        get("elev"),
                        get("habitat"),
                        get("nuc_basecount"),
                        get("insdc_acs"),
                        get("marker_code"),
                        get("sequence_run_site"),
                        get("sequence_upload_date"),
                        get("geopol_denorm.country_iso3"),
                        get("marker_count"),
                    ]
                )
                n_out += 1

    print(f"Read rows: {n_in:,}")
    print(f"Wrote rows: {n_out:,}")
    print(f"Rows with parsed coordinates: {n_coord:,}")
    print(f"Output: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
