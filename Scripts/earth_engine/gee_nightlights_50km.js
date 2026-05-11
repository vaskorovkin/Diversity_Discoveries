/*
 * Harmonized Nighttime Lights: Aggregate to 50km cells
 *
 * Uses the Li, Zhou et al. (2020) harmonized NTL dataset which calibrates
 * DMSP-OLS to VIIRS-equivalent scale, providing a consistent time series.
 *
 * Output: harmonized_nightlights_50km.csv
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid50_land_cells';

var START_YEAR = 2005;
var END_YEAR = 2023;
var HARMONIZED_END = 2021;

// ============================================================================
// LOAD DATA
// ============================================================================

var grid = ee.FeatureCollection(GRID_ASSET);
var hntl_dmsp = ee.ImageCollection('projects/sat-io/open-datasets/Harmonized_NTL/dmsp');
var hntl_viirs = ee.ImageCollection('projects/sat-io/open-datasets/Harmonized_NTL/viirs');
var viirs_raw = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG');

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

  var annualImage = ee.Algorithms.If(
    year.lte(2013),
    hntl_dmsp.filter(ee.Filter.calendarRange(yearInt, yearInt, 'year'))
      .first().select(0).rename('ntl'),
    ee.Algorithms.If(
      year.lte(HARMONIZED_END),
      hntl_viirs.filter(ee.Filter.calendarRange(yearInt, yearInt, 'year'))
        .first().select(0).rename('ntl'),
      viirs_raw.filterDate(
        ee.Date.fromYMD(year, 1, 1),
        ee.Date.fromYMD(year, 12, 31)
      ).select('avg_rad').mean().max(0).rename('ntl')
    )
  );

  annualImage = ee.Image(annualImage);

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
  description: 'harmonized_nightlights_50km',
  fileNamePrefix: 'harmonized_nightlights_50km',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'ntl_mean']
});

print('Years:', START_YEAR, 'to', END_YEAR);
print('Sample (5 rows):', results.limit(5));

var ntl2023 = viirs_raw.filterDate('2023-01-01', '2023-12-31')
  .select('avg_rad').mean().max(0);
Map.addLayer(ntl2023, {min: 0, max: 30, palette: ['black', 'blue', 'yellow', 'white']},
  'NTL 2023');
Map.addLayer(grid, {color: 'red'}, 'Grid Cells', false);
