/*
 * Hansen Global Forest Change: Aggregate to 50km cells
 *
 * Tree-cover-weighted forest loss calculation:
 * - Loss area = sum of (treecover2000/100 * pixel_area) for pixels where lossyear == year
 * - Baseline forest = sum of (treecover2000/100 * pixel_area) for all pixels with treecover2000 > 0
 *
 * Input: Upload bold_grid50_land_cells.zip as Earth Engine table asset
 * Output: CSV with cell_id, year, forest_loss_km2, baseline_forest_km2
 */

// ============================================================================
// CONFIGURATION - UPDATE THIS PATH
// ============================================================================

var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid50_land_cells';

var START_YEAR = 2001;
var END_YEAR = 2023;
var MIN_TREE_COVER = 0;

// ============================================================================
// LOAD DATA
// ============================================================================

var hansen = ee.Image('UMD/hansen/global_forest_change_2023_v1_11');
var grid = ee.FeatureCollection(GRID_ASSET);

var treecover2000 = hansen.select('treecover2000');
var lossyear = hansen.select('lossyear');

var treecoverFraction = treecover2000.divide(100);
var pixelAreaKm2 = ee.Image.pixelArea().divide(1e6);
var weightedForestArea = treecoverFraction.multiply(pixelAreaKm2);

// ============================================================================
// COMPUTE BASELINE FOREST AREA PER CELL
// ============================================================================

var forestMask = treecover2000.gt(MIN_TREE_COVER);
var baselineForestArea = weightedForestArea.updateMask(forestMask);

var baselineByCell = baselineForestArea.reduceRegions({
  collection: grid,
  reducer: ee.Reducer.sum(),
  scale: 30,
  crs: 'EPSG:4326'
});

baselineByCell = baselineByCell.map(function(f) {
  var s = f.get('sum');
  return f.set('baseline_forest_km2', ee.Algorithms.If(s, s, 0));
});

// ============================================================================
// COMPUTE ANNUAL FOREST LOSS PER CELL
// ============================================================================

var computeYearlyLoss = function(year) {
  var lossYearCode = ee.Number(year).subtract(2000);

  var yearLossMask = lossyear.eq(lossYearCode);
  var yearLossArea = weightedForestArea.updateMask(yearLossMask);

  var lossByCell = yearLossArea.reduceRegions({
    collection: grid,
    reducer: ee.Reducer.sum(),
    scale: 30,
    crs: 'EPSG:4326'
  });

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

var years = ee.List.sequence(START_YEAR, END_YEAR);
var annualLoss = ee.FeatureCollection(years.map(computeYearlyLoss)).flatten();

// ============================================================================
// EXPORT RESULTS
// ============================================================================

Export.table.toDrive({
  collection: annualLoss,
  description: 'hansen_forest_loss_50km_annual',
  fileNamePrefix: 'hansen_forest_loss_50km_annual',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'year', 'forest_loss_km2']
});

Export.table.toDrive({
  collection: baselineByCell,
  description: 'hansen_baseline_forest_50km',
  fileNamePrefix: 'hansen_baseline_forest_50km',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'cell_x', 'cell_y', 'baseline_forest_km2']
});

var computeCumulativeLoss = function(year) {
  var lossYearCode = ee.Number(year).subtract(2000);
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

Export.table.toDrive({
  collection: cumulativeLoss,
  description: 'hansen_cumulative_loss_50km',
  fileNamePrefix: 'hansen_cumulative_loss_50km',
  fileFormat: 'CSV',
  selectors: ['cell_id', 'year', 'cumulative_loss_km2']
});

print('Grid cells:', grid.size());
print('Years:', START_YEAR, 'to', END_YEAR);
print('Sample baseline (first 5 cells):', baselineByCell.limit(5));
print('Sample annual loss (first 5 rows):', annualLoss.limit(5));

Map.addLayer(treecover2000, {min: 0, max: 100, palette: ['white', 'green']}, 'Tree Cover 2000');
Map.addLayer(lossyear.selfMask(), {min: 1, max: 23, palette: ['yellow', 'red']}, 'Loss Year');
Map.addLayer(grid, {color: 'blue'}, 'Grid Cells', false);
