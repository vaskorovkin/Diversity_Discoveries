/*
 * MODIS MCD64A1 Burned Area: Aggregate to 50km cells by quarter
 *
 * Aggregates monthly burned area to quarterly cell-level totals.
 * - burned_area_km2: total burned area per cell-quarter
 * - any_burned: indicator for any burned pixels in cell-quarter
 *
 * Input: bold_grid50_land_cells asset
 * Output: CSV with cell_id, year, quarter, burned_area_km2, any_burned
 */

// ============================================================================
// CONFIGURATION - UPDATE THIS PATH
// ============================================================================

var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid50_land_cells';

// MODIS MCD64A1 starts in late 2000; use 2001-2023 for consistency
var START_YEAR = 2001;
var END_YEAR = 2023;

// ============================================================================
// LOAD DATA
// ============================================================================

var modis = ee.ImageCollection('MODIS/061/MCD64A1');
var grid = ee.FeatureCollection(GRID_ASSET);
var pixelAreaKm2 = ee.Image.pixelArea().divide(1e6);

// ============================================================================
// COMPUTE QUARTERLY BURNED AREA PER CELL
// ============================================================================

var QUARTERS = ee.List([
  ee.Dictionary({quarter: 1, startMonth: 1, endMonth: 3}),
  ee.Dictionary({quarter: 2, startMonth: 4, endMonth: 6}),
  ee.Dictionary({quarter: 3, startMonth: 7, endMonth: 9}),
  ee.Dictionary({quarter: 4, startMonth: 10, endMonth: 12})
]);

var computeQuarterlyBurned = function(year) {
  year = ee.Number(year);

  var quarterly = QUARTERS.map(function(qdict) {
    qdict = ee.Dictionary(qdict);
    var quarter = ee.Number(qdict.get('quarter'));
    var startMonth = ee.Number(qdict.get('startMonth'));
    var endMonth = ee.Number(qdict.get('endMonth'));

    var periodStart = ee.Date.fromYMD(year, startMonth, 1);
    var periodEnd = ee.Date.fromYMD(year, endMonth, 1).advance(1, 'month');

    var quarterImages = modis.filterDate(periodStart, periodEnd);

    var burnedMask = quarterImages.select('BurnDate')
      .map(function(img) {
        return img.gt(0);
      })
      .max();

    var burnedArea = pixelAreaKm2.updateMask(burnedMask);

    var burnedByCell = burnedArea.reduceRegions({
      collection: grid,
      reducer: ee.Reducer.sum(),
      scale: 500,
      crs: 'EPSG:4326'
    });

    return burnedByCell.map(function(f) {
      var area = f.get('sum');
      var areaVal = ee.Algorithms.If(area, area, 0);
      return ee.Feature(null, {
        'cell_id': f.get('cell_id'),
        'cell_x': f.get('cell_x'),
        'cell_y': f.get('cell_y'),
        'year': year,
        'quarter': quarter,
        'period': ee.String(year.format()).cat('Q').cat(quarter.format()),
        'burned_area_km2': areaVal,
        'any_burned': ee.Algorithms.If(ee.Number(areaVal).gt(0), 1, 0)
      });
    });
  });

  return ee.FeatureCollection(quarterly).flatten();
};

var years = ee.List.sequence(START_YEAR, END_YEAR);
var quarterlyBurned = ee.FeatureCollection(years.map(computeQuarterlyBurned)).flatten();

// ============================================================================
// EXPORT RESULTS
// ============================================================================

Export.table.toDrive({
  collection: quarterlyBurned,
  description: 'modis_burned_area_50km_quarterly',
  fileNamePrefix: 'modis_burned_area_50km_quarterly',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'quarter', 'period', 'burned_area_km2', 'any_burned']
});

// ============================================================================
// PRINT SUMMARY FOR VERIFICATION
// ============================================================================

print('Grid cells:', grid.size());
print('Years:', START_YEAR, 'to', END_YEAR);
print('Quarters per year:', 4);
print('Sample quarterly burned area (first 5 rows):', quarterlyBurned.limit(5));

var recentQuarterBurn = modis.filterDate('2023-10-01', '2023-12-31')
  .select('BurnDate')
  .max()
  .selfMask();
Map.addLayer(recentQuarterBurn, {min: 1, max: 366, palette: ['yellow', 'orange', 'red']}, 'Burn Date 2023 Q4');
Map.addLayer(grid, {color: 'blue'}, 'Grid Cells', false);
