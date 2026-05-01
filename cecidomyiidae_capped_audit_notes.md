# Cecidomyiidae Capped Download Audit

Important note: Diptera is not fully complete. The remaining incomplete piece
is Costa Rica (`C-R`) Cecidomyiidae. The capped Costa Rica file is a diagnostic
partial extract and must not be treated as complete.

Two capped BOLD TSV files are relevant:

- `Data/raw/bold/diagnostic_capped_redundant/cecidomyiidae_global_capped/bold_global_diptera_family_cecidomyiidae_capped_records.tsv`
- `Data/raw/bold/diptera_cecidomyiidae_costa_rica_capped/bold_cecidomyiidae_costa_rica_capped_records.tsv`

Both contain exactly 1,000,000 data rows. The global capped extract contains
765,476 Costa Rica rows. The Costa Rica capped extract contains 1,000,000
Costa Rica rows. Their overlap by record/process/sample key is 765,476, so the
Costa Rica-specific capped file adds 234,524 Costa Rica records beyond the
global capped file.

Local audit outputs:

- `Output/audits/bold_cecidomyiidae_capped_file_audit.md`
- `Output/audits/bold_cecidomyiidae_capped_file_field_audit.csv`
- `Output/audits/bold_cecidomyiidae_capped_file_year_counts.csv`

## Candidate Split Fields In The Files

For the Costa Rica capped extract:

- `province/state`: 100% nonmissing, 6 unique values. Largest bucket is
  Guanacaste Province with 440,037 rows.
- `region`: 95.6% nonmissing, 12 unique values.
- `sector`: 95.6% nonmissing, 27 unique values.
- `site`: 95.6% nonmissing, 88 unique values.
- `site_code`: 97.9% nonmissing, 79 unique values.
- `coord`: 100% nonmissing, 113 unique coordinate pairs.
- `collection_date_start`: 100% nonmissing, 1,472 unique dates.
- `collectors`: 100% nonmissing, 33 unique values.
- `bold_recordset_code_arr`: 100% nonmissing, 1,993 unique values.
- `bin_uri`: 99.4% nonmissing, 45,222 unique values.

These fields would be useful for an offline partition after download. Most are
not useful as BOLD API split filters.

## BOLD API Split Tests

Date/year filters do not work with the current BOLD summary/download API.
The preprocessor treats values such as `collection_date_start:2020`,
`collection_year:2020`, and `year:2020` as generic ID searches, not date
filters. Summary calls return HTTP 500 or timeout.

Province/state syntax is accepted by the preprocessor when written as
`geo:province/state:<value>`, but it does not reduce the summary count in
practice: all tested Costa Rica provinces returned the full Costa Rica
Cecidomyiidae count of 1,122,446.

Institution filtering works, but it is not a useful split because almost all
Costa Rica Cecidomyiidae records are from one institution:

- `inst:name:Centre for Biodiversity Genomics`: 1,122,430
- `inst:name:Mined from GenBank, NCBI`: 14

Other fields such as `sector`, `site`, `site_code`, `coord`,
`collection_code`, `collectors`, and `bold_recordset_code_arr` are matched by
the preprocessor as generic ID terms rather than real filters.

## Interpretation

The BOLD API still does not offer a clean way to split Costa Rica
Cecidomyiidae below the 1M cap using collection year, province/state, site,
recordset, or coordinates. The capped Costa Rica file is useful and adds
coverage relative to the global capped extract, but it should not be treated as
complete. The remaining route is either a BOLD bulk export request or accepting
a documented capped gap for Costa Rica Cecidomyiidae.
