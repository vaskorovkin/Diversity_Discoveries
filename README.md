# Diversity Discoveries

This project builds micro data for studying how biodiversity enters scientific sampling and discovery systems. The current working data source is BOLD public barcode metadata, used to prototype sampling geography at species/taxon, grid-cell, and year levels.

## Repository Contents

- `Scripts/`: Python scripts for BOLD downloads, cleaning, audits, and maps.
- `DoFiles/`: Stata 16 import and summary scripts.
- `Notes/`: LaTeX research notes.
- `bold_taxon_size_notes.txt`: BOLD taxon size and coverage notes.
- `Data/`: ignored local data downloads and processed files.
- `Output/`: ignored local maps and audits.
- `Literature/`: ignored local PDFs.

The GitHub repository intentionally excludes large data, generated outputs, PDFs, and temporary download files.

## Current BOLD Data

Downloaded BOLD groups include Fungi, Plantae, Mollusca, Chordata, Hemiptera, selected smaller insect orders, and Animalia excluding Arthropoda/Chordata/Mollusca. Raw BOLD TSV files are under `Data/raw/bold/`.

Important caveat: Hemiptera is capped. The BOLD summary reports 1,053,311 specimens, but the downloaded file contains exactly 1,000,000 data rows. Treat it as an incomplete extract until split by country, family, or another query dimension.

## Core Commands

Audit all BOLD downloads:

```bash
python3 Scripts/audit_bold_downloads.py
```

Create a minimal Fungi TSV:

```bash
python3 Scripts/make_bold_fungi_minimal.py
```

Map BOLD Fungi on a 100 km equal-area grid:

```bash
python3 Scripts/map_bold_fungi_grid.py --cell-km 100
```

Import global BOLD Fungi into Stata:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/02_import_bold_fungi_global.do"
```

## BOLD API Notes

BOLD can return transient `403 Forbidden` or `503 Service Unavailable` errors after many or large requests. Wait before retrying. The downloader scripts save one JSON summary and query token per request, plus a `.part` file during active downloads. A final `.tsv` file with no `.part` suffix means the stream finished.

Rows in BOLD TSV downloads are marker/sequence records, not necessarily unique specimens. It is normal for data rows to exceed the BOLD summary specimen count.

## Next Steps

1. Split Hemiptera into complete subqueries.
2. Add clean/minimal TSV builders for Plantae, Mollusca, Chordata, and insect orders.
3. Build grid-cell/year sampling panels from geocoded records.
4. Link sampling layers to discovery data such as ENA/NCBI, COCONUT, NPAtlas, PubChem, ChEMBL, patents, and publications.
