* reg_natural_products_gbif.do
* GBIF Plantae–only NP regressions (Option B)
*
* Restricts NP outcomes to the GBIF Plantae pipeline only (98.5% of NP
* species observations). Uses GBIF plant richness as the interaction
* moderator instead of IUCN total richness.
* Companion event-study file: DoFiles/reg_event_study_natural_products_gbif.do
*
* Table GP1: NP species count (8 cols)
* Table GP2: NP share + compound diversity (8 cols)
* Table GP3: Conflict × Plant Richness interaction (8 cols)
* Table GP4: Stacked NP vs non-NP plants (4 cols)
* Table GP5: Intensive-margin benchmark (8 cols)

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/reg_natural_products_gbif.log", replace text

* ===================================================================
* 1. Import GBIF Plantae NP outcomes from chempot CSV
* ===================================================================

import delimited "`proj'/Data/processed/discovery/natural_products/cell_year_chemical_potential.csv", clear
keep if source_group == "gbif_plantae"
keep if year <= 2024
drop source_group
rename n_species_with_compounds       gp_np_species
rename n_species_sampled              gp_total_species
rename n_unique_compounds             gp_unique_compounds
rename share_np_species               gp_np_share
rename n_records                      gp_records
keep cell_id year gp_*
tempfile gp_data
save `gp_data'

* ===================================================================
* 2. Load master panel, merge, zero-fill
* ===================================================================

use "`proj'/Data/analysis/BOLD_regressor_panel.dta", clear
keep if year >= 2005 & year <= 2023

merge 1:1 cell_id year using `gp_data'
drop _merge

foreach v of varlist gp_np_species gp_total_species gp_unique_compounds gp_records {
    replace `v' = 0 if missing(`v')
}
replace gp_np_share = 0 if missing(gp_np_share)

* ===================================================================
* 3. Derived variables
* ===================================================================

gen gp_np_log = ln(gp_np_species + 1)
gen gp_compounds_log = ln(gp_unique_compounds + 1)
gen gp_np_any = (gp_np_species > 0)
gen gp_records_log = ln(gp_records + 1)

* ===================================================================
* 4. Encode, declare panel
* ===================================================================

encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)
xtset cell_id_num year

* ===================================================================
* 5. RHS variables (same as reg_spec1.do)
* ===================================================================

gen burned_share = burned_area_km2 / cell_area_km2
gen cyclone = ibtracs_any_64kt
replace cyclone = 0 if missing(cyclone)
gen earthquake = (comcat_events_m6 > 0) if !missing(comcat_events_m6)
replace earthquake = 0 if missing(earthquake)
gen log_gdp_pc = log(gdp_pcap_current_usd)
gen log_gdp_pc_sq = log_gdp_pc^2

* GBIF pre-period plant richness (standardized)
sum gbif_p_rich_log
gen gp_rich_std = (gbif_p_rich_log - r(mean)) / r(sd)

gen L1_pdsi_anomaly = L.pdsi_anomaly
gen L2_pdsi_anomaly = L2.pdsi_anomaly
gen L1_tmax_anomaly = L.tmax_anomaly
gen L2_tmax_anomaly = L2.tmax_anomaly

* ===================================================================
* 6. Summary statistics
* ===================================================================

summarize gp_np_any gp_np_species gp_np_log gp_unique_compounds ///
          gp_compounds_log gp_np_share gp_records gp_records_log ///
          gp_total_species gp_rich_std

* ===================================================================
* add_sum_rows helper
* ===================================================================

capture program drop add_sum_rows
program define add_sum_rows
    syntax , NAME(name) EXPR(string asis)
    qui lincom `expr'
    qui estadd scalar `name' = r(estimate)
    qui estadd scalar `name'_se = r(se)
    qui estadd scalar `name'_p = r(p)
    local b = r(estimate)
    local se = r(se)
    local p = r(p)
    local star ""
    if `p' < 0.01      local star "***"
    else if `p' < 0.05 local star "**"
    else if `p' < 0.10 local star "*"
    local btxt : display %9.4f `b'
    local btxt = strtrim("`btxt'")
    local setxt : display %9.4f `se'
    local setxt = strtrim("`setxt'")
    qui estadd local `name'_txt "`btxt'`star'"
    qui estadd local `name'_se_txt "(`setxt')"
end


* ===================================================================
* TABLE GP1: GBIF Plant NP species count
*   LHS: gp_np_any (extensive), gp_np_log (intensive)
*   Cell + Country×Year + Biome×Year FE (Table 3 structure)
* ===================================================================

est clear

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) Extensive — contemporaneous
eststo gp1_1: reghdfe gp_np_any conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (2) Intensive — contemporaneous
eststo gp1_2: reghdfe gp_np_log conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (3) Extensive — with lags
eststo gp1_3: reghdfe gp_np_any conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (4) Intensive — with lags
eststo gp1_4: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* --- Panel B: conflict = 1[any events] ---

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (5) Extensive — contemporaneous
eststo gp1_5: reghdfe gp_np_any conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (6) Intensive — contemporaneous
eststo gp1_6: reghdfe gp_np_log conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (7) Extensive — with lags
eststo gp1_7: reghdfe gp_np_any conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (8) Intensive — with lags
eststo gp1_8: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* --- Display Table GP1 ---

esttab gp1_*, keep(conflict L1_conflict L2_conflict ///
             forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl ///
             protected_share) ///
    order(conflict L1_conflict L2_conflict ///
          forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl ///
          protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              L1_conflict "Conflict (L1)" ///
              L2_conflict "Conflict (L2)" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              cyclone "Cyclone (64kt+)" ///
              earthquake "Earthquake (M6+)" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
              log1p_ntl "NTL (log)" ///
              protected_share "Prot. share") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." ///
                 "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table GP1: GBIF Plant NP Species Count") ///
    mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress


* ===================================================================
* TABLE GP2: NP share & compound diversity
*   LHS: gp_np_share (composition), gp_compounds_log (compound stock)
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict
gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) Share — contemporaneous
eststo gp2_1: reghdfe gp_np_share conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (2) Compounds — contemporaneous
eststo gp2_2: reghdfe gp_compounds_log conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (3) Share — with lags
eststo gp2_3: reghdfe gp_np_share conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (4) Compounds — with lags
eststo gp2_4: reghdfe gp_compounds_log conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (5) Share — contemporaneous, binary
eststo gp2_5: reghdfe gp_np_share conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (6) Compounds — contemporaneous, binary
eststo gp2_6: reghdfe gp_compounds_log conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (7) Share — with lags, binary
eststo gp2_7: reghdfe gp_np_share conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (8) Compounds — with lags, binary
eststo gp2_8: reghdfe gp_compounds_log conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

* --- Display Table GP2 ---

esttab gp2_*, keep(conflict L1_conflict L2_conflict) ///
    order(conflict L1_conflict L2_conflict) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              L1_conflict "Conflict (L1)" ///
              L2_conflict "Conflict (L2)") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." ///
                 "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table GP2: GBIF Plant NP Share and Compound Diversity") ///
    mtitles("Share" "ln(Cmpd+1)" "Share" "ln(Cmpd+1)" ///
            "Share" "ln(Cmpd+1)" "Share" "ln(Cmpd+1)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress


* ===================================================================
* TABLE GP3: Conflict × Plant Richness interaction
*   Uses GBIF pre-period plant richness (gp_rich_std)
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict
gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) Extensive — contemporaneous
eststo gp3_1: reghdfe gp_np_any conflict c.conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (2) Intensive — contemporaneous
eststo gp3_2: reghdfe gp_np_log conflict c.conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (3) Extensive — with lags
eststo gp3_3: reghdfe gp_np_any conflict L1_conflict L2_conflict ///
        c.conflict#c.gp_rich_std c.L1_conflict#c.gp_rich_std c.L2_conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.gp_rich_std + c.L1_conflict#c.gp_rich_std + c.L2_conflict#c.gp_rich_std)
}

qui {
* (4) Intensive — with lags
eststo gp3_4: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        c.conflict#c.gp_rich_std c.L1_conflict#c.gp_rich_std c.L2_conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.gp_rich_std + c.L1_conflict#c.gp_rich_std + c.L2_conflict#c.gp_rich_std)
}

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (5) Extensive — contemporaneous, binary
eststo gp3_5: reghdfe gp_np_any conflict c.conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (6) Intensive — contemporaneous, binary
eststo gp3_6: reghdfe gp_np_log conflict c.conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (7) Extensive — with lags, binary
eststo gp3_7: reghdfe gp_np_any conflict L1_conflict L2_conflict ///
        c.conflict#c.gp_rich_std c.L1_conflict#c.gp_rich_std c.L2_conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.gp_rich_std + c.L1_conflict#c.gp_rich_std + c.L2_conflict#c.gp_rich_std)
}

qui {
* (8) Intensive — with lags, binary
eststo gp3_8: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        c.conflict#c.gp_rich_std c.L1_conflict#c.gp_rich_std c.L2_conflict#c.gp_rich_std ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.gp_rich_std + c.L1_conflict#c.gp_rich_std + c.L2_conflict#c.gp_rich_std)
}

* --- Display Table GP3 ---

esttab gp3_*, keep(conflict c.conflict#c.gp_rich_std ///
             L1_conflict c.L1_conflict#c.gp_rich_std ///
             L2_conflict c.L2_conflict#c.gp_rich_std) ///
    order(conflict c.conflict#c.gp_rich_std ///
          L1_conflict c.L1_conflict#c.gp_rich_std ///
          L2_conflict c.L2_conflict#c.gp_rich_std) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              "c.conflict#c.gp_rich_std" "Conflict x Plant Rich." ///
              L1_conflict "Conflict (L1)" ///
              "c.L1_conflict#c.gp_rich_std" "Conflict (L1) x Plant Rich." ///
              L2_conflict "Conflict (L2)" ///
              "c.L2_conflict#c.gp_rich_std" "Conflict (L2) x Plant Rich.") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          conflict_rich_sum_txt conflict_rich_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum conflict x rich. L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." ///
                 "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table GP3: Conflict x GBIF Plant Richness Interaction") ///
    mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress


* ===================================================================
* TABLE GP4: Stacked NP vs non-NP plants — direct differential test
*   Restrict to cell-years with GBIF plant sampling
*   Each row becomes 2: NP plant species, non-NP plant species
*   Key coefficient: conflict × is_np
* ===================================================================

preserve

drop conflict L1_conflict L2_conflict

keep if gp_total_species > 0

gen gp_nonnp = gp_total_species - gp_np_species
replace gp_nonnp = 0 if gp_nonnp < 0
gen gp_nonnp_log = ln(gp_nonnp + 1)

* Both conflict measures before stacking
gen conflict_cont = log(1 + ucdp_events_all)
gen L1_conflict_cont = L.conflict_cont
gen L2_conflict_cont = L2.conflict_cont
gen conflict_bin = ucdp_any_all
gen L1_conflict_bin = L.conflict_bin
gen L2_conflict_bin = L2.conflict_bin

expand 2, gen(is_np)

gen y_log = cond(is_np==1, gp_np_log, gp_nonnp_log)

* Conflict × NP interactions
gen conflict_cont_np = conflict_cont * is_np
gen L1_conflict_cont_np = L1_conflict_cont * is_np
gen L2_conflict_cont_np = L2_conflict_cont * is_np
gen conflict_bin_np = conflict_bin * is_np
gen L1_conflict_bin_np = L1_conflict_bin * is_np
gen L2_conflict_bin_np = L2_conflict_bin * is_np

* Control × NP interactions
foreach v of varlist forest_loss_share burned_share cyclone earthquake ///
    pdsi_anomaly tmax_anomaly log1p_ntl ///
    L1_pdsi_anomaly L2_pdsi_anomaly L1_tmax_anomaly L2_tmax_anomaly {
    gen `v'_np = `v' * is_np
}
gen protected_share_np = protected_share * is_np
gen log_gdp_prot = log_gdp_pc * protected_share
gen log_gdp_prot_np = log_gdp_prot * is_np
gen log_gdpsq_prot = log_gdp_pc_sq * protected_share
gen log_gdpsq_prot_np = log_gdpsq_prot * is_np

est clear

qui {
* (1) Contemporaneous, log(1+events)
eststo gp4_1: reghdfe y_log conflict_cont conflict_cont_np ///
        forest_loss_share forest_loss_share_np ///
        burned_share burned_share_np cyclone cyclone_np ///
        earthquake earthquake_np pdsi_anomaly pdsi_anomaly_np ///
        tmax_anomaly tmax_anomaly_np log1p_ntl log1p_ntl_np ///
        protected_share protected_share_np ///
        log_gdp_prot log_gdp_prot_np log_gdpsq_prot log_gdpsq_prot_np ///
        c.road_density_km_per_km2#i.year#i.is_np, ///
        absorb(cell_id_num#is_np country_num#year#is_np i.resolve_biome_num#i.year#is_np) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell_type "\checkmark"
estadd local fe_cy_type "\checkmark"
estadd local fe_biome_yr_type "\checkmark"
estadd local road_yr_type "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (2) With lags, log(1+events)
eststo gp4_2: reghdfe y_log conflict_cont conflict_cont_np ///
        L1_conflict_cont L1_conflict_cont_np ///
        L2_conflict_cont L2_conflict_cont_np ///
        forest_loss_share forest_loss_share_np ///
        burned_share burned_share_np cyclone cyclone_np ///
        earthquake earthquake_np ///
        pdsi_anomaly pdsi_anomaly_np ///
        L1_pdsi_anomaly L1_pdsi_anomaly_np ///
        L2_pdsi_anomaly L2_pdsi_anomaly_np ///
        tmax_anomaly tmax_anomaly_np ///
        L1_tmax_anomaly L1_tmax_anomaly_np ///
        L2_tmax_anomaly L2_tmax_anomaly_np ///
        log1p_ntl log1p_ntl_np ///
        protected_share protected_share_np ///
        log_gdp_prot log_gdp_prot_np log_gdpsq_prot log_gdpsq_prot_np ///
        c.road_density_km_per_km2#i.year#i.is_np, ///
        absorb(cell_id_num#is_np country_num#year#is_np i.resolve_biome_num#i.year#is_np) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell_type "\checkmark"
estadd local fe_cy_type "\checkmark"
estadd local fe_biome_yr_type "\checkmark"
estadd local road_yr_type "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict_cont + L1_conflict_cont + L2_conflict_cont)
add_sum_rows, name(conflict_np_sum) expr(conflict_cont_np + L1_conflict_cont_np + L2_conflict_cont_np)
}

qui {
* (3) Contemporaneous, 1[events>0]
eststo gp4_3: reghdfe y_log conflict_bin conflict_bin_np ///
        forest_loss_share forest_loss_share_np ///
        burned_share burned_share_np cyclone cyclone_np ///
        earthquake earthquake_np pdsi_anomaly pdsi_anomaly_np ///
        tmax_anomaly tmax_anomaly_np log1p_ntl log1p_ntl_np ///
        protected_share protected_share_np ///
        log_gdp_prot log_gdp_prot_np log_gdpsq_prot log_gdpsq_prot_np ///
        c.road_density_km_per_km2#i.year#i.is_np, ///
        absorb(cell_id_num#is_np country_num#year#is_np i.resolve_biome_num#i.year#is_np) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell_type "\checkmark"
estadd local fe_cy_type "\checkmark"
estadd local fe_biome_yr_type "\checkmark"
estadd local road_yr_type "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (4) With lags, 1[events>0]
eststo gp4_4: reghdfe y_log conflict_bin conflict_bin_np ///
        L1_conflict_bin L1_conflict_bin_np ///
        L2_conflict_bin L2_conflict_bin_np ///
        forest_loss_share forest_loss_share_np ///
        burned_share burned_share_np cyclone cyclone_np ///
        earthquake earthquake_np ///
        pdsi_anomaly pdsi_anomaly_np ///
        L1_pdsi_anomaly L1_pdsi_anomaly_np ///
        L2_pdsi_anomaly L2_pdsi_anomaly_np ///
        tmax_anomaly tmax_anomaly_np ///
        L1_tmax_anomaly L1_tmax_anomaly_np ///
        L2_tmax_anomaly L2_tmax_anomaly_np ///
        log1p_ntl log1p_ntl_np ///
        protected_share protected_share_np ///
        log_gdp_prot log_gdp_prot_np log_gdpsq_prot log_gdpsq_prot_np ///
        c.road_density_km_per_km2#i.year#i.is_np, ///
        absorb(cell_id_num#is_np country_num#year#is_np i.resolve_biome_num#i.year#is_np) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell_type "\checkmark"
estadd local fe_cy_type "\checkmark"
estadd local fe_biome_yr_type "\checkmark"
estadd local road_yr_type "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict_bin + L1_conflict_bin + L2_conflict_bin)
add_sum_rows, name(conflict_np_sum) expr(conflict_bin_np + L1_conflict_bin_np + L2_conflict_bin_np)
}

* --- Display Table GP4 ---

esttab gp4_*, keep(conflict_cont conflict_cont_np ///
             L1_conflict_cont L1_conflict_cont_np ///
             L2_conflict_cont L2_conflict_cont_np ///
             conflict_bin conflict_bin_np ///
             L1_conflict_bin L1_conflict_bin_np ///
             L2_conflict_bin L2_conflict_bin_np) ///
    order(conflict_cont conflict_cont_np ///
          L1_conflict_cont L1_conflict_cont_np ///
          L2_conflict_cont L2_conflict_cont_np ///
          conflict_bin conflict_bin_np ///
          L1_conflict_bin L1_conflict_bin_np ///
          L2_conflict_bin L2_conflict_bin_np) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict_cont "Conflict" ///
              conflict_cont_np "Conflict x NP" ///
              L1_conflict_cont "Conflict (L1)" ///
              L1_conflict_cont_np "Conflict (L1) x NP" ///
              L2_conflict_cont "Conflict (L2)" ///
              L2_conflict_cont_np "Conflict (L2) x NP" ///
              conflict_bin "Conflict" ///
              conflict_bin_np "Conflict x NP" ///
              L1_conflict_bin "Conflict (L1)" ///
              L1_conflict_bin_np "Conflict (L1) x NP" ///
              L2_conflict_bin "Conflict (L2)" ///
              L2_conflict_bin_np "Conflict (L2) x NP") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          conflict_np_sum_txt conflict_np_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell_type fe_cy_type fe_biome_yr_type road_yr_type, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum conflict x NP L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." ///
                 "Cell x Type FE" "Country x Year x Type FE" ///
                 "Biome x Year x Type FE" "Road dens. x Year x Type") ///
          fmt(%s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table GP4: Stacked NP vs Non-NP Plants — Direct Differential Test") ///
    mtitles("Contemp." "With Lags" "Contemp." "With Lags") ///
    mgroups("log(1+events)" "1[events>0]", ///
            pattern(1 0 1 0)) ///
    compress

restore


* ===================================================================
* TABLE GP5: Intensive-margin benchmark — sampling decomposition
*   All cols use log(1+events) conflict, paired as {contemp, lags}
*   Cols 1-2:  gp_np_log — full sample (baseline)
*   Cols 3-4:  gp_np_log — if gp_records > 0 (no effort control)
*   Cols 5-6:  gp_np_log + GBIF plant effort control — full sample
*   Cols 7-8:  gp_np_log + effort control — if gp_records > 0
*   Cols 9-10: gp_np_share — if gp_records > 0
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict
gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* --- Col 1: gp_np_log, contemporaneous, full sample ---
eststo gp5_1: reghdfe gp_np_log conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "None"
estadd local sample_restr "Full"
estadd local conflict_measure "log(1+events)"
}

qui {
* --- Col 2: gp_np_log, with lags, full sample ---
eststo gp5_2: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "None"
estadd local sample_restr "Full"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* --- Col 3: gp_np_log, contemporaneous, if gp_records > 0, no effort control ---
eststo gp5_3: reghdfe gp_np_log conflict forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if gp_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "None"
estadd local sample_restr "GBIF rec>0"
estadd local conflict_measure "log(1+events)"
}

qui {
* --- Col 4: gp_np_log, with lags, if gp_records > 0, no effort control ---
eststo gp5_4: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if gp_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "None"
estadd local sample_restr "GBIF rec>0"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* --- Col 5: gp_np_log + GBIF effort, contemporaneous, full ---
eststo gp5_5: reghdfe gp_np_log conflict gp_records_log ///
        forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "ln(1+GBIF rec)"
estadd local sample_restr "Full"
estadd local conflict_measure "log(1+events)"
}

qui {
* --- Col 6: gp_np_log + GBIF effort, with lags, full ---
eststo gp5_6: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        gp_records_log ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "ln(1+GBIF rec)"
estadd local sample_restr "Full"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* --- Col 7: gp_np_log + effort, contemp., if gp_records > 0 ---
eststo gp5_7: reghdfe gp_np_log conflict gp_records_log ///
        forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if gp_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "ln(1+GBIF rec)"
estadd local sample_restr "GBIF rec>0"
estadd local conflict_measure "log(1+events)"
}

qui {
* --- Col 8: gp_np_log + effort, lags, if gp_records > 0 ---
eststo gp5_8: reghdfe gp_np_log conflict L1_conflict L2_conflict ///
        gp_records_log ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if gp_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "ln(1+GBIF rec)"
estadd local sample_restr "GBIF rec>0"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* --- Col 9: gp_np_share, contemporaneous, if gp_records > 0 ---
eststo gp5_9: reghdfe gp_np_share conflict gp_records_log ///
        forest_loss_share ///
        burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if gp_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "ln(1+GBIF rec)"
estadd local sample_restr "GBIF rec>0"
estadd local conflict_measure "log(1+events)"
}

qui {
* --- Col 10: gp_np_share, with lags, if gp_records > 0 ---
eststo gp5_10: reghdfe gp_np_share conflict L1_conflict L2_conflict ///
        gp_records_log ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if gp_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local sample_ctrl "ln(1+GBIF rec)"
estadd local sample_restr "GBIF rec>0"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

* --- Display Table GP5 ---

esttab gp5_*, keep(conflict gp_records_log ///
             L1_conflict L2_conflict) ///
    order(conflict gp_records_log ///
          L1_conflict L2_conflict) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict (log 1+events)" ///
              gp_records_log "GBIF plant effort (log)" ///
              L1_conflict "Conflict (L1)" ///
              L2_conflict "Conflict (L2)") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          conflict_measure sample_ctrl sample_restr ///
          ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Conflict measure" "Effort control" "Sample restriction" ///
                 "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." ///
                 "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s ///
              %s %s %s ///
              %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table GP5: Intensive-Margin Benchmark — GBIF Plant Sampling Decomposition") ///
    mtitles("Contemp." "Lags" "Contemp." "Lags" "Contemp." "Lags" "Contemp." "Lags" "Contemp." "Lags") ///
    mgroups("ln(NP+1)" "ln(NP+1), rec>0" "ln(NP+1) | effort" "ln(NP+1) | effort, rec>0" "NP share, rec>0", ///
            pattern(1 0 1 0 1 0 1 0 1 0)) ///
    compress

log close
