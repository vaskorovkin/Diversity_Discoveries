# AI Handover

Date: 2026-05-01

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
Exhibits/data/bold_grid100_cell_year_panel_collection_2005_2025.csv
Exhibits/data/bold_grid100_cell_year_panel_collection_2005_2025_summary.csv
```

After regenerating the collection-year panel, check:

```text
Exhibits/data/bold_grid100_cell_year_panel_collection_2005_2025_summary.csv
```

The panel uses BOLD `collection_year`, 2005-2025, 100 km equal-area land
cells, and zero-fills all land cell x year combinations. It is a strict
land-cell panel; coastal/island/marine-adjacent records outside the land-cell
universe are excluded for now.

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

The do-file estimates 4 tables (8 columns each, 32 specifications total).
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

Suggested commit summary:

```text
Complete regressor pipeline and Stata merge
```

Suggested commit description:

```text
Adds download and aggregation scripts for all regressor datasets: TerraClimate
climate anomalies (PDSI/tmax/ppt with 1981-2010 baseline), CHIRPS precipitation,
GRIP4 road density, GLOBIO4 MSA biodiversity intactness, and time-varying WDPA
protected-area panel. Includes fast v2 WDPA panel script using sjoin+clip.

Adds Stata merge do-file (DoFiles/merge_all_regressors.do) that builds the
complete analysis panel (BOLD_regressor_panel.dta) from all outcome and regressor
CSVs. Drops Antarctica and date-line edge cells. Logs to Logs/.

Updates all documentation: AI_HANDOVER.md, Scripts/README.md, DoFiles/README.md,
and regressor_dataset_options.md.
```
