* reg_spec_organisms.do
* Organism heterogeneity: Table 3 spec from reg_spec1 by taxonomic group
* Table 1: Chordata records
* Table 2: Insecta records
* Table 3: Plantae + Fungi records

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/reg_spec_organisms.log", replace text

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

gen L1_pdsi_anomaly = L.pdsi_anomaly
gen L2_pdsi_anomaly = L2.pdsi_anomaly
gen L1_tmax_anomaly = L.tmax_anomaly
gen L2_tmax_anomaly = L2.tmax_anomaly

* -------------------------------------------------------------------
* add_sum_rows
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

* -------------------------------------------------------------------
* Macro for esttab (reused across tables)
* -------------------------------------------------------------------

local esttab_opts ///
    keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
    mtitles("Any" "log(1+R)" "Any" "log(1+R)" "Any" "log(1+R)" "Any" "log(1+R)") ///
    mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress

* -------------------------------------------------------------------
* Program to run one 8-column table (Panel A + B)
* -------------------------------------------------------------------

capture program drop run_table
program define run_table
    syntax , PREFIX(string) ANY(varname) LOG(varname)

    * --- Panel A: conflict = log(1 + events) ---

    cap drop conflict L1_conflict L2_conflict
    gen conflict = log(1 + ucdp_events_all)
    gen L1_conflict = L.conflict
    gen L2_conflict = L2.conflict

    qui {
    eststo `prefix'_1: reghdfe `any' conflict forest_loss_share ///
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
    eststo `prefix'_2: reghdfe `log' conflict forest_loss_share ///
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
    eststo `prefix'_3: reghdfe `any' conflict L1_conflict L2_conflict ///
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
    eststo `prefix'_4: reghdfe `log' conflict L1_conflict L2_conflict ///
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
    eststo `prefix'_5: reghdfe `any' conflict forest_loss_share ///
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
    eststo `prefix'_6: reghdfe `log' conflict forest_loss_share ///
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
    eststo `prefix'_7: reghdfe `any' conflict L1_conflict L2_conflict ///
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
    eststo `prefix'_8: reghdfe `log' conflict L1_conflict L2_conflict ///
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
end

* ===================================================================
* TABLE 1: Chordata
* ===================================================================

est clear
run_table, prefix(t1) any(any_chordata) log(log1p_chordata)

esttab t1_*, `esttab_opts' ///
    title("Table 1: Shocks and Chordata Sampling")

* ===================================================================
* TABLE 2: Insecta
* ===================================================================

est clear
run_table, prefix(t2) any(any_insecta) log(log1p_insecta)

esttab t2_*, `esttab_opts' ///
    title("Table 2: Shocks and Insecta Sampling")

* ===================================================================
* TABLE 3: Plantae + Fungi
* ===================================================================

est clear
run_table, prefix(t3) any(any_plantae_fungi) log(log1p_plantae_fungi)

esttab t3_*, `esttab_opts' ///
    title("Table 3: Shocks and Plantae + Fungi Sampling")

log close
