# Do-Files

Merge all regressor datasets into the BOLD panel:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/merge_all_regressors.do"
```

The do-file imports all outcome and regressor CSVs, merges on `cell_id` (and
`year` for panels), trims the master panel to `2005-2024` for compatibility
with the conflict panel, optionally merges the GBIF preserved/material plant
panel if it exists, optionally merges the static GBIF pre-period plant
richness file if it exists, drops Antarctica and date-line edge cells, and saves:

```text
Data/analysis/BOLD_regressor_panel.dta
Logs/merge_all_regressors.log
```

## 50 km Yearly Experiment Panel

After the `test_50km_year` Python builders and Earth Engine exports are in
place, build the 50 km experiment panel with:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/build_tests_spatial_time_panel_50km_year.do"
```

This expects the time-varying WDPA protected-area panel at:

```text
Data/regressors/tests_spatial_time/wdpa/wdpa_protected_panel_50km.csv
```

Create it with the May 2026 WDPA/WDOECM File Geodatabase:

```bash
python3 Scripts/aggregate_wdpa_protected_panel_100km_v2.py --variant test_50km_year --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

## 50 km Quarterly Panel

The quarterly 50 km build is available as an experimental panel:

- BOLD outcomes are quarter-resolved
- MODIS burned area is quarter-resolved
- UCDP, ComCat, IBTrACS, TerraClimate, and CHIRPS are quarter-resolved
- Hansen forest loss is source-limited to annual loss year and is expanded to
  quarters with `hansen_source_freq = "annual"`
- harmonized nightlights are source-limited to annual values and are expanded
  to quarters with `ntl_source_freq = "annual_harmonized"`
- WDPA protected share is annual and repeated within quarters, using the same
  `STATUS_YR`-based 50 km panel as the yearly experiment
- World Bank GDP remains annual and is merged by `iso_a3 x year`

Build it with:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/build_tests_spatial_time_panel_50km_quarter.do"
```

This writes:

```text
Data/analysis/tests_spatial_time/BOLD_regressor_panel_50km_quarter.dta
Logs/build_tests_spatial_time_panel_50km_quarter.log
```

## Regression Specifications

Run the main regression table do-file with:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec1.do"
```

At the top of `reg_spec1.do`, set `local panel_mode` to one of:

- `"100-yearly"`: baseline 100 km x year panel; log `Logs/reg_spec1_100km_year.log`
- `"50-yearly"`: experimental 50 km x year panel; log `Logs/reg_spec1_50km_year.log`
- `"50-quarterly"`: experimental 50 km x quarter panel; log `Logs/reg_spec1_50km_quarter.log`

The do-file restricts to 2005-2023 and estimates 5 tables (8 specifications
each, 40 total):

- **Table 1** (Cell + Year FE): baseline with `log_gdp_pc`, `log_gdp_pc_sq`,
  `protected_share`, and GDP×PA interactions.
- **Table 2** (Cell + Country×Year FE): GDP main effects absorbed; GDP×PA
  interactions and conflict survive.
- **Table 3** (Table 2 + Biome×Time FE + Road×Time controls): adds
  biome-by-time absorbed effects and road-density-by-time controls, where time
  is year in yearly modes and quarter in quarterly mode.
- **Table 4** (Table 3 + Conflict×MSA interaction): adds `c.conflict#c.msa_overall`
  to test whether conflict effects vary with biodiversity intactness.
- **Table 5** (Table 3 + Conflict×Richness interaction): adds
  `c.conflict#c.richness_std` (standardized IUCN species richness).

Each table has 8 columns: {Any, log(1+N)} × {Contemporaneous, With Lags} ×
{log(1+events), 1[events>0]} conflict measures. Lag specifications include
L0-L2 distributed lags for conflict, PDSI, and tmax with `lincom` sum tests.

Standard errors are clustered at cell level. In quarterly mode, the Stata panel
time variable is `time_id = yq(year, quarter)`, so `L.` and `L2.` are
one-quarter and two-quarter lags rather than one-year and two-year lags.

`reg_spec1.do` also has a quarterly-only switch:

```stata
// local quarterly_cell_season_fe "on"
local quarterly_cell_season_fe "off"
```

When switched on for `50-quarterly`, it adds cell-by-quarter-of-year fixed
effects (`cell_id x quarter`) and writes a `_cellseason.log` file.

### Africa-Only Regression Mirror

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec1_africa.do" all
```

`reg_spec1_africa.do` is the same 5-table / 8-column specification as
`reg_spec1.do`, but restricts the estimation sample to `continent == "Africa"`
after the 2005-2023 time restriction. It accepts the same panel modes:

- `"100-yearly"`: log `Logs/reg_spec1_100km_year_africa.log`
- `"50-yearly"`: log `Logs/reg_spec1_50km_year_africa.log`
- `"50-quarterly"`: log `Logs/reg_spec1_50km_quarter_africa.log`
- `"all"`: runs the three modes sequentially

Recent Africa runs indicate that average conflict effects are generally weaker
at 100 km, but 50 km yearly and 50 km quarterly effects remain negative and
large relative to Africa's lower dependent-variable means. The strongest and
most stable Africa signal is the `Conflict x Species Richness` gradient in
Table 5.

### Lead-Placebo Regression Mirror

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec1_leads.do" all
```

`reg_spec1_leads.do` mirrors `reg_spec1.do` but adds two future conflict terms,
`F1_conflict` and `F2_conflict`, as placebo checks. It keeps 2024 in memory only
to construct future conflict, while setting the main outcomes missing after
2023. In the reported tables, lead placebo terms are included only in the same
four lag-specification columns that include `L1_conflict` and `L2_conflict`, so
`Sum conflict F1-F2` is directly comparable to `Sum conflict L0-L2`.

Logs:

- `Logs/reg_spec1_100km_year_leads.log`
- `Logs/reg_spec1_50km_year_leads.log`
- `Logs/reg_spec1_50km_quarter_leads.log`

Use these logs to assess whether the main distributed-lag estimates are
preceded by significant future-conflict placebo effects.

### TWFE Spatial-Time Event-Study Diagnostic

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_event_study_twfe_simple.do"
```

This is a deliberately simpler event-study diagnostic than
`reg_event_study.do`. It runs only TWFE onset event studies for the three
panel modes:

- `100-yearly`
- `50-yearly`
- `50-quarterly`

Use the clickers at the top to run one mode or all modes, choose simple vs rich
FE, and choose short vs long event windows. In rich-FE mode it uses the same
control family as `reg_spec1.do`; in quarterly mode the time variable is
`time_id = yq(year, quarter)`.

Logs saved to `Logs/reg_event_study_twfe_simple.log`. Figures saved to
`Output/figures/event_study/`.

### Conflict Signal Decomposition

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_conflict_signal_decomposition.do"
```

This is not an event-study file. It diagnoses why the main `reg_spec1` TWFE
tables are stronger than the onset event studies by rerunning distributed-lag
conflict models across:

- full panel
- ever-conflict cells only
- cells excluding conflict-in-2005 left-censored cases
- clean first-onset cells plus never-conflict controls

It also compares current conflict exposure with lagged cumulative conflict
stock. Outputs are written to `Exhibits/tables/conflict_signal_decomp_*.tex`
and `Exhibits/tables/conflict_signal_stock_*.tex`; log saved to
`Logs/reg_conflict_signal_decomposition.log`.

### GBIF Plantae Regression Mirror

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec1_gbif_plantae.do"
```

Runs the same 5-table / 8-column structure as `reg_spec1.do`, with the same
RHS variables and fixed effects, but swaps the dependent variable to the GBIF
preserved/material Plantae panel merged into `Data/analysis/BOLD_regressor_panel.dta`
(with aliased GBIF plant columns preserved in the merged panel). It now also
adds a sixth table that mirrors the richness-interaction design using a static
GBIF pre-period plant-richness moderator.
The sample restriction remains 2005-2023 to match `reg_spec1.do`.

If present, the merged panel also carries aliased static GBIF pre-period plant
richness controls:

- `gbif_p_rich_base`
- `gbif_p_rich_log`
- `gbif_p_rich_z`
- `gbif_p_genrich_base`
- `gbif_p_genrich_log`
- `gbif_p_genrich_z`
- `gbif_p_rich_log_std`

Logs saved to `Logs/reg_spec1_gbif_plantae.log`.

### BIN Outcome Regressions

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec_bin.do"
```

Replaces total-record LHS with BIN (Barcode Index Number) outcomes.
`n_bins` = distinct BINs sampled per cell-year (species richness of sampling);
`n_new_bins` = globally new BINs first observed in that cell-year (discovery).

- **Table 1**: n_bins — Country×Year + Biome×Year FE (mirrors reg_spec1 Table 3)
- **Table 2**: n_new_bins — same FE structure
- **Table 3**: n_bins — Conflict × Richness interaction (mirrors reg_spec1 Table 5)
- **Table 4**: n_new_bins — Conflict × Richness interaction
- **Table 5**: n_new_bins — sampling effort control (log1p_total), cols 1-4
  without interaction, cols 5-8 with Conflict × Richness

Logs saved to `Logs/reg_spec_bin.log`.

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_event_study_bin_new.do"
```

Companion event-study file for the BIN discovery outcomes
`any_n_new_bins` and `log1p_n_new_bins`. Mirrors the sampling event-study
ladder: TWFE, BJS, continuous-intensity distributed lag, dCDH, `csdid`, and
multi-shock TWFE/BJS comparisons.

Logs saved to `Logs/reg_event_study_bin_new.log`. Figures saved to
`Output/figures/event_study/`.

### Organism Heterogeneity

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec_organisms.do"
```

Runs the Table 3 spec from reg_spec1 (Country×Year + Biome×Year FE) with
kingdom/phylum-level LHS variables:

- **Table 1**: Chordata records
- **Table 2**: Insecta records
- **Table 3**: Plantae + Fungi records

Uses a `run_table` program to avoid repeating the 8-regression block.
Logs saved to `Logs/reg_spec_organisms.log`.

### Benchmarking: Sampling vs Discovery Decomposition

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec_benchmark.do"
```

Compact 8-column table comparing conflict coefficients across outcomes:

- **Cols 1-2**: LHS = log1p_total (sampling volume)
- **Cols 3-4**: LHS = log1p_n_new_bins (discovery)
- **Cols 5-6**: LHS = log1p_n_new_bins controlling for log1p_total
- **Cols 7-8**: Same as 5-6, restricted to cell-years with total_records > 0
  (intensive margin only)

All columns use log(1+events) conflict measure. Logs saved to
`Logs/reg_spec_benchmark.log`.

### Sampling Event-Study Ladder

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_event_study.do"
```

Main event-study file for biodiversity sampling outcomes:

- `any_total`
- `log1p_total`

Implements the dynamic identification ladder:

- **Table 1**: conflict-only TWFE vs BJS event-study comparison
- **Table 2**: continuous-treatment distributed lag + dCDH + `csdid`
- **Table 3**: multi-shock BJS comparison (conflict, drought, fire)
- **Table 4**: multi-shock TWFE comparison
- **Figures 1-6**: paired TWFE/BJS plots, multi-shock plots, and
  continuous-treatment plots

The file has an FE clicker at the top:

- `rich`: cell + country×year + biome×year FE
- `simple`: cell + year FE only

Logs saved to `Logs/reg_event_study.log`. Figures saved to
`Output/figures/event_study/`.

### Publication Linkage (Option A)

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_publications.do"
```

Runs the corrected BOLD specimen-cohort publication-yield tables. The outcome
is downstream PubMed yield within fixed windows after specimen collection
(`0-3`, `0-5`, and `0-10` years), with completeness flags by window. The main
tables mirror the Table 3 and Table 5 structures from `reg_spec1.do`.

Logs saved to `Logs/reg_publications.log`.

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_event_study_publications_5yr.do"
```

Companion event-study file for the corrected 5-year downstream BOLD
publication-yield outcomes:

- `any_bold_pub_total_0_5yr`
- `log1p_bold_pub_total_0_5yr`

Because these outcomes require `bold_pub_complete_0_5yr == 1`, this file uses
a shorter onset design than the sampling file:

- conflict onset uses `K=5`
- event-study window is `-5/+8`

Otherwise it mirrors the main event-study ladder: TWFE, BJS,
continuous-intensity distributed lag, dCDH, `csdid`, and multi-shock TWFE/BJS
comparisons.

Logs saved to `Logs/reg_event_study_publications_5yr.log`. Figures saved to
`Output/figures/event_study/`.

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_publications_gbif_exposure.do"
```

Runs the separate GBIF Literature API exposure tables. The default outcomes are
cohort-timed (`gbif_pub_*_0_3yr`, `gbif_pub_*_0_5yr`, `gbif_pub_*_0_10yr`):
collection cell-year `t` receives dataset-linked publications only in
`[t, t+K]`. This fixes the timing problem but remains dataset-level exposure,
not specimen-specific downstream publication yield. The 0-5 year horizon is
the primary diagnostic; 0-3 and 0-10 years are horizon-sensitivity checks. The
do-file runs total and Plantae outcomes for all three horizons and prints the
effective sample years after each completeness-window restriction. Legacy
publication-year exposure tables remain in the do-file behind an opt-in local
switch.

Logs saved to `Logs/reg_publications_gbif_exposure.log`.

### Natural Products (Option B)

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_natural_products.do"
```

Tests whether conflict reduces sampling of natural-product-relevant species
(species with known bioactive compounds in LOTUS/COCONUT). Uses the same
Table 3 FE structure (Cell + Country×Year + Biome×Year + Road×Year) as
`reg_spec1.do`. Requires the chemical-potential panel to be merged into
`BOLD_regressor_panel.dta` (conditional import in `merge_all_regressors.do`).

Seven tables:

- **Table NP1**: NP species count — 1[NP>0] (extensive) and ln(NP+1) (intensive).
  8 columns: {Contemp, Lags} × {log(1+events), 1[events>0]}.
- **Table NP2**: NP share (compositional test) and ln(unique compounds + 1).
  Same 8-column structure.
- **Table NP3**: Conflict × Species Richness interaction with NP LHS.
  Mirrors Table 5 from `reg_spec1.do`.
- **Table NP4**: Source decomposition — BOLD vs GBIF. 4 columns:
  {ln(NP+1), NP share} × {BOLD, GBIF}. With lags, log(1+events) only.
- **Table NP5**: Name-resolution robustness. 4 columns: strict BIN,
  no fuzzy, no BIN, named only. With lags, log(1+events) only.
- **Table NP6**: Stacked NP vs non-NP — direct differential test.
  Each cell-year stacked as 2 rows (NP species, non-NP species). All
  controls and FEs interacted with type. 4 columns: {Contemp, Lags} ×
  {log(1+events), 1[events>0]}. Key coefficient: `Conflict × NP`.
- **Table NP7**: Intensive-margin benchmark — sampling decomposition.
  8 columns (all log(1+events), {Contemp, Lags}): cols 1-2 ln(NP+1)
  baseline; cols 3-4 add log(1+total_records) sampling control; cols 5-6
  same restricted to total_records>0; cols 7-8 NP share on total_records>0.

Logs saved to `Logs/reg_natural_products.log`.

### Natural Products — GBIF Plantae Only (Option B)

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_natural_products_gbif.do"
```

Restricts NP outcomes to the GBIF Plantae pipeline only (98.5% of NP
species observations). Imports `gbif_plantae` rows from the chemical-
potential CSV directly. Uses GBIF pre-period plant richness as the
interaction moderator instead of IUCN total richness.

Five tables:

- **Table GP1**: GBIF plant NP species count. 8 columns:
  {extensive, intensive} × {Contemp, Lags} × {log(1+events), 1[events>0]}.
- **Table GP2**: NP share + compound diversity. Same 8-column structure.
- **Table GP3**: Conflict × GBIF Plant Richness interaction. 8 columns.
- **Table GP4**: Stacked NP vs non-NP plants — direct differential test.
  4 columns: {Contemp, Lags} × {log(1+events), 1[events>0]}.
- **Table GP5**: Intensive-margin benchmark. 10 columns (all log(1+events)):
  cols 1-2 baseline full sample; cols 3-4 restricted to GBIF rec>0 without
  effort control; cols 5-6 full with effort control; cols 7-8 rec>0 with
  effort control; cols 9-10 NP share on rec>0.

Logs saved to `Logs/reg_natural_products_gbif.log`.

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_event_study_natural_products_gbif.do"
```

Companion event-study file for the primary GBIF Plantae natural-products
outcomes:

- `gp_np_any`
- `gp_np_log`

Mirrors the main event-study ladder: TWFE, BJS, continuous-intensity
distributed lag, dCDH, `csdid`, and multi-shock TWFE/BJS comparisons.

Logs saved to `Logs/reg_event_study_natural_products_gbif.log`. Figures saved
to `Output/figures/event_study/`.

### Foreign vs Domestic Collecting Composition

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_foreign_collecting.do"
```

Tests whether conflict selectively deters foreign collectors while leaving
domestic collecting unaffected. Uses the same Table 3 and Table 5 FE
structures from `reg_spec1.do`. Eight tables (64 regressions total), organized
as Panel A (conflict = log(1+events)) and Panel B (conflict = 1[events>0]):

- **FC3a**: Intensive margin, log(1+events) — Table 3 FE
- **FC3b**: Extensive margin, log(1+events) — Table 3 FE
- **FC3c**: Intensive margin, 1[events>0] — Table 3 FE
- **FC3d**: Extensive margin, 1[events>0] — Table 3 FE
- **FC5a**: Intensive + Conflict×Richness, log(1+events)
- **FC5b**: Extensive + Conflict×Richness, log(1+events)
- **FC5c**: Intensive + Conflict×Richness, 1[events>0]
- **FC5d**: Extensive + Conflict×Richness, 1[events>0]

Each table has 8 columns: {Domestic, Foreign, Distant, Collaboration} ×
{Contemporaneous, With Lags}. LHS variables are `log1p_*` / `any_*` versions
of `domestic_score_sum`, `foreign_score_sum` (regional+distant),
`distant_score_sum`, and `records_collab`. Missing scores imputed to 0
before transformation.

Logs saved to `Logs/reg_foreign_collecting.log`.

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/desc_foreign_collecting.do"
```

Standalone descriptive companion to `reg_foreign_collecting.do`. Reads
`BOLD_regressor_panel.dta` and produces coverage counts, summary stats,
correlations, histograms, and binscatters of foreign / domestic / distant /
collaborative collecting against GDP, richness, biome, and hotspot status.
Figures exported to `Exhibits/`. Logs saved to
`Logs/desc_foreign_collecting.log`.
