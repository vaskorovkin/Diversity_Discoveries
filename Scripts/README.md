# Scripts

## Regressor Aggregation

- `aggregate_ucdp_ged_100km.py`: aggregates a downloaded UCDP GED CSV to the BOLD 100 km land-cell x year grid for 2005-2024. See `Scripts/ucdp_ged_README.md`.
- `download_baseline_geography.py`: downloads the raw RESOLVE ecoregions and CEPF hotspot files used by the static baseline geography overlays. See `Scripts/baseline_geography_README.md`.
- `aggregate_resolve_ecoregions_100km.py`: assigns RESOLVE 2017 ecoregion, biome, and realm to each BOLD 100 km land cell by centroid overlay.
- `aggregate_cepf_hotspots_100km.py`: assigns CEPF/Conservation International biodiversity hotspot indicators to each BOLD 100 km land cell by centroid overlay.
- `aggregate_wdpa_protected_share_100km.py`: computes May 2026 WDPA protected-area area/share for each BOLD 100 km land cell from a local WDPA polygon GPKG/SHP. This is a snapshot regressor, not a historical panel.
- `aggregate_wdpa_protected_panel_100km.py`: builds time-varying protected-area cell-year panel (2001-2024) using WDPA STATUS_YR designation year. Slow dissolve-based approach; see v2.
- `aggregate_wdpa_protected_panel_100km_v2.py`: fast sjoin+clip approach to WDPA panel (same output, ~2 min vs hours). Preferred.
- `download_terraclimate.py`: downloads TerraClimate NetCDF files (PDSI, tmax, ppt) for 2001-2023.
- `download_terraclimate_baseline.py`: downloads TerraClimate baseline years (1981-2000) for proper 1981-2010 anomaly calculation.
- `aggregate_terraclimate_100km.py`: aggregates TerraClimate data to 100 km cells with anomalies relative to 1981-2010 baseline.
- `download_chirps.py`: downloads CHIRPS annual precipitation GeoTIFFs (1981-2023).
- `aggregate_chirps_100km.py`: aggregates CHIRPS precipitation to 100 km cells with anomalies relative to 1981-2010 baseline.
- `download_groads.py`: instructions and verification for gROADS v1 manual download from NASA SEDAC.
- `aggregate_groads_100km.py`: computes road density (km/km²) per 100 km cell from gROADS shapefile.
- `download_grip_roads.py`: downloads GRIP4 pre-computed road density rasters (~3.5MB, no login).
- `aggregate_grip_roads_100km.py`: aggregates GRIP4 road density to 100 km cells (fast, uses raster).
- `download_globio_msa.py`: downloads GLOBIO4 MSA (Mean Species Abundance) rasters for baseline biodiversity intactness.
- `aggregate_globio_msa_100km.py`: aggregates GLOBIO MSA to 100 km cells.
- `download_worldbank_gdp.py`: downloads World Bank GDP per capita (current US$, WDI indicator NY.GDP.PCAP.CD) for all countries, 2001-2024. Uses WB API v2, no key required. Output: `Data/regressors/worldbank/worldbank_gdp_pcap_panel.csv`.
- `download_ibtracs.py`: downloads NOAA IBTrACS tropical-cyclone track CSVs (default: official `since1980` file, v04r01) to `Data/raw/ibtracs/`.
- `aggregate_ibtracs_100km.py`: aggregates IBTrACS track points to 100 km cells by year. Outputs point counts, unique-storm counts, 34kt/64kt exposure counts, and max wind.
- `download_comcat_earthquakes.py`: downloads global USGS ComCat earthquakes year by year from the official FDSN event service. Defaults: 2005-2025, `eventtype=earthquake`, `minmagnitude=4.5`.
- `aggregate_comcat_100km.py`: aggregates ComCat earthquakes to 100 km cells by year. Outputs event counts, `M6+`, `M7+`, shallow-event counts, and max/mean magnitude.
- `request_gbif_plantae_downloads.py`: submits two GBIF Darwin Core Archive requests for plants: preserved/material records and human observations, both with coordinates and years 2005-2025. Can also poll and download the finished ZIPs.
- `14_build_gbif_plantae_minimal.py`: streams `occurrence.txt` from the GBIF preserved/material plant archive into a compact CSV with the fields needed for downstream summaries and panel work.
- `15_build_gbif_plantae_cell_year_panel.py`: builds the zero-filled 100 km cell-year panel for the GBIF preserved/material plant archive, with total, plant, preserved-specimen, and material-sample counts plus `any_*`/`log1p_*` transforms.
- `gee_nightlights_100km.js`: Google Earth Engine script to aggregate Li et al. (2020) harmonized nighttime lights to 100 km cells. Consistent VIIRS-equivalent scale 2005-2023. Cell-level income proxy. See `Scripts/gee_nightlights_README.md`.
- `merge_nightlights_exports.py`: merges harmonized nightlights GEE export into a cell-year panel with log-radiance.
- `download_acled.py`: downloads ACLED conflict events via API (requires free ACLED account, Bearer token via `--token` or `--token-file`). Year-by-year download, full global coverage 2005-2024. Alternative: manually export CSV from ACLED data export tool.
- `aggregate_acled_100km.py`: aggregates ACLED events to 100 km cells. Event counts and fatalities by type (battles, explosions, violence against civilians, protests, riots). Plus `acled_any_violent` indicator.
- `download_species_richness.py`: instructions and verification for IUCN Red List species range map downloads (manual, free account). Covers mammals, amphibians, reptiles.
- `aggregate_species_richness_100km.py`: computes baseline species richness per 100 km cell from IUCN range map shapefiles (mammals, amphibians, reptiles). Handles multi-part shapefiles. Spatial join with IUCN filters (extant, native, resident/breeding).
- `aggregate_species_richness_birds_100km.py`: separate bird species richness script for BirdLife BOTW GeoPackage (~9 GB). Run in a separate terminal to avoid RAM exhaustion.
- `gee_hansen_forest_loss_100km.js`: Google Earth Engine script to aggregate Hansen Global Forest Change to 100 km cells using tree-cover-weighted method. See `Scripts/gee_hansen_forest_loss_README.md`.
- `merge_hansen_exports.py`: merges Earth Engine CSV exports into a complete cell-year panel with lags.
- `gee_modis_burned_area_100km.js`: Google Earth Engine script to aggregate MODIS MCD64A1 burned area to 100 km cells.
- `merge_modis_burned_exports.py`: merges MODIS Earth Engine CSV exports into a complete cell-year panel with lags.

## Downloaders

- `download_bold_fungi.py`: generic BOLD downloader. Use `--query` and `--stem` for arbitrary taxa.
- `download_bold_plants.py`: global Plantae wrapper.
- `download_bold_mollusca.py`: global Mollusca wrapper.
- `download_bold_chordata.py`: global Chordata wrapper.
- `download_bold_insect_orders_small.py`: selected smaller insect orders.
- `download_bold_non_insect_arthropods_and_microbes.py`: selected non-insect arthropod orders/classes plus Chromista, Protozoa, Archaea, and Bacteria; one TSV per positive-count group.
- `download_bold_cecidomyiidae_except_costa_rica_by_country.py`: Cecidomyiidae downloader split by country/ocean while excluding Costa Rica, which still exceeds the 1M cap.
- `download_bold_cecidomyiidae_costa_rica_capped.py`: capped Costa Rica Cecidomyiidae diagnostic extract; useful as partial coverage only.
- `download_bold_coleoptera_by_family.py`: Coleoptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 21s after successful family downloads.
- `download_bold_coleoptera_remaining_combined.py`: computes missing Coleoptera families from the manifest and downloads them with one combined BOLD query.
- `download_bold_chironomidae_by_country.py`: Chironomidae downloader split into one BOLD request per country/ocean value.
- `download_bold_diptera_from_ceratopogonidae.py`: Diptera family downloader that starts at Ceratopogonidae, leaving the four over-cap families for separate split plans.
- `download_bold_phoridae_by_country.py`: Phoridae downloader split into one BOLD request per country/ocean value.
- `download_bold_sciaridae_by_country.py`: Sciaridae downloader split into one BOLD request per country/ocean value.
- `download_bold_hemiptera_by_family.py`: Hemiptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 11s after successful family downloads.
- `download_bold_hymenoptera_by_family.py`: Hymenoptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 11s after successful family downloads.
- `download_bold_lepidoptera_by_family.py`: Lepidoptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 11s after successful family downloads.
- `download_bold_animals_except_acm.py`: animal phyla excluding Arthropoda, Chordata, and Mollusca.

## Cleaning And Audits

- `make_bold_fungi_minimal.py`: creates a smaller Stata-friendly Fungi TSV from the raw BOLD export.
- `audit_bold_downloads.py`: checks all local BOLD record files against summary JSON counts and flags capped/truncated files.
- `audit_bold_taxon_coverage.py`: checks intended taxon coverage against local manifests and files; it does not query BOLD.
- `summarize_bold_cecidomyiidae_new_world.py`: estimates BOLD Cecidomyiidae counts for New World countries/territories before geography-split downloads.
- `summarize_bold_tsv_genera.py`: counts genus values in a BOLD TSV export and optionally writes a genus-count CSV.
- `summarize_bold_order_families_v4.py`: scrapes BOLD v4 taxonomy-browser family splits for large insect orders and appends them to `bold_taxon_size_notes.txt`.
- `summarize_bold_diptera_large_family_genera_v4.py`: scrapes BOLD v4 genus splits for the four Diptera families above the 1M query cap and appends them to `bold_taxon_size_notes.txt`.
- `summarize_bold_diptera_oversized_country_counts.py`: extracts top country/ocean counts for the four over-cap Diptera families from BOLD summary metadata.
- `summarize_bold_non_insect_groups.py`: summarizes selected non-insect arthropod, microbe-like, and broad taxon groups and appends planning tables to `bold_taxon_size_notes.txt`.
- `09_institution_country_mapping.py`: extracts top collector names from `bold_minimal_records.csv` with record counts and shares. Use `--top-n` to control how many (default 500). Output: `collectors/bold_top{N}_collectors.csv`.
- `11_build_collector_individuals.py`: splits raw collector strings into person-level names and aggregates weighted record counts across combinations. Output: `collectors/bold_top500_collector_individuals.csv`. Use `--input`/`--output`/`--top-n` for larger runs.
- `11_merge_collector_affiliations.py`: merges GPT and Claude affiliation guesses into one file. Classifies each name as AGREED, GPT_ONLY, CLAUDE_ONLY, DISAGREE, ORG, AMBIGUOUS, or UNRESOLVED. Output: `collectors/bold_collector_affiliations_merged.csv`.
- `12_fill_missing_countries.py`: fills collectors without LLM country assignments using BOLD record data. ORGs are mapped via a hardcoded lookup table. AMBIGUOUS and UNRESOLVED names are inferred from their BOLD institution field and co-collector countries. Also applies manual corrections for names with identifiable institutions (e.g., Station Linné→SWE). Output: updates `collectors/bold_collector_affiliations_merged.csv` in place.
- `13_build_parachute_panel.py`: builds cell × year panel of foreign vs domestic collecting for parachute science analysis. Matches collector names to home countries (ISO3→ISO2 conversion), compares to BOLD `country_iso`. Multi-collector records are averaged (1 foreign + 1 domestic = 0.5). Output: `collectors/bold_parachute_cell_year_panel.csv`.

## BOLD Pipeline (00–07)

Run order from project root:

```bash
python3 Scripts/00_build_bold_minimal.py
python3 Scripts/01_tables_counts.py
python3 Scripts/02_timeseries.py
python3 Scripts/03_maps_grid.py
python3 Scripts/04_maps_admin1.py
python3 Scripts/05_cell_correlations.py
python3 Scripts/06_build_cell_year_panel.py
python3 Scripts/07_audit_supply_fields.py
```

`00_build_bold_minimal.py` streams raw BOLD TSV files into `Data/processed/bold/bold_minimal_records.csv`. The later scripts read that file. `05` builds `bold_grid100_land_cells.csv`. `06` builds the cell-year panel for Stata regressions. `07` audits coverage of supply-side metadata fields (inst, collectors, etc.) and writes a LaTeX table to `Exhibits/tables/`.

Shared constants and helpers are in `pipeline_utils.py`.

Outputs: `Data/processed/bold/` (data), `Exhibits/tables/`, `Exhibits/figures/`, `Exhibits/maps/`.

## Mapping

- `map_bold_fungi_admin1.py`: maps geocoded Fungi records to Natural Earth admin-1 polygons.
- `map_bold_fungi_grid.py`: maps geocoded Fungi records to equal-area grid cells. Baseline is 100 km.

## Stata Merge

- `DoFiles/merge_all_regressors.do`: imports all outcome and regressor CSVs, merges panels 1:1 on `cell_id year` and static baselines m:1 on `cell_id`, drops Antarctica and date-line edge cells, saves `Data/analysis/BOLD_regressor_panel.dta`. Log output: `Logs/merge_all_regressors.log`.

## Examples

```bash
python3 Scripts/download_bold_fungi.py --query "tax:kingdom:Fungi" --stem bold_global_fungi --summary-only
python3 Scripts/download_bold_plants.py
python3 Scripts/download_bold_non_insect_arthropods_and_microbes.py
python3 Scripts/download_bold_cecidomyiidae_except_costa_rica_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_cecidomyiidae_costa_rica_capped.py
python3 Scripts/download_bold_coleoptera_by_family.py
python3 Scripts/download_bold_coleoptera_remaining_combined.py
python3 Scripts/download_bold_chironomidae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_diptera_from_ceratopogonidae.py
python3 Scripts/download_bold_phoridae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_sciaridae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_hemiptera_by_family.py
python3 Scripts/download_bold_hymenoptera_by_family.py
python3 Scripts/download_bold_lepidoptera_by_family.py
python3 Scripts/audit_bold_downloads.py
python3 Scripts/audit_bold_taxon_coverage.py
python3 Scripts/summarize_bold_cecidomyiidae_new_world.py
python3 Scripts/summarize_bold_tsv_genera.py Data/raw/bold/diagnostic_capped_redundant/cecidomyiidae_global_capped/bold_global_diptera_family_cecidomyiidae_capped_records.tsv --output Output/audits/cecidomyiidae_capped_genus_counts.csv
python3 Scripts/map_bold_fungi_grid.py --cell-km 100
python3 Scripts/summarize_bold_order_families_v4.py
python3 Scripts/summarize_bold_diptera_large_family_genera_v4.py
python3 Scripts/summarize_bold_diptera_oversized_country_counts.py
python3 Scripts/summarize_bold_non_insect_groups.py
python3 Scripts/aggregate_ucdp_ged_100km.py
python3 Scripts/download_ibtracs.py
python3 Scripts/aggregate_ibtracs_100km.py
python3 Scripts/download_comcat_earthquakes.py --min-magnitude 4.5
python3 Scripts/aggregate_comcat_100km.py --min-magnitude 4.5
python3 Scripts/request_gbif_plantae_downloads.py --gbif-username YOUR_USERNAME --gbif-password YOUR_PASSWORD --notification-email YOU@example.com --submit-only
python3 Scripts/14_build_gbif_plantae_minimal.py
python3 Scripts/15_build_gbif_plantae_cell_year_panel.py
python3 Scripts/09_institution_country_mapping.py
python3 Scripts/11_build_collector_individuals.py
# --- Collector affiliation pipeline (top 633) ---
# 1. Generate prompt: Prompts/prompt_collector_affiliations.txt
# 2. Paste into ChatGPT and Claude separately → save as collectors/bold_collectors_affiliations_{gpt,claude}.csv
# 3. Merge and review:
python3 Scripts/11_merge_collector_affiliations.py
# 4. Manual review: open collectors/bold_collector_affiliations_merged.csv, resolve DISAGREE rows
# 5. Fill remaining missing countries from BOLD co-collectors, institutions, and manual fixes:
python3 Scripts/12_fill_missing_countries.py
# 6. Build parachute science cell-year panel:
python3 Scripts/13_build_parachute_panel.py
# --- Expansion to 10K collectors ---
# Batch prompts in Prompts/prompt_collectors_batch{1-5}.txt
# Classify via GPT, save results to collectors/bold_batch{1-5}_classifications_gpt.csv
# Then merge batches, rebuild parachute panel
python3 Scripts/download_baseline_geography.py
python3 Scripts/aggregate_resolve_ecoregions_100km.py
python3 Scripts/aggregate_cepf_hotspots_100km.py
python3 Scripts/aggregate_wdpa_protected_share_100km.py --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
python3 Scripts/aggregate_wdpa_protected_panel_100km_v2.py --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
python3 Scripts/download_terraclimate_baseline.py --skip-existing
python3 Scripts/download_terraclimate.py --skip-existing
python3 Scripts/aggregate_terraclimate_100km.py
python3 Scripts/download_chirps.py --skip-existing
python3 Scripts/aggregate_chirps_100km.py
python3 Scripts/download_grip_roads.py
python3 Scripts/aggregate_grip_roads_100km.py
python3 Scripts/download_globio_msa.py --types overall
python3 Scripts/aggregate_globio_msa_100km.py
```
