# Scripts

## Downloaders

- `download_bold_fungi.py`: generic BOLD downloader. Use `--query` and `--stem` for arbitrary taxa.
- `download_bold_plants.py`: global Plantae wrapper.
- `download_bold_mollusca.py`: global Mollusca wrapper.
- `download_bold_chordata.py`: global Chordata wrapper.
- `download_bold_insect_orders_small.py`: selected smaller insect orders.
- `download_bold_animals_except_acm.py`: animal phyla excluding Arthropoda, Chordata, and Mollusca.

## Cleaning And Audits

- `make_bold_fungi_minimal.py`: creates a smaller Stata-friendly Fungi TSV from the raw BOLD export.
- `audit_bold_downloads.py`: checks all local BOLD record files against summary JSON counts and flags capped/truncated files.

## Mapping

- `map_bold_fungi_admin1.py`: maps geocoded Fungi records to Natural Earth admin-1 polygons.
- `map_bold_fungi_grid.py`: maps geocoded Fungi records to equal-area grid cells. Baseline is 100 km.

## Examples

```bash
python3 Scripts/download_bold_fungi.py --query "tax:kingdom:Fungi" --stem bold_global_fungi --summary-only
python3 Scripts/download_bold_plants.py
python3 Scripts/audit_bold_downloads.py
python3 Scripts/map_bold_fungi_grid.py --cell-km 100
```
