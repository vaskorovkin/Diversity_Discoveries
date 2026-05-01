# Scripts

## Downloaders

- `download_bold_fungi.py`: generic BOLD downloader. Use `--query` and `--stem` for arbitrary taxa.
- `download_bold_plants.py`: global Plantae wrapper.
- `download_bold_mollusca.py`: global Mollusca wrapper.
- `download_bold_chordata.py`: global Chordata wrapper.
- `download_bold_insect_orders_small.py`: selected smaller insect orders.
- `download_bold_non_insect_arthropods_and_microbes.py`: selected non-insect arthropod orders/classes plus Chromista, Protozoa, Archaea, and Bacteria; one TSV per positive-count group.
- `download_bold_cecidomyiidae_except_costa_rica_by_country.py`: Cecidomyiidae downloader split by country/ocean while excluding Costa Rica, which still exceeds the 1M cap.
- `download_bold_cecidomyiidae_costa_rica_capped.py`: capped Costa Rica Cecidomyiidae diagnostic extract; useful as partial coverage only.
- `download_bold_coleoptera_by_family.py`: Coleoptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 21s after successful family downloads.
- `download_bold_coleoptera_remaining_combined.py`: computes missing Coleoptera families from the manifest and downloads them with one combined BOLD query.
- `download_bold_chironomidae_by_country.py`: Chironomidae downloader split into one BOLD request per country/ocean value.
- `download_bold_diptera_from_ceratopogonidae.py`: Diptera family downloader that starts at Ceratopogonidae, leaving the four over-cap families for separate split plans.
- `download_bold_phoridae_by_country.py`: Phoridae downloader split into one BOLD request per country/ocean value.
- `download_bold_sciaridae_by_country.py`: Sciaridae downloader split into one BOLD request per country/ocean value.
- `download_bold_hemiptera_by_family.py`: Hemiptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 11s after successful family downloads.
- `download_bold_hymenoptera_by_family.py`: Hymenoptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 11s after successful family downloads.
- `download_bold_lepidoptera_by_family.py`: Lepidoptera downloader split into one BOLD request per family to avoid the 1M-record cap. Defaults: 61s between failed retry attempts and 11s after successful family downloads.
- `download_bold_animals_except_acm.py`: animal phyla excluding Arthropoda, Chordata, and Mollusca.

## Cleaning And Audits

- `make_bold_fungi_minimal.py`: creates a smaller Stata-friendly Fungi TSV from the raw BOLD export.
- `audit_bold_downloads.py`: checks all local BOLD record files against summary JSON counts and flags capped/truncated files.
- `audit_bold_taxon_coverage.py`: checks intended taxon coverage against local manifests and files; it does not query BOLD.
- `summarize_bold_cecidomyiidae_new_world.py`: estimates BOLD Cecidomyiidae counts for New World countries/territories before geography-split downloads.
- `summarize_bold_tsv_genera.py`: counts genus values in a BOLD TSV export and optionally writes a genus-count CSV.
- `summarize_bold_order_families_v4.py`: scrapes BOLD v4 taxonomy-browser family splits for large insect orders and appends them to `bold_taxon_size_notes.txt`.
- `summarize_bold_diptera_large_family_genera_v4.py`: scrapes BOLD v4 genus splits for the four Diptera families above the 1M query cap and appends them to `bold_taxon_size_notes.txt`.
- `summarize_bold_diptera_oversized_country_counts.py`: extracts top country/ocean counts for the four over-cap Diptera families from BOLD summary metadata.
- `summarize_bold_non_insect_groups.py`: summarizes selected non-insect arthropod, microbe-like, and broad taxon groups and appends planning tables to `bold_taxon_size_notes.txt`.

## Mapping

- `map_bold_fungi_admin1.py`: maps geocoded Fungi records to Natural Earth admin-1 polygons.
- `map_bold_fungi_grid.py`: maps geocoded Fungi records to equal-area grid cells. Baseline is 100 km.

## Examples

```bash
python3 Scripts/download_bold_fungi.py --query "tax:kingdom:Fungi" --stem bold_global_fungi --summary-only
python3 Scripts/download_bold_plants.py
python3 Scripts/download_bold_non_insect_arthropods_and_microbes.py
python3 Scripts/download_bold_cecidomyiidae_except_costa_rica_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_cecidomyiidae_costa_rica_capped.py
python3 Scripts/download_bold_coleoptera_by_family.py
python3 Scripts/download_bold_coleoptera_remaining_combined.py
python3 Scripts/download_bold_chironomidae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_diptera_from_ceratopogonidae.py
python3 Scripts/download_bold_phoridae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_sciaridae_by_country.py --retries 2 --retry-sleep 61 --between-country-sleep 11
python3 Scripts/download_bold_hemiptera_by_family.py
python3 Scripts/download_bold_hymenoptera_by_family.py
python3 Scripts/download_bold_lepidoptera_by_family.py
python3 Scripts/audit_bold_downloads.py
python3 Scripts/audit_bold_taxon_coverage.py
python3 Scripts/summarize_bold_cecidomyiidae_new_world.py
python3 Scripts/summarize_bold_tsv_genera.py Data/raw/bold/diptera_by_family/bold_global_diptera_family_cecidomyiidae_capped_records.tsv --output Output/audits/cecidomyiidae_capped_genus_counts.csv
python3 Scripts/map_bold_fungi_grid.py --cell-km 100
python3 Scripts/summarize_bold_order_families_v4.py
python3 Scripts/summarize_bold_diptera_large_family_genera_v4.py
python3 Scripts/summarize_bold_diptera_oversized_country_counts.py
python3 Scripts/summarize_bold_non_insect_groups.py
```
