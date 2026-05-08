* reg_natural_products.do
* Conflict → Natural-product-relevant sampling (Option B)
* Table NP1: NP species count — Cell + Country×Year + Biome×Year FE
* Table NP2: NP share & compound diversity — same FE
* Table NP3: Conflict × Species Richness interaction with NP LHS
* Table NP4: Source decomposition (BOLD vs GBIF)
* Table NP5: Name-resolution robustness

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/reg_natural_products.log", replace text

use "`proj'/Data/analysis/BOLD_regressor_panel.dta", clear

* -------------------------------------------------------------------
* 1. Sample restriction
* -------------------------------------------------------------------

keep if year >= 2005 & year <= 2023

* -------------------------------------------------------------------
* 2. Encode cell_id, country; declare panel
* -------------------------------------------------------------------

encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)
xtset cell_id_num year

* -------------------------------------------------------------------
* 3. Construct RHS variables (same as reg_spec1.do)
* -------------------------------------------------------------------

gen burned_share = burned_area_km2 / cell_area_km2
gen cyclone = ibtracs_any_64kt
replace cyclone = 0 if missing(cyclone)
gen earthquake = (comcat_events_m6 > 0) if !missing(comcat_events_m6)
replace earthquake = 0 if missing(earthquake)
gen log_gdp_pc = log(gdp_pcap_current_usd)
gen log_gdp_pc_sq = log_gdp_pc^2

sum richness_total
gen richness_std = (richness_total - r(mean)) / r(sd)

gen L1_pdsi_anomaly = L.pdsi_anomaly
gen L2_pdsi_anomaly = L2.pdsi_anomaly
gen L1_tmax_anomaly = L.tmax_anomaly
gen L2_tmax_anomaly = L2.tmax_anomaly

* -------------------------------------------------------------------
* 4. Construct NP-specific derived variables
* -------------------------------------------------------------------

gen np_sp_strict_log = ln(np_sp_strict + 1)
gen np_sp_no_fuzzy_log = ln(np_sp_no_fuzzy + 1)
gen np_sp_no_bin_log = ln(np_sp_no_bin + 1)
gen np_sp_named_only_log = ln(np_sp_named_only + 1)

gen np_bold_sp_w_comp_log = ln(np_bold_sp_w_comp + 1)
gen np_gbif_sp_w_comp_log = ln(np_gbif_sp_w_comp + 1)

* -------------------------------------------------------------------
* 5. Summary statistics — NP outcomes
* -------------------------------------------------------------------

summarize np_species_w_comp_any np_species_w_comp np_species_w_comp_log ///
          np_unique_compounds np_unique_compounds_log np_share ///
          np_plantae np_fungi np_animalia ///
          np_bold_sp_w_comp np_gbif_sp_w_comp ///
          np_sp_strict np_sp_no_fuzzy np_sp_no_bin np_sp_named_only

* -------------------------------------------------------------------
* add_sum_rows helper
* -------------------------------------------------------------------

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
* TABLE NP1: NP species count — Cell + Country×Year + Biome×Year FE
*   LHS: np_species_w_comp_any (extensive), np_species_w_comp_log (intensive)
*   Mirrors reg_spec1.do Table 3
* ===================================================================

est clear

* -------------------------------------------------------------------
* Panel A: conflict = log(1 + events)
* -------------------------------------------------------------------

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) Extensive — contemporaneous
eststo np1_1: reghdfe np_species_w_comp_any conflict forest_loss_share ///
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
eststo np1_2: reghdfe np_species_w_comp_log conflict forest_loss_share ///
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
eststo np1_3: reghdfe np_species_w_comp_any conflict L1_conflict L2_conflict ///
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
eststo np1_4: reghdfe np_species_w_comp_log conflict L1_conflict L2_conflict ///
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

* -------------------------------------------------------------------
* Panel B: conflict = 1[any events]
* -------------------------------------------------------------------

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

qui {
* (5) Extensive — contemporaneous
eststo np1_5: reghdfe np_species_w_comp_any conflict forest_loss_share ///
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
eststo np1_6: reghdfe np_species_w_comp_log conflict forest_loss_share ///
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
eststo np1_7: reghdfe np_species_w_comp_any conflict L1_conflict L2_conflict ///
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
eststo np1_8: reghdfe np_species_w_comp_log conflict L1_conflict L2_conflict ///
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

* -------------------------------------------------------------------
* Display Table NP1
* -------------------------------------------------------------------

esttab np1_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              cyclone "Cyclone (64kt+)" ///
              earthquake "Earthquake (M6+)" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
              log1p_ntl "NTL (log)" ///
              protected_share "Prot. share" ///
              c.log_gdp_pc#c.protected_share "ln(GDP pc) x Prot." ///
              c.log_gdp_pc_sq#c.protected_share "ln(GDP pc)^2 x Prot.") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table NP1: Conflict and NP Species Sampling") ///
    mtitles("1[NP>0]" "ln(NP+1)" "1[NP>0]" "ln(NP+1)" "1[NP>0]" "ln(NP+1)" "1[NP>0]" "ln(NP+1)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE NP2: NP share & compound diversity
*   LHS: np_share, np_unique_compounds_log
*   Tests whether conflict changes the *composition* toward/away from
*   chemically valuable species, beyond the volume effect
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict

* -------------------------------------------------------------------
* Panel A: conflict = log(1 + events)
* -------------------------------------------------------------------

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) NP share — contemporaneous
eststo np2_1: reghdfe np_share conflict forest_loss_share ///
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
* (2) Compound diversity — contemporaneous
eststo np2_2: reghdfe np_unique_compounds_log conflict forest_loss_share ///
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
* (3) NP share — with lags
eststo np2_3: reghdfe np_share conflict L1_conflict L2_conflict ///
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
* (4) Compound diversity — with lags
eststo np2_4: reghdfe np_unique_compounds_log conflict L1_conflict L2_conflict ///
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

* -------------------------------------------------------------------
* Panel B: conflict = 1[any events]
* -------------------------------------------------------------------

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

qui {
* (5) NP share — contemporaneous
eststo np2_5: reghdfe np_share conflict forest_loss_share ///
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
* (6) Compound diversity — contemporaneous
eststo np2_6: reghdfe np_unique_compounds_log conflict forest_loss_share ///
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
* (7) NP share — with lags
eststo np2_7: reghdfe np_share conflict L1_conflict L2_conflict ///
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
* (8) Compound diversity — with lags
eststo np2_8: reghdfe np_unique_compounds_log conflict L1_conflict L2_conflict ///
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

* -------------------------------------------------------------------
* Display Table NP2
* -------------------------------------------------------------------

esttab np2_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              cyclone "Cyclone (64kt+)" ///
              earthquake "Earthquake (M6+)" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
              log1p_ntl "NTL (log)" ///
              protected_share "Prot. share" ///
              c.log_gdp_pc#c.protected_share "ln(GDP pc) x Prot." ///
              c.log_gdp_pc_sq#c.protected_share "ln(GDP pc)^2 x Prot.") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table NP2: Conflict, NP Share, and Compound Diversity") ///
    mtitles("NP share" "ln(Cmpd+1)" "NP share" "ln(Cmpd+1)" "NP share" "ln(Cmpd+1)" "NP share" "ln(Cmpd+1)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE NP3: Conflict × Species Richness with NP LHS
*   Mirrors reg_spec1.do Table 5
*   Does conflict hit NP sampling harder in biodiverse cells?
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict

* -------------------------------------------------------------------
* Panel A: conflict = log(1 + events)
* -------------------------------------------------------------------

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) Extensive — contemporaneous
eststo np3_1: reghdfe np_species_w_comp_any conflict c.conflict#c.richness_std ///
        forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
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
eststo np3_2: reghdfe np_species_w_comp_log conflict c.conflict#c.richness_std ///
        forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
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
eststo np3_3: reghdfe np_species_w_comp_any conflict L1_conflict L2_conflict ///
        c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
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
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (4) Intensive — with lags
eststo np3_4: reghdfe np_species_w_comp_log conflict L1_conflict L2_conflict ///
        c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
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
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* -------------------------------------------------------------------
* Panel B: conflict = 1[any events]
* -------------------------------------------------------------------

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

qui {
* (5) Extensive — contemporaneous
eststo np3_5: reghdfe np_species_w_comp_any conflict c.conflict#c.richness_std ///
        forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
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
eststo np3_6: reghdfe np_species_w_comp_log conflict c.conflict#c.richness_std ///
        forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
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
eststo np3_7: reghdfe np_species_w_comp_any conflict L1_conflict L2_conflict ///
        c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
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
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (8) Intensive — with lags
eststo np3_8: reghdfe np_species_w_comp_log conflict L1_conflict L2_conflict ///
        c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
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
add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* -------------------------------------------------------------------
* Display Table NP3
* -------------------------------------------------------------------

esttab np3_*, keep(conflict c.conflict#c.richness_std ///
             forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict c.conflict#c.richness_std ///
          forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              c.conflict#c.richness_std "Conflict x Richness (SD)" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              cyclone "Cyclone (64kt+)" ///
              earthquake "Earthquake (M6+)" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
              log1p_ntl "NTL (log)" ///
              protected_share "Prot. share" ///
              c.log_gdp_pc#c.protected_share "ln(GDP pc) x Prot." ///
              c.log_gdp_pc_sq#c.protected_share "ln(GDP pc)^2 x Prot.") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          conflict_rich_sum_txt conflict_rich_sum_se_txt ///
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum conflict x Rich. L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %s %s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table NP3: Conflict x Species Richness — NP Outcomes") ///
    mtitles("1[NP>0]" "ln(NP+1)" "1[NP>0]" "ln(NP+1)" "1[NP>0]" "ln(NP+1)" "1[NP>0]" "ln(NP+1)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE NP4: Source decomposition — BOLD vs GBIF
*   With-lags only, log(1+events) conflict
*   Shows which upstream pipeline drives the NP signal
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) BOLD NP species (log)
eststo np4_1: reghdfe np_bold_sp_w_comp_log conflict L1_conflict L2_conflict ///
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
estadd local source "BOLD"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (2) BOLD NP share
eststo np4_2: reghdfe np_bold_share conflict L1_conflict L2_conflict ///
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
estadd local source "BOLD"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (3) GBIF NP species (log)
eststo np4_3: reghdfe np_gbif_sp_w_comp_log conflict L1_conflict L2_conflict ///
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
estadd local source "GBIF"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (4) GBIF NP share
eststo np4_4: reghdfe np_gbif_share conflict L1_conflict L2_conflict ///
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
estadd local source "GBIF"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

* -------------------------------------------------------------------
* Display Table NP4
* -------------------------------------------------------------------

esttab np4_*, keep(conflict L1_conflict L2_conflict ///
             forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl) ///
    order(conflict L1_conflict L2_conflict ///
          forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl) ///
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
              log1p_ntl "NTL (log)") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          source ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Source" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table NP4: Source Decomposition — BOLD vs GBIF") ///
    mtitles("ln(NP+1)" "NP share" "ln(NP+1)" "NP share") ///
    mgroups("BOLD" "GBIF Plantae", ///
            pattern(1 0 1 0)) ///
    compress

* ===================================================================
* TABLE NP5: Name-resolution robustness
*   With-lags, log(1+events), same FE
*   Four NP species count variants: strict BIN, no fuzzy, no BIN, named only
* ===================================================================

est clear

qui {
* (1) Strict BIN consensus (>=80%)
eststo np5_1: reghdfe np_sp_strict_log conflict L1_conflict L2_conflict ///
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
estadd local variant "Strict BIN"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (2) No fuzzy GBIF API matches
eststo np5_2: reghdfe np_sp_no_fuzzy_log conflict L1_conflict L2_conflict ///
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
estadd local variant "No fuzzy"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (3) No BIN consensus (only named BOLD records)
eststo np5_3: reghdfe np_sp_no_bin_log conflict L1_conflict L2_conflict ///
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
estadd local variant "No BIN"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

qui {
* (4) Named species only (no BIN recovery at all)
eststo np5_4: reghdfe np_sp_named_only_log conflict L1_conflict L2_conflict ///
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
estadd local variant "Named only"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
}

* -------------------------------------------------------------------
* Display Table NP5
* -------------------------------------------------------------------

esttab np5_*, keep(conflict L1_conflict L2_conflict ///
             forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl) ///
    order(conflict L1_conflict L2_conflict ///
          forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl) ///
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
              log1p_ntl "NTL (log)") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          variant ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "NP variant" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table NP5: Name-Resolution Robustness") ///
    mtitles("Strict BIN" "No fuzzy" "No BIN" "Named only") ///
    compress

* ===================================================================
* TABLE NP6: Stacked NP vs non-NP — direct differential test
*   Unit of observation: cell × year × type (is_np = 0/1)
*   LHS: ln(species + 1) where species = NP or non-NP count
*   Key coefficient: conflict × is_np (differential effect)
*   All controls and FEs interacted with is_np
* ===================================================================

preserve

drop conflict L1_conflict L2_conflict

* --- Restrict to cell-years with species sampling data ---
keep if !missing(np_species_sampled) & np_species_sampled > 0

* --- Non-NP species count ---
gen nonnp_species = np_species_sampled - np_species_w_comp
replace nonnp_species = 0 if missing(nonnp_species)
gen nonnp_log = ln(nonnp_species + 1)

* --- Both conflict measures (compute before stacking) ---
gen conflict_cont = log(1 + ucdp_events_all)
gen L1_conflict_cont = L.conflict_cont
gen L2_conflict_cont = L2.conflict_cont
gen conflict_bin = ucdp_any_all
gen L1_conflict_bin = L.conflict_bin
gen L2_conflict_bin = L2.conflict_bin

* --- Stack: 2 rows per cell-year ---
expand 2, gen(is_np)

* --- Outcome ---
gen y_log = cond(is_np==1, np_species_w_comp_log, nonnp_log)

* --- Conflict × NP interactions ---
gen conflict_cont_np = conflict_cont * is_np
gen L1_conflict_cont_np = L1_conflict_cont * is_np
gen L2_conflict_cont_np = L2_conflict_cont * is_np
gen conflict_bin_np = conflict_bin * is_np
gen L1_conflict_bin_np = L1_conflict_bin * is_np
gen L2_conflict_bin_np = L2_conflict_bin * is_np

* --- Control × NP interactions ---
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

* -------------------------------------------------------------------
* Panel A: conflict = log(1 + events)
* -------------------------------------------------------------------

qui {
* (1) Contemporaneous
eststo np6_1: reghdfe y_log ///
    conflict_cont conflict_cont_np ///
    forest_loss_share forest_loss_share_np ///
    burned_share burned_share_np ///
    cyclone cyclone_np ///
    earthquake earthquake_np ///
    pdsi_anomaly pdsi_anomaly_np ///
    tmax_anomaly tmax_anomaly_np ///
    log1p_ntl log1p_ntl_np ///
    protected_share protected_share_np ///
    log_gdp_prot log_gdp_prot_np ///
    log_gdpsq_prot log_gdpsq_prot_np ///
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
* (2) With lags
eststo np6_2: reghdfe y_log ///
    conflict_cont conflict_cont_np ///
    L1_conflict_cont L1_conflict_cont_np ///
    L2_conflict_cont L2_conflict_cont_np ///
    forest_loss_share forest_loss_share_np ///
    burned_share burned_share_np ///
    cyclone cyclone_np ///
    earthquake earthquake_np ///
    pdsi_anomaly pdsi_anomaly_np ///
    L1_pdsi_anomaly L1_pdsi_anomaly_np ///
    L2_pdsi_anomaly L2_pdsi_anomaly_np ///
    tmax_anomaly tmax_anomaly_np ///
    L1_tmax_anomaly L1_tmax_anomaly_np ///
    L2_tmax_anomaly L2_tmax_anomaly_np ///
    log1p_ntl log1p_ntl_np ///
    protected_share protected_share_np ///
    log_gdp_prot log_gdp_prot_np ///
    log_gdpsq_prot log_gdpsq_prot_np ///
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

* -------------------------------------------------------------------
* Panel B: conflict = 1[any events]
* -------------------------------------------------------------------

qui {
* (3) Contemporaneous
eststo np6_3: reghdfe y_log ///
    conflict_bin conflict_bin_np ///
    forest_loss_share forest_loss_share_np ///
    burned_share burned_share_np ///
    cyclone cyclone_np ///
    earthquake earthquake_np ///
    pdsi_anomaly pdsi_anomaly_np ///
    tmax_anomaly tmax_anomaly_np ///
    log1p_ntl log1p_ntl_np ///
    protected_share protected_share_np ///
    log_gdp_prot log_gdp_prot_np ///
    log_gdpsq_prot log_gdpsq_prot_np ///
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
* (4) With lags
eststo np6_4: reghdfe y_log ///
    conflict_bin conflict_bin_np ///
    L1_conflict_bin L1_conflict_bin_np ///
    L2_conflict_bin L2_conflict_bin_np ///
    forest_loss_share forest_loss_share_np ///
    burned_share burned_share_np ///
    cyclone cyclone_np ///
    earthquake earthquake_np ///
    pdsi_anomaly pdsi_anomaly_np ///
    L1_pdsi_anomaly L1_pdsi_anomaly_np ///
    L2_pdsi_anomaly L2_pdsi_anomaly_np ///
    tmax_anomaly tmax_anomaly_np ///
    L1_tmax_anomaly L1_tmax_anomaly_np ///
    L2_tmax_anomaly L2_tmax_anomaly_np ///
    log1p_ntl log1p_ntl_np ///
    protected_share protected_share_np ///
    log_gdp_prot log_gdp_prot_np ///
    log_gdpsq_prot log_gdpsq_prot_np ///
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

* -------------------------------------------------------------------
* Display Table NP6
* -------------------------------------------------------------------

esttab np6_*, keep(conflict_cont conflict_cont_np ///
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
    title("Table NP6: Stacked NP vs Non-NP — Direct Differential Test") ///
    mtitles("Contemp." "With Lags" "Contemp." "With Lags") ///
    mgroups("log(1+events)" "1[events>0]", ///
            pattern(1 0 1 0)) ///
    compress

restore

log close
