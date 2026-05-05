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
import delimited "`proj'/Data/processed/bold/bold_grid100_cell_year_panel_collection_2005_2025.csv", clear
keep if year<=2024
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

import delimited "`proj'/Data/regressors/worldbank/worldbank_gdp_pcap_panel.csv", clear
tempfile wbgdp
save `wbgdp'

import delimited "`proj'/Data/regressors/nightlights/nightlights_100km_panel.csv", clear
tempfile ntl
save `ntl'

import delimited "`proj'/Data/regressors/acled/acled_100km_cell_year_2005_2024.csv", clear
tempfile acled
save `acled'

import delimited "`proj'/Data/regressors/ibtracs/ibtracs_100km_cell_year_2005_2025.csv", clear
keep if year<=2024
tempfile ibtracs
save `ibtracs'

import delimited "`proj'/Data/regressors/comcat/comcat_100km_cell_year_2005_2025.csv", clear
keep if year<=2024
tempfile comcat
save `comcat'

import delimited "`proj'/Data/processed/bold/collectors/bold_parachute_cell_year_panel.csv", clear
tempfile parachute
save `parachute'

local have_gbif_plantae 0
capture confirm file "`proj'/Data/processed/gbif/plantae/gbif_plantae_preserved_material_cell_year_panel_2005_2025.csv"
if _rc==0 {
    import delimited "`proj'/Data/processed/gbif/plantae/gbif_plantae_preserved_material_cell_year_panel_2005_2025.csv", clear
    keep if year<=2024
    keep cell_id year total_records plant_records preserved_specimen_records material_sample_records ///
        any_total_records any_plant_records any_preserved_specimen_records any_material_sample_records ///
        log1p_total_records log1p_plant_records log1p_preserved_specimen_records log1p_material_sample_records
    rename total_records gbif_p_total
    rename plant_records gbif_p_plant
    rename preserved_specimen_records gbif_p_preserved
    rename material_sample_records gbif_p_material
    rename any_total_records gbif_p_any_total
    rename any_plant_records gbif_p_any_plant
    rename any_preserved_specimen_records gbif_p_any_preserved
    rename any_material_sample_records gbif_p_any_material
    rename log1p_total_records gbif_p_log_total
    rename log1p_plant_records gbif_p_log_plant
    rename log1p_preserved_specimen_records gbif_p_log_preserved
    rename log1p_material_sample_records gbif_p_log_material
    tempfile gbif_plantae
    save `gbif_plantae'
    local have_gbif_plantae 1
}

* --- Static baselines: species richness ---

import delimited "`proj'/Data/regressors/baseline_geography/species_richness_100km_cells.csv", clear
tempfile richness
save `richness'

import delimited "`proj'/Data/regressors/baseline_geography/species_richness_birds_100km_cells.csv", clear
tempfile richness_birds
save `richness_birds'

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

merge 1:1 cell_id year using `ntl'
rename _merge _merge_ntl

merge 1:1 cell_id year using `acled'
rename _merge _merge_acled

merge 1:1 cell_id year using `ibtracs'
rename _merge _merge_ibtracs

merge 1:1 cell_id year using `comcat'
rename _merge _merge_comcat

merge 1:1 cell_id year using `parachute'
rename _merge _merge_parachute

if `have_gbif_plantae' == 1 {
    merge 1:1 cell_id year using `gbif_plantae'
    rename _merge _merge_gbif_plantae
}

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

merge m:1 cell_id using `richness'
rename _merge _merge_richness

merge m:1 cell_id using `richness_birds'
rename _merge _merge_richness_birds

* --- Country-year regressors (iso_a3 × year; requires iso_a3 from RESOLVE) ---

merge m:1 iso_a3 year using `wbgdp'
rename _merge _merge_wbgdp

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
tab _merge_wbgdp
tab _merge_ntl
tab _merge_acled
tab _merge_ibtracs
tab _merge_comcat
tab _merge_richness
tab _merge_richness_birds
tab _merge_parachute
capture confirm variable _merge_gbif_plantae
if _rc==0 tab _merge_gbif_plantae

describe
summarize

log close
