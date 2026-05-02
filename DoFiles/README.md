# Do-Files

Merge all regressor datasets into the BOLD panel:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/merge_all_regressors.do"
```

The do-file imports all outcome and regressor CSVs, merges on `cell_id` (and
`year` for panels), drops Antarctica and date-line edge cells, and saves:

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
