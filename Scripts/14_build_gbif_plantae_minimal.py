#!/usr/bin/env python3
"""Build a minimal plant occurrence file from a GBIF Darwin Core Archive.

This streams the GBIF occurrence.txt table and keeps only the fields needed for
the project's downstream summaries and panel work.

Default input:
    Data/raw/gbif/plantae/gbif_plantae_preserved_material_dwca_2005_2025/occurrence.txt

Default output:
    Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv

Default summary:
    Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_dwca_2005_2025"
    / "occurrence.txt"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal.csv"
)
DEFAULT_SUMMARY = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "gbif"
    / "plantae"
    / "gbif_plantae_preserved_material_minimal_summary.csv"
)


FIELD_MAP = [
    ("gbifID", "gbif_id"),
    ("datasetKey", "dataset_key"),
    ("datasetName", "dataset_name"),
    ("publisher", "publisher"),
    ("license", "license"),
    ("basisOfRecord", "basis_of_record"),
    ("occurrenceStatus", "occurrence_status"),
    ("institutionCode", "institution_code"),
    ("collectionCode", "collection_code"),
    ("catalogNumber", "catalog_number"),
    ("recordNumber", "record_number"),
    ("recordedBy", "recorded_by"),
    ("identifiedBy", "identified_by"),
    ("eventDate", "event_date"),
    ("year", "year"),
    ("month", "month"),
    ("day", "day"),
    ("countryCode", "country_code"),
    ("stateProvince", "state_province"),
    ("county", "county"),
    ("municipality", "municipality"),
    ("locality", "locality"),
    ("decimalLatitude", "latitude"),
    ("decimalLongitude", "longitude"),
    ("coordinateUncertaintyInMeters", "coordinate_uncertainty_m"),
    ("geodeticDatum", "geodetic_datum"),
    ("scientificName", "scientific_name"),
    ("taxonKey", "taxon_key"),
    ("kingdom", "kingdom"),
    ("phylum", "phylum"),
    ("class", "class_name"),
    ("order", "order"),
    ("family", "family"),
    ("genus", "genus"),
    ("species", "species"),
    ("acceptedScientificName", "accepted_scientific_name"),
    ("acceptedTaxonKey", "accepted_taxon_key"),
]


def parse_year(value: str) -> str:
    value = (value or "").strip()
    if len(value) >= 4 and value[:4].isdigit():
        year = int(value[:4])
        if 1800 <= year <= 2100:
            return str(year)
    return ""


def parse_coord(lat: str, lon: str) -> tuple[str, str, str]:
    lat = (lat or "").strip()
    lon = (lon or "").strip()
    if not lat or not lon:
        return "", "", "0"
    try:
        f_lat = float(lat)
        f_lon = float(lon)
    except ValueError:
        return "", "", "0"
    if not (-90 <= f_lat <= 90 and -180 <= f_lon <= 180):
        return "", "", "0"
    return f"{f_lat:.8g}", f"{f_lon:.8g}", "1"


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--chunksize", type=int, default=200_000)
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Missing GBIF occurrence file: {args.input}")

    csv.field_size_limit(100_000_000)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    rows_with_coords = 0
    rows_with_country = 0
    rows_with_year = 0
    basis_counts: dict[str, int] = {}

    out_fields = [new for _, new in FIELD_MAP] + ["has_coord"]

    with args.input.open(newline="", encoding="utf-8") as src, args.output.open("w", newline="", encoding="utf-8") as dst:
        reader = csv.reader(src, delimiter="\t")
        header = next(reader)
        header_idx = {name: i for i, name in enumerate(header)}
        required = {
            "gbifID",
            "datasetKey",
            "datasetName",
            "publisher",
            "license",
            "basisOfRecord",
            "occurrenceStatus",
            "institutionCode",
            "collectionCode",
            "catalogNumber",
            "recordNumber",
            "recordedBy",
            "identifiedBy",
            "eventDate",
            "year",
            "month",
            "day",
            "countryCode",
            "stateProvince",
            "county",
            "municipality",
            "locality",
            "decimalLatitude",
            "decimalLongitude",
            "coordinateUncertaintyInMeters",
            "scientificName",
            "taxonKey",
            "kingdom",
            "phylum",
            "class",
            "order",
            "family",
            "genus",
            "species",
            "acceptedScientificName",
            "acceptedTaxonKey",
        }
        missing = [orig for orig in required if orig not in header_idx]
        if missing:
            raise ValueError(f"Missing expected columns in GBIF archive: {missing[:20]}")

        writer = csv.writer(dst)
        writer.writerow(out_fields)

        for row_num, row in enumerate(reader, 1):
            total_rows += 1
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))

            lat_raw = row[header_idx["decimalLatitude"]]
            lon_raw = row[header_idx["decimalLongitude"]]
            lat_clean, lon_clean, has_coord = parse_coord(lat_raw, lon_raw)
            if has_coord == "1":
                rows_with_coords += 1

            country = clean(row[header_idx["countryCode"]])
            if country:
                rows_with_country += 1

            year = clean(row[header_idx["year"]])
            if not year:
                year = parse_year(row[header_idx["eventDate"]])
            if year:
                rows_with_year += 1

            basis = clean(row[header_idx["basisOfRecord"]])
            basis_counts[basis] = basis_counts.get(basis, 0) + 1

            out_row = []
            for orig, _new in FIELD_MAP:
                if orig == "decimalLatitude":
                    out_row.append(lat_clean)
                elif orig == "decimalLongitude":
                    out_row.append(lon_clean)
                elif orig == "year":
                    out_row.append(year)
                elif orig not in header_idx:
                    out_row.append("")
                else:
                    out_row.append(clean(row[header_idx[orig]]))
            out_row.append(has_coord)
            writer.writerow(out_row)

            if row_num % args.chunksize == 0:
                print(
                    f"  rows {row_num:,}: coords={rows_with_coords:,}, year={rows_with_year:,}, country={rows_with_country:,}",
                    flush=True,
                )

    basis_rows = [
        {"basis_of_record": basis, "count": count}
        for basis, count in sorted(basis_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    with args.summary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(
            [
                {"metric": "raw_rows", "value": total_rows},
                {"metric": "rows_with_coords", "value": rows_with_coords},
                {"metric": "rows_with_country", "value": rows_with_country},
                {"metric": "rows_with_year", "value": rows_with_year},
                {"metric": "unique_basis_of_record", "value": len(basis_counts)},
            ]
        )

    basis_path = args.summary.with_name(args.summary.stem + "_basis_counts.csv")
    with basis_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["basis_of_record", "count"])
        writer.writeheader()
        writer.writerows(basis_rows)

    print(f"Wrote minimal plant file: {args.output}", flush=True)
    print(f"Wrote summary: {args.summary}", flush=True)
    print(f"Wrote basis counts: {basis_path}", flush=True)
    print(f"Rows: {total_rows:,}", flush=True)
    print(f"Rows with coords: {rows_with_coords:,}", flush=True)
    print(f"Rows with country: {rows_with_country:,}", flush=True)
    print(f"Rows with year: {rows_with_year:,}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
