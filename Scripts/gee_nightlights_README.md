# Harmonized Nighttime Lights Aggregation to 100km Cells

Cell-level income proxy using the Li, Zhou et al. (2020) harmonized nighttime
lights dataset. DMSP-OLS (2005-2013) is calibrated to VIIRS-equivalent scale,
providing a consistent time series with no sensor break.

Reference: Li et al. (2020) "A harmonized global nighttime light dataset
1992-2018" *Scientific Data* 7(1).

## Step-by-Step

### 1. Open Earth Engine

Go to [code.earthengine.google.com](https://code.earthengine.google.com).

The grid asset is already uploaded:
```
projects/symmetric-lock-495018-e0/assets/bold_grid100_land_cells
```

If not, see `Scripts/gee_hansen_forest_loss_README.md` for upload instructions.

### 2. Run the Script

1. Create a new file in the Code Editor
2. Paste `Scripts/gee_nightlights_100km.js`
3. Click **Run**
4. Check the console for band names and date ranges (verification prints)

### 3. Export

One export task appears in the **Tasks** tab:

| Task | Source | Years | Expected time |
|------|--------|-------|---------------|
| `harmonized_nightlights_100km` | Li et al. harmonized + raw VIIRS | 2005-2023 | 30-60 min |

Click **Run** on the task.

### 4. Download and Merge

Download CSV from Google Drive to `Data/regressors/nightlights/`, then:

```bash
python3 Scripts/merge_nightlights_exports.py
```

## Output

`Data/regressors/nightlights/nightlights_100km_panel.csv`

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
- For GEE setup details, see `Scripts/gee_hansen_forest_loss_README.md`.
