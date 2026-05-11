/*
 * VIIRS Nighttime Lights: Aggregate monthly VIIRS to 50km x quarter cells
 *
 * This is the quarterly counterpart to the annual harmonized NTL script.
 * It uses raw VIIRS monthly VCMSLCFG because the harmonized DMSP/VIIRS
 * product is annual. Coverage starts in the VIIRS era, not in 2005.
 *
 * Input: Upload bold_grid50_land_cells.zip as an Earth Engine table asset.
 * Output: viirs_nightlights_50km_quarterly.csv
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid50_land_cells';

var START_YEAR = 2012;
var END_YEAR = 2024;

// ============================================================================
// LOAD DATA
// ============================================================================

var grid = ee.FeatureCollection(GRID_ASSET);
var viirs = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG');

print('VIIRS bands:', viirs.first().bandNames());
print('VIIRS date range:', viirs.aggregate_min('system:time_start'),
      viirs.aggregate_max('system:time_start'));
print('Grid cells:', grid.size());

// ============================================================================
// COMPUTE QUARTERLY MEAN RADIANCE PER CELL
// ============================================================================

var computeQuarter = function(yearQuarter) {
  yearQuarter = ee.Dictionary(yearQuarter);
  var year = ee.Number(yearQuarter.get('year'));
  var quarter = ee.Number(yearQuarter.get('quarter'));
  var startMonth = quarter.subtract(1).multiply(3).add(1);
  var startDate = ee.Date.fromYMD(year, startMonth, 1);
  var endDate = startDate.advance(3, 'month');

  var quarterImage = viirs
    .filterDate(startDate, endDate)
    .select('avg_rad')
    .mean()
    .max(0)
    .rename('ntl');

  var cellMeans = quarterImage.reduceRegions({
    collection: grid,
    reducer: ee.Reducer.mean(),
    scale: 1000,
    crs: 'EPSG:4326'
  });

  return cellMeans.map(function(f) {
    var val = f.get('mean');
    return ee.Feature(null, {
      'cell_id': f.get('cell_id'),
      'cell_x': f.get('cell_x'),
      'cell_y': f.get('cell_y'),
      'year': year,
      'quarter': quarter,
      'ntl_mean': ee.Algorithms.If(val, val, 0)
    });
  });
};

var years = ee.List.sequence(START_YEAR, END_YEAR);
var quarters = ee.List.sequence(1, 4);
var yearQuarters = years.map(function(y) {
  return quarters.map(function(q) {
    return ee.Dictionary({'year': y, 'quarter': q});
  });
}).flatten();

var results = ee.FeatureCollection(yearQuarters.map(computeQuarter)).flatten();

// ============================================================================
// EXPORT
// ============================================================================

Export.table.toDrive({
  collection: results,
  description: 'viirs_nightlights_50km_quarterly',
  fileNamePrefix: 'viirs_nightlights_50km_quarterly',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'quarter', 'ntl_mean']
});

print('Years:', START_YEAR, 'to', END_YEAR);
print('Sample (5 rows):', results.limit(5));

var ntl2023q1 = viirs.filterDate('2023-01-01', '2023-04-01')
  .select('avg_rad').mean().max(0);
Map.addLayer(ntl2023q1, {min: 0, max: 30, palette: ['black', 'blue', 'yellow', 'white']},
  'VIIRS NTL 2023 Q1');
Map.addLayer(grid, {color: 'red'}, 'Grid Cells', false);
