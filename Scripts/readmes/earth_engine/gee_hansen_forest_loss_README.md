# Hansen Forest Loss Aggregation to BOLD Cells

This document explains how to run the Google Earth Engine script that
aggregates Hansen Global Forest Change data to BOLD equal-area cells using
tree-cover-weighted forest loss. The baseline script is 100 km. The 50 km
experimental script is documented with the rest of the spatial/time workflow in
`Scripts/readmes/earth_engine/tests_spatial_time_README.md`.

## Method

**Tree-cover-weighted forest loss** accounts for partial canopy cover:

```
loss_area = sum over pixels [ (treecover2000 / 100) × pixel_area ]
```

For a 30m pixel with 80% tree cover that was lost in 2015:
- Pixel area ≈ 0.0009 km² (varies slightly by latitude)
- Weighted contribution = 0.80 × 0.0009 = 0.00072 km²

This is more accurate than binary counting because it weights high-canopy-cover forest loss more heavily than sparse woodland loss.

## Output Files

The script exports three CSV files to Google Drive:

| File | Rows | Columns |
|------|------|---------|
| `hansen_forest_loss_100km_annual.csv` | 14,566 cells × 23 years = ~335K | cell_id, cell_x, cell_y, year, forest_loss_km2 |
| `hansen_baseline_forest_100km.csv` | 14,566 cells | cell_id, cell_x, cell_y, baseline_forest_km2 |
| `hansen_cumulative_loss_100km.csv` | ~335K | cell_id, year, cumulative_loss_km2 |

Merge in Stata/Python:

```stata
import delimited "hansen_baseline_forest_100km.csv", clear
tempfile baseline
save `baseline'

import delimited "hansen_forest_loss_100km_annual.csv", clear
merge m:1 cell_id using `baseline', nogen
gen forest_loss_share = forest_loss_km2 / baseline_forest_km2
```

## Step-by-Step Instructions

### 1. Sign In to Google Earth Engine

Go to [code.earthengine.google.com](https://code.earthengine.google.com) and sign in with `vaskorovkin@gmail.com`.

If you haven't registered for Earth Engine yet:
1. Go to [signup.earthengine.google.com](https://signup.earthengine.google.com)
2. Register for a free noncommercial account
3. Wait for approval (usually instant for academic use)

### 2. Upload the Grid as an Earth Engine Asset

**First check whether the asset already exists** under your project — open
the **Assets** tab in the left panel of the Code Editor and look for:
```
projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells
```
If it's there, skip to Step 3.

The source file is at:
```
Data/processed/bold/bold_grid100_land_cells.geojson
```

GEE no longer offers a direct GeoJSON option in the **NEW → Table upload**
menu, so convert it to a zipped shapefile first. From a terminal:

```bash
cd Data/processed/bold
ogr2ogr -f "ESRI Shapefile" bold_grid100_land_cells.shp bold_grid100_land_cells.geojson
zip bold_grid100_land_cells.zip bold_grid100_land_cells.shp \
    bold_grid100_land_cells.shx bold_grid100_land_cells.dbf \
    bold_grid100_land_cells.prj
```

Then in the Code Editor:

1. Click the **Assets** tab in the left panel.
2. Click **NEW** (red button) → **Table upload** → **Shape files
   (.shp, .shx, .dbf, .prj, or .zip)**.
3. Select `bold_grid100_land_cells.zip` from your computer.
4. Set **Asset ID** to:
   `projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells`
5. Click **Upload**.
6. Wait for ingestion (5-15 minutes for ~14K features).

You can check progress in the **Tasks** tab (orange gear icon, top right).

Once complete, the asset path is:
```
projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells
```

### 3. Create and Run the Script

1. In Earth Engine Code Editor, click **NEW** → **File**
2. Name it `hansen_forest_loss_100km`
3. Copy the contents of `Scripts/earth_engine/gee_hansen_forest_loss_100km.js` into the editor
4. Verify the `GRID_ASSET` path matches your uploaded asset:
   ```javascript
   var GRID_ASSET = 'projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells';
   ```
5. Click **Run**

### 4. Export Results

After running:

1. Look at the **Tasks** tab (orange gear icon, top right)
2. You'll see three tasks in gray: "hansen_forest_loss_100km_annual", "hansen_baseline_forest_100km", "hansen_cumulative_loss_100km"
3. Click **Run** on each task
4. In the dialog, verify:
   - Drive folder: (leave default or set a folder)
   - File format: CSV
5. Click **Run**

Each export takes 30-90 minutes. You'll receive email notifications when complete.

### 5. Download from Google Drive

Once exports finish:

1. Go to [drive.google.com](https://drive.google.com)
2. Find the CSV files (in root or your specified folder)
3. Download to `Diversity_Discoveries/Data/regressors/hansen/`

## Processing Time Estimate

| Component | Time |
|-----------|------|
| Upload GeoJSON asset | 5-15 min |
| Run script (compute) | 2-5 min |
| Export baseline CSV | 20-40 min |
| Export annual loss CSV | 45-90 min |
| Export cumulative loss CSV | 45-90 min |

**Total: 2-4 hours** (mostly waiting for exports)

Exports run in parallel, so start all three and let them run.

## Troubleshooting

**"Asset not found" error:**
- Check that the asset finished uploading (Assets tab → refresh)
- Verify the path matches exactly (case-sensitive)

**"User memory limit exceeded" error:**
- This happens if the grid is too large or scale is too fine
- The script uses scale=30, which should work but is slower
- If errors persist, try scale=100 (less accurate but faster)

**Export stuck or slow:**
- Large exports queue behind other users
- Peak hours (US daytime) are slower
- Just wait; Earth Engine manages the queue

**Missing cells in output:**
- Cells with zero forest loss may not appear
- After download, merge with full cell list and fill zeros

## Merge Script (Python)

After downloading the Earth Engine exports, use the tracked merge script:

```bash
python3 Scripts/aggregate/merge_hansen_exports.py
python3 Scripts/aggregate/merge_hansen_exports.py --variant test_50km_year
python3 Scripts/aggregate/merge_hansen_exports.py --variant test_50km_quarter
```

For quarterly variants, annual Hansen loss-year values are expanded to
quarters and labeled with `hansen_source_freq = "annual"`.

## Variables for Regression

After merging, you'll have:

| Variable | Description |
|----------|-------------|
| `baseline_forest_km2` | Year-2000 tree-cover-weighted forest area in cell |
| `forest_loss_km2` | Tree-cover-weighted forest loss in cell-year |
| `forest_loss_share` | `forest_loss_km2 / baseline_forest_km2` |
| `cumulative_loss_km2` | Sum of losses from 2001 through year |
| `cumulative_loss_share` | `cumulative_loss_km2 / baseline_forest_km2` |

For lag effects, create `L1_forest_loss_km2`, `L2_forest_loss_km2`, etc. in Stata.
