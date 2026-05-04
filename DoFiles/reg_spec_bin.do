* reg_spec_bin.do
* Shocks → BOLD BIN outcomes (species breadth and discovery)
* Table 1: n_bins — Country×Year + Biome×Year FE
* Table 2: n_new_bins — Country×Year + Biome×Year FE
* Table 3: n_bins — Conflict × Richness interaction
* Table 4: n_new_bins — Conflict × Richness interaction
* Table 5: n_new_bins — Sampling effort control (+/- Conflict × Richness)

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/reg_spec_bin.log", replace text

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
* 3. Construct RHS variables
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
* 4. Summary statistics for BIN outcomes
* -------------------------------------------------------------------

summarize any_n_bins log1p_n_bins n_bins any_n_new_bins log1p_n_new_bins n_new_bins

* -------------------------------------------------------------------
* add_sum_rows: compute sum of L0+L1+L2 via lincom, store as estadd
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
* TABLE 1: n_bins — Country×Year + Biome×Year FE
* ===================================================================

est clear

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

* --- Panel A: conflict = log(1 + events) ---

qui {
eststo t1_1: reghdfe any_n_bins conflict forest_loss_share ///
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
eststo t1_2: reghdfe log1p_n_bins conflict forest_loss_share ///
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
eststo t1_3: reghdfe any_n_bins conflict L1_conflict L2_conflict ///
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
eststo t1_4: reghdfe log1p_n_bins conflict L1_conflict L2_conflict ///
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
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

qui {
eststo t1_5: reghdfe any_n_bins conflict forest_loss_share ///
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
eststo t1_6: reghdfe log1p_n_bins conflict forest_loss_share ///
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
eststo t1_7: reghdfe any_n_bins conflict L1_conflict L2_conflict ///
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
eststo t1_8: reghdfe log1p_n_bins conflict L1_conflict L2_conflict ///
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

esttab t1_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
    title("Table 1: Shocks and BIN Richness (n_bins)") ///
    mtitles("Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE 2: n_new_bins — Country×Year + Biome×Year FE
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
eststo t2_1: reghdfe any_n_new_bins conflict forest_loss_share ///
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
eststo t2_2: reghdfe log1p_n_new_bins conflict forest_loss_share ///
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
eststo t2_3: reghdfe any_n_new_bins conflict L1_conflict L2_conflict ///
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
eststo t2_4: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
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

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

qui {
eststo t2_5: reghdfe any_n_new_bins conflict forest_loss_share ///
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
eststo t2_6: reghdfe log1p_n_new_bins conflict forest_loss_share ///
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
eststo t2_7: reghdfe any_n_new_bins conflict L1_conflict L2_conflict ///
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
eststo t2_8: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
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

esttab t2_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
    title("Table 2: Shocks and New BIN Discovery (n_new_bins)") ///
    mtitles("Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE 3: n_bins — Conflict × Richness interaction
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
eststo t3_1: reghdfe any_n_bins conflict c.conflict#c.richness_std ///
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
eststo t3_2: reghdfe log1p_n_bins conflict c.conflict#c.richness_std ///
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
eststo t3_3: reghdfe any_n_bins conflict L1_conflict L2_conflict ///
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
eststo t3_4: reghdfe log1p_n_bins conflict L1_conflict L2_conflict ///
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

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

qui {
eststo t3_5: reghdfe any_n_bins conflict c.conflict#c.richness_std ///
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
eststo t3_6: reghdfe log1p_n_bins conflict c.conflict#c.richness_std ///
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
eststo t3_7: reghdfe any_n_bins conflict L1_conflict L2_conflict ///
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
eststo t3_8: reghdfe log1p_n_bins conflict L1_conflict L2_conflict ///
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

esttab t3_*, keep(conflict c.conflict#c.richness_std ///
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
    title("Table 3: Conflict x Richness — BIN Richness (n_bins)") ///
    mtitles("Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE 4: n_new_bins — Conflict × Richness interaction
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
eststo t4_1: reghdfe any_n_new_bins conflict c.conflict#c.richness_std ///
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
eststo t4_2: reghdfe log1p_n_new_bins conflict c.conflict#c.richness_std ///
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
eststo t4_3: reghdfe any_n_new_bins conflict L1_conflict L2_conflict ///
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
eststo t4_4: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
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

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

qui {
eststo t4_5: reghdfe any_n_new_bins conflict c.conflict#c.richness_std ///
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
eststo t4_6: reghdfe log1p_n_new_bins conflict c.conflict#c.richness_std ///
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
eststo t4_7: reghdfe any_n_new_bins conflict L1_conflict L2_conflict ///
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
eststo t4_8: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
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

esttab t4_*, keep(conflict c.conflict#c.richness_std ///
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
    title("Table 4: Conflict x Richness — New BIN Discovery (n_new_bins)") ///
    mtitles("Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE 5: n_new_bins — Sampling effort control (+/- interaction)
*   Cols 1-4: no interaction; Cols 5-8: Conflict × Richness
* ===================================================================

est clear

drop conflict L1_conflict L2_conflict

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

* --- Cols 1-4: no interaction ---

qui {
eststo t5_1: reghdfe any_n_new_bins conflict log1p_total ///
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
eststo t5_2: reghdfe log1p_n_new_bins conflict log1p_total ///
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
eststo t5_3: reghdfe any_n_new_bins conflict L1_conflict L2_conflict ///
        log1p_total ///
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
eststo t5_4: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
        log1p_total ///
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

* --- Cols 5-8: with Conflict × Richness interaction ---

qui {
eststo t5_5: reghdfe any_n_new_bins conflict c.conflict#c.richness_std ///
        log1p_total ///
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
eststo t5_6: reghdfe log1p_n_new_bins conflict c.conflict#c.richness_std ///
        log1p_total ///
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
eststo t5_7: reghdfe any_n_new_bins conflict L1_conflict L2_conflict ///
        c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
        log1p_total ///
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
eststo t5_8: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
        c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
        log1p_total ///
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

esttab t5_*, keep(conflict c.conflict#c.richness_std ///
             log1p_total ///
             forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict c.conflict#c.richness_std ///
          log1p_total ///
          forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              c.conflict#c.richness_std "Conflict x Richness (SD)" ///
              log1p_total "Sampling effort (log)" ///
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
    title("Table 5: New BIN Discovery + Sampling Effort (n_new_bins)") ///
    mtitles("Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)" "Any" "log(1+B)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

log close
