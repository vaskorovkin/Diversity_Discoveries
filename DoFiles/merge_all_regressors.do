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

import delimited "`proj'/Data/processed/bold/collectors/bold_foreign_collecting_cell_year_panel.csv", clear
tempfile foreign_collecting
save `foreign_collecting'

* --- Chemical-potential panel (Option B) ---
local have_chempot 0
capture confirm file "`proj'/Data/processed/discovery/natural_products/cell_year_chemical_potential.csv"
if _rc==0 {
    import delimited "`proj'/Data/processed/discovery/natural_products/cell_year_chemical_potential.csv", clear
    keep if year<=2024
    * keep combined rows as primary; bold/gbif as source decomposition
    keep if source_group=="combined"
    drop source_group
    rename n_species_sampled              np_species_sampled
    rename n_species_with_compounds       np_species_w_comp
    rename n_compounds_total              np_compounds_total
    rename n_unique_compounds             np_unique_compounds
    rename share_np_species               np_share
    rename n_animalia_with_compounds      np_animalia
    rename n_plantae_with_compounds       np_plantae
    rename n_fungi_with_compounds         np_fungi
    rename n_species_with_compounds_strict     np_sp_strict
    rename n_species_with_compounds_no_fuzz   np_sp_no_fuzzy
    rename n_species_with_compounds_no_bin    np_sp_no_bin
    rename n_species_with_compounds_named_o   np_sp_named_only
    rename n_records                       np_records
    * log transforms
    gen np_species_w_comp_log = ln(np_species_w_comp + 1)
    gen np_unique_compounds_log = ln(np_unique_compounds + 1)
    gen np_species_w_comp_any = (np_species_w_comp > 0)
    tempfile chempot
    save `chempot'
    local have_chempot 1

    * also save per-source decomposition
    import delimited "`proj'/Data/processed/discovery/natural_products/cell_year_chemical_potential.csv", clear
    keep if year<=2024
    keep if source_group=="bold"
    drop source_group
    rename n_species_with_compounds np_bold_sp_w_comp
    rename n_species_sampled        np_bold_sp_sampled
    rename share_np_species         np_bold_share
    keep cell_id year np_bold_sp_w_comp np_bold_sp_sampled np_bold_share
    tempfile chempot_bold
    save `chempot_bold'

    import delimited "`proj'/Data/processed/discovery/natural_products/cell_year_chemical_potential.csv", clear
    keep if year<=2024
    keep if source_group=="gbif_plantae"
    drop source_group
    rename n_species_with_compounds np_gbif_sp_w_comp
    rename n_species_sampled        np_gbif_sp_sampled
    rename share_np_species         np_gbif_share
    keep cell_id year np_gbif_sp_w_comp np_gbif_sp_sampled np_gbif_share
    tempfile chempot_gbif
    save `chempot_gbif'
}

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

local have_gbif_preperiod_richness 0
capture confirm file "`proj'/Data/regressors/plants/gbif_plantae_preperiod_richness_1999_2004.csv"
if _rc==0 {
    import delimited "`proj'/Data/regressors/plants/gbif_plantae_preperiod_richness_1999_2004.csv", clear
    keep cell_id ///
        gbif_plant_richness_base gbif_plant_genus_richness_base ///
        gbif_plant_richness_base_any gbif_plant_genus_richness_base_a ///
        gbif_plant_richness_base_log1p gbif_plant_genus_richness_base_l ///
        gbif_plant_richness_base_z gbif_plant_genus_richness_base_z
    rename gbif_plant_richness_base gbif_p_rich_base
    rename gbif_plant_genus_richness_base gbif_p_genrich_base
    rename gbif_plant_richness_base_any gbif_p_rich_any
    rename gbif_plant_genus_richness_base_a gbif_p_genrich_any
    rename gbif_plant_richness_base_log1p gbif_p_rich_log
    rename gbif_plant_genus_richness_base_l gbif_p_genrich_log
    rename gbif_plant_richness_base_z gbif_p_rich_z
    rename gbif_plant_genus_richness_base_z gbif_p_genrich_z
    tempfile gbif_preperiod_richness
    save `gbif_preperiod_richness'
    local have_gbif_preperiod_richness 1
}

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

merge 1:1 cell_id year using `foreign_collecting'
rename _merge _merge_foreign_collecting

if `have_gbif_plantae' == 1 {
    merge 1:1 cell_id year using `gbif_plantae'
    rename _merge _merge_gbif_plantae
}

if `have_chempot' == 1 {
    merge 1:1 cell_id year using `chempot'
    rename _merge _merge_chempot
    merge 1:1 cell_id year using `chempot_bold'
    rename _merge _merge_chempot_bold
    merge 1:1 cell_id year using `chempot_gbif'
    rename _merge _merge_chempot_gbif

    * Zero-fill NP vars for master-only cell-years (no sampling → no NP)
    foreach v of varlist np_species_w_comp np_unique_compounds ///
            np_sp_strict np_sp_no_fuzzy np_sp_no_bin np_sp_named_only ///
            np_animalia np_plantae np_fungi np_compounds_total np_records ///
            np_species_sampled {
        replace `v' = 0 if missing(`v')
    }
    replace np_share = 0 if missing(np_share)
    replace np_species_w_comp_log = 0 if missing(np_species_w_comp_log)
    replace np_unique_compounds_log = 0 if missing(np_unique_compounds_log)
    replace np_species_w_comp_any = 0 if missing(np_species_w_comp_any)
    foreach v of varlist np_bold_sp_w_comp np_bold_sp_sampled np_bold_share ///
            np_gbif_sp_w_comp np_gbif_sp_sampled np_gbif_share {
        capture replace `v' = 0 if missing(`v')
    }
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

if `have_gbif_preperiod_richness' == 1 {
    merge m:1 cell_id using `gbif_preperiod_richness'
    rename _merge _merge_gbif_preperiod_richness
}

* --- Country-year regressors (iso_a3 × year; requires iso_a3 from RESOLVE) ---

merge m:1 iso_a3 year using `wbgdp'
rename _merge _merge_wbgdp

* -------------------------------------------------------------------
* 4. Save
* -------------------------------------------------------------------

drop if continent=="Antarctica"
drop if cell_area_km2>10001

* --- Derived foreign collecting shares ---
gen fc_scored = domestic_score_sum + regional_score_sum + distant_score_sum
gen foreign_share = (regional_score_sum + distant_score_sum) / fc_scored ///
    if fc_scored > 0
gen regional_share = regional_score_sum / fc_scored if fc_scored > 0
gen distant_share = distant_score_sum / fc_scored if fc_scored > 0
gen domestic_share = domestic_score_sum / fc_scored if fc_scored > 0
gen foreign_records = records_foreign_regional + records_foreign_distant
gen collab_share = records_collab / records_classified if records_classified > 0

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
capture confirm variable _merge_gbif_preperiod_richness
if _rc==0 tab _merge_gbif_preperiod_richness
tab _merge_foreign_collecting
capture confirm variable _merge_gbif_plantae
if _rc==0 tab _merge_gbif_plantae
capture confirm variable _merge_chempot
if _rc==0 {
    tab _merge_chempot
    tab _merge_chempot_bold
    tab _merge_chempot_gbif
}

describe
summarize

log close
