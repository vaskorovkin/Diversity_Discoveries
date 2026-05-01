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

Downloaded BOLD groups include Fungi, Plantae, Mollusca, Chordata, selected smaller insect orders, animal phyla excluding Arthropoda/Chordata/Mollusca, non-insect arthropod groups, and Bacteria. Large insect orders are split family by family where needed: Coleoptera, Hemiptera, Hymenoptera, Lepidoptera, and manageable Diptera families from Ceratopogonidae downward. Raw BOLD TSV files are under `Data/raw/bold/`.

Important note: Diptera is not fully complete. The remaining incomplete piece is
Costa Rica (`C-R`) Cecidomyiidae. BOLD reports 1,122,446 Costa Rica
Cecidomyiidae records, which exceeds the 1,000,000-record API cap. The capped
Costa Rica file is included in the exhibit pipeline so that this major cluster
is not dropped, but it is partial and must not be treated as complete.

Current caveat: four Diptera families exceed the 1,000,000-record BOLD query cap at the family level: Cecidomyiidae, Chironomidae, Phoridae, and Sciaridae. Chironomidae, Phoridae, Sciaridae, and non-Costa-Rica Cecidomyiidae now have country-level request scripts; Costa Rica Cecidomyiidae still needs a further split or a BOLD bulk export. See `diptera_oversized_family_problem.md`.

## Core Commands

Audit all BOLD downloads:

```bash
python3 Scripts/audit_bold_downloads.py
```

Audit intended taxon coverage against local manifests:

```bash
python3 Scripts/audit_bold_taxon_coverage.py
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

## Exhibit Pipeline

The current Stata-ready BOLD panel is generated from compact exhibit files, not
from raw TSVs directly. Run order:

```bash
python3 Scripts/exhibits/00_build_bold_minimal.py
python3 Scripts/exhibits/01_tables_counts.py
python3 Scripts/exhibits/02_timeseries.py
python3 Scripts/exhibits/03_maps_grid.py
python3 Scripts/exhibits/04_maps_admin1.py
python3 Scripts/exhibits/05_cell_correlations.py
python3 Scripts/exhibits/06_build_cell_year_panel.py
```

Main panel output:

```text
Exhibits/data/bold_grid100_cell_year_panel_upload_2005_2025.csv
Exhibits/data/bold_grid100_cell_year_panel_upload_2005_2025_summary.csv
```

The panel uses BOLD `sequence_upload_year`, 2005-2025, 100 km equal-area land
cells, and includes zero cell-years. It has outcomes for total records,
Animalia, Plantae, Fungi, Bacteria, Plantae + Fungi, non-Chordata Animalia,
Arthropoda, Insecta, and Chordata, with extensive-margin (`any_*`) and
intensive-margin (`log1p_*`) versions.

Current panel audit:

```text
Land cells: 14,566
Panel rows: 305,886
Coordinate records in 2005-2025: 17,439,280
Records assigned to land cells: 15,302,751
Coordinate records outside land-cell universe: 2,136,529
```

The panel is intentionally a strict land-cell panel. Some coastal, island, and
marine/coastal records fall outside the land-cell universe and are not included
in the current regression panel.

## BOLD API Notes

BOLD can return transient `403 Forbidden` or `503 Service Unavailable` errors after many or large requests. Wait before retrying. The downloader scripts save one JSON summary and query token per request, plus a `.part` file during active downloads. A final `.tsv` file with no `.part` suffix means the stream finished.

Rows in BOLD TSV downloads are marker/sequence records, not necessarily unique specimens. It is normal for data rows to exceed the BOLD summary specimen count.

## Plant And Discovery Stack

BOLD is not sufficient as the main plant layer. For plants, the project should use herbarium/specimen and botanical-name infrastructure alongside barcode data:

- Plant sampling: GBIF preserved specimens/herbarium records as the main global layer, with iDigBio as a US-heavy complement and BIEN as a cleaned botanical occurrence/trait/range complement.
- Plant name cleaning: WCVP/POWO/IPNI/World Flora Online for accepted names and synonyms; Kew MPNS for medicinal, herbal drug, common-name, and pharmacological-name disambiguation.
- Plant chemistry and discovery outcomes: COCONUT, LOTUS, KNApSAcK, and where accessible NAPRALERT for plant natural products and plant-metabolite links; PubChem and ChEMBL for compound bioactivity and assay outcomes.

## Next Steps

1. Import the 2005-2025 upload-year cell panel into Stata and run first
   extensive/intensive-margin sampling regressions.
2. Decide whether to add a robustness panel based on collection year.
3. Decide whether to create a second panel that includes all observed cells
   plus land zero cells, rather than strict land-centroid cells only.
4. Link sampling layers to discovery data and broader sequencing effort:
   ENA for Europe/EMBL-EBI submissions; DDBJ for Japan-linked submissions;
   NCBI GenBank/SRA/BioSample for global sequencing records; CNCB-NGDC GSA
   and CNGBdb for China-linked sequencing data; plus COCONUT, NPAtlas,
   PubChem, ChEMBL, patents, and publications for natural-product and
   discovery proxies.
