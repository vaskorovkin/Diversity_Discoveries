/*
 * Hansen Global Forest Change: Aggregate to 100km cells
 *
 * Tree-cover-weighted forest loss calculation:
 * - Loss area = sum of (treecover2000/100 * pixel_area) for pixels where lossyear == year
 * - Baseline forest = sum of (treecover2000/100 * pixel_area) for all pixels with treecover2000 > 0
 *
 * Input: Upload bold_grid100_land_cells.geojson as Earth Engine asset
 * Output: CSV with cell_id, year, forest_loss_km2, baseline_forest_km2
 *
 * Instructions:
 * 1. Upload GeoJSON to Earth Engine as asset (see README below)
 * 2. Update GRID_ASSET path to your uploaded asset
 * 3. Run script
 * 4. Export results from Tasks panel
 */

// ============================================================================
// CONFIGURATION - UPDATE THIS PATH
// ============================================================================

// After uploading your GeoJSON, replace this with your asset path
var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells';

// Years to process (Hansen GFC v1.11 covers 2001-2023)
var START_YEAR = 2001;
var END_YEAR = 2023;

// Minimum tree cover threshold (0 = include all pixels with any tree cover)
var MIN_TREE_COVER = 0;

// ============================================================================
// LOAD DATA
// ============================================================================

// Load Hansen Global Forest Change dataset
var hansen = ee.Image('UMD/hansen/global_forest_change_2023_v1_11');

// Load the 100km grid cells
var grid = ee.FeatureCollection(GRID_ASSET);

// Extract bands
var treecover2000 = hansen.select('treecover2000');
var lossyear = hansen.select('lossyear');
var datamask = hansen.select('datamask');

// Create tree cover fraction (0-1 scale)
var treecoverFraction = treecover2000.divide(100);

// Pixel area in square kilometers (Hansen is 30m resolution)
// At equator: 30m × 30m = 900 m² = 0.0009 km² = 9e-4 km²
// But pixel area varies with latitude, so we compute it properly
var pixelAreaKm2 = ee.Image.pixelArea().divide(1e6);

// Tree-cover-weighted area per pixel (in km²)
// This represents "effective forest area" accounting for partial canopy cover
var weightedForestArea = treecoverFraction.multiply(pixelAreaKm2);

// ============================================================================
// COMPUTE BASELINE FOREST AREA PER CELL
// ============================================================================

// Mask to pixels with tree cover above threshold
var forestMask = treecover2000.gt(MIN_TREE_COVER);
var baselineForestArea = weightedForestArea.updateMask(forestMask);

// Sum baseline forest area per cell
var baselineByCell = baselineForestArea.reduceRegions({
  collection: grid,
  reducer: ee.Reducer.sum(),
  scale: 30,
  crs: 'EPSG:4326'
});

// Rename the sum column and handle null values
baselineByCell = baselineByCell.map(function(f) {
  var s = f.get('sum');
  return f.set('baseline_forest_km2', ee.Algorithms.If(s, s, 0));
});

// ============================================================================
// COMPUTE ANNUAL FOREST LOSS PER CELL
// ============================================================================

// Function to compute forest loss for a single year
var computeYearlyLoss = function(year) {
  // lossyear values: 1 = 2001, 2 = 2002, ..., 23 = 2023
  var lossYearCode = ee.Number(year).subtract(2000);

  // Mask to pixels lost in this year
  var yearLossMask = lossyear.eq(lossYearCode);
  var yearLossArea = weightedForestArea.updateMask(yearLossMask);

  // Sum loss area per cell
  var lossByCell = yearLossArea.reduceRegions({
    collection: grid,
    reducer: ee.Reducer.sum(),
    scale: 30,
    crs: 'EPSG:4326'
  });

  // Add year and rename columns, handling null values
  lossByCell = lossByCell.map(function(f) {
    var loss = f.get('sum');
    return ee.Feature(null, {
      'cell_id': f.get('cell_id'),
      'cell_x': f.get('cell_x'),
      'cell_y': f.get('cell_y'),
      'year': year,
      'forest_loss_km2': ee.Algorithms.If(loss, loss, 0)
    });
  });

  return lossByCell;
};

// Process all years
var years = ee.List.sequence(START_YEAR, END_YEAR);
var annualLoss = ee.FeatureCollection(years.map(computeYearlyLoss)).flatten();

// ============================================================================
// EXPORT RESULTS
// ============================================================================

// Export annual forest loss (long format: one row per cell-year)
Export.table.toDrive({
  collection: annualLoss,
  description: 'hansen_forest_loss_100km_annual',
  fileNamePrefix: 'hansen_forest_loss_100km_annual',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'forest_loss_km2']
});

// Export baseline forest area (one row per cell)
Export.table.toDrive({
  collection: baselineByCell,
  description: 'hansen_baseline_forest_100km',
  fileNamePrefix: 'hansen_baseline_forest_100km',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'baseline_forest_km2']
});

// ============================================================================
// OPTIONAL: CUMULATIVE LOSS AND REMAINING FOREST
// ============================================================================

// Compute cumulative loss through each year
var computeCumulativeLoss = function(year) {
  var lossYearCode = ee.Number(year).subtract(2000);

  // Mask to pixels lost in this year or earlier
  var cumLossMask = lossyear.lte(lossYearCode).and(lossyear.gt(0));
  var cumLossArea = weightedForestArea.updateMask(cumLossMask);

  var cumLossByCell = cumLossArea.reduceRegions({
    collection: grid,
    reducer: ee.Reducer.sum(),
    scale: 30,
    crs: 'EPSG:4326'
  });

  cumLossByCell = cumLossByCell.map(function(f) {
    var loss = f.get('sum');
    return ee.Feature(null, {
      'cell_id': f.get('cell_id'),
      'year': year,
      'cumulative_loss_km2': ee.Algorithms.If(loss, loss, 0)
    });
  });

  return cumLossByCell;
};

var cumulativeLoss = ee.FeatureCollection(years.map(computeCumulativeLoss)).flatten();

// Export cumulative loss
Export.table.toDrive({
  collection: cumulativeLoss,
  description: 'hansen_cumulative_loss_100km',
  fileNamePrefix: 'hansen_cumulative_loss_100km',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'year', 'cumulative_loss_km2']
});

// ============================================================================
// PRINT SUMMARY FOR VERIFICATION
// ============================================================================

print('Grid cells:', grid.size());
print('Years:', START_YEAR, 'to', END_YEAR);
print('Sample baseline (first 5 cells):', baselineByCell.limit(5));
print('Sample annual loss (first 5 rows):', annualLoss.limit(5));

// Map visualization (optional)
Map.addLayer(treecover2000, {min: 0, max: 100, palette: ['white', 'green']}, 'Tree Cover 2000');
Map.addLayer(lossyear.selfMask(), {min: 1, max: 23, palette: ['yellow', 'red']}, 'Loss Year');
Map.addLayer(grid, {color: 'blue'}, 'Grid Cells', false);
