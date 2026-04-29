# Do-Files

Run the pilot import from Stata with:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/01_import_bold_pilot.do"
```

The do-file imports:

```text
Data/processed/bold/bold_trochilidae_costa_rica_minimal.tsv
```

and writes:

```text
Data/processed/bold/bold_trochilidae_costa_rica_minimal.dta
```

The minimal TSV is already cleaner than the raw BOLD export for Stata: it avoids the long sequence strings, nested list-looking primer fields, and bracketed coordinate field in the raw records.

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
