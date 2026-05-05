# Diversity Discoveries

This project builds micro data for studying how biodiversity enters scientific sampling and discovery systems. The current working data source is BOLD public barcode metadata, used to prototype sampling geography at species/taxon, grid-cell, and year levels.

## Repository Contents

- `Scripts/`: Python scripts for BOLD downloads, cleaning, audits, and maps.
- `DoFiles/`: Stata 16 import and summary scripts.
- `Notes/`: LaTeX research notes.
- `bold_taxon_size_notes.txt`: BOLD taxon size and coverage notes.
- `Data/`: ignored local data downloads and processed files.
- `Output/`: ignored local maps and audits.
- `Exhibits/`: ignored generated exhibit tables, maps, and regression panels.
- `Literature/`: ignored local PDFs.

The GitHub repository intentionally excludes large data, generated outputs, PDFs, and temporary download files.

## Current BOLD Data

Downloaded BOLD groups include Fungi, Plantae, Mollusca, Chordata, selected smaller insect orders, animal phyla excluding Arthropoda/Chordata/Mollusca, non-insect arthropod groups, and Bacteria. Large insect orders are split family by family where needed: Coleoptera, Hemiptera, Hymenoptera, Lepidoptera, and manageable Diptera families from Ceratopogonidae downward. Raw BOLD TSV files are under `Data/raw/bold/`.

Important note: Diptera is not fully complete. The remaining incomplete piece is
Costa Rica (`C-R`) Cecidomyiidae. BOLD reports 1,122,446 Costa Rica
Cecidomyiidae records, which exceeds the 1,000,000-record API cap. The capped
Costa Rica file is included in the exhibit pipeline so that this major cluster
is not dropped, but it is partial and must not be treated as complete.

Current caveat: four Diptera families exceed the 1,000,000-record BOLD query cap at the family level: Cecidomyiidae, Chironomidae, Phoridae, and Sciaridae. Chironomidae, Phoridae, Sciaridae, and non-Costa-Rica Cecidomyiidae now have country-level request scripts; Costa Rica Cecidomyiidae still needs a further split or a BOLD bulk export. See `diptera_oversized_family_problem.md`.

## Core Commands

Audit all BOLD downloads:

```bash
python3 Scripts/audit_bold_downloads.py
```

Audit intended taxon coverage against local manifests:

```bash
python3 Scripts/audit_bold_taxon_coverage.py
```

Create a minimal Fungi TSV:

```bash
python3 Scripts/make_bold_fungi_minimal.py
```

Map BOLD Fungi on a 100 km equal-area grid:

```bash
python3 Scripts/map_bold_fungi_grid.py --cell-km 100
```

Import global BOLD Fungi into Stata:

```stata
do "/Users/vasilykorovkin/Documents/Diversity_Discoveries/DoFiles/02_import_bold_fungi_global.do"
```

## Exhibit Pipeline

The current Stata-ready BOLD panel is generated from compact exhibit files, not
from raw TSVs directly. Run order:

```bash
python3 Scripts/00_build_bold_minimal.py
python3 Scripts/01_tables_counts.py
python3 Scripts/02_timeseries.py
python3 Scripts/03_maps_grid.py
python3 Scripts/04_maps_admin1.py
python3 Scripts/05_cell_correlations.py
python3 Scripts/06_build_cell_year_panel.py
```

Main panel output:

```text
Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025.csv
Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025_summary.csv
```

The panel uses BOLD `collection_year`, 2005-2025, 100 km equal-area land
cells, and includes zero cell-years. It has outcomes for total records,
Animalia, Plantae, Fungi, Bacteria, Plantae + Fungi, non-Chordata Animalia,
Arthropoda, Insecta, and Chordata, with extensive-margin (`any_*`) and
intensive-margin (`log1p_*`) versions.

After regenerating the collection-year panel, check the audit summary at:

```text
Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025_summary.csv
```

The panel is intentionally a strict land-cell panel. Some coastal, island, and
marine/coastal records fall outside the land-cell universe and are not included
in the current regression panel.

The first non-BOLD regressor is UCDP GED conflict, aggregated to the same 100 km
land cells:

```text
Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024.csv
Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024_summary.csv
```

It contains all UCDP GED events, best/low/high fatalities, civilian deaths,
type splits for state/non-state/one-sided violence, and precision-filtered
versions using `where_prec` 1-2. Logs and lags should be generated in Stata.

Static baseline geography has also been assigned to the 100 km land cells using
the RESOLVE 2017 terrestrial ecoregions shapefile:

```text
Data/regressors/baseline_geography/resolve_ecoregions_100km_cells.csv
```

This file has one row per BOLD land cell with ecoregion, biome, realm, and
match flags. It is a centroid overlay, so it is best used as a baseline stratum,
heterogeneity variable, or interaction term rather than a time-varying shock.
The raw RESOLVE and CEPF inputs are reproducibly downloaded by
`Scripts/download_baseline_geography.py`; see
`Scripts/baseline_geography_README.md`. The geospatial Python requirements for
these overlays are listed in `requirements_baseline_geography.txt`.

CEPF/Conservation International biodiversity hotspots have also been assigned
by centroid overlay:

```text
Data/regressors/baseline_geography/cepf_hotspots_100km_cells.csv
```

This file has one row per BOLD land cell with `cepf_hotspot_any`,
`cepf_hotspot_count`, and `cepf_hotspot_names`.

A WDPA/Protected Planet protected-area share script is prepared for the local
May 2026 WDPA/WDOECM polygon geodatabase:

```text
Scripts/aggregate_wdpa_protected_share_100km.py
```

The output is a May 2026 snapshot, `protected_share_c`, not a historical
cell-year protected-area panel. It is appropriate as a baseline control or
heterogeneity variable. A time-varying protected-area measure would require a
separate build using `STATUS_YR` and/or historical WDPA releases.

Hansen Global Forest Change (tree-cover-weighted forest loss) is aggregated via
Google Earth Engine:

```text
Data/regressors/hansen/hansen_forest_loss_100km_panel.csv
```

See `Scripts/gee_hansen_forest_loss_README.md` for the Earth Engine workflow.
Hansen covers 2001-2023; variables include `baseline_forest_km2`,
`forest_loss_km2`, `forest_loss_share`, `cumulative_loss_km2`, and lags.

Natural-disaster and climate-shock files currently in use are:

```text
Data/raw/ibtracs/ibtracs_since1980_list_v04r01.csv
Data/raw/ibtracs/ibtracs_download_manifest.csv
Data/regressors/ibtracs/ibtracs_100km_cell_year_2005_2025.csv
Data/regressors/ibtracs/ibtracs_100km_cell_year_2005_2025_summary.csv

Data/raw/comcat/comcat_earthquakes_2005_2025_m4p5.csv
Data/raw/comcat/comcat_download_manifest.csv
Data/regressors/comcat/comcat_100km_cell_year_2005_2025.csv
Data/regressors/comcat/comcat_100km_cell_year_2005_2025_summary.csv

Data/regressors/modis/modis_burned_area_100km_panel.csv
Data/regressors/modis/modis_burned_area_100km_panel_summary.csv

Data/regressors/terraclimate/terraclimate_100km_panel.csv
Data/regressors/chirps/chirps_100km_panel.csv
```

These should be interpreted as follows:

- `ibtracs_since1980_list_v04r01.csv`: raw NOAA IBTrACS tropical-cyclone track
  points, global, since 1980, one row per storm-time observation.
- `ibtracs_download_manifest.csv`: download metadata for the local IBTrACS raw
  file (source, timestamp, size, hash).
- `ibtracs_100km_cell_year_2005_2025.csv`: BOLD-grid cell-year cyclone
  exposure panel. Main variables are `ibtracs_points_all`,
  `ibtracs_storms_all`, `ibtracs_points_34kt`, `ibtracs_points_64kt`,
  `ibtracs_any_all`, `ibtracs_any_34kt`, `ibtracs_any_64kt`, and
  `ibtracs_max_wmo_wind_kts`.
- `ibtracs_100km_cell_year_2005_2025_summary.csv`: audit summary for the
  processed IBTrACS panel.

- `comcat_earthquakes_2005_2025_m4p5.csv`: raw USGS ComCat earthquake event
  file, global, one row per earthquake, restricted at download to
  magnitude `>= 4.5`.
- `comcat_download_manifest.csv`: download metadata for the local ComCat raw
  file.
- `comcat_100km_cell_year_2005_2025.csv`: BOLD-grid cell-year earthquake
  exposure panel. Main variables are `comcat_events_all`, `comcat_events_m6`,
  `comcat_events_m7`, `comcat_shallow_events`, `comcat_any_all`,
  `comcat_max_mag`, `comcat_mean_mag`, and `comcat_mean_depth_km`.
- `comcat_100km_cell_year_2005_2025_summary.csv`: audit summary for the
  processed ComCat panel.

- `modis_burned_area_100km_panel.csv`: processed MODIS MCD64A1 burned-area
  cell-year panel from Earth Engine. Variables include `burned_area_km2`,
  `any_burned`, `cumulative_burned_km2`, and lags.
- `modis_burned_area_100km_panel_summary.csv`: annual summary and audit of the
  processed MODIS burned-area panel.

- `terraclimate_100km_panel.csv`: processed cell-year climate-shock panel from
  TerraClimate. Variables include `pdsi_mean`, `pdsi_anomaly`, `tmax_mean`,
  `tmax_anomaly`, `ppt_mean`, and `ppt_anomaly`.
- `chirps_100km_panel.csv`: processed CHIRPS precipitation panel. Variables
  include `chirps_precip_mm` and `chirps_precip_anomaly`; coverage is
  50°S-50°N only.

## BOLD API Notes

BOLD can return transient `403 Forbidden` or `503 Service Unavailable` errors after many or large requests. Wait before retrying. The downloader scripts save one JSON summary and query token per request, plus a `.part` file during active downloads. A final `.tsv` file with no `.part` suffix means the stream finished.

Rows in BOLD TSV downloads are marker/sequence records, not necessarily unique specimens. It is normal for data rows to exceed the BOLD summary specimen count.

## Plant And Discovery Stack

BOLD is not sufficient as the main plant layer. For plants, the project should use herbarium/specimen and botanical-name infrastructure alongside barcode data:

- Plant sampling: GBIF preserved specimens/herbarium records as the main global layer, with iDigBio as a US-heavy complement and BIEN as a cleaned botanical occurrence/trait/range complement.
- GBIF preserved/material plant workflow: `Scripts/request_gbif_plantae_downloads.py` requests the archive, `Scripts/14_build_gbif_plantae_minimal.py` streams the preserved/material `occurrence.txt` into a compact CSV, `Scripts/15_build_gbif_plantae_cell_year_panel.py` builds the 100 km cell-year panel with total and basis-of-record breakdowns, and `DoFiles/reg_spec1_gbif_plantae.do` mirrors the main `reg_spec1` tables on the GBIF Plantae panel.
- Main GBIF plant outputs now live under `Data/processed/gbif/plantae/`; the preserved/material archive is the main plant regression source, while the human-observation archive is a separate comparator.
- Plant name cleaning: WCVP/POWO/IPNI/World Flora Online for accepted names and synonyms; Kew MPNS for medicinal, herbal drug, common-name, and pharmacological-name disambiguation.
- Plant chemistry and discovery outcomes: COCONUT, LOTUS, KNApSAcK, and where accessible NAPRALERT for plant natural products and plant-metabolite links; PubChem and ChEMBL for compound bioactivity and assay outcomes.

## Next Steps

1. Merge the 2005-2025 BOLD collection-year panel with the 2005-2024 UCDP GED
   conflict panel and run first extensive/intensive-margin sampling regressions
   over the common 2005-2024 window.
2. Finish Hansen Global Forest Change aggregation from Earth Engine and merge
   annual tree-cover loss into the same cell-year panel.
3. Decide whether to create a second panel that includes all observed cells
   plus land zero cells, rather than strict land-centroid cells only.
4. Link sampling layers to discovery data and broader sequencing effort:
   ENA for Europe/EMBL-EBI submissions; DDBJ for Japan-linked submissions;
   NCBI GenBank/SRA/BioSample for global sequencing records; CNCB-NGDC GSA
   and CNGBdb for China-linked sequencing data; plus COCONUT, NPAtlas,
   PubChem, ChEMBL, patents, and publications for natural-product and
   discovery proxies.
