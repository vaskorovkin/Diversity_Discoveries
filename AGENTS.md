# Agent Guide

This repository is a research data project. Preserve downloaded data and never remove or overwrite user data unless explicitly asked.

## Ground Rules

- Work from `/Users/vasilykorovkin/Documents/Diversity_Discoveries`.
- Keep `Data/`, `Output/`, and `Literature/*.pdf` out of Git.
- Do not commit raw data, processed TSV/DTA files, generated maps, audit CSVs, or PDFs.
- Use `python3`, not `python`.
- Stata scripts target Stata 16.
- BOLD downloads can be slow and rate-limited. Avoid running multiple large BOLD API jobs at once.
- If BOLD returns repeated `403` or `503`, stop and wait rather than retrying aggressively.

## Project Structure

- `Scripts/download_bold_fungi.py` is the generic BOLD downloader despite its historical name. It accepts `--query`, `--stem`, `--summary-only`, `--force`, and `--ignore-cap`.
- `Scripts/download_bold_plants.py`, `download_bold_mollusca.py`, and `download_bold_chordata.py` are thin wrappers around the generic downloader.
- `Scripts/download_bold_animals_except_acm.py` downloads non-Arthropoda, non-Chordata, non-Mollusca animal phyla one phylum at a time.
- `Scripts/download_bold_insect_orders_small.py` downloads selected smaller insect orders one order at a time.
- `Scripts/download_bold_coleoptera_by_family.py`, `download_bold_hemiptera_by_family.py`, `download_bold_hymenoptera_by_family.py`, and `download_bold_lepidoptera_by_family.py` download large insect orders one family at a time.
- `Scripts/download_bold_diptera_from_ceratopogonidae.py` downloads manageable Diptera families while intentionally skipping the four over-cap families: Cecidomyiidae, Chironomidae, Phoridae, and Sciaridae.
- `Scripts/download_bold_chironomidae_by_country.py`, `download_bold_phoridae_by_country.py`, and `download_bold_sciaridae_by_country.py` download over-cap Diptera families one country/ocean value at a time.
- `Scripts/download_bold_cecidomyiidae_except_costa_rica_by_country.py` downloads all positive Cecidomyiidae country/ocean buckets except Costa Rica, because Costa Rica alone is over the BOLD cap.
- `Scripts/download_bold_cecidomyiidae_costa_rica_capped.py` downloads a capped Costa Rica Cecidomyiidae diagnostic extract; do not treat it as complete.
- `Scripts/exhibits/00_build_bold_minimal.py` builds compact BOLD records for exhibits and regressions. It includes the capped Costa Rica Cecidomyiidae file by default, but excludes the redundant global capped Cecidomyiidae and old capped Hemiptera files.
- `Scripts/exhibits/06_build_cell_year_panel.py` builds the main 100 km land-cell x collection-year panel for 2005-2025.
- `Scripts/aggregate_ucdp_ged_100km.py` aggregates a downloaded UCDP GED CSV to the same 100 km land cells for 2005-2024. Logs and lags are intentionally left for Stata.
- `Scripts/download_baseline_geography.py` downloads raw RESOLVE ecoregions and CEPF hotspot inputs for the static baseline geography overlays. See `Scripts/baseline_geography_README.md`.
- `Scripts/aggregate_resolve_ecoregions_100km.py` assigns RESOLVE 2017 ecoregion, biome, and realm to each 100 km land cell by centroid overlay.
- `Scripts/aggregate_cepf_hotspots_100km.py` assigns CEPF/Conservation International biodiversity hotspot indicators to each 100 km land cell by centroid overlay.
- `Scripts/aggregate_wdpa_protected_share_100km.py` computes protected-area share by 100 km cell from a local WDPA polygon GPKG/SHP. It has not been run yet because WDPA is not local.
- Baseline-geography geospatial dependencies are listed in `requirements_baseline_geography.txt`.
- `Scripts/download_bold_non_insect_arthropods_and_microbes.py` downloads selected non-insect arthropod groups plus Bacteria and logs zero-record BOLD v5 groups.
- `Scripts/audit_bold_downloads.py` audits local BOLD TSVs against their summary JSON files.
- `Scripts/audit_bold_taxon_coverage.py` audits the intended taxon coverage plan against local manifests and files without hitting BOLD.
- `Scripts/make_bold_fungi_minimal.py` creates the current Stata-friendly Fungi TSV.
- `Scripts/map_bold_fungi_grid.py` maps geocoded Fungi records on equal-area cells.

## Known Data State

Run this for the current local audit:

```bash
python3 Scripts/audit_bold_downloads.py
```

As of the latest coverage audit:

- 847 intended taxon units were audited locally.
- 818 were downloaded cleanly.
- 16 were downloaded but still appear in stale failed-download logs from earlier BOLD 403/503 attempts.
- 9 are BOLD v5 zero-record groups or tiny v4/v5 taxonomy mismatches.
- The over-cap Diptera families Chironomidae, Phoridae, and Sciaridae have country-level split downloads. Cecidomyiidae is split by country except Costa Rica, where the capped 1M-record file is included but incomplete.
- The old order-level Hemiptera file is capped, but Hemiptera by-family downloads are now the relevant complete working version.
- The current Stata-ready BOLD panel is `Exhibits/data/bold_grid100_cell_year_panel_collection_2005_2025.csv`. It has 305,886 rows: 14,566 land cells x 21 years. It uses collection year, zero-fills land cell-years, and excludes coordinate records outside the strict land-cell universe.
- The current UCDP regressor panel is `Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024.csv`. It has 291,320 rows: 14,566 land cells x 20 years. Merge with BOLD over the common 2005-2024 window.
- The current static baseline geography file is `Data/regressors/baseline_geography/resolve_ecoregions_100km_cells.csv`. It has 14,566 unique cells, 14,291 RESOLVE matches, 1,243 explicit `Rock and Ice` cells, and 275 unmatched cells.
- The current hotspot file is `Data/regressors/baseline_geography/cepf_hotspots_100km_cells.csv`. It has 14,566 unique cells, 2,430 cells in any hotspot, and all 36 hotspot names are represented.
- WDPA protected-area share is script-ready but not run. It needs a local Protected Planet / WDPA polygon file.

## Safe Workflow

Before editing:

```bash
git status --short --ignored
```

Before committing:

```bash
python3 -m py_compile Scripts/*.py Scripts/exhibits/*.py
python3 Scripts/audit_bold_taxon_coverage.py
git status --short
```

Commit only code/docs. Avoid adding ignored data by force unless the user explicitly asks.

## Useful Commands

Download a BOLD taxon:

```bash
python3 Scripts/download_bold_fungi.py --query "tax:order:Hemiptera" --stem bold_global_hemiptera --summary-only
```

Run remaining animal phyla in small paste-safe batches:

```bash
python3 Scripts/download_bold_animals_except_acm.py --phyla Chaetognatha Ctenophora Entoprocta --retries 2 --retry-sleep 300
```

Download Chironomidae, Phoridae, or Sciaridae by country/ocean:

```bash
python3 Scripts/download_bold_cecidomyiidae_except_costa_rica_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_cecidomyiidae_costa_rica_capped.py
python3 Scripts/download_bold_chironomidae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_phoridae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_sciaridae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
```

Map Fungi sampling at 50, 100, or 200 km:

```bash
python3 Scripts/map_bold_fungi_grid.py --cell-km 100
```

Build the main Stata-ready BOLD cell-year panel:

```bash
python3 Scripts/exhibits/06_build_cell_year_panel.py
```

Aggregate UCDP GED conflict to the BOLD grid after placing the GED CSV in
`Data/raw/ucdp/`:

```bash
python3 Scripts/aggregate_ucdp_ged_100km.py
```
