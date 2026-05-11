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

## Spatial-Time Experiment Panels

The canonical pipeline remains `100 km x year`. Experimental alternatives are
centralized in `Scripts/panel_variants.py`:

```text
baseline_100km_year
test_50km_year
test_50km_quarter
```

The 50 km variants write under `Data/processed/tests_spatial_time/`,
`Data/regressors/tests_spatial_time/`, and
`Data/analysis/tests_spatial_time/`, so they do not overwrite the baseline
100 km outputs. The quarterly path is a true quarterly panel for BOLD, MODIS,
UCDP, ComCat, IBTrACS, TerraClimate, and CHIRPS. Hansen forest loss,
harmonized nightlights, WDPA, and World Bank GDP are source-limited annual
series and are repeated within year/quarter with source-frequency flags where
appropriate.

Earth Engine scripts now live in `Scripts/earth_engine/`. The 50 km Earth
Engine instructions are in:

```text
Scripts/earth_engine/tests_spatial_time_README.md
```

The raster aggregators for TerraClimate, CHIRPS, GRIP roads, and GLOBIO MSA
use `Scripts/raster_zonal.py`, which rasterizes actual cell polygons and
aggregates by rasterized cell labels. This replaced the older lon/lat
bounding-box windows.

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
May 2026 WDPA/WDOECM polygon File Geodatabase:

```text
Scripts/aggregate_wdpa_protected_share_100km.py
Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

The baseline 100 km output is
`Data/regressors/baseline_geography/wdpa_protected_share_100km_cells.csv`.
The 50 km experiment output is
`Data/regressors/tests_spatial_time/baseline_geography/wdpa_protected_share_50km_cells.csv`.
Both are May 2026 snapshots, not historical cell-year protected-area panels.
They are appropriate as baseline controls or heterogeneity variables.

The preferred analysis panels use the `STATUS_YR`-based WDPA panel built by:

```bash
python3 Scripts/aggregate_wdpa_protected_panel_100km_v2.py --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
python3 Scripts/aggregate_wdpa_protected_panel_100km_v2.py --variant test_50km_year --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

Hansen Global Forest Change (tree-cover-weighted forest loss) is aggregated via
Google Earth Engine:

```text
Data/regressors/hansen/hansen_forest_loss_100km_panel.csv
```

See `Scripts/earth_engine/gee_hansen_forest_loss_README.md` for the Earth Engine workflow.
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
- GBIF preserved/material plant workflow: `Scripts/request_gbif_plantae_downloads.py` requests the archive and can target either or both of `preserved_material` and `human_observation`; `Scripts/14_build_gbif_plantae_minimal.py` streams the preserved/material `occurrence.txt` into a compact CSV; `Scripts/15_build_gbif_plantae_cell_year_panel.py` builds the 100 km cell-year panel with total and basis-of-record breakdowns; `Scripts/17_build_gbif_plantae_preperiod_richness.py` builds a static 1999-2004 plant-richness baseline from the pre-period archive; and `DoFiles/reg_spec1_gbif_plantae.do` now includes both the original GBIF plant mirror and a Table 6 plant-richness interaction using the pre-period GBIF richness measure.
- Main GBIF plant outputs now live under `Data/processed/gbif/plantae/`; the preserved/material archive is the main plant regression source, while the human-observation archive is a separate comparator.
- Static GBIF plant richness controls now live under `Data/regressors/plants/`, with both raw and transformed pre-period species/genus richness variables merged into the Stata analysis panel under short aliases.
- R setup for botanical richness/distribution work: `Scripts/plant_r_setup.R` installs and loads BIEN, rWCVP, rWCVPdata, expowo, sf, terra, and basic tidyverse packages, then writes a package/session manifest to `Output/audits/`.
- BIEN should not be queried cell by cell for the full 100 km grid. `Scripts/19_extract_gbif_plantae_species_universe.py` first builds the observed GBIF preserved/material plant species universe, and `Scripts/18_bien_range_download_pilot.R` then works through the canonical species-like pool in rank-window batches, checking BIEN range availability, downloading BIEN range shapefiles locally in bulk, recording timing/disk-footprint metrics, and optionally converting them to BIEN skinny ranges plus a local richness raster. The current completed run covers the full canonical pool of `236,166` names in five batches and yielded `64,760` downloaded BIEN range-map species.
- Plant name cleaning: WCVP/POWO/IPNI/World Flora Online for accepted names and synonyms; Kew MPNS for medicinal, herbal drug, common-name, and pharmacological-name disambiguation.
- Plant chemistry and discovery outcomes: COCONUT, LOTUS, KNApSAcK, and where accessible NAPRALERT for plant natural products and plant-metabolite links; PubChem and ChEMBL for compound bioactivity and assay outcomes.
- Publication linkage: Option A outputs live under `Data/processed/discovery/publications/`. `Scripts/20_link_bold_to_pubmed.py` builds the BOLD accession-to-PubMed linkage: `5,230,497` GenBank/INSDC accessions covered, with `1,983,992` accessions linked to at least one PMID. The production linkage parses GenBank `efetch` flat-file `PUBMED` references because Entrez `elink` returned collapsed batch-level linksets that were not safe for per-accession attribution. Persistent unresolved NCBI `400` failures are documented in `bold_pubmed_efetch_failures_remaining.csv` (`5,435` accessions, ~0.104%). `Scripts/20b_fetch_pubmed_metadata.py` fetches PubMed year/DOI/title metadata for 24,093 BOLD-linked PMIDs. `Scripts/21_link_gbif_datasets_to_publications.py` links GBIF Plantae preserved-material `dataset_key` values to GBIF Literature records (`842,961` logical dataset-publication rows); this is dataset-level publication exposure, not direct specimen citation. `Scripts/28_build_publication_cell_year_panel.py` builds the legacy publication-year exposure panel (`305,886` land-cell-year rows, `498,448` long audit rows, `38,396` BOLD-linked publication counts, `46,947,009` GBIF dataset-publication exposure counts). Because the pooled total is dominated by GBIF dataset-level exposure, the corrected main downstream-publication outcome is `Scripts/29_build_bold_publication_yield_panel.py`: a BOLD-only collection-cohort panel counting linked PubMed publications within 0–3, 0–5, and 0–10 years after specimen collection. `Scripts/30_build_gbif_publication_exposure_panel.py` applies the same collection-cohort timing to GBIF dataset literature links for a separate diagnostic exposure panel (`305,886` land-cell-year rows); it fixes timing but remains dataset-level exposure rather than specimen-specific citation.

## Next Steps

1. Compare `reg_spec1.do` outputs across `100-yearly`, `50-yearly`, and
   `50-quarterly` after every panel rebuild.
2. Treat `reg_event_study_twfe_simple.do` and
   `reg_conflict_signal_decomposition.do` as diagnostics for whether the
   strong TWFE table signal comes from clean onset timing, repeated exposure,
   or composition.
3. Keep the 100 km yearly pipeline as the fallback benchmark until the 50 km
   and quarterly results are stable across logs, tables, and sample audits.
4. Continue discovery-linkage work through the corrected BOLD publication
   yield, GBIF publication exposure diagnostics, and natural-products panels.
