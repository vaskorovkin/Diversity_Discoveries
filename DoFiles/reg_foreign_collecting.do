* reg_foreign_collecting.do
* Shocks → foreign vs domestic collecting composition
* Panel A: conflict = log(1+events)
*   FC3a/FC3b: Table 3 FE (Cell + Country×Year + Biome×Year + Road×Year)
*   FC5a/FC5b: + Conflict × Species Richness interaction
* Panel B: conflict = 1[events>0]
*   FC3c/FC3d, FC5c/FC5d: same specifications

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
do "`proj'/DoFiles/_beamer_paths.do"
local codex_tabledir "$DD_CODEX_TABLES"

capture log close
log using "`proj'/Logs/reg_foreign_collecting.log", replace text

use "`proj'/Data/analysis/BOLD_regressor_panel.dta", clear

keep if year >= 2005 & year <= 2023

* -------------------------------------------------------------------
* 1. Encode, declare panel
* -------------------------------------------------------------------

encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)
xtset cell_id_num year

* -------------------------------------------------------------------
* 2. RHS variables (mirroring reg_spec1)
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
* 3. LHS variables (foreign collecting outcomes)
* -------------------------------------------------------------------

foreach v of varlist domestic_score_sum regional_score_sum distant_score_sum ///
    records_collab {
    replace `v' = 0 if missing(`v')
}

gen foreign_score_sum = regional_score_sum + distant_score_sum

gen log1p_domestic = log(1 + domestic_score_sum)
gen log1p_foreign  = log(1 + foreign_score_sum)
gen log1p_distant  = log(1 + distant_score_sum)
gen log1p_collab   = log(1 + records_collab)

gen any_domestic = (domestic_score_sum > 0)
gen any_foreign  = (foreign_score_sum > 0)
gen any_distant  = (distant_score_sum > 0)
gen any_collab   = (records_collab > 0)

di _n "=== OUTCOME SUMMARY ==="
summarize log1p_domestic log1p_foreign log1p_distant log1p_collab ///
    any_domestic any_foreign any_distant any_collab

* -------------------------------------------------------------------
* add_sum_rows helper (same as reg_spec1)
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

capture program drop export_fc3_deck
program define export_fc3_deck
    syntax anything(name=models) , FILE(string)
    esttab `models' using "`file'", ///
        replace fragment noobs ///
        keep(conflict L1_conflict L2_conflict) ///
        order(conflict L1_conflict L2_conflict) ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        mtitles("Dom C" "Dom L" "For C" "For L" "Dist C" "Dist L" "Coll C" "Coll L") ///
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

capture program drop export_fc5_deck
program define export_fc5_deck
    syntax anything(name=models) , FILE(string)
    esttab `models' using "`file'", ///
        replace fragment noobs ///
        keep(conflict L1_conflict L2_conflict c.conflict#c.richness_std) ///
        order(conflict L1_conflict L2_conflict c.conflict#c.richness_std) ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        mtitles("Dom C" "Dom L" "For C" "For L" "Dist C" "Dist L" "Coll C" "Coll L") ///
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

* ===================================================================
* PANEL A: conflict = log(1 + events)
* ===================================================================

gen conflict = log(1 + ucdp_events_all)
gen L1_conflict = L.conflict
gen L2_conflict = L2.conflict

* ===================================================================
* TABLE FC3a: Intensive margin — Table 3 FE
* ===================================================================

est clear

local outcomes "log1p_domestic log1p_foreign log1p_distant log1p_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc3a_`col': reghdfe `y' conflict ///
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

    local ++col
    qui {
    eststo fc3a_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc3a_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
    title("Table FC3a: Shocks and Collecting Composition — Intensive, log(1+events)") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc3_deck fc3a_*, file("`codex_tabledir'/tab_foreign_collecting_fc3a_intensive_logevents.tex")

* ===================================================================
* TABLE FC3b: Extensive margin — Table 3 FE
* ===================================================================

est clear

local outcomes "any_domestic any_foreign any_distant any_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc3b_`col': reghdfe `y' conflict ///
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

    local ++col
    qui {
    eststo fc3b_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc3b_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
    title("Table FC3b: Shocks and Collecting Composition — Extensive, log(1+events)") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc3_deck fc3b_*, file("`codex_tabledir'/tab_foreign_collecting_fc3b_extensive_logevents.tex")

* ===================================================================
* TABLE FC5a: Intensive + Conflict × Richness
* ===================================================================

est clear

local outcomes "log1p_domestic log1p_foreign log1p_distant log1p_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc5a_`col': reghdfe `y' conflict c.conflict#c.richness_std ///
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

    local ++col
    qui {
    eststo fc5a_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc5a_*, keep(conflict c.conflict#c.richness_std ///
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
    title("Table FC5a: Conflict x Richness — Intensive, log(1+events)") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc5_deck fc5a_*, file("`codex_tabledir'/tab_foreign_collecting_fc5a_intensive_richness_logevents.tex")

* ===================================================================
* TABLE FC5b: Extensive + Conflict × Richness
* ===================================================================

est clear

local outcomes "any_domestic any_foreign any_distant any_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc5b_`col': reghdfe `y' conflict c.conflict#c.richness_std ///
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

    local ++col
    qui {
    eststo fc5b_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc5b_*, keep(conflict c.conflict#c.richness_std ///
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
    title("Table FC5b: Conflict x Richness — Extensive, log(1+events)") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc5_deck fc5b_*, file("`codex_tabledir'/tab_foreign_collecting_fc5b_extensive_richness_logevents.tex")

* ===================================================================
* PANEL B: conflict = 1[events > 0]
* ===================================================================

drop conflict L1_conflict L2_conflict
gen conflict = ucdp_any_all
gen L1_conflict = L.ucdp_any_all
gen L2_conflict = L2.ucdp_any_all

* ===================================================================
* TABLE FC3c: Intensive margin — Table 3 FE, 1[events>0]
* ===================================================================

est clear

local outcomes "log1p_domestic log1p_foreign log1p_distant log1p_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc3c_`col': reghdfe `y' conflict ///
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

    local ++col
    qui {
    eststo fc3c_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc3c_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
    title("Table FC3c: Shocks and Collecting Composition — Intensive, 1[events>0]") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc3_deck fc3c_*, file("`codex_tabledir'/tab_foreign_collecting_fc3c_intensive_anyevent.tex")

* ===================================================================
* TABLE FC3d: Extensive margin — Table 3 FE, 1[events>0]
* ===================================================================

est clear

local outcomes "any_domestic any_foreign any_distant any_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc3d_`col': reghdfe `y' conflict ///
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

    local ++col
    qui {
    eststo fc3d_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc3d_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
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
    title("Table FC3d: Shocks and Collecting Composition — Extensive, 1[events>0]") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc3_deck fc3d_*, file("`codex_tabledir'/tab_foreign_collecting_fc3d_extensive_anyevent.tex")

* ===================================================================
* TABLE FC5c: Intensive + Conflict × Richness, 1[events>0]
* ===================================================================

est clear

local outcomes "log1p_domestic log1p_foreign log1p_distant log1p_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc5c_`col': reghdfe `y' conflict c.conflict#c.richness_std ///
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

    local ++col
    qui {
    eststo fc5c_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc5c_*, keep(conflict c.conflict#c.richness_std ///
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
    title("Table FC5c: Conflict x Richness — Intensive, 1[events>0]") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc5_deck fc5c_*, file("`codex_tabledir'/tab_foreign_collecting_fc5c_intensive_richness_anyevent.tex")

* ===================================================================
* TABLE FC5d: Extensive + Conflict × Richness, 1[events>0]
* ===================================================================

est clear

local outcomes "any_domestic any_foreign any_distant any_collab"
local col = 0

foreach y of local outcomes {

    local ++col
    qui {
    eststo fc5d_`col': reghdfe `y' conflict c.conflict#c.richness_std ///
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

    local ++col
    qui {
    eststo fc5d_`col': reghdfe `y' conflict L1_conflict L2_conflict ///
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
}

esttab fc5d_*, keep(conflict c.conflict#c.richness_std ///
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
    title("Table FC5d: Conflict x Richness — Extensive, 1[events>0]") ///
    mtitles("Cont." "Lags" "Cont." "Lags" "Cont." "Lags" "Cont." "Lags") ///
    mgroups("Domestic" "Foreign" "Distant" "Collaboration", ///
            pattern(1 0 1 0 1 0 1 0)) ///
    compress
export_fc5_deck fc5d_*, file("`codex_tabledir'/tab_foreign_collecting_fc5d_extensive_richness_anyevent.tex")

* Publish all local exhibits to the merged deck on Dropbox.
dd_mirror_outputs

log close
