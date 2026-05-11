# Earth Engine Exports for `tests_spatial_time`

These scripts are only for the experimental 50 km spatial/time pipeline. They
should be copied into the Google Earth Engine Code Editor after the 50 km grid
has been uploaded as a table asset.

## Required grid asset

Build the grid locally:

```bash
python3 Scripts/build_land_cells.py --variant test_50km_year
```

Upload this file in Earth Engine using `NEW` -> `Shape files (.shp, .shx, .dbf,
.prj, or .zip)`:

```text
Data/processed/tests_spatial_time/bold/bold_grid50_land_cells.zip
```

Set the uploaded asset ID to match the scripts:

```text
projects/symmetric-lock-495018-e0/assets/bold_grid50_land_cells
```

## Annual exports used by `test_50km_year`

Run these in Earth Engine and download the exported CSVs into the matching local
paths:

```text
gee_hansen_forest_loss_50km.js
Data/regressors/tests_spatial_time/hansen/hansen_baseline_forest_50km.csv
Data/regressors/tests_spatial_time/hansen/hansen_forest_loss_50km_annual.csv
Data/regressors/tests_spatial_time/hansen/hansen_cumulative_loss_50km.csv

gee_modis_burned_area_50km.js
Data/regressors/tests_spatial_time/modis/modis_burned_area_50km_annual.csv

gee_nightlights_50km.js
Data/regressors/tests_spatial_time/nightlights/harmonized_nightlights_50km.csv
```

## Quarterly exports used by `test_50km_quarter`

`gee_modis_burned_area_50km_quarterly.js` uses the same uploaded
`bold_grid50_land_cells` asset and exports:

```text
Data/regressors/tests_spatial_time/modis/modis_burned_area_50km_quarterly.csv
```

Hansen forest loss and harmonized nightlights do not need separate quarterly
Earth Engine exports for the main quarterly pipeline. Hansen reports annual
loss year, and harmonized nightlights are intentionally kept annual to preserve
2005-2023 coverage. Their annual 50 km CSVs are expanded to quarters by the
local merge scripts.

The full `test_50km_quarter` path uses:

- BOLD sampling at cell-quarter frequency from collection month
- MODIS burned area at cell-quarter frequency
- UCDP GED by event start quarter
- ComCat earthquakes by event quarter
- IBTrACS cyclones by storm-point quarter
- TerraClimate quarterly values from monthly NetCDF time slices
- CHIRPS quarterly precipitation totals from monthly GeoTIFFs
- Hansen forest loss expanded from annual source data to quarters, because
  Hansen reports loss year but not loss month
- annual harmonized nightlights expanded to quarters, because this preserves
  2005-2023 coverage whereas VIIRS-only quarterly lights would lose early years

## Local WDPA Input

The 50 km protected-area builders use the same local May 2026 WDPA/WDOECM File
Geodatabase as the baseline pipeline. The Stata analysis panels use the
`STATUS_YR`-based panel:

```bash
python3 Scripts/aggregate_wdpa_protected_panel_100km_v2.py --variant test_50km_year --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

The expected output is:

```text
Data/regressors/tests_spatial_time/wdpa/wdpa_protected_panel_50km.csv
```

The optional static snapshot share is still available through
`aggregate_wdpa_protected_share_100km.py --variant test_50km_year`, but it is
not the preferred analysis control.

## Local Rebuild Commands After Earth Engine

For the 50 km yearly panel:

```bash
python3 Scripts/06_build_cell_year_panel.py --variant test_50km_year
python3 Scripts/merge_hansen_exports.py --variant test_50km_year
python3 Scripts/merge_modis_burned_exports.py --variant test_50km_year
python3 Scripts/merge_nightlights_exports.py --variant test_50km_year
python3 Scripts/aggregate_ucdp_ged_100km.py --variant test_50km_year
python3 Scripts/aggregate_ibtracs_100km.py --variant test_50km_year
python3 Scripts/aggregate_comcat_100km.py --variant test_50km_year
python3 Scripts/aggregate_terraclimate_100km.py --variant test_50km_year
python3 Scripts/aggregate_chirps_100km.py --variant test_50km_year
python3 Scripts/aggregate_resolve_ecoregions_100km.py --variant test_50km_year
python3 Scripts/aggregate_grip_roads_100km.py --variant test_50km_year
python3 Scripts/aggregate_species_richness_100km.py --variant test_50km_year
python3 Scripts/aggregate_globio_msa_100km.py --variant test_50km_year
python3 Scripts/aggregate_wdpa_protected_panel_100km_v2.py --variant test_50km_year --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

For the 50 km quarterly panel:

```bash
python3 Scripts/06_build_cell_year_panel.py --variant test_50km_quarter
python3 Scripts/merge_modis_burned_exports.py --variant test_50km_quarter
python3 Scripts/merge_hansen_exports.py --variant test_50km_quarter
python3 Scripts/merge_nightlights_exports.py --variant test_50km_quarter
python3 Scripts/aggregate_ucdp_ged_100km.py --variant test_50km_quarter
python3 Scripts/aggregate_ibtracs_100km.py --variant test_50km_quarter
python3 Scripts/aggregate_comcat_100km.py --variant test_50km_quarter
python3 Scripts/aggregate_terraclimate_100km.py --variant test_50km_quarter
python3 Scripts/download_chirps_monthly.py --skip-existing --end-year 2023
python3 Scripts/aggregate_chirps_100km.py --variant test_50km_quarter
```
