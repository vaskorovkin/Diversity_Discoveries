* reg_spec1_acled_table3_definitions.do
* Replicate reg_spec1 Table 3 with alternative ACLED treatment definitions.
*
* Each displayed table has the same eight-column structure as reg_spec1 Table 3:
*   columns 1-4: log(1 + ACLED event count)
*   columns 5-8: 1[ACLED event count > 0]
*   columns 3/4 and 7/8 include L1/L2 treatment lags.

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
do "`proj'/DoFiles/_beamer_paths.do"

* -------------------------------------------------------------------
* HDFE backend
* -------------------------------------------------------------------

local hdfe_cmd "reghdfe"
// local hdfe_cmd "reghdfejl"

* ACLED has full 2005+ coverage for Africa; global coverage starts later.
local africa_only "on"

* -------------------------------------------------------------------
* Panel selector
* Choose one:
*   "100-yearly"
*   "50-yearly"
*   "50-quarterly"
*   "all"
* -------------------------------------------------------------------

local panel_mode "50-yearly"
if "`1'" != "" {
    local panel_mode "`1'"
}

if "`panel_mode'" == "all" {
    foreach m in "100-yearly" "50-yearly" "50-quarterly" {
        di _n as text "============================================================"
        di as text "Running reg_spec1_acled_table3_definitions.do for panel_mode = `m'"
        di as text "============================================================"
        do "`proj'/DoFiles/reg_spec1_acled_table3_definitions.do" "`m'"
    }
    exit
}

* Optional seasonal control for quarterly panels only.
// local quarterly_cell_season_fe "on"
local quarterly_cell_season_fe "off"

if "`panel_mode'" == "100-yearly" {
    local panel_path "`proj'/Data/analysis/BOLD_regressor_panel.dta"
    local log_path   "`proj'/Logs/reg_spec1_acled_table3_defs_100km_year.log"
    local panel_freq "year"
    local mode_tag "100km_year"
}
else if "`panel_mode'" == "50-yearly" {
    local panel_path "`proj'/Data/analysis/tests_spatial_time/BOLD_regressor_panel_50km_year.dta"
    local log_path   "`proj'/Logs/reg_spec1_acled_table3_defs_50km_year.log"
    local panel_freq "year"
    local mode_tag "50km_year"
}
else if "`panel_mode'" == "50-quarterly" {
    local panel_path "`proj'/Data/analysis/tests_spatial_time/BOLD_regressor_panel_50km_quarter.dta"
    local log_path   "`proj'/Logs/reg_spec1_acled_table3_defs_50km_quarter.log"
    local panel_freq "quarter"
    local mode_tag "50km_quarter"
}
else {
    di as error "Unknown panel_mode: `panel_mode'"
    di as error `"{p}Valid options are "100-yearly", "50-yearly", "50-quarterly", and "all".{p_end}"'
    error 198
}

if !inlist("`quarterly_cell_season_fe'", "on", "off") {
    di as error "quarterly_cell_season_fe must be either on or off."
    error 198
}

if "`panel_freq'" == "quarter" & "`quarterly_cell_season_fe'" == "on" {
    local log_path = subinstr("`log_path'", ".log", "_cellseason.log", .)
}
if "`africa_only'" == "on" {
    local log_path = subinstr("`log_path'", ".log", "_africa.log", .)
}

capture confirm file "`panel_path'"
if _rc {
    di as error "Missing analysis panel: `panel_path'"
    error 601
}

capture log close
log using "`log_path'", replace text

global codex_tabledir "$DD_CODEX_TABLES"
global acled_defs_mode_tag "`mode_tag'"

capture which `hdfe_cmd'
if _rc {
    di as error "Requested HDFE backend `hdfe_cmd' is not installed."
    if "`hdfe_cmd'" == "reghdfejl" {
        di as text "Install in Stata with: ssc install julia; ssc install reghdfejl"
    }
    error 111
}

use "`panel_path'", clear

if "`africa_only'" == "on" {
    keep if continent == "Africa"
}

keep if year >= 2005 & year <= 2023

encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)

if "`panel_freq'" == "quarter" {
    capture confirm variable quarter
    if _rc {
        di as error "panel_mode = 50-quarterly requires a quarter variable."
        error 111
    }
    gen time_id = yq(year, quarter)
    format time_id %tq
    local timevar "time_id"
    xtset cell_id_num time_id
}
else {
    local timevar "year"
    xtset cell_id_num year
}

local absorb_cell_season ""
if "`panel_freq'" == "quarter" & "`quarterly_cell_season_fe'" == "on" {
    egen cell_season = group(cell_id_num quarter)
    local absorb_cell_season "cell_season"
}
else if "`panel_freq'" != "quarter" & "`quarterly_cell_season_fe'" == "on" {
    di as text "quarterly_cell_season_fe ignored because panel_mode is annual."
}

egen country_time = group(country_num `timevar')
egen biome_time   = group(resolve_biome_num `timevar')
replace country_time = . if missing(country_num)
replace biome_time   = . if missing(resolve_biome_num)

local absorb_rich "cell_id_num country_time biome_time `absorb_cell_season'"
local road_time "c.road_density_km_per_km2#i.`timevar'"

di as text "Panel mode: `panel_mode'"
di as text "Time variable: `timevar'"
di as text "Quarterly cell x season FE: `quarterly_cell_season_fe'"
di as text "HDFE backend: `hdfe_cmd'"

* -------------------------------------------------------------------
* RHS controls from reg_spec1 Table 3
* -------------------------------------------------------------------

gen burned_share = burned_area_km2 / cell_area_km2
gen cyclone = ibtracs_any_64kt
replace cyclone = 0 if missing(cyclone)
gen earthquake = (comcat_events_m6 > 0) if !missing(comcat_events_m6)
replace earthquake = 0 if missing(earthquake)
gen log_gdp_pc = log(gdp_pcap_current_usd)
gen log_gdp_pc_sq = log_gdp_pc^2
gen log_gdp_pc_x_protected_share = log_gdp_pc * protected_share
gen log_gdp_pc_sq_x_protected_share = log_gdp_pc_sq * protected_share

gen L1_pdsi_anomaly = L.pdsi_anomaly
gen L2_pdsi_anomaly = L2.pdsi_anomaly
gen L1_tmax_anomaly = L.tmax_anomaly
gen L2_tmax_anomaly = L2.tmax_anomaly

foreach v in acled_events_all acled_events_battles acled_events_explosions ///
        acled_events_vac acled_events_protests acled_events_riots ///
        acled_events_strategic {
    capture confirm variable `v'
    if _rc {
        di as error "Missing ACLED variable `v'. Rebuild the analysis panel with ACLED merged first."
        error 111
    }
    replace `v' = 0 if missing(`v')
}

gen acled_events_violent = acled_events_battles + acled_events_explosions + acled_events_vac

summarize any_total log1p_total acled_events_all acled_events_violent ///
    acled_events_battles acled_events_explosions acled_events_vac ///
    acled_events_protests acled_events_riots acled_events_strategic ///
    forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
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

capture program drop run_acled_table3
program define run_acled_table3
    syntax , COUNTVAR(name) LABEL(string)

    est clear
    capture drop conflict L1_conflict L2_conflict

    gen conflict = log(1 + `countvar')
    gen L1_conflict = L.conflict
    gen L2_conflict = L2.conflict

    qui {
    eststo t3_1: ${hdfe_cmd} any_total conflict forest_loss_share ///
            burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "log(1+`label')"
    }

    qui {
    eststo t3_2: ${hdfe_cmd} log1p_total conflict forest_loss_share ///
            burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "log(1+`label')"
    }

    qui {
    eststo t3_3: ${hdfe_cmd} any_total conflict L1_conflict L2_conflict ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "log(1+`label')"
    add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
    add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
    add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
    }

    qui {
    eststo t3_4: ${hdfe_cmd} log1p_total conflict L1_conflict L2_conflict ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "log(1+`label')"
    add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
    add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
    add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
    }

    drop conflict L1_conflict L2_conflict
    gen conflict = (`countvar' > 0)
    gen L1_conflict = L.conflict
    gen L2_conflict = L2.conflict

    qui {
    eststo t3_5: ${hdfe_cmd} any_total conflict forest_loss_share ///
            burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "1[`label'>0]"
    }

    qui {
    eststo t3_6: ${hdfe_cmd} log1p_total conflict forest_loss_share ///
            burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "1[`label'>0]"
    }

    qui {
    eststo t3_7: ${hdfe_cmd} any_total conflict L1_conflict L2_conflict ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "1[`label'>0]"
    add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
    add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
    add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
    }

    qui {
    eststo t3_8: ${hdfe_cmd} log1p_total conflict L1_conflict L2_conflict ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share log_gdp_pc_x_protected_share ///
            log_gdp_pc_sq_x_protected_share ///
            ${road_time}, ///
            absorb(${absorb_rich}) ///
            vce(cluster cell_id_num)
    estadd ysumm, mean sd
    estadd local fe_cell "\checkmark"
    estadd local fe_cy "\checkmark"
    estadd local fe_biome_yr "\checkmark"
    estadd local road_yr "\checkmark"
    estadd local conflict_measure "1[`label'>0]"
    add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
    add_sum_rows, name(pdsi_sum) expr(pdsi_anomaly + L1_pdsi_anomaly + L2_pdsi_anomaly)
    add_sum_rows, name(tmax_sum) expr(tmax_anomaly + L1_tmax_anomaly + L2_tmax_anomaly)
    }

    esttab t3_*, keep(conflict forest_loss_share burned_share cyclone earthquake ///
                 pdsi_anomaly tmax_anomaly log1p_ntl ///
                 protected_share log_gdp_pc_x_protected_share ///
                 log_gdp_pc_sq_x_protected_share) ///
        order(conflict forest_loss_share burned_share cyclone earthquake ///
              pdsi_anomaly tmax_anomaly log1p_ntl ///
              protected_share log_gdp_pc_x_protected_share ///
              log_gdp_pc_sq_x_protected_share) ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        varlabels(conflict "ACLED treatment" ///
                  forest_loss_share "Forest loss" ///
                  burned_share "Burned area" ///
                  cyclone "Cyclone (64kt+)" ///
                  earthquake "Earthquake (M6+)" ///
                  pdsi_anomaly "PDSI anom." ///
                  tmax_anomaly "Tmax anom." ///
                  log1p_ntl "NTL (log)" ///
                  protected_share "Prot. share" ///
                  log_gdp_pc_x_protected_share "ln(GDP pc) x Prot." ///
                  log_gdp_pc_sq_x_protected_share "ln(GDP pc)^2 x Prot.") ///
        stats(conflict_sum_txt conflict_sum_se_txt ///
              pdsi_sum_txt pdsi_sum_se_txt ///
              tmax_sum_txt tmax_sum_se_txt ///
              conflict_measure ymean ysd N r2 ///
              fe_cell fe_cy fe_biome_yr road_yr, ///
              labels("Sum ACLED treatment L0-L2" " " ///
                     "Sum PDSI L0-L2" " " ///
                     "Sum tmax L0-L2" " " ///
                     "ACLED measure" "Dep. var. mean" "Dep. var. SD" ///
                     "Obs." "R-sq." "Cell FE" "Country x Time FE" ///
                     "Biome x Time FE" "Road dens. x Time") ///
              fmt(%s %s %s %s %s %s ///
                  %s %9.4f %9.4f %9.0fc %9.4f %s %s %s %s)) ///
        title("Table 3 ACLED definition: `label'") ///
        mtitles("Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)" "Any" "log(1+N)") ///
        mgroups("Contemporaneous" "With Lags" "Contemporaneous" "With Lags", ///
                pattern(1 0 1 0 1 0 1 0)) ///
        compress

    esttab t3_1 t3_2 t3_3 t3_4 t3_5 t3_6 t3_7 t3_8 ///
        using "$codex_tabledir/tab_acled_defs_${acled_defs_mode_tag}_`countvar'.tex", ///
        replace fragment nomtitles noobs ///
        keep(conflict L1_conflict L2_conflict) ///
        order(conflict L1_conflict L2_conflict) ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        varlabels(conflict "ACLED treatment" ///
                  L1_conflict "ACLED treatment (t-1)" ///
                  L2_conflict "ACLED treatment (t-2)") ///
        stats(conflict_sum_txt conflict_sum_se_txt ymean N r2 ///
              fe_cell fe_cy fe_biome_yr, ///
              labels("Sum L0-L2" "SE" "Dep. var. mean" "Obs." "R-sq." ///
                     "Cell FE" "Country x Time FE" "Biome x Time FE") ///
              fmt(%s %s %9.4f %9.0fc %9.4f %s %s %s))
end

global hdfe_cmd "`hdfe_cmd'"
global absorb_rich "`absorb_rich'"
global road_time "`road_time'"

run_acled_table3, countvar(acled_events_all) label("all ACLED events")
run_acled_table3, countvar(acled_events_violent) label("violent ACLED events")
run_acled_table3, countvar(acled_events_battles) label("battles")
run_acled_table3, countvar(acled_events_explosions) label("explosions/remote violence")
run_acled_table3, countvar(acled_events_vac) label("violence against civilians")
run_acled_table3, countvar(acled_events_protests) label("protests")
run_acled_table3, countvar(acled_events_riots) label("riots")
run_acled_table3, countvar(acled_events_strategic) label("strategic developments")

* Publish all local exhibits to the merged deck on Dropbox.
dd_mirror_outputs

log close
