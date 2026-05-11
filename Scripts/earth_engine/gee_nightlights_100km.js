/*
 * Harmonized Nighttime Lights: Aggregate to 100km cells
 *
 * Uses the Li, Zhou et al. (2020) harmonized NTL dataset which calibrates
 * DMSP-OLS to VIIRS-equivalent scale, providing a consistent time series.
 *
 * Source: Li et al. (2020) "A harmonized global nighttime light dataset
 * 1992-2018" Scientific Data 7(1).
 *
 * GEE community catalog:
 *   DMSP (harmonized): projects/sat-io/open-datasets/Harmonized_NTL/dmsp
 *   VIIRS (harmonized): projects/sat-io/open-datasets/Harmonized_NTL/viirs
 *
 * Coverage on GEE: 1992-2021. For 2022-2023, we extend with raw VIIRS DNB
 * monthly composites (already on VIIRS scale — the harmonization calibrates
 * DMSP upward to match VIIRS, so raw VIIRS is consistent with the series).
 *
 * Resolution: 30 arc-seconds (~1km). Band: b1 (harmonized DN).
 * Authors recommend masking pixels <= 7 as noise (we keep all for cell means).
 *
 * Input: Same grid asset as Hansen/MODIS (bold_grid100_land_cells)
 * Output: Single CSV — harmonized_nightlights_100km.csv
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells';

var START_YEAR = 2005;
var END_YEAR = 2023;

// Li et al. harmonized NTL on GEE ends at 2021
var HARMONIZED_END = 2021;

// ============================================================================
// LOAD DATA
// ============================================================================

var grid = ee.FeatureCollection(GRID_ASSET);

// Li et al. harmonized collections (both calibrated to VIIRS-equivalent scale)
var hntl_dmsp = ee.ImageCollection('projects/sat-io/open-datasets/Harmonized_NTL/dmsp');
var hntl_viirs = ee.ImageCollection('projects/sat-io/open-datasets/Harmonized_NTL/viirs');

// Raw VIIRS for 2022-2023 extension
var viirs_raw = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG');

// Print band info for verification
print('HNTL DMSP bands:', hntl_dmsp.first().bandNames());
print('HNTL VIIRS bands:', hntl_viirs.first().bandNames());
print('HNTL DMSP date range:', hntl_dmsp.aggregate_min('system:time_start'),
      hntl_dmsp.aggregate_max('system:time_start'));
print('HNTL VIIRS date range:', hntl_viirs.aggregate_min('system:time_start'),
      hntl_viirs.aggregate_max('system:time_start'));
print('Grid cells:', grid.size());

// ============================================================================
// COMPUTE ANNUAL MEAN RADIANCE PER CELL
// ============================================================================

var computeYear = function(year) {
  year = ee.Number(year);
  var yearInt = year.int();

  // Select the right image source based on year
  var annualImage = ee.Algorithms.If(
    year.lte(2013),
    // 2005-2013: harmonized DMSP (one image per year)
    hntl_dmsp.filter(ee.Filter.calendarRange(yearInt, yearInt, 'year'))
      .first().select(0).rename('ntl'),

    ee.Algorithms.If(
      year.lte(HARMONIZED_END),
      // 2014-2021: harmonized VIIRS (one image per year)
      hntl_viirs.filter(ee.Filter.calendarRange(yearInt, yearInt, 'year'))
        .first().select(0).rename('ntl'),

      // 2022-2023: raw VIIRS monthly, averaged to annual
      viirs_raw.filterDate(
        ee.Date.fromYMD(year, 1, 1),
        ee.Date.fromYMD(year, 12, 31)
      ).select('avg_rad').mean().max(0).rename('ntl')
    )
  );

  annualImage = ee.Image(annualImage);

  // Mean radiance per cell
  var cellMeans = annualImage.reduceRegions({
    collection: grid,
    reducer: ee.Reducer.mean(),
    scale: 1000,
    crs: 'EPSG:4326'
  });

  return cellMeans.map(function(f) {
    var val = f.get('mean');
    var meanVal = ee.Algorithms.If(val, val, 0);
    return ee.Feature(null, {
      'cell_id': f.get('cell_id'),
      'cell_x': f.get('cell_x'),
      'cell_y': f.get('cell_y'),
      'year': year,
      'ntl_mean': meanVal
    });
  });
};

var years = ee.List.sequence(START_YEAR, END_YEAR);
var results = ee.FeatureCollection(years.map(computeYear)).flatten();

// ============================================================================
// EXPORT
// ============================================================================

Export.table.toDrive({
  collection: results,
  description: 'harmonized_nightlights_100km',
  fileNamePrefix: 'harmonized_nightlights_100km',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'ntl_mean']
});

// ============================================================================
// VERIFICATION
// ============================================================================

print('Years:', START_YEAR, 'to', END_YEAR);
print('Sample (5 rows):', results.limit(5));

// Map: most recent year
var ntl2023 = viirs_raw.filterDate('2023-01-01', '2023-12-31')
  .select('avg_rad').mean().max(0);
Map.addLayer(ntl2023, {min: 0, max: 30, palette: ['black', 'blue', 'yellow', 'white']},
  'NTL 2023');
Map.addLayer(grid, {color: 'red'}, 'Grid Cells', false);
