* reg_spec1.do
* Shocks → BOLD sampling activity
* Table 1: Cell + Year FE (main)
* Table 2: Cell + Country×Year FE (robustness)

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/reg_spec1.log", replace text

use "`proj'/Data/analysis/BOLD_regressor_panel.dta", clear

* -------------------------------------------------------------------
* 1. Sample restriction
* -------------------------------------------------------------------

keep if year >= 2005 & year <= 2023

gen very_rich = ((continent == "Europe" & country!="Russia") | ///
country == "Canada" | ///
country == "United States of America" | ///
country == "Australia" | ///
country == "New Zealand")

// c.very_rich##c.protected_share -- this is interesting finding on its own

//drop if very_rich == 1

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
gen log_gdp_pc = log(gdp_pcap_current_usd)
gen log_gdp_pc_sq = log_gdp_pc^2

gen L1_pdsi_anomaly = L.pdsi_anomaly
gen L2_pdsi_anomaly = L2.pdsi_anomaly
gen L1_tmax_anomaly = L.tmax_anomaly
gen L2_tmax_anomaly = L2.tmax_anomaly

* -------------------------------------------------------------------
* 4. Summary statistics
* -------------------------------------------------------------------

summarize any_total log1p_total ucdp_events_all ucdp_any_all ///
          forest_loss_share burned_share pdsi_anomaly tmax_anomaly ///
          protected_share gdp_pcap_current_usd log_gdp_pc

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
* TABLE 1: Cell + Year FE (main specification)
* ===================================================================

est clear

* -------------------------------------------------------------------
* Panel A: conflict = log(1 + events)
* -------------------------------------------------------------------

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

qui {
* (1) Extensive margin — contemporaneous
eststo t1_1: reghdfe any_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (2) Intensive margin — contemporaneous
eststo t1_2: reghdfe log1p_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (3) Extensive margin — with lags
eststo t1_3: reghdfe any_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (4) Intensive margin — with lags
eststo t1_4: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
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
* (5) Extensive margin — contemporaneous
eststo t1_5: reghdfe any_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (6) Intensive margin — contemporaneous
eststo t1_6: reghdfe log1p_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (7) Extensive margin — with lags
eststo t1_7: reghdfe any_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (8) Intensive margin — with lags
eststo t1_8: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        c.log_gdp_pc##c.protected_share log_gdp_pc_sq c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_year "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* -------------------------------------------------------------------
* Display Table 1
* -------------------------------------------------------------------

esttab t1_*, keep(conflict forest_loss_share burned_share ///
             pdsi_anomaly tmax_anomaly ///
             log_gdp_pc log_gdp_pc_sq ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict forest_loss_share burned_share ///
          pdsi_anomaly tmax_anomaly ///
          log_gdp_pc log_gdp_pc_sq ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
              log_gdp_pc "ln(GDP pc)" ///
              log_gdp_pc_sq "ln(GDP pc)^2" ///
              protected_share "Prot. share" ///
              c.log_gdp_pc#c.protected_share "ln(GDP pc) x Prot." ///
              c.log_gdp_pc_sq#c.protected_share "ln(GDP pc)^2 x Prot.") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_year, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Year FE") ///
          fmt(%s %s %s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s)) ///
    title("Table 1: Shocks and BOLD Sampling — Cell + Year FE") ///
    mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE 2: Cell + Country×Year FE (robustness)
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
* (1) Extensive margin — contemporaneous
eststo t2_1: reghdfe any_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (2) Intensive margin — contemporaneous
eststo t2_2: reghdfe log1p_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local conflict_measure "log(1+events)"
}

qui {
* (3) Extensive margin — with lags
eststo t2_3: reghdfe any_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local conflict_measure "log(1+events)"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (4) Intensive margin — with lags
eststo t2_4: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
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
* (5) Extensive margin — contemporaneous
eststo t2_5: reghdfe any_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (6) Intensive margin — contemporaneous
eststo t2_6: reghdfe log1p_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local conflict_measure "1[events>0]"
}

qui {
* (7) Extensive margin — with lags
eststo t2_7: reghdfe any_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (8) Intensive margin — with lags
eststo t2_8: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share, ///
        absorb(cell_id_num country_num#year) vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local conflict_measure "1[events>0]"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* -------------------------------------------------------------------
* Display Table 2
* -------------------------------------------------------------------

esttab t2_*, keep(conflict forest_loss_share burned_share ///
             pdsi_anomaly tmax_anomaly ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict forest_loss_share burned_share ///
          pdsi_anomaly tmax_anomaly ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
              protected_share "Prot. share" ///
              c.log_gdp_pc#c.protected_share "ln(GDP pc) x Prot." ///
              c.log_gdp_pc_sq#c.protected_share "ln(GDP pc)^2 x Prot.") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE") ///
          fmt(%s %s %s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s)) ///
    title("Table 2: Shocks and BOLD Sampling — Cell + Country x Year FE") ///
    mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE 3: Cell + Country×Year + Biome×Year FE + Road density×Year
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
* (1) Extensive margin — contemporaneous
eststo t3_1: reghdfe any_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
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
* (2) Intensive margin — contemporaneous
eststo t3_2: reghdfe log1p_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
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
* (3) Extensive margin — with lags
eststo t3_3: reghdfe any_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
* (4) Intensive margin — with lags
eststo t3_4: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
* (5) Extensive margin — contemporaneous
eststo t3_5: reghdfe any_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
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
* (6) Intensive margin — contemporaneous
eststo t3_6: reghdfe log1p_total conflict forest_loss_share ///
        burned_share pdsi_anomaly tmax_anomaly ///
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
* (7) Extensive margin — with lags
eststo t3_7: reghdfe any_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
* (8) Intensive margin — with lags
eststo t3_8: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
* Display Table 3
* -------------------------------------------------------------------

esttab t3_*, keep(conflict forest_loss_share burned_share ///
             pdsi_anomaly tmax_anomaly ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict forest_loss_share burned_share ///
          pdsi_anomaly tmax_anomaly ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
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
    title("Table 3: Shocks and BOLD Sampling — Country x Year + Biome x Year FE") ///
    mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* ===================================================================
* TABLE 4: Table 3 + Conflict × MSA interaction
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
* (1) Extensive margin — contemporaneous
eststo t4_1: reghdfe any_total conflict c.conflict#c.msa_overall ///
        forest_loss_share burned_share pdsi_anomaly tmax_anomaly ///
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
* (2) Intensive margin — contemporaneous
eststo t4_2: reghdfe log1p_total conflict c.conflict#c.msa_overall ///
        forest_loss_share burned_share pdsi_anomaly tmax_anomaly ///
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
* (3) Extensive margin — with lags
eststo t4_3: reghdfe any_total conflict L1_conflict L2_conflict ///
        c.conflict#c.msa_overall c.L1_conflict#c.msa_overall c.L2_conflict#c.msa_overall ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
add_sum_rows, name(conflict_msa_sum) expr(c.conflict#c.msa_overall + c.L1_conflict#c.msa_overall + c.L2_conflict#c.msa_overall)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (4) Intensive margin — with lags
eststo t4_4: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        c.conflict#c.msa_overall c.L1_conflict#c.msa_overall c.L2_conflict#c.msa_overall ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
add_sum_rows, name(conflict_msa_sum) expr(c.conflict#c.msa_overall + c.L1_conflict#c.msa_overall + c.L2_conflict#c.msa_overall)
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
* (5) Extensive margin — contemporaneous
eststo t4_5: reghdfe any_total conflict c.conflict#c.msa_overall ///
        forest_loss_share burned_share pdsi_anomaly tmax_anomaly ///
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
* (6) Intensive margin — contemporaneous
eststo t4_6: reghdfe log1p_total conflict c.conflict#c.msa_overall ///
        forest_loss_share burned_share pdsi_anomaly tmax_anomaly ///
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
* (7) Extensive margin — with lags
eststo t4_7: reghdfe any_total conflict L1_conflict L2_conflict ///
        c.conflict#c.msa_overall c.L1_conflict#c.msa_overall c.L2_conflict#c.msa_overall ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
add_sum_rows, name(conflict_msa_sum) expr(c.conflict#c.msa_overall + c.L1_conflict#c.msa_overall + c.L2_conflict#c.msa_overall)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

qui {
* (8) Intensive margin — with lags
eststo t4_8: reghdfe log1p_total conflict L1_conflict L2_conflict ///
        c.conflict#c.msa_overall c.L1_conflict#c.msa_overall c.L2_conflict#c.msa_overall ///
        forest_loss_share burned_share ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly ///
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
add_sum_rows, name(conflict_msa_sum) expr(c.conflict#c.msa_overall + c.L1_conflict#c.msa_overall + c.L2_conflict#c.msa_overall)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* -------------------------------------------------------------------
* Display Table 4
* -------------------------------------------------------------------

esttab t4_*, keep(conflict c.conflict#c.msa_overall ///
             forest_loss_share burned_share ///
             pdsi_anomaly tmax_anomaly ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict c.conflict#c.msa_overall ///
          forest_loss_share burned_share ///
          pdsi_anomaly tmax_anomaly ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
              c.conflict#c.msa_overall "Conflict x MSA" ///
              forest_loss_share "Forest loss" ///
              burned_share "Burned area" ///
              pdsi_anomaly "PDSI anom." ///
              tmax_anomaly "Tmax anom." ///
              protected_share "Prot. share" ///
              c.log_gdp_pc#c.protected_share "ln(GDP pc) x Prot." ///
              c.log_gdp_pc_sq#c.protected_share "ln(GDP pc)^2 x Prot.") ///
    stats(conflict_sum_txt conflict_sum_se_txt ///
          conflict_msa_sum_txt conflict_msa_sum_se_txt ///
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          conflict_measure ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum conflict x MSA L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Conflict measure" "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %s %s %s %s %s ///
              %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Table 4: Conflict x Biodiversity Intactness (MSA)") ///
    mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

log close
