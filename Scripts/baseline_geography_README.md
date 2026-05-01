# Baseline Geography Replication Notes

This folder contains scripts to reproduce baseline geography layers used with
the BOLD 100 km land-cell grid. RESOLVE and CEPF are static by construction.
The current WDPA script uses a May 2026 snapshot, so it is static in the current
outputs even though protected areas can change over time.

## Python Dependencies

The download script itself uses only the Python standard library. The overlay
scripts require the geospatial Python stack listed in:

```text
requirements_baseline_geography.txt
```

The current local environment used:

```text
pandas 2.3.3
geopandas 1.0.1
shapely 2.0.7
```

## Inputs

The common project grid input is:

```text
Exhibits/data/bold_grid100_land_cells.csv
Exhibits/data/bold_grid100_land_cells.geojson
```

These grid files are project-generated, not external downloads. If they are
missing, regenerate them from the exhibit pipeline:

```bash
python3 Scripts/exhibits/00_build_bold_minimal.py
python3 Scripts/exhibits/03_maps_grid.py
python3 Scripts/exhibits/05_cell_correlations.py
python3 Scripts/exhibits/export_grid100_land_cells_geojson.py
```

For ecoregions and hotspots, only the CSV land-cell file is required. For WDPA
protected-area shares, the GeoJSON polygon file is required.

The external raw inputs are downloaded by:

```bash
python3 Scripts/download_baseline_geography.py
```

This creates:

```text
Data/raw/baseline_geography/resolve_ecoregions/Ecoregions2017.zip
Data/raw/baseline_geography/resolve_ecoregions/Ecoregions2017.shp
Data/raw/baseline_geography/resolve_ecoregions/Ecoregions2017.dbf
Data/raw/baseline_geography/resolve_ecoregions/Ecoregions2017.shx
Data/raw/baseline_geography/resolve_ecoregions/Ecoregions2017.prj
Data/raw/baseline_geography/cepf_hotspots.geojson
Data/raw/baseline_geography/baseline_geography_download_metadata.json
```

The metadata JSON records source URLs, retrieval time, byte sizes, and SHA256
hashes.

## Source URLs

RESOLVE 2017 terrestrial ecoregions:

```text
https://storage.googleapis.com/teow2016/Ecoregions2017.zip
```

CEPF / Conservation International terrestrial biodiversity hotspots:

```text
https://services.arcgis.com/nzS0F0zdNLvs7nc8/arcgis/rest/services/Terrestrial_biodiversity_hotspots/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson
```

Documentation pages:

- RESOLVE Earth Engine catalog: https://developers.google.com/earth-engine/datasets/catalog/RESOLVE_ECOREGIONS_2017
- CEPF hotspots definition/download page: https://www.cepf.net/our-work/biodiversity-hotspots/hotspots-defined
- CEPF ArcGIS FeatureServer metadata: https://services.arcgis.com/nzS0F0zdNLvs7nc8/arcgis/rest/services/Terrestrial_biodiversity_hotspots/FeatureServer

## Build Outputs

Run the overlays after downloading:

```bash
python3 Scripts/aggregate_resolve_ecoregions_100km.py
python3 Scripts/aggregate_cepf_hotspots_100km.py
```

Outputs:

```text
Data/regressors/baseline_geography/resolve_ecoregions_100km_cells.csv
Data/regressors/baseline_geography/cepf_hotspots_100km_cells.csv
```

Current expected audits:

- RESOLVE: 14,566 unique cells; 14,291 matched to an ecoregion; 1,243
  `Rock and Ice`; 275 unmatched.
- CEPF hotspots: 14,566 unique cells; 2,430 cells inside any hotspot; 36
  hotspot names represented; no centroid matched multiple hotspots.

## WDPA / Protected Planet

WDPA is not downloaded by `download_baseline_geography.py` because Protected
Planet requires a separate user download and terms workflow. Use the polygon
geodatabase/GPKG/SHP download, not the CSV-only download. The CSV file contains
attributes but no polygon geometry, so it cannot be used to compute protected
area share.

After placing or extracting the local WDPA polygon file under
`Data/raw/baseline_geography/wdpa/`, run the script with the actual local
filename. For the May 2026 public WDPA/WDOECM geodatabase currently used here:

```bash
python3 Scripts/aggregate_wdpa_protected_share_100km.py --wdpa Data/raw/baseline_geography/wdpa/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7/WDPA_WDOECM_May2026_Public_a0228029fd20816e371672dc358b399cf7dedb126f0bbcf3737106d7952c82a7.gdb
```

The script automatically selects the polygon layer in a FileGDB/GPKG. By
default it excludes proposed sites, fully marine sites where identifiable, and
OECM-only records in combined WDPA/WDOECM files. Add `--include-oecm` if the
target variable should include OECMs as conserved areas, and `--include-marine`
if marine protected areas should be counted in coastal land cells.

This output is a snapshot measure, conceptually `protected_share_c` as of the
downloaded WDPA release. It should be used as a baseline control or
heterogeneity variable. It is not a cell-year protection shock. To build a
dynamic protected-area panel, use `STATUS_YR` and/or historical WDPA releases;
current polygons applied backward by `STATUS_YR <= year` would be only an
approximation because it does not recover historical boundary changes or
downgrading/degazettement/reduction.

Output:

```text
Data/regressors/baseline_geography/wdpa_protected_share_100km_cells.csv
```
