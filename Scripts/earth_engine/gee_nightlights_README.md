# Harmonized Nighttime Lights Aggregation to BOLD Cells

Cell-level income proxy using the Li, Zhou et al. (2020) harmonized nighttime
lights dataset. DMSP-OLS (2005-2013) is calibrated to VIIRS-equivalent scale,
providing a consistent time series with no sensor break.

The baseline script aggregates to 100 km cells. The 50 km yearly script uses
the same annual harmonized source. The 50 km quarterly pipeline intentionally
expands annual harmonized values within year rather than using VIIRS-only
quarterly lights, because preserving 2005-2023 coverage is more important than
quarterly NTL timing for the current design.

Reference: Li et al. (2020) "A harmonized global nighttime light dataset
1992-2018" *Scientific Data* 7(1).

## Step-by-Step

### 1. Open Earth Engine

Go to [code.earthengine.google.com](https://code.earthengine.google.com) and
sign in with the Google account that owns project
`symmetric-lock-495018-e0`.

### 2. Confirm the Grid Asset Is Already Uploaded

In the left panel, click the **Assets** tab and look for:
```
projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells
```

**If it's there, skip to Step 3.** If not, upload it as follows:

1. Click **NEW** (red button) → **Table upload** → **Shape files
   (.shp, .shx, .dbf, .prj, or .zip)**.

   Note: GEE no longer offers a direct GeoJSON option in the upload menu,
   so the GeoJSON must be converted to a zipped shapefile first. From a
   terminal:

   ```bash
   cd Data/processed/bold
   ogr2ogr -f "ESRI Shapefile" bold_grid100_land_cells.shp bold_grid100_land_cells.geojson
   zip bold_grid100_land_cells.zip bold_grid100_land_cells.shp \
       bold_grid100_land_cells.shx bold_grid100_land_cells.dbf \
       bold_grid100_land_cells.prj
   ```

2. In the upload dialog, select the `.zip` from
   `Data/processed/bold/bold_grid100_land_cells.zip`.
3. Set **Asset ID** to:
   `projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells`.
4. Click **Upload**. Ingestion takes 5-15 minutes for ~14K features.
   Watch progress in the **Tasks** tab (orange gear icon, top right).

(Full troubleshooting and timing notes for the upload step live in
`Scripts/earth_engine/gee_hansen_forest_loss_README.md`.)

### 3. Run the Script

1. Create a new file in the Code Editor (**Scripts** tab → **NEW** → **File**).
2. Paste the contents of `Scripts/earth_engine/gee_nightlights_100km.js`.
3. Verify the `GRID_ASSET` path at the top of the script matches the
   asset path above.
4. Click **Run**.
5. Check the console for band names and date ranges (verification prints).

### 4. Export

One export task appears in the **Tasks** tab:

| Task | Source | Years | Expected time |
|------|--------|-------|---------------|
| `harmonized_nightlights_100km` | Li et al. harmonized + raw VIIRS | 2005-2023 | 30-60 min |

Click **Run** on the task.

### 5. Download and Merge

Download CSV from Google Drive to `Data/regressors/nightlights/`, then:

```bash
python3 Scripts/merge_nightlights_exports.py
python3 Scripts/merge_nightlights_exports.py --variant test_50km_year
python3 Scripts/merge_nightlights_exports.py --variant test_50km_quarter
```

## Output

`Data/regressors/nightlights/nightlights_100km_panel.csv`

50 km variants write under:

```text
Data/regressors/tests_spatial_time/nightlights/nightlights_50km_panel.csv
Data/regressors/tests_spatial_time/nightlights/nightlights_50km_quarter_panel.csv
```

| Variable | Description |
|----------|-------------|
| `ntl_mean` | Mean harmonized radiance in cell-year (consistent scale across all years) |
| `log1p_ntl` | log(1 + ntl_mean) |
| `any_light` | 1 if any nightlight detected |
| `L1_log1p_ntl` | 1-year lag of log1p_ntl |

## Data Sources

| Years | Source | GEE Asset |
|-------|--------|-----------|
| 2005-2013 | Li et al. harmonized DMSP (calibrated to VIIRS scale) | `projects/sat-io/open-datasets/Harmonized_NTL/dmsp` |
| 2014-2021 | Li et al. harmonized VIIRS | `projects/sat-io/open-datasets/Harmonized_NTL/viirs` |
| 2022-2023 | Raw VIIRS DNB monthly (averaged to annual) | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` |

The harmonization calibrates DMSP upward to match VIIRS, so raw VIIRS for
2022-2023 is already on the correct scale — no sensor dummy needed.

## Notes

- Resolution: 30 arc-seconds (~1km). Aggregated to cell mean at scale=1000.
- Li et al. recommend masking pixels with DN ≤ 7 as noise. The script keeps
  all pixels for cell-level means (noise averages out at 100km scale).
- The Li et al. dataset is available through 2024 on Figshare but only
  through 2021 on the GEE community catalog (as of mid-2026).
- For GEE setup details, see `Scripts/earth_engine/gee_hansen_forest_loss_README.md`.
