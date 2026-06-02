* reg_publications.do
* Conflict -> downstream publication output (Option A)
* Mirrors reg_spec1.do Table 3 and Table 5 using publication outcomes.
* Companion event-study file: DoFiles/reg_event_study_publications_5yr.do

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
do "`proj'/DoFiles/_beamer_paths.do"

capture log close
log using "`proj'/Logs/reg_publications.log", replace text

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
* 3. Construct RHS variables, matching reg_spec1.do
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
* 4. Corrected BOLD publication-yield outcome summary
* -------------------------------------------------------------------

capture confirm variable bold_pub_total_0_5yr
if _rc == 0 {
    summarize bold_pub_total_0_3yr any_bold_pub_total_0_3yr log1p_bold_pub_total_0_3yr ///
              bold_pub_total_0_5yr any_bold_pub_total_0_5yr log1p_bold_pub_total_0_5yr ///
              bold_pub_total_0_10yr any_bold_pub_total_0_10yr log1p_bold_pub_total_0_10yr ///
              bold_pub_animalia_0_5yr bold_pub_plantae_0_5yr ///
              bold_pub_fungi_0_5yr bold_pub_bacteria_0_5yr
}

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

* -------------------------------------------------------------------
* Table 3 runner: country x year + biome x year FE + road density x year
* -------------------------------------------------------------------

capture program drop run_table3
program define run_table3
    syntax , PREFIX(string) ANY(varname) LOG(varname)

    cap drop conflict L1_conflict L2_conflict

    * Panel A: conflict = log(1 + events)
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

    * Panel B: conflict = 1[any events]
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

* -------------------------------------------------------------------
* Table 5 runner: Table 3 FE + Conflict x IUCN richness
* -------------------------------------------------------------------

capture program drop run_table5
program define run_table5
    syntax , PREFIX(string) ANY(varname) LOG(varname)

    cap drop conflict L1_conflict L2_conflict

    * Panel A: conflict = log(1 + events)
    gen conflict = log(1 + ucdp_events_all)
    gen L1_conflict = L.conflict
    gen L2_conflict = L2.conflict

    qui {
    eststo `prefix'_1: reghdfe `any' conflict c.conflict#c.richness_std ///
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
    eststo `prefix'_2: reghdfe `log' conflict c.conflict#c.richness_std ///
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
    eststo `prefix'_3: reghdfe `any' conflict L1_conflict L2_conflict ///
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
    eststo `prefix'_4: reghdfe `log' conflict L1_conflict L2_conflict ///
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

    * Panel B: conflict = 1[any events]
    drop conflict L1_conflict L2_conflict
    gen conflict = ucdp_any_all
    gen L1_conflict = L.ucdp_any_all
    gen L2_conflict = L2.ucdp_any_all

    qui {
    eststo `prefix'_5: reghdfe `any' conflict c.conflict#c.richness_std ///
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
    eststo `prefix'_6: reghdfe `log' conflict c.conflict#c.richness_std ///
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
    eststo `prefix'_7: reghdfe `any' conflict L1_conflict L2_conflict ///
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
    eststo `prefix'_8: reghdfe `log' conflict L1_conflict L2_conflict ///
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
end

* -------------------------------------------------------------------
* esttab wrappers
* -------------------------------------------------------------------

capture program drop print_table3
program define print_table3
    syntax , PREFIX(string) TITLE(string)

    esttab `prefix'_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
        title(`"`title' -- Table 3 FE"') ///
        mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
        mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
                pattern(1 0 1 0 1 0 1 0)) ///
        compress
end

capture program drop print_table5
program define print_table5
    syntax , PREFIX(string) TITLE(string)

    esttab `prefix'_*, keep(conflict c.conflict#c.richness_std ///
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
        title(`"`title' -- Table 5 Conflict x Richness"') ///
        mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
        mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
                pattern(1 0 1 0 1 0 1 0)) ///
        compress
end

capture program drop export_pub_t3_deck
program define export_pub_t3_deck
    syntax , PREFIX(string) FILE(string)
    esttab `prefix'_* using "`file'", ///
        replace fragment noobs ///
        keep(conflict L1_conflict L2_conflict) ///
        order(conflict L1_conflict L2_conflict) ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        mtitles("Any" "Log N" "Any" "Log N" "Any" "Log N" "Any" "Log N") ///
        varlabels(conflict "Conflict" ///
                  L1_conflict "Conflict (t-1)" ///
                  L2_conflict "Conflict (t-2)") ///
        stats(conflict_sum_txt conflict_sum_se_txt ymean N r2 ///
              fe_cell fe_cy fe_biome_yr, ///
              labels("Sum L0-L2" "SE" "Dep. var. mean" ///
                     "Obs." "R-sq." "Cell FE" "Country x Year FE" ///
                     "Biome x Year FE") ///
              fmt(%s %s %9.4f %9.0fc %9.4f %s %s %s))
end

capture program drop export_pub_t5_deck
program define export_pub_t5_deck
    syntax , PREFIX(string) FILE(string)
    esttab `prefix'_* using "`file'", ///
        replace fragment noobs ///
        keep(conflict L1_conflict L2_conflict c.conflict#c.richness_std) ///
        order(conflict L1_conflict L2_conflict c.conflict#c.richness_std) ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        mtitles("Any" "Log N" "Any" "Log N" "Any" "Log N" "Any" "Log N") ///
        varlabels(conflict "Conflict" ///
                  L1_conflict "Conflict (t-1)" ///
                  L2_conflict "Conflict (t-2)" ///
                  c.conflict#c.richness_std "Conflict x Richness") ///
        stats(conflict_sum_txt conflict_sum_se_txt ///
              conflict_rich_sum_txt conflict_rich_sum_se_txt ymean N r2 ///
              fe_cell fe_cy fe_biome_yr, ///
              labels("Sum L0-L2" "SE" ///
                     "Sum Conflict x Rich. L0-L2" "SE" ///
                     "Dep. var. mean" "Obs." "R-sq." ///
                     "Cell FE" "Country x Year FE" "Biome x Year FE") ///
              fmt(%s %s %s %s %9.4f %9.0fc %9.4f %s %s %s))
end

capture program drop run_publication_outcome
program define run_publication_outcome
    syntax , PREFIX(string) ANY(string) LOG(string) TITLE(string)

    capture confirm variable `any'
    if _rc != 0 {
        di as text "Skipping `title': missing `any'"
        exit
    }
    capture confirm variable `log'
    if _rc != 0 {
        di as text "Skipping `title': missing `log'"
        exit
    }

    di as text "================================================================="
    di as text `"`title'"'
    di as text "Any outcome: `any'"
    di as text "Log outcome: `log'"
    di as text "================================================================="

    summarize `any' `log'

    est clear
    run_table3, prefix(`prefix't3) any(`any') log(`log')
    print_table3, prefix(`prefix't3) title(`"`title'"')
    export_pub_t3_deck, prefix(`prefix't3) file("$DD_CODEX_TABLES/tab_publications_`prefix'_t3.tex")

    est clear
    run_table5, prefix(`prefix't5) any(`any') log(`log')
    print_table5, prefix(`prefix't5) title(`"`title'"')
    export_pub_t5_deck, prefix(`prefix't5) file("$DD_CODEX_TABLES/tab_publications_`prefix'_t5.tex")
end

capture program drop run_publication_yield
program define run_publication_yield
    syntax , PREFIX(string) ANY(string) LOG(string) COMPLETE(string) TITLE(string)

    capture confirm variable `any'
    if _rc != 0 {
        di as text "Skipping `title': missing `any'"
        exit
    }
    capture confirm variable `log'
    if _rc != 0 {
        di as text "Skipping `title': missing `log'"
        exit
    }
    capture confirm variable `complete'
    if _rc != 0 {
        di as text "Skipping `title': missing completeness flag `complete'"
        exit
    }

    preserve
    keep if `complete' == 1
    run_publication_outcome, prefix(`prefix') any(`any') log(`log') title(`"`title'"')
    restore
end

* ===================================================================
* Corrected main tables: BOLD specimen-cohort publication yield
* ===================================================================

run_publication_yield, prefix(y5_total) ///
    any(any_bold_pub_total_0_5yr) log(log1p_bold_pub_total_0_5yr) ///
    complete(bold_pub_complete_0_5yr) ///
    title("BOLD publication yield within 5 years: total")

run_publication_yield, prefix(y5_animalia) ///
    any(any_bold_pub_animalia_0_5yr) log(log1p_bold_pub_animalia_0_5yr) ///
    complete(bold_pub_complete_0_5yr) ///
    title("BOLD publication yield within 5 years: Animalia")

run_publication_yield, prefix(y5_plantae) ///
    any(any_bold_pub_plantae_0_5yr) log(log1p_bold_pub_plantae_0_5yr) ///
    complete(bold_pub_complete_0_5yr) ///
    title("BOLD publication yield within 5 years: Plantae")

run_publication_yield, prefix(y5_fungi) ///
    any(any_bold_pub_fungi_0_5yr) log(log1p_bold_pub_fungi_0_5yr) ///
    complete(bold_pub_complete_0_5yr) ///
    title("BOLD publication yield within 5 years: Fungi")

run_publication_yield, prefix(y3_total) ///
    any(any_bold_pub_total_0_3yr) log(log1p_bold_pub_total_0_3yr) ///
    complete(bold_pub_complete_0_3yr) ///
    title("BOLD publication yield within 3 years: total")

run_publication_yield, prefix(y10_total) ///
    any(any_bold_pub_total_0_10yr) log(log1p_bold_pub_total_0_10yr) ///
    complete(bold_pub_complete_0_10yr) ///
    title("BOLD publication yield within 10 years: total")

di as text "================================================================="
di as text "Fungi-only BOLD publication-yield consistency-check slice"
di as text "================================================================="

capture confirm variable fungi_records
if _rc == 0 {
    preserve
    keep if bold_pub_complete_0_5yr == 1
    keep if fungi_records > 0 | bold_pub_fungi_0_5yr > 0
    run_publication_outcome, prefix(y5_fungi_slice) ///
        any(any_bold_pub_fungi_0_5yr) log(log1p_bold_pub_fungi_0_5yr) ///
        title("Fungi-only slice: BOLD publication yield within 5 years")
    restore
}
else {
    di as text "Skipping fungi-only BOLD yield slice: fungi_records not found."
}

* Publish all local exhibits to the merged deck on Dropbox.
dd_mirror_outputs

log close
