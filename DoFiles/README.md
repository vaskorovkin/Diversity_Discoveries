# Do-Files

Merge all regressor datasets into the BOLD panel:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/merge_all_regressors.do"
```

The do-file imports all outcome and regressor CSVs, merges on `cell_id` (and
`year` for panels), trims the master panel to `2005-2024` for compatibility
with the conflict panel, drops Antarctica and date-line edge cells, and saves:

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

Each table has 8 columns: {Any, log(1+N)} × {Contemporaneous, With Lags} ×
{log(1+events), 1[events>0]} conflict measures. Lag specifications include
L0-L2 distributed lags for conflict, PDSI, and tmax with `lincom` sum tests.

Standard errors clustered at cell level. Logs saved to `Logs/reg_spec1.log`.

Legacy files `reg_spec1_global_south.do` and `reg_spec1_country_year_fe.do` are
superseded by `reg_spec1.do`.
