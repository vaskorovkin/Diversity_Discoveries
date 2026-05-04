# Exhibits Pipeline Plan

This note records the planned Python exhibit pipeline for BOLD summary
statistics, maps, and cell-level correlations.

## Output Folder

Write exhibit-ready outputs to:

```text
Exhibits/
```

Suggested structure:

```text
Data/processed/bold/
Exhibits/tables/
Exhibits/figures/
Exhibits/maps/
```

## Script Structure

Use separate scripts so each Roman-letter block can be rerun independently,
while sharing compact prepared data:

```text
Scripts/00_build_bold_minimal.py
Scripts/01_tables_counts.py
Scripts/02_timeseries.py
Scripts/03_maps_grid.py
Scripts/04_maps_admin1.py
Scripts/05_cell_correlations.py
```

The expensive step is `00_build_bold_minimal.py`, which streams raw BOLD TSVs
once and writes compact intermediate files. Later scripts should read those
compact files and should not need to re-stream all raw downloads.

## I. Tables With Observation Counts

Generate tables with BOLD row counts, labeled as `record_count` rather than
specimen abundance:

- observations by kingdom
- Animalia observations by class

Include useful supporting columns where feasible:

```text
record_count
records_with_coordinates
share_with_coordinates
unique_countries
unique_species
first_collection_year
last_collection_year
```

Tables and time series should use all records, including records without
coordinates.

## II. Time Series Graphs

Generate observation count by year time series:

- raw counts
- `log(1 + count)`

Use `collection_year` from `collection_date_start` as the main sampling-year
measure. If easy, also generate secondary time series based on
`sequence_upload_year`.

## III. Maps With Counts

Generate both:

- 100 km equal-area grid maps
- subnational/admin-1 maps

Initial map set:

- whole world, all observations
- whole world, Chordata only

Use coordinate-present records only for maps. Use raw counts with a logarithmic
color scale, for example `matplotlib.colors.LogNorm(vmin=1, vmax=max_count)`.
Zero/no-data cells or regions should be white or transparent.

The preferred first-pass grid is 100 km equal-area cells. Later robustness maps
can use 50 km and 200 km cells.

## IV. Cell-Level Correlations

Build a global 100 km land-cell universe. Include cells with zero BOLD records
so zeros represent no observed sampling, not missing data.

For each cell and kingdom:

```text
record_count = observed BOLD rows in the cell and kingdom
record_count = 0 if no records for that kingdom-cell
log_record_count = log(1 + record_count)
```

Generate pairwise kingdom correlations for:

- whole world
- South America
- Africa

Generate both:

- correlations in raw levels
- correlations in `log(1 + count)`

Do not include a presence/absence correlation table in the first pass.

## Notes

- Maps and correlations use coordinate-present records only.
- Tables and time series use all records.
- BOLD records are barcode/sequence rows and may not equal unique specimens.
- Keep the Costa Rica Cecidomyiidae caveat visible: Diptera is not fully
  complete because Costa Rica Cecidomyiidae exceeds the BOLD API cap.
