# Regressor Dataset Options For BOLD/GBIF Cell-Year Regressions

Date: 2026-05-01

This note lists candidate regressors for cell-level and cell-year regressions of biodiversity sampling/discovery outcomes. The main current outcome is the BOLD 100 km land-cell x collection-year panel:

```text
Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025.csv
```

The central empirical problem is that observed sampling is not only biodiversity. It is approximately:

```text
observed sampling = biodiversity opportunity x researcher/search access x sequencing capacity x database submission
```

So regressors should be classified by whether they mainly shift biodiversity, mainly shift search/access, or both.

## Priority Order

For a first empirical pass, use:

1. **Annual tree-cover loss:** Hansen Global Forest Change.
2. **Conflict:** UCDP GED first; ACLED as broader robustness if credentials/API are convenient.
3. **Fire / burned area:** MODIS MCD64A1.
4. **Climate anomalies:** TerraClimate or ERA5-Land; CHIRPS for precipitation in the tropics/subtropics.
5. **Baseline biodiversity:** RESOLVE ecoregions/hotspots plus IUCN/BirdLife/Map of Life range-derived richness if feasible.

## 1. Actual Biodiversity Levels

These are mostly slow-moving or time-invariant. With cell fixed effects, they enter through interactions or initial conditions, not as standalone regressors.

| Dataset | What It Measures | Geography/Time | Download Option | Use |
|---|---|---|---|---|
| RESOLVE Ecoregions 2017 | 846 terrestrial ecoregions, biomes, realms, habitat/protection categories | Global, static | Shapefile from [ecoregions.world](https://ecoregions.world/) or Earth Engine `RESOLVE/ECOREGIONS/2017`; see also [Google Earth Engine catalog](https://developers.google.com/earth-engine/datasets/catalog/RESOLVE_ECOREGIONS_2017) | Baseline ecological strata, FE/interactions, heterogeneity |
| Biodiversity Hotspots | Conservation International/CEPF hotspot polygons | Global, static | GIS data link on [CEPF hotspots page](https://www.cepf.net/our-work/biodiversity-hotspots/hotspots-defined) | High-biodiversity/high-threat indicator |
| IUCN Red List spatial data | Species range maps for comprehensively assessed groups | Global, static/updated | Spatial download portal: [IUCN Red List spatial data](https://d2eo89ldedz6pl.cloudfront.net/resources/spatial-data-download); usually requires account/terms | Range-derived richness, threatened richness, endemicity |
| BirdLife range maps | Bird distribution polygons | Global, static/updated | BirdLife Data Zone/request/download workflow; use as bird-specific richness layer | Charismatic/well-studied taxa comparison |
| Map of Life | Species habitat/range indicators, Species Habitat Index, Species Protection Index | Global; some annual indicator products | Platform at [mol.org](https://mol.org/); bulk/API access needs checking | Richness, habitat-suitable range, habitat-loss proxies |
| Biodiversity Intactness Index (BII) / PREDICTS | Modeled local biodiversity intactness based on land use and other pressures | Global terrestrial; time/scenario layers through NHM data portal | [Natural History Museum BII](https://www.nhm.ac.uk/our-science/services/data/biodiversity-intactness-index.html/) and data portal links | Baseline intactness; interaction with shocks |
| GLOBIO Mean Species Abundance (MSA) | Modeled biodiversity intactness, including MSA overall/plants/birds+mammals | Global raster, scenario/year products | [GLOBIO data downloads](https://www.globio.info/globio-data-downloads) | Alternative modeled biodiversity/intactness layer |

## 2. Biodiversity Shocks

These plausibly change biodiversity itself and are most useful for cell x year regressions.

| Dataset | What It Measures | Geography/Time | Download Option | Use |
|---|---|---|---|---|
| Hansen Global Forest Change | Tree cover in 2000, annual tree-cover loss year, gain, data mask | Global, 30 m, 2001 onward | Direct raster tiles from the Hansen/UMD site or cloud mirrors; variables include `treecover2000`, `loss`, `lossyear`; see dataset summary at [Cecil Earth](https://docs.cecil.earth/datasets/9659ec1d-7091-4f8b-9db5-e9fe07d2f508) | Main annual habitat-loss shock |
| ESA CCI Land Cover | Annual land-cover classes | Global, 300 m, 1992 onward | [ESA CCI Land Cover data](https://climate.esa.int/en/projects/land-cover/data/) | Cropland/grassland/wetland conversion; slower but broad land-cover transitions |
| Copernicus Global Land Cover | Land cover and cover fractions | Global, 100 m, 2015-2019 | [Copernicus Land Monitoring Service](https://land.copernicus.eu/en/products/global-dynamic-land-cover/copernicus-global-land-service-land-cover-100m-collection-3-epoch-2015-2019-globe), CDSE/S3/OData/Zenodo | Higher-resolution land-cover robustness for recent years |
| MODIS MCD64A1 Burned Area | Monthly burned area and burn date | Global, 500 m, 2000 onward | NASA LAADS/LP DAAC, Earthdata, or Earth Engine `MODIS/061/MCD64A1`; see [NASA LAADS](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MCD64A1/) and [Earth Engine catalog](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD64A1) | Fire/burned-area shock |
| TerraClimate | Monthly temperature, precipitation, drought/water-balance variables | Global terrestrial, ~4 km, 1950-present | [TerraClimate](https://www.climatologylab.org/terraclimate.html), NetCDF files by variable/year | Drought, heat, water deficit, climate anomalies |
| ERA5-Land | Hourly/monthly land reanalysis, temperature, precipitation, soil moisture, etc. | Global, ~9 km, 1950 to near-present | Copernicus/ECMWF CDS; see [ERA5-Land](https://www.ecmwf.int/en/era5-land) | Climate extremes, heat, soil moisture |
| CHIRPS | Daily precipitation | Quasi-global 50S-50N, 0.05 degree, 1981-present | ERDDAP/NOAA/UCSB; see [NOAA catalog](https://catalog.data.gov/dataset/chirps-version-2-0-precipitation-global-0-05-daily-1981-present) and [ERDDAP](https://coastwatch.pfeg.noaa.gov/erddap/griddap/chirps20GlobalDailyP05.html) | Rainfall/drought anomalies, especially tropics |
| Protected Planet / WDPA | Protected-area polygons and attributes | Global, updated monthly | [Protected Planet](https://www.protectedplanet.net/) / WDPA; service metadata also available through UNEP-WCMC | Protection as mitigating/positive shock; protected-area share by cell-year if status dates usable |

## 3. Search / Access Shocks

These affect collection/sequencing probability even when biodiversity is unchanged.

| Dataset | What It Measures | Geography/Time | Download Option | Use |
|---|---|---|---|---|
| UCDP GED | Geocoded organized-violence events, deaths, actors | Global, 1989-2024 in GED 25.1; candidate data monthly beyond | [UCDP downloads](https://ucdp.uu.se/downloads/), CSV/Excel/R/Stata/codebook | Main conflict shock; aggregate events/deaths to cell-year |
| ACLED | Political violence, demonstrations, strategic developments | Global/near-real-time, broader event taxonomy | Requires myACLED account/API key; [ACLED access guide](https://acleddata.com/knowledge-base/acled-access-guide/) and [API docs](https://acleddata.com/acled-api-documentation) | Broader conflict/protest/access shock; robustness to UCDP |
| gROADSv1 | Baseline global roads network | Global, mostly 1980s-2010 vintage | NASA/SEDAC [gROADSv1](https://www.earthdata.nasa.gov/data/catalog/esdis-ciesin-sedac-groads-v1-1.0) | Baseline accessibility; interact with shocks |
| OpenStreetMap roads | Current roads and infrastructure | Global/current, with historical planet history possible but large | Planet/extracts; [OSM extract options](https://wiki.openstreetmap.org/wiki/Extract), Geofabrik country/continent PBFs | Current accessibility; caution for endogenous/current mapping intensity |
| Night lights | Economic activity / accessibility proxy | Global annual/monthly depending product | VIIRS/DMSP through NOAA/Earth Engine | Research capacity/access controls; not a biodiversity shock |
| Institutions / universities / airports / cities | Search capacity and logistics | Global/static or annual | Various public geocoded sources; use cautiously | Controls/interactions for search capacity |
| COVID shock | Fieldwork/sequencing disruption | Global 2020-2021 | Construct as year shocks or country policy measures | Search disruption; likely absorbed by year/country-year FE |

## 4. Mixed Shocks

These can affect both biodiversity and sampling/search. They are useful but need careful interpretation.

| Shock | Biodiversity Channel | Search/Access Channel | Candidate Data |
|---|---|---|---|
| Deforestation | Habitat loss, fragmentation, local species decline | Roads/frontier access, land-use activity, more human presence | Hansen GFC, ESA CCI/Copernicus land cover |
| Fire | Mortality, habitat disturbance, succession | Temporarily easier/harder access; disaster response; visibility | MODIS MCD64A1, VIIRS active fires |
| Conflict | Hunting/land-use changes, protected-area pressure, displacement | Reduces fieldwork and institutional access | UCDP GED, ACLED |
| Natural disasters | Habitat disturbance, mortality, hydrological change | Fieldwork disruption and recovery access | GDACS, EM-DAT, MODIS fires, CHIRPS/TerraClimate/ERA5 |
| Protected-area creation | Habitat protection and reduced destruction | May increase scientific attention/monitoring | WDPA/Protected Planet |

## Identification Strategy

For the BOLD sampling panel:

```text
log1p(BOLD sampling_ct) =
  beta1 * forest_loss_ct
  + beta2 * conflict_ct
  + beta3 * disaster_or_climate_shock_ct
  + cell FE
  + year FE
  + country-year FE where feasible
```

Run separately for:

- all records
- Animalia
- Plantae
- Fungi
- Plantae + Fungi
- non-Chordata Animalia
- Arthropoda
- Insecta
- Chordata

Use both:

- extensive margin: `any_* = 1[count_ct > 0]`
- intensive margin: `log1p_* = log(1 + count_ct)`

The useful empirical tests are comparative:

- If conflict reduces all outcomes similarly, that looks like a search/access shock.
- If deforestation predicts future declines in plant/fungi/insect sampling more than Chordata, that is more consistent with an ecological/biodiversity channel.
- If deforestation increases sampling in the short run but reduces it later, that suggests an access/frontier channel followed by biodiversity loss.
- Baseline biodiversity should be used through interactions, e.g. `forest_loss_ct x baseline_richness_c`, because fixed cell effects absorb time-invariant biodiversity levels.

## First Concrete Build Targets

1. Aggregate Hansen GFC `lossyear` to 100 km cells by year:
   - forest loss area
   - forest loss share of baseline forest
   - lagged/cumulative loss

   Current status: implemented via Google Earth Engine in
   `Scripts/gee_hansen_forest_loss_100km.js`. Uses tree-cover-weighted method
   (loss area = sum of treecover2000/100 × pixel area for loss pixels). Output:

   ```text
   Data/regressors/hansen/hansen_forest_loss_100km_panel.csv
   ```

   Variables: `baseline_forest_km2`, `forest_loss_km2`, `forest_loss_share`,
   `cumulative_loss_km2`, `cumulative_loss_share`, and 1-2 year lags. Covers
   2001-2023.

2. Aggregate UCDP GED to cells by year:
   - event count
   - fatalities
   - any conflict

   Current status: implemented in `Scripts/aggregate_ucdp_ged_100km.py` and
   run on `Data/raw/ucdp/GEDEvent_v25_1.csv`. Output:

   ```text
   Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024.csv
   Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024_summary.csv
   ```

   The file contains raw event and fatality variables only; generate logs and
   lags in Stata.
3. Aggregate MODIS MCD64A1 to cells by year:
   - burned area
   - any burned area

   Current status: implemented via Google Earth Engine in
   `Scripts/gee_modis_burned_area_100km.js`. Output:

   ```text
   Data/regressors/modis/modis_burned_area_100km_panel.csv
   ```

   Variables: `burned_area_km2`, `any_burned`, `cumulative_burned_km2`, and
   1-2 year lags. Covers 2001-2023.

4. Aggregate TerraClimate or CHIRPS/ERA5 anomalies:
   - annual precipitation anomaly
   - drought/water-deficit anomaly
   - heat anomaly

   Current status: TerraClimate implemented in
   `Scripts/download_terraclimate.py`, `Scripts/download_terraclimate_baseline.py`,
   and `Scripts/aggregate_terraclimate_100km.py`. Output:

   ```text
   Data/regressors/terraclimate/terraclimate_100km_panel.csv
   ```

   Variables: `pdsi_mean`, `pdsi_anomaly`, `tmax_mean`, `tmax_anomaly`,
   `ppt_mean`, `ppt_anomaly`. Anomalies relative to 1981-2010 baseline.
   Covers 2001-2023.

   CHIRPS implemented in `Scripts/download_chirps.py` and
   `Scripts/aggregate_chirps_100km.py`. Output:

   ```text
   Data/regressors/chirps/chirps_100km_panel.csv
   ```

   Variables: `chirps_precip_mm`, `chirps_precip_anomaly`. Coverage: 50°S-50°N
   only. Anomalies relative to 1981-2010 baseline.

5. Add baseline geography:
   - ecoregion
   - biome/realm
   - hotspot indicator
   - protected-area share
   - modeled richness/intactness when available

   Current status for ecoregion/biome/realm: implemented locally with RESOLVE
   2017 centroid overlay in `Scripts/aggregate_resolve_ecoregions_100km.py`.
   Raw input download is reproducible via `Scripts/download_baseline_geography.py`
   and documented in `Scripts/baseline_geography_README.md`. Geospatial package
   dependencies are listed in `requirements_baseline_geography.txt`.
   Output:

   ```text
   Data/regressors/baseline_geography/resolve_ecoregions_100km_cells.csv
   ```

   Audit: 14,566 unique land cells; 14,291 matched to RESOLVE ecoregions;
   1,243 are explicit `Rock and Ice`; 275 remain unmatched.

   Current status for hotspot indicator: implemented locally with CEPF/
   Conservation International hotspot polygons in
   `Scripts/aggregate_cepf_hotspots_100km.py`. Output:

   ```text
   Data/regressors/baseline_geography/cepf_hotspots_100km_cells.csv
   ```

   Audit: 14,566 unique land cells; 2,430 cells inside any hotspot; all 36
   hotspot names represented; no cell centroid matched multiple hotspots.

   Current status for protected-area share: script prepared and local May 2026
   WDPA/WDOECM polygon geodatabase is present. Script:

   ```text
   Scripts/aggregate_wdpa_protected_share_100km.py
   ```

   Expected output:

   ```text
   Data/regressors/baseline_geography/wdpa_protected_share_100km_cells.csv
   ```

   This is a snapshot regressor, not a time-varying protected-area panel. Use
   it as baseline geography/control/heterogeneity.

   Current status for time-varying WDPA panel: implemented in
   `Scripts/aggregate_wdpa_protected_panel_100km_v2.py` (fast sjoin+clip). Output:

   ```text
   Data/regressors/wdpa/wdpa_protected_panel_100km.csv
   ```

   Variables: `protected_area_km2`, `protected_share`, `any_protected`,
   `new_protection_km2`. Covers 2001-2024.

   Current status for GLOBIO MSA: implemented in
   `Scripts/download_globio_msa.py` and `Scripts/aggregate_globio_msa_100km.py`.
   Output:

   ```text
   Data/regressors/baseline_geography/globio_msa_100km_cells.csv
   ```

   Variable: `msa_overall` (0-1, 2015 baseline). Mean 0.58.

   Current status for road density: implemented in
   `Scripts/download_grip_roads.py` and `Scripts/aggregate_grip_roads_100km.py`.
   Output:

   ```text
   Data/regressors/baseline_geography/grip_roads_100km_cells.csv
   ```

   Variables: `road_density_km_per_km2`, `any_road`, `log_road_density`.

   All regressors are merged into `Data/analysis/BOLD_regressor_panel.dta` via
   `DoFiles/merge_all_regressors.do`.
