* reg_spec_benchmark.do
* Benchmarking: conflict → sampling vs BINs vs BINs|sampling
* Cols 1-2: log1p_total (sampling)
* Cols 3-4: log1p_n_new_bins (discovery)
* Cols 5-6: log1p_n_new_bins controlling for log1p_total

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/reg_spec_benchmark.log", replace text

use "`proj'/Data/analysis/BOLD_regressor_panel.dta", clear

keep if year >= 2005 & year <= 2023

encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)
xtset cell_id_num year

gen burned_share = burned_area_km2 / cell_area_km2
gen cyclone = ibtracs_any_64kt
replace cyclone = 0 if missing(cyclone)
gen earthquake = (comcat_events_m6 > 0) if !missing(comcat_events_m6)
replace earthquake = 0 if missing(earthquake)
gen log_gdp_pc = log(gdp_pcap_current_usd)
gen log_gdp_pc_sq = log_gdp_pc^2

gen L1_pdsi_anomaly = L.pdsi_anomaly
gen L2_pdsi_anomaly = L2.pdsi_anomaly
gen L1_tmax_anomaly = L.tmax_anomaly
gen L2_tmax_anomaly = L2.tmax_anomaly

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

est clear

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

* --- Col 1: log1p_total, contemporaneous ---

qui {
eststo b1: reghdfe log1p_total conflict forest_loss_share ///
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
estadd local lhs_var "Sampling"
estadd local effort_ctrl ""
}

* --- Col 2: log1p_total, with lags ---

qui {
eststo b2: reghdfe log1p_total conflict L1_conflict L2_conflict ///
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
estadd local lhs_var "Sampling"
estadd local effort_ctrl ""
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* --- Col 3: log1p_n_new_bins, contemporaneous ---

qui {
eststo b3: reghdfe log1p_n_new_bins conflict forest_loss_share ///
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
estadd local lhs_var "Discovery"
estadd local effort_ctrl ""
}

* --- Col 4: log1p_n_new_bins, with lags ---

qui {
eststo b4: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
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
estadd local lhs_var "Discovery"
estadd local effort_ctrl ""
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* --- Col 5: log1p_n_new_bins | log1p_total, contemporaneous ---

qui {
eststo b5: reghdfe log1p_n_new_bins conflict log1p_total ///
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
estadd local lhs_var "Discovery"
estadd local effort_ctrl "\checkmark"
}

* --- Col 6: log1p_n_new_bins | log1p_total, with lags ---

qui {
eststo b6: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
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
estadd local lhs_var "Discovery"
estadd local effort_ctrl "\checkmark"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

* --- Col 7: log1p_n_new_bins | log1p_total, contemporaneous, intensive margin ---

qui {
eststo b7: reghdfe log1p_n_new_bins conflict log1p_total ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if total_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local lhs_var "Discovery"
estadd local effort_ctrl "\checkmark"
estadd local sample_restr "Records>0"
}

* --- Col 8: log1p_n_new_bins | log1p_total, with lags, intensive margin ---

qui {
eststo b8: reghdfe log1p_n_new_bins conflict L1_conflict L2_conflict ///
        log1p_total ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
        tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.year ///
        if total_records > 0, ///
        absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
        vce(cluster cell_id_num)
estadd ysumm, mean sd
estadd local fe_cell "\checkmark"
estadd local fe_cy "\checkmark"
estadd local fe_biome_yr "\checkmark"
estadd local road_yr "\checkmark"
estadd local lhs_var "Discovery"
estadd local effort_ctrl "\checkmark"
estadd local sample_restr "Records>0"
add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
}

esttab b*, keep(conflict log1p_total ///
             forest_loss_share burned_share cyclone earthquake ///
             pdsi_anomaly tmax_anomaly log1p_ntl ///
             protected_share c.log_gdp_pc#c.protected_share ///
             c.log_gdp_pc_sq#c.protected_share) ///
    order(conflict log1p_total ///
          forest_loss_share burned_share cyclone earthquake ///
          pdsi_anomaly tmax_anomaly log1p_ntl ///
          protected_share c.log_gdp_pc#c.protected_share ///
          c.log_gdp_pc_sq#c.protected_share) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(conflict "Conflict" ///
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
          pdsi_sum_txt pdsi_sum_se_txt ///
          tmax_sum_txt tmax_sum_se_txt ///
          lhs_var effort_ctrl sample_restr ymean ysd N r2 ///
          fe_cell fe_cy fe_biome_yr road_yr, ///
          labels("Sum conflict L0-L2" " " ///
                 "Sum PDSI L0-L2" " " ///
                 "Sum tmax L0-L2" " " ///
                 "Dep. variable" "Sampling effort ctrl." "Sample restriction" ///
                 "Dep. var. mean" "Dep. var. SD" ///
                 "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                 "Biome x Year FE" "Road dens. x Year") ///
          fmt(%s %s %s %s %s %s ///
              %s %s %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
    title("Benchmarking: Conflict and Sampling vs Discovery vs Discovery|Sampling") ///
    mtitles("Contemp." "Lags" "Contemp." "Lags" "Contemp." "Lags" "Contemp." "Lags") ///
    mgroups("Sampling" "Discovery" "Discovery | Effort" "Disc. | Effort (int.)", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

log close
