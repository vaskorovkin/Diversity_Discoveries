* merge_all_regressors.do
* Merges BOLD outcome panel with all regressor datasets
* Master: BOLD collection-year panel (cell_id × year)

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

log using "`proj'/Logs/merge_all_regressors.log", replace text

* -------------------------------------------------------------------
* 1. Import all CSVs as tempfiles
* -------------------------------------------------------------------

* --- Master: BOLD outcomes ---
import delimited "`proj'/Exhibits/data/BOLD_grid100_cell_year_panel_collection_2005_2025.csv", clear
tempfile BOLD
save `BOLD'

* --- Panel regressors (cell_id × year) ---

import delimited "`proj'/Data/regressors/ucdp/ucdp_ged_100km_cell_year_2005_2024.csv", clear
tempfile ucdp
save `ucdp'

import delimited "`proj'/Data/regressors/hansen/hansen_forest_loss_100km_panel.csv", clear
tempfile hansen
save `hansen'

import delimited "`proj'/Data/regressors/modis/modis_burned_area_100km_panel.csv", clear
tempfile modis
save `modis'

import delimited "`proj'/Data/regressors/terraclimate/terraclimate_100km_panel.csv", clear
tempfile terraclimate
save `terraclimate'

import delimited "`proj'/Data/regressors/chirps/chirps_100km_panel.csv", clear
tempfile chirps
save `chirps'

import delimited "`proj'/Data/regressors/wdpa/wdpa_protected_panel_100km.csv", clear
tempfile wdpa_panel
save `wdpa_panel'

* --- Static baselines (cell_id only) ---

import delimited "`proj'/Data/regressors/baseline_geography/resolve_ecoregions_100km_cells.csv", clear
tempfile resolve
save `resolve'

import delimited "`proj'/Data/regressors/baseline_geography/cepf_hotspots_100km_cells.csv", clear
tempfile cepf
save `cepf'

import delimited "`proj'/Data/regressors/baseline_geography/wdpa_protected_share_100km_cells.csv", clear
tempfile wdpa_static
save `wdpa_static'

import delimited "`proj'/Data/regressors/baseline_geography/grip_roads_100km_cells.csv", clear
tempfile grip
save `grip'

import delimited "`proj'/Data/regressors/baseline_geography/globio_msa_100km_cells.csv", clear
tempfile globio
save `globio'

* -------------------------------------------------------------------
* 2. Merge panels 1:1 on cell_id year
* -------------------------------------------------------------------

use `BOLD', clear

merge 1:1 cell_id year using `ucdp'
rename _merge _merge_ucdp

merge 1:1 cell_id year using `hansen'
rename _merge _merge_hansen

merge 1:1 cell_id year using `modis'
rename _merge _merge_modis

merge 1:1 cell_id year using `terraclimate'
rename _merge _merge_terraclimate

merge 1:1 cell_id year using `chirps'
rename _merge _merge_chirps

merge 1:1 cell_id year using `wdpa_panel'
rename _merge _merge_wdpa_panel

* -------------------------------------------------------------------
* 3. Merge static baselines m:1 on cell_id
* -------------------------------------------------------------------

merge m:1 cell_id using `resolve'
rename _merge _merge_resolve

merge m:1 cell_id using `cepf'
rename _merge _merge_cepf

merge m:1 cell_id using `wdpa_static'
rename _merge _merge_wdpa_static

merge m:1 cell_id using `grip'
rename _merge _merge_grip

merge m:1 cell_id using `globio'
rename _merge _merge_globio

* -------------------------------------------------------------------
* 4. Save
* -------------------------------------------------------------------

drop if continent=="Antarctica"
drop if cell_area_km2>10001

compress
save "`proj'/Data/analysis/BOLD_regressor_panel.dta", replace

tab _merge_ucdp
tab _merge_hansen
tab _merge_modis
tab _merge_terraclimate
tab _merge_chirps
tab _merge_wdpa_panel
tab _merge_resolve
tab _merge_cepf
tab _merge_wdpa_static
tab _merge_grip
tab _merge_globio

describe
summarize

log close
