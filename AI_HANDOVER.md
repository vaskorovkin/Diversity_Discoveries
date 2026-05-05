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
```

Build commands:

```bash
python3 Scripts/14_build_gbif_plantae_minimal.py
python3 Scripts/15_build_gbif_plantae_cell_year_panel.py
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/merge_all_regressors.do"
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec1_gbif_plantae.do"
```

The GBIF plant panel is a mirror of `reg_spec1.do`: same RHS, same FE structure, same 2005-2023 sample restriction, but with GBIF preserved/material Plantae outcomes.

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

## Collector Affiliation Pipeline (Parachute Science Analysis)

Goal: classify BOLD collectors as foreign or domestic relative to where they
collect, to measure "parachute science" — researchers who collect specimens in
countries other than their own.

### Pipeline steps

1. **Extract top collectors** (`09_institution_country_mapping.py`):
   Reads `bold_minimal_records.csv`, counts collector strings, outputs
   `bold_top500_collectors.csv` (raw collector strings with record counts).

2. **Split to individuals** (`11_build_collector_individuals.py`):
   Splits comma-separated collector strings (e.g., "D.Janzen, W.Hallwachs")
   into person-level rows. Output: `bold_top500_collector_individuals.csv`
   (633 unique individuals, covering ~85% of all BOLD records with a
   collector field).

3. **LLM affiliation guesses**: The prompt file
   `Data/processed/bold/prompt_collector_affiliations.txt` was pasted into
   ChatGPT and Claude separately. Both returned institution + country for
   each name. Saved as:
   - `bold_collectors_affiliations_gpt.csv` (81.5% matched, aggressive)
   - `bold_collectors_affiliations_claude.csv` (43.0% matched, cautious but
     gives country even when institution is unknown)

4. **Merge** (`11_merge_collector_affiliations.py`):
   Merges GPT + Claude answers. Status categories:
   - AGREED (231): both gave same country → accept
   - GPT_ONLY (257): GPT matched, Claude UNKNOWN → accept GPT
   - CLAUDE_ONLY (13): Claude matched, GPT didn't → accept Claude
   - REVIEWED (28): both answered but disagreed → manually resolved
   - ORG (33): organizations/teams, not people
   - AMBIGUOUS (37): single-word names, can't identify
   - UNRESOLVED (34): neither matched (15 have country from Claude's name-pattern guess)
   Output: `bold_collector_affiliations_merged.csv`

5. **Manual review**: 28 DISAGREE rows resolved by hand. Key decisions:
   - Home institution country is coded (not collecting country)
   - Trish/T. Shute → CAN (CBG Guelph, verified from BOLD records)
   - Carolina Cano → CRI (ACG/Janzen project, verified from BOLD records)
   - Marco Millan Valera → GBR (Wellcome Sanger, verified from BOLD records)
   - Joseph Hubert Masoy → MDG (Claude was correct; GPT said PNG)
   - GPT hallucinated "Parks Canada" for several UK-based volunteers (rows 606-613)
   - SANBI vs SANParks distinction matters (different South African orgs)

6. **Fill remaining countries** (`12_fill_missing_countries.py`):
   For the ~89 collectors without LLM country, infers country from BOLD
   record data. Three methods, applied in priority order:
   - ORGs: hardcoded lookup table (BIOBus→CAN, Parks Canada→CAN, ICFC Manu→PER, etc.)
   - BOLD institution field: maps `inst` values to countries (e.g., "University of Guelph"→CAN)
   - Co-collector inference: finds other names in the same collector string
     that already have resolved countries, votes by frequency
   - MANUAL_FIXES dict: 5 hand-verified corrections applied after auto-inference
   Result: 630/633 (99.5%) coverage.

### Retired scripts

The following scripts were superseded by the LLM-based approach and removed:
- `10_researcher_affiliation_search.py` — Brave Search API lookup (low accuracy, API key dependent)
- `12_collector_country_from_bold.py` — added BOLD collecting-country columns, but redundant since the regression compares LLM home country vs cell country directly
- `12_search_collector_affiliations.py` — wrapper around the old search approach
- `infer_affiliations_from_search.py` — original Google/DuckDuckGo search script

### Coverage as of 2026-05-05

- 633 unique individuals extracted from top-500 raw collector strings
- 630/633 (99.5%) have a country assignment after LLM merge + manual review
  + `12_fill_missing_countries.py` (auto 83 + 5 manual corrections)
- 3 truly unresolvable: Allinghman (#267, zero BOLD records), local collector
  (#435, generic label), Kjurstens (#478, zero BOLD records)
- Manual corrections in `12_fill_missing_countries.py` MANUAL_FIXES dict:
  Ethel Aberg→SWE (Station Linné), lgt. W.Stark→AUT, E. Friedrich→DEU,
  Koehler→DEU (inst=Bavarian State Collection, co-collector vote was wrong),
  Ashton→GBR

### Key findings from LLM comparison

- GPT is much more aggressive (81.5% vs 43% coverage) but occasionally
  hallucinates institutions (Parks Canada for UK volunteers)
- Claude is cautious but provides useful country guesses from name patterns
  (West African surnames → CIV/BFA/GIN)
- Country agreement where both answered: 87% (366/421)
- Both LLMs know well-published taxonomists well; both fail on
  parataxonomists and field technicians

7. **Parachute science panel** (`13_build_parachute_panel.py`):
   For each geocoded BOLD record with a collector field, matches names to
   home countries and compares to `country_iso`. Multi-collector records
   use averaged scores (1 foreign + 1 domestic = 0.5 foreign). Aggregates
   to cell × year. Output: `collectors/bold_parachute_cell_year_panel.csv`
   with: `records_total`, `records_matched`, `records_unmatched`,
   `foreign_score_sum`, `domestic_score_sum`, `foreign_share`,
   `n_collectors_foreign`, `n_collectors_domestic`.
   Merged into Stata panel via `merge 1:1 cell_id year` in
   `DoFiles/merge_all_regressors.do`.

### Directory structure

All collector/affiliation files live in `Data/processed/bold/collectors/`:
- `bold_top500_collectors.csv` — raw collector strings (top 500)
- `bold_top500_collector_individuals.csv` — 633 individuals from top 500
- `bold_all_collector_individuals.csv` — all ~101K unique individuals
- `bold_top999999_collectors.csv` — all raw collector strings
- `bold_collectors_affiliations_gpt.csv` — GPT classifications (top 633)
- `bold_collectors_affiliations_claude.csv` — Claude classifications (top 633)
- `bold_collector_affiliations_merged.csv` — merged + reviewed + filled
- `bold_parachute_cell_year_panel.csv` — cell × year output panel
- `bold_batch1_classifications_gpt.csv` — GPT batch 1 results (expansion)
- `supply_top10_collectors.csv` — top 10 collector strings exhibit

LLM prompt files are in `Prompts/`:
- `prompt_collector_affiliations.txt` — original top-633 prompt
- `prompt_collectors_batch{1-5}.txt` — expansion batches (9,358 new names)

### Descriptive analysis (DoFiles/desc_parachute.do)

Key findings from `desc_parachute.do` (run after merge):
- Mean foreign_share: 0.37 across cell-years with matched collectors
- Poorer countries get more foreign collecting: GDP Q1 52% vs Q4 20%
- More biodiverse cells get more: richness Q4 51% vs Q1 19%
- Biodiversity hotspots: 62% foreign vs non-hotspot 30%
- Recommended estimation: WLS with `aweight = records_matched` — cells
  with more classified collectors are more informative. Do NOT impute
  unclassified records as domestic (biases toward finding effects).

### Geographic coverage ceiling

- 51,779 cell-years have both BOLD records and a collector field
- 14,710 cell-years have records but blank collector fields (unrecoverable)
- Top 633 collectors cover 84.5% of records but only 5,766 cell-years
  (geographically concentrated — mainly Janzen/Hallwachs Costa Rica)
- Coverage curve: top 5K → 27,604 cell-years (53%); top 10K → 35,462 (69%)

### Expansion to 10,000 collectors (in progress)

To improve geographic coverage, extracted 10,000 collector individuals using
`09_institution_country_mapping.py --top-n 10000` and
`11_build_collector_individuals.py --top-n 10000`. The 9,358 new names
(beyond the original 633) are split into 5 batch prompts in `Prompts/`:
- Batch 1 (ranks 1-2432): uses original rank numbering — already classified
  by GPT, saved as `collectors/bold_batch1_classifications_gpt.csv`
- Batches 2-5 (~2000 names each): use sequential 1-N numbering (GPT stopped
  early when batch 1 used original ranks past 2000)
- Each batch prompt includes "IMPORTANT: classify ALL names" instruction

After all 5 batches are classified:
1. Write a merge script to combine the 5 batch results with the original 633
2. Re-run `13_build_parachute_panel.py` with the expanded lookup
3. Re-run Stata merge and descriptives

### Next steps

- Classify remaining batches 2-5 via GPT (user runs manually)
- Merge expanded classifications into a single affiliations file
- Rebuild parachute panel with ~10K collectors for better geographic coverage
- Add `foreign_share` to regression specifications (OLS + WLS)
