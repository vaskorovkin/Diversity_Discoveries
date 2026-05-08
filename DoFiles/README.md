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

Run the global BOLD Fungi import and summary stats with:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/02_import_bold_fungi_global.do"
```

The do-file imports:

```text
Data/processed/bold/bold_global_fungi_minimal.tsv
```

and writes:

```text
Data/processed/bold/bold_global_fungi_minimal.dta
Data/processed/bold/bold_global_fungi_summary.log
```

Rows in the global Fungi file are BOLD sequence/marker records, not necessarily unique specimens.

## Regression Specifications

Run the main regression table do-file with:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/reg_spec1.do"
```

The do-file loads `Data/analysis/BOLD_regressor_panel.dta`, restricts to
2005-2023, and estimates 4 tables (8 specifications each, 32 total):

- **Table 1** (Cell + Year FE): baseline with `log_gdp_pc`, `log_gdp_pc_sq`,
  `protected_share`, and GDP×PA interactions.
- **Table 2** (Cell + Country×Year FE): GDP main effects absorbed; GDP×PA
  interactions and conflict survive.
- **Table 3** (Table 2 + Biome×Year FE + Road×Year controls): adds
  `i.resolve_biome_num#i.year` absorbed and `c.road_density_km_per_km2#i.year`
  as regressors.
- **Table 4** (Table 3 + Conflict×MSA interaction): adds `c.conflict#c.msa_overall`
  to test whether conflict effects vary with biodiversity intactness.
- **Table 5** (Table 3 + Conflict×Richness interaction): adds
  `c.conflict#c.richness_std` (standardized IUCN species richness).

Each table has 8 columns: {Any, log(1+N)} × {Contemporaneous, With Lags} ×
{log(1+events), 1[events>0]} conflict measures. Lag specifications include
L0-L2 distributed lags for conflict, PDSI, and tmax with `lincom` sum tests.

Standard errors clustered at cell level. Logs saved to `Logs/reg_spec1.log`.

Legacy files `reg_spec1_global_south.do` and `reg_spec1_country_year_fe.do` are
superseded by `reg_spec1.do`.

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
