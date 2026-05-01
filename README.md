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
Costa Rica diagnostic file is partial and must not be treated as complete.

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

## BOLD API Notes

BOLD can return transient `403 Forbidden` or `503 Service Unavailable` errors after many or large requests. Wait before retrying. The downloader scripts save one JSON summary and query token per request, plus a `.part` file during active downloads. A final `.tsv` file with no `.part` suffix means the stream finished.

Rows in BOLD TSV downloads are marker/sequence records, not necessarily unique specimens. It is normal for data rows to exceed the BOLD summary specimen count.

## Plant And Discovery Stack

BOLD is not sufficient as the main plant layer. For plants, the project should use herbarium/specimen and botanical-name infrastructure alongside barcode data:

- Plant sampling: GBIF preserved specimens/herbarium records as the main global layer, with iDigBio as a US-heavy complement and BIEN as a cleaned botanical occurrence/trait/range complement.
- Plant name cleaning: WCVP/POWO/IPNI/World Flora Online for accepted names and synonyms; Kew MPNS for medicinal, herbal drug, common-name, and pharmacological-name disambiguation.
- Plant chemistry and discovery outcomes: COCONUT, LOTUS, KNApSAcK, and where accessible NAPRALERT for plant natural products and plant-metabolite links; PubChem and ChEMBL for compound bioactivity and assay outcomes.

## Next Steps

1. Finish split plans for the four oversized Diptera families and audit summed split counts against BOLD v5 family summaries.
2. Add clean/minimal TSV builders for Plantae, Mollusca, Chordata, insect orders, and country/family split downloads.
3. Build grid-cell/year sampling panels from geocoded records.
4. Link sampling layers to discovery data and broader sequencing effort:
   ENA for Europe/EMBL-EBI submissions; DDBJ for Japan-linked submissions;
   NCBI GenBank/SRA/BioSample for global sequencing records; CNCB-NGDC GSA
   and CNGBdb for China-linked sequencing data; plus COCONUT, NPAtlas,
   PubChem, ChEMBL, patents, and publications for natural-product and
   discovery proxies.
