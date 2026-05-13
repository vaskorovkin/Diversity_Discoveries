* build_tests_spatial_time_panel_50km_year.do
* Build the 50 km yearly experiment analysis panel used to test whether
* finer spatial aggregation improves the baseline reg_spec1 / reg_event_study
* designs without touching the canonical 100 km yearly panel.

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/build_tests_spatial_time_panel_50km_year.log", replace text

local root_processed "`proj'/Data/processed/tests_spatial_time"
local root_regress   "`proj'/Data/regressors/tests_spatial_time"
local root_analysis  "`proj'/Data/analysis/tests_spatial_time"

capture mkdir "`proj'/Data/analysis"
capture mkdir "`root_analysis'"

* -------------------------------------------------------------------
* 1. Import required CSVs as tempfiles
* -------------------------------------------------------------------

capture confirm file "`root_processed'/bold/bold_grid50_cell_year_panel_collection_2005_2025.csv"
if _rc {
    di as error "Missing BOLD 50km yearly panel: `root_processed'/bold/bold_grid50_cell_year_panel_collection_2005_2025.csv"
    error 601
}
import delimited "`root_processed'/bold/bold_grid50_cell_year_panel_collection_2005_2025.csv", clear
keep if year <= 2024
tempfile BOLD
save `BOLD'

capture confirm file "`root_regress'/ucdp/ucdp_ged_50km_cell_year_2005_2024.csv"
if _rc {
    di as error "Missing UCDP 50km yearly panel."
    error 601
}
import delimited "`root_regress'/ucdp/ucdp_ged_50km_cell_year_2005_2024.csv", clear
tempfile ucdp
save `ucdp'

capture confirm file "`root_regress'/hansen/hansen_forest_loss_50km_panel.csv"
if _rc {
    di as error "Missing Hansen 50km yearly panel."
    error 601
}
import delimited "`root_regress'/hansen/hansen_forest_loss_50km_panel.csv", clear
tempfile hansen
save `hansen'

capture confirm file "`root_regress'/modis/modis_burned_area_50km_panel.csv"
if _rc {
    di as error "Missing MODIS 50km yearly panel."
    error 601
}
import delimited "`root_regress'/modis/modis_burned_area_50km_panel.csv", clear
tempfile modis
save `modis'

capture confirm file "`root_regress'/terraclimate/terraclimate_50km_panel.csv"
if _rc {
    di as error "Missing TerraClimate 50km yearly panel."
    error 601
}
import delimited "`root_regress'/terraclimate/terraclimate_50km_panel.csv", clear
tempfile terraclimate
save `terraclimate'

capture confirm file "`root_regress'/chirps/chirps_50km_panel.csv"
if _rc {
    di as error "Missing CHIRPS 50km yearly panel."
    error 601
}
import delimited "`root_regress'/chirps/chirps_50km_panel.csv", clear
tempfile chirps
save `chirps'

capture confirm file "`root_regress'/nightlights/nightlights_50km_panel.csv"
if _rc {
    di as error "Missing nightlights 50km yearly panel."
    error 601
}
import delimited "`root_regress'/nightlights/nightlights_50km_panel.csv", clear
tempfile ntl
save `ntl'

capture confirm file "`root_regress'/acled/acled_50km_cell_year_2005_2024.csv"
if _rc {
    di as error "Missing ACLED 50km yearly panel."
    error 601
}
import delimited "`root_regress'/acled/acled_50km_cell_year_2005_2024.csv", clear
tempfile acled
save `acled'

capture confirm file "`root_regress'/ibtracs/ibtracs_50km_cell_year_2005_2025.csv"
if _rc {
    di as error "Missing IBTrACS 50km yearly panel."
    error 601
}
import delimited "`root_regress'/ibtracs/ibtracs_50km_cell_year_2005_2025.csv", clear
keep if year <= 2024
tempfile ibtracs
save `ibtracs'

capture confirm file "`root_regress'/comcat/comcat_50km_cell_year_2005_2025.csv"
if _rc {
    di as error "Missing ComCat 50km yearly panel."
    error 601
}
import delimited "`root_regress'/comcat/comcat_50km_cell_year_2005_2025.csv", clear
keep if year <= 2024
tempfile comcat
save `comcat'

capture confirm file "`root_regress'/baseline_geography/resolve_ecoregions_50km_cells.csv"
if _rc {
    di as error "Missing RESOLVE 50km cells."
    error 601
}
import delimited "`root_regress'/baseline_geography/resolve_ecoregions_50km_cells.csv", clear
keep cell_id resolve_eco_id resolve_eco_name resolve_biome_num resolve_biome_name ///
    resolve_realm resolve_eco_biome resolve_nnh resolve_nnh_name resolve_license ///
    resolve_matched resolve_rock_ice
tempfile resolve
save `resolve'

capture confirm file "`root_regress'/wdpa/wdpa_protected_panel_50km.csv"
if _rc {
    di as error "Missing time-varying WDPA protected-area 50km panel."
    error 601
}
import delimited "`root_regress'/wdpa/wdpa_protected_panel_50km.csv", clear
keep cell_id year cell_area_km2 protected_area_km2 protected_share ///
    any_protected new_protection_km2
tempfile wdpa_panel
save `wdpa_panel'

capture confirm file "`root_regress'/baseline_geography/grip_roads_50km_cells.csv"
if _rc {
    di as error "Missing GRIP roads 50km cells."
    error 601
}
import delimited "`root_regress'/baseline_geography/grip_roads_50km_cells.csv", clear
keep cell_id road_density_m_per_km2 road_density_km_per_km2 any_road log_road_density
tempfile grip
save `grip'

capture confirm file "`root_regress'/baseline_geography/globio_msa_50km_cells.csv"
if _rc {
    di as error "Missing GLOBIO MSA 50km cells."
    error 601
}
import delimited "`root_regress'/baseline_geography/globio_msa_50km_cells.csv", clear
tempfile globio
save `globio'

capture confirm file "`root_regress'/baseline_geography/species_richness_50km_cells.csv"
if _rc {
    di as error "Missing species richness 50km cells."
    error 601
}
import delimited "`root_regress'/baseline_geography/species_richness_50km_cells.csv", clear
tempfile richness
save `richness'

capture confirm file "`proj'/Data/regressors/worldbank/worldbank_gdp_pcap_panel.csv"
if _rc {
    di as error "Missing World Bank GDP panel."
    error 601
}
import delimited "`proj'/Data/regressors/worldbank/worldbank_gdp_pcap_panel.csv", clear
tempfile wbgdp
save `wbgdp'

* -------------------------------------------------------------------
* 2. Merge panel datasets 1:1 on cell_id year
* -------------------------------------------------------------------

use `BOLD', clear

merge 1:1 cell_id year using `ucdp', keep(1 3)
rename _merge _merge_ucdp

merge 1:1 cell_id year using `hansen', keep(1 3)
rename _merge _merge_hansen

merge 1:1 cell_id year using `modis', keep(1 3)
rename _merge _merge_modis

merge 1:1 cell_id year using `terraclimate', keep(1 3)
rename _merge _merge_terraclimate

merge 1:1 cell_id year using `chirps', keep(1 3)
rename _merge _merge_chirps

merge 1:1 cell_id year using `wdpa_panel', keep(1 3)
rename _merge _merge_wdpa_panel

merge 1:1 cell_id year using `ntl', keep(1 3)
rename _merge _merge_ntl

merge 1:1 cell_id year using `acled', keep(1 3)
rename _merge _merge_acled

merge 1:1 cell_id year using `ibtracs', keep(1 3)
rename _merge _merge_ibtracs

merge 1:1 cell_id year using `comcat', keep(1 3)
rename _merge _merge_comcat

* -------------------------------------------------------------------
* 3. Merge static datasets m:1 on cell_id and country-year data on iso_a3 year
* -------------------------------------------------------------------

merge m:1 cell_id using `resolve', keep(1 3)
rename _merge _merge_resolve

merge m:1 cell_id using `grip', keep(1 3)
rename _merge _merge_grip

merge m:1 cell_id using `globio', keep(1 3)
rename _merge _merge_globio

merge m:1 cell_id using `richness', keep(1 3)
rename _merge _merge_richness

merge m:1 iso_a3 year using `wbgdp', keep(1 3)
rename _merge _merge_wbgdp

* -------------------------------------------------------------------
* 4. Finalize and save
* -------------------------------------------------------------------

drop if continent == "Antarctica"
compress
save "`root_analysis'/BOLD_regressor_panel_50km_year.dta", replace

tab _merge_ucdp
tab _merge_hansen
tab _merge_modis
tab _merge_terraclimate
tab _merge_chirps
tab _merge_wdpa_panel
tab _merge_ntl
tab _merge_acled
tab _merge_ibtracs
tab _merge_comcat
tab _merge_resolve
tab _merge_grip
tab _merge_globio
tab _merge_richness
tab _merge_wbgdp

describe
summarize

log close
