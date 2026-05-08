# AI Handover

Date: 2026-05-05

## Ground Rules

- Work from `/Users/vasilykorovkin/Documents/Diversity_Discoveries`.
- The user commits and pushes. Do not run `git commit` or `git push`.
- Use `python3`, not `python`.
- Do not delete or overwrite data in `Data/`, `Output/`, or `Literature/`.
- Large BOLD jobs can trigger HTTP 403/503 throttling. Prefer one large BOLD download at a time. If repeated 403s occur, stop and wait.

## Current BOLD Download State

Core BOLD downloads and family split scripts are in `Scripts/`. Large data are ignored by Git.

Important warning: Diptera is not fully complete. The remaining incomplete
piece is Costa Rica (`C-R`) Cecidomyiidae. The capped Costa Rica diagnostic
download is partial and must not be used as complete coverage. It is included
by default in the exhibit pipeline so the Costa Rica Cecidomyiidae cluster is
not dropped, but it remains capped at 1M records.

Diptera status:

- Manageable Diptera families in `Data/raw/bold/diptera_by_family/` are complete, excluding the four over-cap families.
- Sciaridae country split is complete: 96 manifest rows, 96 TSV files, no failures, no `.part`.
- Phoridae country split is complete: 91 manifest rows, 91 TSV files, no failures, no `.part`.
- Chironomidae country split is complete: 126 manifest rows, 126 TSV files, no failures, no `.part`.
- Cecidomyiidae is the remaining problem:
  - Non-Costa-Rica country split script exists: `Scripts/download_bold_cecidomyiidae_except_costa_rica_by_country.py`.
  - Costa Rica exceeds the BOLD 1M cap by itself.
  - `Scripts/download_bold_cecidomyiidae_costa_rica_capped.py` exists for a capped Costa Rica diagnostic extract.
  - Do not treat Cecidomyiidae as complete until the split/cap issue is explicitly audited.

Recent Diptera audit excluding Cecidomyiidae:

```text
manageable_diptera_families: expected 154, downloaded 154, missing 0, partial 0, stale failed-log rows 5
sciaridae_by_country: expected 96, downloaded 96, missing 0, partial 0, failed 0
phoridae_by_country: expected 91, downloaded 91, missing 0, partial 0, failed 0
chironomidae_by_country: expected 126, downloaded 126, missing 0, partial 0, failed 0
```

Country split totals are slightly below family summary totals because records with blank `country/ocean` are not captured by country-level BOLD queries:

```text
Sciaridae: country sum 1,171,781 vs family summary 1,172,067
Phoridae: country sum 1,377,782 vs family summary 1,385,577
Chironomidae: country sum 1,643,776 vs family summary 1,647,619
```

## Useful Commands

Run the exhibit pipeline:

```bash
python3 Scripts/00_build_bold_minimal.py
python3 Scripts/01_tables_counts.py
python3 Scripts/02_timeseries.py
python3 Scripts/03_maps_grid.py
python3 Scripts/04_maps_admin1.py
python3 Scripts/05_cell_correlations.py
python3 Scripts/06_build_cell_year_panel.py
```

Main panel output:

```text
Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025.csv
Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025_summary.csv
```

After regenerating the collection-year panel, check:

```text
Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025_summary.csv
```

The panel uses BOLD `collection_year`, 2005-2025, 100 km equal-area land
cells, and zero-fills all land cell x year combinations. BIN outcomes:
`n_bins` = distinct BINs sampled per cell-year; `n_new_bins` = BINs whose
global first appearance (earliest collection year across all cells) is that
year, credited to every cell that collected the BIN in its first year. It is
a strict land-cell panel; coastal/island/marine-adjacent records outside the
land-cell universe are excluded for now.

UCDP GED conflict has been aggregated to the same 100 km land cells:

```text
Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024.csv
Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024_summary.csv
```

Current UCDP audit:

```text
raw_events: 385,918
events_in_year_window: 304,784
events_in_land_cells: 295,705
events_outside_land_cells: 9,079
output_rows: 291,320
output_cells: 14,566
output_years: 20
cell_years_with_ucdp_events_all: 15,830
ucdp_events_all: 295,705
ucdp_best_all: 2,037,751
ucdp_deaths_civilians_all: 385,455
state events: 212,970
non-state events: 47,223
one-sided events: 35,512
```

Use the common 2005-2024 window when merging BOLD and UCDP. Generate logs and
lags in Stata, not in the raw UCDP regressor file.

RESOLVE 2017 ecoregions have been assigned to the 100 km land cells:

```text
Scripts/download_baseline_geography.py
Scripts/baseline_geography_README.md
Scripts/aggregate_resolve_ecoregions_100km.py
Data/regressors/baseline_geography/resolve_ecoregions_100km_cells.csv
```

Current RESOLVE audit:

```text
output_rows: 14,566
unique_cells: 14,566
duplicate_cell_ids: 0
matched_to_ecoregion: 14,291
unmatched: 275
rock_and_ice_cells: 1,243
unique_ecoregions: 680
unique_biomes: 15
unique_realms: 9
```

The overlay uses cell centroids. Use it as static baseline geography for
strata, interactions, or heterogeneity; it is not a cell-year shock.

CEPF/Conservation International biodiversity hotspots have also been assigned
to the 100 km land cells:

```text
Scripts/aggregate_cepf_hotspots_100km.py
Data/regressors/baseline_geography/cepf_hotspots_100km_cells.csv
```

Current hotspot audit:

```text
output_rows: 14,566
unique_cells: 14,566
duplicate_cell_ids: 0
cells_in_any_hotspot: 2,430
unique_hotspot_names_hit: 36
cells_matching_multiple_hotspots: 0
```

WDPA/Protected Planet protected-area share is currently running or ready to run
from the local May 2026 WDPA/WDOECM polygon geodatabase. The script is:

```text
Scripts/aggregate_wdpa_protected_share_100km.py
```

Current local input:

```bash
python3 Scripts/aggregate_wdpa_protected_share_100km.py --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

The WDPA output is a May 2026 snapshot by cell, not a historical
protected-area panel. Treat it as baseline geography/control/heterogeneity.

For a time-varying protected-area panel using STATUS_YR:

```bash
python3 Scripts/aggregate_wdpa_protected_panel_100km.py --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

Output:

```text
Data/regressors/wdpa/wdpa_protected_panel_100km.csv
```

Variables: `protected_area_km2`, `protected_share`, `any_protected`,
`new_protection_km2`. Covers 2001-2024. Generate lags/deltas in Stata.

Limitations: uses current polygon boundaries applied backward; STATUS_YR is
designation year, not exact boundary history; downgrading/degazettement not
captured. Suitable for first-pass treatment analysis.

The v1 script (`aggregate_wdpa_protected_panel_100km.py`) uses dissolve+overlay
and takes hours. The v2 script (`aggregate_wdpa_protected_panel_100km_v2.py`)
uses sjoin+clip and finishes in ~2 minutes. Use v2.

## GBIF Plantae Pipeline

Main plant layer is the GBIF preserved/material archive, not the human-observation archive.

Raw download:

```text
Data/raw/gbif/plantae/gbif_plantae_preserved_material_dwca_2005_2025/
```

Processed outputs:

```text
Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv
Data/processed/gbif/plantae/gbif_plantae_preserved_material_cell_year_panel_2005_2025.csv
Data/regressors/plants/gbif_plantae_preperiod_richness_1999_2004.csv
```

Build commands:

```bash
python3 Scripts/14_build_gbif_plantae_minimal.py
python3 Scripts/15_build_gbif_plantae_cell_year_panel.py
python3 Scripts/17_build_gbif_plantae_preperiod_richness.py
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/merge_all_regressors.do"
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec1_gbif_plantae.do"
```

The GBIF plant panel is a mirror of `reg_spec1.do`: same RHS, same FE structure, same 2005-2023 sample restriction, but with GBIF preserved/material Plantae outcomes. The merged Stata panel also now carries static pre-period plant-richness aliases (`gbif_p_rich_base`, `gbif_p_rich_log`, `gbif_p_rich_z`, `gbif_p_genrich_base`, `gbif_p_genrich_log`, `gbif_p_genrich_z`, `gbif_p_rich_log_std`). `reg_spec1_gbif_plantae.do` now includes Table 6: conflict interacted with GBIF pre-period plant richness, using `log1p` then standardization to match the updated Table 5 richness scaling.

BIEN remains a secondary plant-richness route. Direct `BIEN_list_sf()` cell-by-cell queries over the 100 km grid were too brittle and slow. The current exploratory path is to first build the observed GBIF species universe with `Scripts/19_extract_gbif_plantae_species_universe.py`, then run `Scripts/18_bien_range_download_pilot.R` in rank windows over the canonical species pool. The current completed BIEN sweep covers the full canonical pool of `236,166` species-like names in five batches:

- batch 1: ranks `1-5000` → `Data/raw/bien/batches/batch_001_ranks_000001_005000/` → `3,736` downloaded species
- batch 2: ranks `5001-30000` → `Data/raw/bien/batches/batch_002_ranks_005001_030000/` → `12,852` downloaded species
- batch 3: ranks `30001-80000` → `Data/raw/bien/batches/batch_003_ranks_030001_080000/` → `17,124` downloaded species
- batch 4: ranks `80001-230000` → `Data/raw/bien/batches/batch_004_ranks_080001_230000/` → `30,241` downloaded species
- batch 5: ranks `230001-236166` → `Data/raw/bien/batches/batch_005_ranks_230001_236166/` → `807` downloaded species

Total downloaded BIEN range-map species: `64,760`. The script records timing and file-size metrics in each batch summary manifest and can optionally build BIEN skinny ranges and a local richness raster if a template raster is provided.

TerraClimate climate anomalies (drought, heat, precipitation):

```bash
python3 Scripts/download_terraclimate.py --skip-existing
python3 Scripts/aggregate_terraclimate_100km.py
```

Download: `Data/raw/terraclimate/` (PDSI, tmax, ppt NetCDFs, ~4km, 1981-2023)

Baseline years (1981-2000) are downloaded separately:

```bash
python3 Scripts/download_terraclimate_baseline.py --skip-existing
```

Output: `Data/regressors/terraclimate/terraclimate_100km_panel.csv`

Variables: `pdsi_mean`, `pdsi_anomaly` (drought), `tmax_mean`, `tmax_anomaly`
(heat), `ppt_mean`, `ppt_anomaly` (precipitation). Anomalies relative to
1981-2010 baseline. Covers 2001-2023.

CHIRPS precipitation anomalies (tropical/subtropical focus):

```bash
python3 Scripts/download_chirps.py --skip-existing
python3 Scripts/aggregate_chirps_100km.py
```

Download: `Data/raw/chirps/` (annual GeoTIFFs, ~5km, 1981-2023 for baseline)
Output: `Data/regressors/chirps/chirps_100km_panel.csv`

Variables: `chirps_precip_mm`, `chirps_precip_anomaly`. Coverage: 50°S-50°N
only (polar cells will have NaN). Anomalies relative to 1981-2010 baseline.

IBTrACS cyclones and ComCat earthquakes (new natural-disaster layers):

```bash
python3 Scripts/download_ibtracs.py
python3 Scripts/aggregate_ibtracs_100km.py

python3 Scripts/download_comcat_earthquakes.py --min-magnitude 4.5
python3 Scripts/aggregate_comcat_100km.py --min-magnitude 4.5
```

Raw downloads:

```text
Data/raw/ibtracs/ibtracs_since1980_list_v04r01.csv
Data/raw/ibtracs/ibtracs_download_manifest.csv
Data/raw/comcat/comcat_earthquakes_2005_2025_m4p5.csv
Data/raw/comcat/comcat_download_manifest.csv
```

Processed outputs:

```text
Data/regressors/ibtracs/ibtracs_100km_cell_year_2005_2025.csv
Data/regressors/ibtracs/ibtracs_100km_cell_year_2005_2025_summary.csv
Data/regressors/comcat/comcat_100km_cell_year_2005_2025.csv
Data/regressors/comcat/comcat_100km_cell_year_2005_2025_summary.csv
```

Interpretation:

- IBTrACS raw file: global NOAA tropical-cyclone track points since 1980, one
  row per storm-time point.
- IBTrACS processed panel: 100 km land-cell x year cyclone exposure with
  `ibtracs_points_all`, `ibtracs_storms_all`, `ibtracs_points_34kt`,
  `ibtracs_points_64kt`, `ibtracs_any_all`, `ibtracs_any_34kt`,
  `ibtracs_any_64kt`, `ibtracs_max_wmo_wind_kts`.
- ComCat raw file: global USGS earthquake events, one row per earthquake,
  downloaded with magnitude `>= 4.5`.
- ComCat processed panel: 100 km land-cell x year earthquake exposure with
  `comcat_events_all`, `comcat_events_m6`, `comcat_events_m7`,
  `comcat_shallow_events`, `comcat_any_all`, `comcat_max_mag`,
  `comcat_mean_mag`, `comcat_mean_depth_km`.

Both processed panels currently cover 2005-2025; at merge/regression stage use
the common 2005-2024 window to stay aligned with UCDP.

GRIP4 road density (baseline accessibility, pre-computed raster):

```bash
python3 Scripts/download_grip_roads.py
python3 Scripts/aggregate_grip_roads_100km.py
```

Download: `Data/raw/grip/` (~3.5MB, no login required)
Output: `Data/regressors/baseline_geography/grip_roads_100km_cells.csv`

Variables: `road_density_m_per_km2`, `road_density_km_per_km2`, `any_road`,
`log_road_density`. Static baseline from GRIP4 (~8km pre-computed density).
Use as accessibility control/interaction.

Alternative: gROADS v1 scripts exist (`download_groads.py`,
`aggregate_groads_100km.py`) but require manual SEDAC download and are slower.

GLOBIO4 MSA (Mean Species Abundance) biodiversity intactness:

```bash
python3 Scripts/download_globio_msa.py --types overall
python3 Scripts/aggregate_globio_msa_100km.py
```

Download: `Data/raw/globio/` (~6GB for overall MSA)
Output: `Data/regressors/baseline_geography/globio_msa_100km_cells.csv`

Variables: `msa_overall` (0-1 scale, 1 = pristine). Static 2015 baseline from
GLOBIO4/PBL (Schipper et al. 2020). Mean MSA across cells: 0.58.

World Bank GDP per capita (country-year panel):

```bash
python3 Scripts/download_worldbank_gdp.py
```

Download: uses WB API v2 (no key), batches 50 countries per request.
Output: `Data/regressors/worldbank/worldbank_gdp_pcap_panel.csv`

Variables: `iso_a3`, `country_name`, `year`, `gdp_pcap_current_usd`.
Covers 2001-2024, 217 countries. Merged m:1 on `iso_a3 year` after RESOLVE
provides `iso_a3`. ~78% of cell-years match (miss = small islands, disputed).

Harmonized nighttime lights (cell-level income proxy):

```bash
# Run GEE script, download export, then:
python3 Scripts/merge_nightlights_exports.py
```

Uses Li, Zhou et al. (2020) harmonized NTL dataset — DMSP calibrated to
VIIRS-equivalent scale for a consistent 2005-2023 series. GEE assets:
`projects/sat-io/open-datasets/Harmonized_NTL/dmsp` (2005-2013) and
`viirs` (2014-2021), extended with raw VIIRS DNB for 2022-2023.

Output: `Data/regressors/nightlights/nightlights_100km_panel.csv`
Variables: `ntl_mean`, `log1p_ntl`, `any_light`. No sensor dummy needed.

ACLED conflict events (alternative to UCDP):

```bash
# Option 1: API download with Bearer token
python3 Scripts/download_acled.py --token-file Data/raw/acled/acled_token.json
# Option 2: manual CSV export from https://acleddata.com/data-export-tool/
# Then:
python3 Scripts/aggregate_acled_100km.py --acled "Data/raw/acled/ACLED Data_2026-05-02.csv"
```

Output: `Data/regressors/acled/acled_100km_cell_year_2005_2024.csv`
Variables: `acled_events_all`, `acled_fatalities_all`, `acled_any_all`,
`acled_any_violent`, plus per-type counts (battles, explosions, vac,
protests, riots, strategic). Much richer than UCDP: 2.2M events vs 296K,
includes protests and riots.

Species richness baseline (IUCN/BirdLife range maps):

```bash
# Mammals, amphibians, reptiles (run together):
python3 Scripts/aggregate_species_richness_100km.py
# Birds (separate terminal — BOTW is 9 GB):
python3 Scripts/aggregate_species_richness_birds_100km.py
```

Input: IUCN range map shapefiles in `Data/raw/iucn_ranges/{MAMMALS,AMPHIBIANS,REPTILES}/`
and BirdLife BOTW GeoPackage in `Data/raw/iucn_ranges/BOTW/`.
Filters: extant, native, resident/breeding (standard macroecology practice).

Output: `Data/regressors/baseline_geography/species_richness_100km_cells.csv`
(mammals + amphibians + reptiles) and
`Data/regressors/baseline_geography/species_richness_birds_100km_cells.csv`.

Plant richness not yet available — Kier et al. (2005) supplementary data
gives vascular plant richness per WWF ecoregion but the Wiley download link
is broken and ecoregion IDs need a crosswalk to RESOLVE 2017.

Hansen Global Forest Change is being aggregated via Google Earth Engine:

```text
Scripts/gee_hansen_forest_loss_100km.js       # Earth Engine script
Scripts/gee_hansen_forest_loss_README.md      # Setup and workflow instructions
Scripts/merge_hansen_exports.py               # Merge GEE exports with cell panel
```

Earth Engine asset:

```text
projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells
```

After exporting from Earth Engine and downloading to `Data/regressors/hansen/`:

```bash
python3 Scripts/merge_hansen_exports.py
```

Hansen output files:

```text
Data/regressors/hansen/hansen_baseline_forest_100km.csv
Data/regressors/hansen/hansen_forest_loss_100km_annual.csv
Data/regressors/hansen/hansen_cumulative_loss_100km.csv
Data/regressors/hansen/hansen_forest_loss_100km_panel.csv
```

Hansen covers 2001-2023 (tree-cover-weighted method). Variables include
`baseline_forest_km2`, `forest_loss_km2`, `forest_loss_share`,
`cumulative_loss_km2`, `cumulative_loss_share`, and 1-2 year lags.

MODIS MCD64A1 burned area is also aggregated via Earth Engine:

```text
Scripts/gee_modis_burned_area_100km.js
Scripts/merge_modis_burned_exports.py
```

After exporting from Earth Engine and downloading to `Data/regressors/modis/`:

```bash
python3 Scripts/merge_modis_burned_exports.py
```

MODIS output:

```text
Data/regressors/modis/modis_burned_area_100km_panel.csv
```

Variables: `burned_area_km2`, `any_burned`, `cumulative_burned_km2`, and 1-2
year lags. Covers 2001-2023.

## Stata Merge

All regressors are merged into a single analysis panel via:

```stata
do "DoFiles/merge_all_regressors.do"
```

Output: `Data/analysis/BOLD_regressor_panel.dta`
Log: `Logs/merge_all_regressors.log`

The do-file:
- Starts from the BOLD collection-year panel (2005-2025)
- Merges panel regressors 1:1 on `cell_id year` (UCDP, Hansen, MODIS,
  TerraClimate, CHIRPS, WDPA panel)
- Merges static baselines m:1 on `cell_id` (RESOLVE, CEPF, WDPA static,
  GRIP roads, GLOBIO MSA)
- Merges World Bank GDP m:1 on `iso_a3 year` (after RESOLVE provides `iso_a3`)
- Drops Antarctica (`continent == "Antarctica"`) and 7 date-line edge cells
  (`cell_area_km2 > 10001`)
- Final panel: 14,559 cells × 25 years (2001-2025), 151 variables

Panel year ranges differ: BOLD 2005-2025, UCDP 2005-2024, Hansen/MODIS/
TerraClimate/CHIRPS 2001-2023, WDPA 2001-2024. The union is 2001-2025;
variables are missing outside their source's range. For analysis, restrict to
`year >= 2005` for BOLD outcomes.

Local coverage audit:

```bash
python3 Scripts/audit_bold_taxon_coverage.py
```

Aggregate UCDP GED after downloading the global CSV to `Data/raw/ucdp/`:

```bash
python3 Scripts/aggregate_ucdp_ged_100km.py
```

Check a country-split folder for missing files, replacing folder/prefix/family as needed:

```bash
python3 -c 'import csv,re;from pathlib import Path;d=Path("Data/raw/bold/diptera_chironomidae_by_country");slug=lambda x:re.sub(r"[^a-z0-9]+","_",x.lower()).strip("_");rows=list(csv.DictReader((d/"chironomidae_country_manifest.csv").open()));missing=[r["country_or_ocean"] for r in rows if not (d/("bold_global_diptera_family_chironomidae_country_"+slug(r["country_or_ocean"])+"_records.tsv")).exists()];print(len(rows), "manifest rows");print(len(missing), "missing");print("\n".join(missing))'
```

Run remaining Cecidomyiidae except Costa Rica if needed:

```bash
python3 Scripts/download_bold_cecidomyiidae_except_costa_rica_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
```

Run capped Costa Rica Cecidomyiidae diagnostic if needed:

```bash
python3 Scripts/download_bold_cecidomyiidae_costa_rica_capped.py
```

## Regression Analysis

Main specification file:

```stata
do "DoFiles/reg_spec1.do"
```

Log: `Logs/reg_spec1.log`

The do-file estimates 5 tables (8 columns each, 40 specifications total).
Sample: 2005-2023. Dependent variables: `any_total` (extensive margin) and
`log1p_total` (intensive margin). SE clustered at cell level.

**Table 1** — Cell + Year FE:
- Conflict (log(1+events) or 1[events>0]), forest loss, burned area, PDSI/tmax
  anomalies, `protected_share`, GDP×PA interactions (linear + quadratic).
- GDP main effects identified off within-country growth net of year FE.
- GDP×PA interaction shows U-shaped PA effect across development levels.

**Table 2** — Cell + Country×Year FE:
- GDP main effects absorbed; GDP×PA interactions survive (cell-level variation).
- Conflict attenuates ~25% but remains significant.
- Burned area flips to significant negative (country-year FE removes
  confounding seasonal/policy variation).

**Table 3** — Table 2 + Biome×Year FE + Road×Year controls:
- `i.resolve_biome_num#i.year` absorbed, `c.road_density_km_per_km2#i.year`
  as regressors (suppressed from output).
- Conflict robust; climate effects largely unchanged.

**Table 4** — Table 3 + Conflict×MSA interaction:
- `c.conflict#c.msa_overall`: positive coefficient — conflict reduces sampling
  less in intact/remote areas (MSA is intactness, not richness).
- Interpretation: conflict disrupts sampling where researchers already go
  (degraded, accessible areas), not in pristine zones.

**Table 5** — Table 3 + Conflict×Richness (IUCN) interaction:
- `c.conflict#c.richness_std`: negative coefficient — conflict reduces sampling
  more in species-rich cells (richness_std is standardized IUCN total richness).

### BIN Outcome Regressions (`reg_spec_bin.do`)

Log: `Logs/reg_spec_bin.log`

Replaces total-record LHS with BIN outcomes: `n_bins` (distinct BINs sampled)
and `n_new_bins` (globally new BINs first observed in that cell-year). Five
tables mirroring the main spec structure, including a sampling-effort control
table. Key finding: conflict effect on new BIN discovery is almost entirely
mediated by reduced sampling volume (the coefficient flips sign when
conditioning on `log1p_total`).

### Organism Heterogeneity (`reg_spec_organisms.do`)

Log: `Logs/reg_spec_organisms.log`

Runs Table 3 spec with Chordata, Insecta, and Plantae+Fungi as LHS. Key
finding: the aggregate conflict effect is driven by insect sampling; Chordata
sampling is conflict-proof. Plantae+Fungi shows a moderate conflict effect
but is distinctively sensitive to climate shocks (Tmax, PDSI).

### Benchmarking Decomposition (`reg_spec_benchmark.do`)

Log: `Logs/reg_spec_benchmark.log`

Compact 8-column table: conflict → sampling (cols 1-2), conflict → discovery
(cols 3-4), conflict → discovery|effort (cols 5-6), and intensive-margin only
(cols 7-8, restricted to `total_records > 0`).

Key findings across tables:
- Conflict is the most robust shock: negative, significant at 1% in nearly all
  specs, survives saturated FE. Sum of L0-L2 distributed lags typically 2-3×
  the contemporaneous effect.
- Forest loss is not significant.
- Burned area is negative and significant with country×year FE.
- PDSI (drought) is positive and significant — wetter conditions predict more
  sampling. Cumulative L0-L2 effect is small and imprecise.
- Tmax (heat) is inconsistent.
- GDP×PA interactions are entirely cross-country (disappear in Table 2+).

## Commit Preparation

Current prepared changes are code/docs only; data and output remain ignored.

## Foreign Collecting Pipeline

Goal: classify BOLD collectors by home country and measure foreign vs domestic
collecting at the cell-year level. "Foreign" is further split into regional
(same continent, different country) and distant (different continent).

### Run order

```bash
python3 Scripts/09_institution_country_mapping.py --top-n 10000
python3 Scripts/11_build_collector_individuals.py --top-n 10000
# --- Original 633 (one-time LLM classification) ---
python3 Scripts/11_merge_collector_affiliations.py
python3 Scripts/12_fill_missing_countries.py
# --- Expansion to ~10K (one-time LLM classification, batches 1-5) ---
# Review files: bold_disagree_for_review_with_judgements.csv,
#               bold_org_for_review_merged_pass1_pass2.csv
python3 Scripts/13a_merge_all_classifications.py
python3 Scripts/13_build_foreign_collecting_panel.py
# --- Stata ---
stata -b do DoFiles/merge_all_regressors.do
stata -b do DoFiles/desc_foreign_collecting.do
```

### Scripts

1. **`09_institution_country_mapping.py`**: extracts top collector strings
   from `bold_minimal_records.csv` with record counts.

2. **`11_build_collector_individuals.py`**: splits comma-separated strings
   into person-level names. With `--top-n 10000`: produces 633 individuals
   from top-500 strings + ~101K full list (`bold_all_collector_individuals.csv`).

3. **`11_merge_collector_affiliations.py`**: merges GPT + Claude guesses
   for the original top-633 collectors. Status: AGREED, GPT_ONLY,
   CLAUDE_ONLY, DISAGREE, ORG, AMBIGUOUS, UNRESOLVED.

4. **`12_fill_missing_countries.py`**: fills remaining original-633
   collectors via BOLD institution field, co-collector inference, and
   manual corrections. Result: 630/633 (99.5%) coverage.

5. **`13a_merge_all_classifications.py`**: merges original 633 + batch 1-5
   LLM classifications into `bold_collector_affiliations_expanded.csv`.
   - Deduplicates within batches (42 removed)
   - Detects 46 local collector names from full 101K list (status=LOCAL_COLLECTOR)
   - Reads reviewed DISAGREE judgements (67 decisions) and ORG merged
     pass1+pass2 (404 decisions, handles multi-country via first ISO3)
   - Hardcoded dual-affiliation fixes (7 researchers + 1 Crimea case)
   - UNRESOLVED_DISAGREE takes GPT's country guess
   - Two-stage output: `_expanded_prereview.csv` (pure LLM) then
     `_expanded.csv` (with all decisions applied)
   - Result: 9,977 collectors, 79.2% with country, 96.2% record-weighted

6. **`13_build_foreign_collecting_panel.py`**: builds cell x year panel.
   Matches collector names to home countries, compares to BOLD `country_iso`.
   Continent lookup from RESOLVE ecoregions for regional/distant split.
   Local collectors are always domestic.
   Output columns:
   - `records_total`, `records_with_collectors`, `records_classified`,
     `records_unclassified`
   - `records_domestic`, `records_foreign_regional`, `records_foreign_distant`
     (categorical, mutually exclusive; hierarchy: distant > regional > domestic)
   - `records_collab` (both domestic + foreign on same record)
   - `domestic_score_sum`, `regional_score_sum`, `distant_score_sum`
     (fractional; mixed-collector records split proportionally)
   - `n_collectors_foreign`, `n_collectors_domestic` (unique names)

   Derived shares computed in `merge_all_regressors.do`:
   `foreign_share`, `regional_share`, `distant_share`, `domestic_share`,
   `collab_share`.

### Coverage as of 2026-05-06

- 9,977 unique collectors classified (633 original + 9,316 batches + 46 local)
- 7,904 (79.2%) have a country assignment; 96.2% record-weighted coverage
- 14.3M records classified out of 16M with collector fields (89% match)
- Breakdown (fractional scores): 49% domestic, 41% regional-foreign,
  10% distant-foreign
- 20% of classified records are local-foreign collaborations
- Remaining unclassified: 2,027 genuinely ambiguous names (1.1M records, 4%)

### Classification hierarchy

AGREED > GPT_ONLY/CLAUDE_ONLY > REVIEWED (manual DISAGREE resolution) >
ORG_REVIEWED (org pass1+pass2) > UNRESOLVED_AGREED (both name-guessed same) >
UNRESOLVED_ONE (one guessed) > UNRESOLVED_DISAGREE (GPT guess used) >
AMBIGUOUS > UNRESOLVED > LOCAL_COLLECTOR (domestic by definition, no fixed country)

### Key design decisions

- Home institution country is coded, not collecting country
- BOLD `inst` field is NOT used (measures submitting institution, not collector)
- Dual-affiliation researchers: 7 hardcoded cases use primary affiliation
- Local collectors (64 name variants, 26K records): always domestic
- Multi-country ORGs: first ISO3 code used
- Crimea (K.A. Efetov): coded as Ukraine

### Directory structure

All files in `Data/processed/bold/collectors/`:
- `bold_all_collector_individuals.csv` — full 101K unique individuals
- `bold_collector_affiliations_633_reviewed.csv` — original 633, manually reviewed
- `bold_collector_affiliations_expanded_prereview.csv` — pure LLM merge
- `bold_collector_affiliations_expanded.csv` — final with all decisions
- `bold_batch{1-5}_classifications_{gpt,claude}.csv` — LLM batch outputs
- `bold_disagree_for_review_with_judgements.csv` — reviewed DISAGREE (67)
- `bold_org_for_review_merged_pass1_pass2.csv` — reviewed ORGs (404)
- `bold_foreign_collecting_cell_year_panel.csv` — cell x year output panel

LLM prompt files in `Prompts/`:
- `prompt_collector_affiliations.txt` — original top-633
- `prompt_collectors_batch{1-5}.txt` — expansion batches

### Foreign Collecting Regressions (`reg_foreign_collecting.do`)

Log: `Logs/reg_foreign_collecting.log`

Eight tables (64 specifications) testing whether conflict selectively deters
foreign collectors while leaving domestic collecting unaffected. Uses Table 3
and Table 5 FE structures from `reg_spec1.do`.

**Table layout**: FC3a/b/c/d (Table 3 FE) and FC5a/b/c/d (+ Conflict×Richness).
Panel A (a/b): conflict = log(1+events). Panel B (c/d): conflict = 1[events>0].
Each table: 8 columns = {Domestic, Foreign, Distant, Collaboration} ×
{Contemporaneous, With Lags}.

**LHS variables**: `log1p_domestic`, `log1p_foreign` (regional+distant),
`log1p_distant`, `log1p_collab` (intensive); `any_domestic`, `any_foreign`,
`any_distant`, `any_collab` (extensive). Missing scores imputed to 0
(~206K cell-years).

**Key findings**:
- Conflict selectively deters foreign (especially distant) collectors;
  domestic collecting is unaffected
- Panel B (binary conflict) produces ~2× larger, more significant coefficients
  than Panel A (log events)
- Richness interaction (FC5 tables): conflict reduces foreign/distant collecting
  more in species-rich cells; sum Conflict×Richness L0-L2 for foreign goes
  from -0.041*** (Panel A) to -0.069*** (Panel B)
- Domestic collecting shows weak cumulative withdrawal only in Panel B
  extensive margin (sum L0-L2 = -0.010**)
- Collaboration (records with both domestic and foreign collectors) is too
  rare (~0.6% of cell-years) to show significant effects

**Sample**: 247,692 obs (contemporaneous), 221,626 (with lags). Outcome means:
log1p_domestic 0.17, log1p_foreign 0.12, log1p_distant 0.09, log1p_collab 0.02.

## Natural Products Pipeline (Option B)

Downstream discovery linkage: maps species sampled in BOLD/GBIF to bioactive
compounds via LOTUS+COCONUT NP databases. Tests whether conflict-induced
sampling shocks disproportionately affect chemically valuable species.

### Build order

```bash
python3 Scripts/22_download_lotus.py
python3 Scripts/22b_download_coconut.py
python3 Scripts/23_build_species_to_compounds.py
python3 Scripts/24_download_gbif_backbone.py
python3 Scripts/25_resolve_species_names.py        # ~40 min (includes GBIF API calls)
python3 Scripts/26_build_shared_species_universe.py # ~10 min
python3 Scripts/27_build_chemical_potential_panel.py # ~25 min
stata -b do DoFiles/merge_all_regressors.do
stata -b do DoFiles/reg_natural_products.do
```

### Key data files

```text
Data/raw/natural_products/lotus/             — LOTUS Zenodo dump (v11)
Data/raw/natural_products/coconut/           — COCONUT 2.0 CSV
Data/raw/gbif/backbone/backbone.zip          — GBIF Backbone Taxonomy (926 MB)
Data/processed/discovery/natural_products/
  species_compound_pairs.csv                 — 1.3M species-compound pairs (long)
  species_to_compounds.csv                   — 58,546 species summaries
  cell_year_chemical_potential.csv           — 246K cell × year × source_group rows
Data/processed/discovery/shared/
  shared_species_universe.csv                — 742,864 species (BOLD ∪ GBIF)
  bin_consensus_lookup.csv                   — 414K BINs with consensus species
  species_name_resolution.csv                — 768K names, 551K resolved (71.7%)
  cache/gbif_match_cache.csv                 — GBIF API fuzzy match cache
```

### Pipeline design

1. **Species → compound mapping** (Script 23): LOTUS + COCONUT as co-equal
   primary NP sources; compounds deduped via InChIKey across DBs. 58,546
   species with ≥1 compound; median 7 compounds per species.

2. **Taxonomic harmonization** (Scripts 24-25): Three-step name resolution
   via GBIF Backbone — gbifid_lookup (LOTUS metadata), exact canonicalName
   match, GBIF API fuzzy fallback (confidence ≥ 90). 41K synonym redirects;
   NP→universe linkage improves from 56% to 71% (+8,767 NP species).

3. **Shared species universe** (Script 26): BOLD (with BIN consensus
   recovery for 1.55M unnamed records) ∪ GBIF Plantae preserved-material.
   BIN consensus lookup persisted for downstream reuse.

4. **Chemical potential panel** (Script 27): Streams BOLD 20M + GBIF 15M
   with on-the-fly EPSG:6933 / 100km gridding (matching existing pipeline).
   Computes NP species count, compound count (InChIKey-deduped), NP share,
   per-kingdom breakdowns, and four robustness columns (strict BIN, no
   fuzzy, no BIN, named only). Signal is plant-driven via GBIF (mean 19.1
   NP species per combined cell-year, 82% nonzero).

5. **Merge** (merge_all_regressors.do): Conditional import behind
   `have_chempot` flag. Imports combined rows as primary + BOLD/GBIF
   decomposition. Handles Stata 32-char column name truncation. Generates
   log transforms and extensive-margin indicator.

### Regression results (`reg_natural_products.do`)

Six tables, all using Table 3 FE structure (cell + country×year + biome×year
+ road×year), cell-clustered SEs. Sample: 2005-2023.

**Table NP1** — NP species count: Conflict reduces NP species sampling at
-0.045*** (intensive, log events with lags). Cumulative L0-L2: -0.058**.

**Table NP2** — NP share: Insignificant — conflict does not shift sampling
composition toward/away from NP species. Compound diversity: -0.072**.

**Table NP3** — Conflict × Richness: Interaction is small and insignificant.

**Table NP4** — Source decomposition: GBIF drives the signal (cumulative
-0.083***); BOLD NP share significant at -0.014**.

**Table NP5** — Name-resolution robustness: All four variants give
near-identical coefficients (-0.045*** to -0.046***).

**Table NP6** — Stacked direct differential test: Each cell-year appears
twice (NP species, non-NP species), all controls and FEs interacted with
type. **Conflict × NP is zero across all specifications** — clean null on
disproportionality. Conflict reduces all species sampling uniformly.

**Bottom line**: Conflict reduces NP-relevant species sampling, but
proportionally to total sampling — no selective avoidance of chemically
valuable species. The NP decline is entirely volume-driven.

### Coordination with Option A

See `DOWNSTREAM_LINKAGE_TRACKER.md`. Shared artifacts in
`Data/processed/discovery/shared/` (universe, BIN lookup, name resolution)
may be read by Option A (publication linkage) but should not be rewritten.
Fungi consistency check across Options A and B is pending.

### Next steps

- Deduplicate ~221 name variants in expanded affiliations
- Second LLM round for 137 still-unresolved ORGs
