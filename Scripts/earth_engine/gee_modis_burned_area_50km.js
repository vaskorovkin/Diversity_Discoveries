/*
 * MODIS MCD64A1 Burned Area: Aggregate to 50km cells
 *
 * Aggregates monthly burned area to annual cell-level totals.
 * - burned_area_km2: total burned area per cell-year
 * - any_burned: indicator for any burned pixels in cell-year
 *
 * Input: bold_grid50_land_cells asset
 * Output: CSV with cell_id, year, burned_area_km2, any_burned
 */

// ============================================================================
// CONFIGURATION - UPDATE THIS PATH
// ============================================================================

var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid50_land_cells';

var START_YEAR = 2001;
var END_YEAR = 2023;

// ============================================================================
// LOAD DATA
// ============================================================================

var modis = ee.ImageCollection('MODIS/061/MCD64A1');
var grid = ee.FeatureCollection(GRID_ASSET);
var pixelAreaKm2 = ee.Image.pixelArea().divide(1e6);

// ============================================================================
// COMPUTE ANNUAL BURNED AREA PER CELL
// ============================================================================

var computeYearlyBurned = function(year) {
  year = ee.Number(year);
  var yearStart = ee.Date.fromYMD(year, 1, 1);
  var yearEnd = ee.Date.fromYMD(year, 12, 31);

  var yearImages = modis.filterDate(yearStart, yearEnd);

  var burnedMask = yearImages.select('BurnDate')
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

  burnedByCell = burnedByCell.map(function(f) {
    var area = f.get('sum');
    var areaVal = ee.Algorithms.If(area, area, 0);
    return ee.Feature(null, {
      'cell_id': f.get('cell_id'),
      'cell_x': f.get('cell_x'),
      'cell_y': f.get('cell_y'),
      'year': year,
      'burned_area_km2': areaVal,
      'any_burned': ee.Algorithms.If(ee.Number(areaVal).gt(0), 1, 0)
    });
  });

  return burnedByCell;
};

var years = ee.List.sequence(START_YEAR, END_YEAR);
var annualBurned = ee.FeatureCollection(years.map(computeYearlyBurned)).flatten();

// ============================================================================
// EXPORT RESULTS
// ============================================================================

Export.table.toDrive({
  collection: annualBurned,
  description: 'modis_burned_area_50km_annual',
  fileNamePrefix: 'modis_burned_area_50km_annual',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'burned_area_km2', 'any_burned']
});

print('Grid cells:', grid.size());
print('Years:', START_YEAR, 'to', END_YEAR);
print('Sample burned area (first 5 rows):', annualBurned.limit(5));

var recentBurn = modis.filterDate('2023-01-01', '2023-12-31')
  .select('BurnDate')
  .max()
  .selfMask();
Map.addLayer(recentBurn, {min: 1, max: 366, palette: ['yellow', 'orange', 'red']}, 'Burn Date 2023');
Map.addLayer(grid, {color: 'blue'}, 'Grid Cells', false);
