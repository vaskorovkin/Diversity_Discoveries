/*
 * MODIS MCD64A1 Burned Area: Aggregate to 100km cells
 *
 * Aggregates monthly burned area to annual cell-level totals.
 * - burned_area_km2: total burned area per cell-year
 * - any_burned: indicator for any burned pixels in cell-year
 *
 * Input: Same grid asset as Hansen (bold_grid100_land_cells)
 * Output: CSV with cell_id, year, burned_area_km2, any_burned
 */

// ============================================================================
// CONFIGURATION - UPDATE THIS PATH
// ============================================================================

var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells';

// MODIS MCD64A1 covers 2000-11 to present; use 2001-2023 to align with Hansen
var START_YEAR = 2001;
var END_YEAR = 2023;

// ============================================================================
// LOAD DATA
// ============================================================================

// Load MODIS MCD64A1 Burned Area Monthly Global 500m
var modis = ee.ImageCollection('MODIS/061/MCD64A1');

// Load the 100km grid cells
var grid = ee.FeatureCollection(GRID_ASSET);

// Pixel area in square kilometers (MODIS is 500m resolution)
var pixelAreaKm2 = ee.Image.pixelArea().divide(1e6);

// ============================================================================
// COMPUTE ANNUAL BURNED AREA PER CELL
// ============================================================================

var computeYearlyBurned = function(year) {
  year = ee.Number(year);

  // Filter to this year
  var yearStart = ee.Date.fromYMD(year, 1, 1);
  var yearEnd = ee.Date.fromYMD(year, 12, 31);

  var yearImages = modis.filterDate(yearStart, yearEnd);

  // BurnDate band: day of burn (1-366) or 0 if unburned
  // Create binary burned mask across all months
  var burnedMask = yearImages.select('BurnDate')
    .map(function(img) {
      return img.gt(0);
    })
    .max();  // Any month burned = 1

  // Burned area = pixel area where burned
  var burnedArea = pixelAreaKm2.updateMask(burnedMask);

  // Sum burned area per cell
  var burnedByCell = burnedArea.reduceRegions({
    collection: grid,
    reducer: ee.Reducer.sum(),
    scale: 500,
    crs: 'EPSG:4326'
  });

  // Add year and compute any_burned indicator
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

// Process all years
var years = ee.List.sequence(START_YEAR, END_YEAR);
var annualBurned = ee.FeatureCollection(years.map(computeYearlyBurned)).flatten();

// ============================================================================
// EXPORT RESULTS
// ============================================================================

Export.table.toDrive({
  collection: annualBurned,
  description: 'modis_burned_area_100km_annual',
  fileNamePrefix: 'modis_burned_area_100km_annual',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'burned_area_km2', 'any_burned']
});

// ============================================================================
// PRINT SUMMARY FOR VERIFICATION
// ============================================================================

print('Grid cells:', grid.size());
print('Years:', START_YEAR, 'to', END_YEAR);
print('Sample burned area (first 5 rows):', annualBurned.limit(5));

// Map visualization (optional)
var recentBurn = modis.filterDate('2023-01-01', '2023-12-31')
  .select('BurnDate')
  .max()
  .selfMask();
Map.addLayer(recentBurn, {min: 1, max: 366, palette: ['yellow', 'orange', 'red']}, 'Burn Date 2023');
Map.addLayer(grid, {color: 'blue'}, 'Grid Cells', false);
