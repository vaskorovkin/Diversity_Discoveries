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
Exhibits/data/bold_grid100_cell_year_panel_upload_2005_2025.csv
Exhibits/data/bold_grid100_cell_year_panel_upload_2005_2025_summary.csv
```

Current panel audit:

```text
land_cells: 14,566
panel_rows: 305,886
coordinate_rows_in_year_window: 17,439,280
coordinate_rows_in_land_cells: 15,302,751
coordinate_rows_outside_land_cells: 2,136,529
total_records: 15,302,751
animalia_records: 14,930,434
plantae_records: 281,388
fungi_records: 86,464
bacteria_records: 4,465
```

The panel uses BOLD `sequence_upload_year`, 2005-2025, 100 km equal-area land
cells, and zero-fills all land cell x year combinations. It is a strict
land-cell panel; coastal/island/marine-adjacent records outside the land-cell
universe are excluded for now.

Local coverage audit:

```bash
python3 Scripts/audit_bold_taxon_coverage.py
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

## Commit Preparation

Current prepared changes are code/docs only; data and output remain ignored.

Suggested commit summary:

```text
Add BOLD exhibit pipeline and cell-year panel
```

Suggested commit description:

```text
Adds exhibit scripts for BOLD minimal records, summary tables, time-series plots, grid/admin maps, cell-level correlations, and the 2005-2025 upload-year cell panel. Includes the capped Costa Rica Cecidomyiidae file by default while continuing to exclude redundant capped diagnostics, and documents the land-cell panel caveat for downstream Stata regressions.
```
