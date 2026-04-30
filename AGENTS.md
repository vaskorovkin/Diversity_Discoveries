# Agent Guide

This repository is a research data project. Preserve downloaded data and never remove or overwrite user data unless explicitly asked.

## Ground Rules

- Work from `/Users/vasilykorovkin/Documents/Diversity_Discoveries`.
- Keep `Data/`, `Output/`, and `Literature/*.pdf` out of Git.
- Do not commit raw data, processed TSV/DTA files, generated maps, audit CSVs, or PDFs.
- Use `python3`, not `python`.
- Stata scripts target Stata 16.
- BOLD downloads can be slow and rate-limited. Avoid running multiple large BOLD API jobs at once.
- If BOLD returns repeated `403` or `503`, stop and wait rather than retrying aggressively.

## Project Structure

- `Scripts/download_bold_fungi.py` is the generic BOLD downloader despite its historical name. It accepts `--query`, `--stem`, `--summary-only`, `--force`, and `--ignore-cap`.
- `Scripts/download_bold_plants.py`, `download_bold_mollusca.py`, and `download_bold_chordata.py` are thin wrappers around the generic downloader.
- `Scripts/download_bold_animals_except_acm.py` downloads non-Arthropoda, non-Chordata, non-Mollusca animal phyla one phylum at a time.
- `Scripts/download_bold_insect_orders_small.py` downloads selected smaller insect orders one order at a time.
- `Scripts/audit_bold_downloads.py` audits local BOLD TSVs against their summary JSON files.
- `Scripts/make_bold_fungi_minimal.py` creates the current Stata-friendly Fungi TSV.
- `Scripts/map_bold_fungi_grid.py` maps geocoded Fungi records on equal-area cells.

## Known Data State

Run this for the current local audit:

```bash
python3 Scripts/audit_bold_downloads.py
```

As of the latest audit:

- 37 BOLD record TSV files are present.
- No `.part` files are present.
- 36 files have data rows greater than or equal to BOLD summary specimens.
- `Data/raw/bold/bold_global_hemiptera_records.tsv` is capped/truncated at exactly 1,000,000 data rows, while the BOLD summary reports 1,053,311 specimens.

## Safe Workflow

Before editing:

```bash
git status --short --ignored
```

Before committing:

```bash
python3 -m py_compile Scripts/*.py
python3 Scripts/audit_bold_downloads.py
git status --short
```

Commit only code/docs. Avoid adding ignored data by force unless the user explicitly asks.

## Useful Commands

Download a BOLD taxon:

```bash
python3 Scripts/download_bold_fungi.py --query "tax:order:Hemiptera" --stem bold_global_hemiptera --summary-only
```

Run remaining animal phyla in small paste-safe batches:

```bash
python3 Scripts/download_bold_animals_except_acm.py --phyla Chaetognatha Ctenophora Entoprocta --retries 2 --retry-sleep 300
```

Map Fungi sampling at 50, 100, or 200 km:

```bash
python3 Scripts/map_bold_fungi_grid.py --cell-km 100
```
