# UCDP GED 100 km Conflict Regressor

This builds a cell-year conflict regressor from UCDP GED event data.

## Download

Download the UCDP GED global CSV from:

```text
https://ucdp.uu.se/downloads/
```

Save the CSV under:

```text
Data/raw/ucdp/
```

If there is exactly one CSV in that folder, the script will auto-detect it. Otherwise pass `--input`.

## Run

From the project root:

```bash
python3 Scripts/aggregate_ucdp_ged_100km.py
```

or explicitly:

```bash
python3 Scripts/aggregate_ucdp_ged_100km.py --input Data/raw/ucdp/YOUR_UCDP_GED_FILE.csv
```

## Output

```text
Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024.csv
Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024_summary.csv
```

The output is zero-filled for all BOLD 100 km land cells x years 2005-2024.

Core variables:

```text
ucdp_events_all
ucdp_best_all
ucdp_low_all
ucdp_high_all
ucdp_deaths_civilians_all
ucdp_any_all
```

It also creates event/fatality variables for:

```text
state
nonstate
onesided
precise
state_precise
nonstate_precise
onesided_precise
```

For example:

```text
ucdp_events_state
ucdp_best_state
ucdp_events_precise
ucdp_best_precise
ucdp_events_state_precise
ucdp_best_state_precise
```

`precise` means `where_prec` is 1 or 2. Logs and lags should be generated in Stata.
