* reg_conflict_signal_decomposition.do
* Diagnose where the reg_spec1 conflict signal comes from.
*
* This is not an event-study file. It reruns reg_spec1-style distributed-lag
* regressions under progressively stricter samples and adds exposure-stock
* specifications to distinguish current conflict from repeated exposure.

clear all
set more off
set matsize 11000

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

* -------------------------------------------------------------------
* Clickers
* -------------------------------------------------------------------

// local hdfe_cmd "reghdfe"
local hdfe_cmd "reghdfejl"

* "100-yearly", "50-yearly", "50-quarterly", or "all"
local panel_mode "all"

* Quarterly-only seasonal hardening for rich-FE diagnostics.
// local quarterly_cell_season_fe "on"
local quarterly_cell_season_fe "off"

if !inlist("`panel_mode'", "100-yearly", "50-yearly", "50-quarterly", "all") {
    di as error "Unknown panel_mode: `panel_mode'"
    error 198
}
if !inlist("`quarterly_cell_season_fe'", "on", "off") {
    di as error "Unknown quarterly_cell_season_fe: `quarterly_cell_season_fe'"
    error 198
}

capture log close
log using "`proj'/Logs/reg_conflict_signal_decomposition.log", replace text

capture mkdir "`proj'/Exhibits"
capture mkdir "`proj'/Exhibits/tables"

foreach pkg in reghdfe ftools estout {
    capture which `pkg'
    if _rc {
        di as text "Installing `pkg' from SSC ..."
        capture ssc install `pkg', replace
    }
}

capture which `hdfe_cmd'
if _rc {
    di as error "Requested HDFE backend `hdfe_cmd' is not installed."
    if "`hdfe_cmd'" == "reghdfejl" {
        di as text "Install in Stata with: ssc install julia; ssc install reghdfejl"
    }
    error 111
}

capture program drop add_lag_sum
program define add_lag_sum
    quietly lincom conflict + L1_conflict + L2_conflict
    estadd scalar sum_l0_l2 = r(estimate)
    estadd scalar sum_l0_l2_se = r(se)
    estadd scalar sum_l0_l2_p = r(p)
end

if "`panel_mode'" == "all" {
    local modes "100-yearly 50-yearly 50-quarterly"
}
else {
    local modes "`panel_mode'"
}

foreach mode of local modes {

    di _n as text "============================================================"
    di as text "Conflict signal decomposition: `mode'"
    di as text "============================================================"

    if "`mode'" == "100-yearly" {
        local panel_path "`proj'/Data/analysis/BOLD_regressor_panel.dta"
        local mode_tag "100km_year"
        local panel_freq "year"
        local clean_periods = 5
    }
    else if "`mode'" == "50-yearly" {
        local panel_path "`proj'/Data/analysis/tests_spatial_time/BOLD_regressor_panel_50km_year.dta"
        local mode_tag "50km_year"
        local panel_freq "year"
        local clean_periods = 5
    }
    else if "`mode'" == "50-quarterly" {
        local panel_path "`proj'/Data/analysis/tests_spatial_time/BOLD_regressor_panel_50km_quarter.dta"
        local mode_tag "50km_quarter"
        local panel_freq "quarter"
        local clean_periods = 8
    }

    capture confirm file "`panel_path'"
    if _rc {
        di as error "Missing analysis panel: `panel_path'"
        error 601
    }

    use "`panel_path'", clear
    keep if year >= 2005 & year <= 2023

    encode cell_id, gen(cell_id_num)
    encode iso_a3, gen(country_num)

    if "`panel_freq'" == "quarter" {
        capture confirm variable quarter
        if _rc {
            di as error "`mode' requires a quarter variable."
            error 111
        }
        gen time_id = yq(year, quarter)
        format time_id %tq
        local timevar "time_id"
    }
    else {
        local timevar "year"
    }
    xtset cell_id_num `timevar'

    * Match reg_spec1 controls.
    gen burned_share = burned_area_km2 / cell_area_km2
    replace burned_share = 0 if missing(burned_share)

    replace forest_loss_share = 0 if missing(forest_loss_share)
    gen cyclone = ibtracs_any_64kt
    replace cyclone = 0 if missing(cyclone)
    gen earthquake = (comcat_events_m6 > 0) if !missing(comcat_events_m6)
    replace earthquake = 0 if missing(earthquake)
    replace log1p_ntl = 0 if missing(log1p_ntl)

    gen log_gdp_pc = log(gdp_pcap_current_usd)
    gen log_gdp_pc_sq = log_gdp_pc^2

    local controls_main ///
        forest_loss_share burned_share cyclone earthquake ///
        pdsi_anomaly tmax_anomaly log1p_ntl ///
        protected_share c.log_gdp_pc#c.protected_share ///
        c.log_gdp_pc_sq#c.protected_share ///
        c.road_density_km_per_km2#i.`timevar'

    egen country_time = group(country_num `timevar')
    egen biome_time   = group(resolve_biome_num `timevar')
    replace country_time = . if missing(country_num)
    replace biome_time   = . if missing(resolve_biome_num)

    local absorb_main "cell_id_num country_time biome_time"
    local fe_desc "cell + country-time + biome-time FE"
    if "`panel_freq'" == "quarter" & "`quarterly_cell_season_fe'" == "on" {
        egen cell_season = group(cell_id_num quarter)
        local absorb_main "`absorb_main' cell_season"
        local fe_desc "`fe_desc' + cell-quarter-season FE"
    }

    replace ucdp_any_all = 0 if missing(ucdp_any_all)
    replace ucdp_events_all = 0 if missing(ucdp_events_all)

    gen conflict_log = log(1 + ucdp_events_all)
    gen conflict_any = ucdp_any_all

    gen L1_conflict_log = L.conflict_log
    gen L2_conflict_log = L2.conflict_log
    gen L1_conflict_any = L.conflict_any
    gen L2_conflict_any = L2.conflict_any

    bysort cell_id_num: egen any_conflict_cell = max(conflict_any)
    bysort cell_id_num: egen baseline_conflict_cell = max(cond(year == 2005, conflict_any, .))
    replace baseline_conflict_cell = 0 if missing(baseline_conflict_cell)

    gen byte clean_pre_conflict = 1
    forvalues k = 1/`clean_periods' {
        replace clean_pre_conflict = 0 if L`k'.conflict_any != 0 | missing(L`k'.conflict_any)
    }
    gen byte onset_flag_conflict = (conflict_any == 1 & clean_pre_conflict == 1)
    bysort cell_id_num (`timevar'): egen onset_time_conflict = min(cond(onset_flag_conflict == 1, `timevar', .))
    gen byte clean_treated = !missing(onset_time_conflict)
    gen byte never_conflict = (any_conflict_cell == 0)

    bysort cell_id_num (`timevar'): gen cum_any_conflict = sum(conflict_any)
    bysort cell_id_num (`timevar'): gen cum_log_conflict = sum(conflict_log)
    gen L1_cum_any_conflict = L.cum_any_conflict
    gen L1_cum_log_conflict = L.cum_log_conflict
    replace L1_cum_any_conflict = 0 if missing(L1_cum_any_conflict)
    replace L1_cum_log_conflict = 0 if missing(L1_cum_log_conflict)

    preserve
        bysort cell_id_num: keep if _n == 1
        count
        local cells_all = r(N)
        count if any_conflict_cell == 1
        local cells_ever = r(N)
        count if baseline_conflict_cell == 1
        local cells_left = r(N)
        count if clean_treated == 1
        local cells_clean = r(N)
        count if never_conflict == 1
        local cells_never = r(N)
    restore

    di as text "Panel file: `panel_path'"
    di as text "Time variable: `timevar'"
    di as text "FE: `fe_desc'"
    di as text "Clean pre-window for first-onset diagnostic: `clean_periods'"
    di as text "Cells total: " as result `cells_all'
    di as text "Ever-conflict cells: " as result `cells_ever'
    di as text "Conflict in 2005 cells (left-censored proxy): " as result `cells_left'
    di as text "Clean first-onset cells: " as result `cells_clean'
    di as text "Never-conflict cells: " as result `cells_never'

    * ---------------------------------------------------------------
    * Table A: distributed-lag decomposition by sample restriction
    * ---------------------------------------------------------------

    foreach measure in log any {
        if "`measure'" == "log" {
            local measure_label "log(1+events)"
            local cvar "conflict_log"
            local l1var "L1_conflict_log"
            local l2var "L2_conflict_log"
        }
        else {
            local measure_label "1[events>0]"
            local cvar "conflict_any"
            local l1var "L1_conflict_any"
            local l2var "L2_conflict_any"
        }

        est clear
        local models ""

        foreach sample in full ever noleft clean {
            foreach lhs in any_total log1p_total {
                preserve
                    if "`sample'" == "ever" {
                        keep if any_conflict_cell == 1
                        local sample_label "Ever-conflict cells only"
                    }
                    else if "`sample'" == "noleft" {
                        keep if baseline_conflict_cell == 0
                        local sample_label "Drop conflict-in-2005 cells"
                    }
                    else if "`sample'" == "clean" {
                        keep if never_conflict == 1 | clean_treated == 1
                        local sample_label "Clean first-onset + never-conflict"
                    }
                    else {
                        local sample_label "Full panel"
                    }

                    gen conflict = `cvar'
                    gen L1_conflict = `l1var'
                    gen L2_conflict = `l2var'

                    qui `hdfe_cmd' `lhs' conflict L1_conflict L2_conflict `controls_main', ///
                        absorb(`absorb_main') ///
                        vce(cluster cell_id_num)

                    local model_name "dl_`measure'_`sample'_"
                    if "`lhs'" == "any_total" {
                        local model_name "`model_name'any"
                        local lhs_label "Any records"
                    }
                    else {
                        local model_name "`model_name'log"
                        local lhs_label "log(1+records)"
                    }

                    estimates store `model_name'
                    qui estadd ysumm, mean sd
                    qui add_lag_sum
                    qui estadd local sample "`sample_label'"
                    qui estadd local lhs_label "`lhs_label'"
                    qui estadd local conflict_measure "`measure_label'"
                    qui estadd local fe "`fe_desc'"
                    local models "`models' `model_name'"
                restore
            }
        }

        esttab `models', ///
            keep(conflict L1_conflict L2_conflict) ///
            order(conflict L1_conflict L2_conflict) ///
            coeflabels(conflict "Conflict" ///
                       L1_conflict "Conflict t-1" ///
                       L2_conflict "Conflict t-2") ///
            se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
            stats(sum_l0_l2 sum_l0_l2_se sum_l0_l2_p ymean ysd N r2 ///
                  sample lhs_label conflict_measure fe, ///
                  labels("Sum conflict L0-L2" "SE: sum L0-L2" "p: sum L0-L2" ///
                         "Dep. var. mean" "Dep. var. SD" "Obs." "R-sq." ///
                         "Sample" "LHS" "Conflict measure" "FE") ///
                  fmt(%9.4f %9.4f %9.4f %9.4f %9.4f %9.0fc %9.4f ///
                      %s %s %s %s)) ///
            title("Conflict signal decomposition: `mode', `measure_label' distributed lags") ///
            compress

        esttab `models' using "`proj'/Exhibits/tables/conflict_signal_decomp_`mode_tag'_`measure'.tex", ///
            replace ///
            keep(conflict L1_conflict L2_conflict) ///
            order(conflict L1_conflict L2_conflict) ///
            coeflabels(conflict "Conflict" ///
                       L1_conflict "Conflict t-1" ///
                       L2_conflict "Conflict t-2") ///
            se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
            stats(sum_l0_l2 sum_l0_l2_se sum_l0_l2_p ymean ysd N r2 ///
                  sample lhs_label conflict_measure fe, ///
                  labels("Sum conflict L0-L2" "SE: sum L0-L2" "p: sum L0-L2" ///
                         "Dep. var. mean" "Dep. var. SD" "Obs." "R-sq." ///
                         "Sample" "LHS" "Conflict measure" "FE") ///
                  fmt(%9.4f %9.4f %9.4f %9.4f %9.4f %9.0fc %9.4f ///
                      %s %s %s %s)) ///
            title("Conflict signal decomposition: `mode', `measure_label' distributed lags") ///
            compress
    }

    * ---------------------------------------------------------------
    * Table B: current conflict versus accumulated exposure
    * ---------------------------------------------------------------

    est clear
    local stock_models ""
    foreach lhs in any_total log1p_total {
        foreach measure in any log {
            if "`measure'" == "any" {
                local current "conflict_any"
                local stock "L1_cum_any_conflict"
                local measure_label "Binary exposure stock"
            }
            else {
                local current "conflict_log"
                local stock "L1_cum_log_conflict"
                local measure_label "Intensity exposure stock"
            }

            qui `hdfe_cmd' `lhs' `current' `stock' `controls_main', ///
                absorb(`absorb_main') ///
                vce(cluster cell_id_num)

            local model_name "stk_`measure'_"
            if "`lhs'" == "any_total" {
                local model_name "`model_name'any"
                local lhs_label "Any records"
            }
            else {
                local model_name "`model_name'log"
                local lhs_label "log(1+records)"
            }

            estimates store `model_name'
            qui estadd ysumm, mean sd
            qui estadd local lhs_label "`lhs_label'"
            qui estadd local exposure "`measure_label'"
            qui estadd local fe "`fe_desc'"
            local stock_models "`stock_models' `model_name'"
        }
    }

    esttab `stock_models', ///
        keep(conflict_any L1_cum_any_conflict conflict_log L1_cum_log_conflict) ///
        order(conflict_any L1_cum_any_conflict conflict_log L1_cum_log_conflict) ///
        coeflabels(conflict_any "Current conflict any" ///
                   L1_cum_any_conflict "Lagged cumulative conflict periods" ///
                   conflict_log "Current log(1+events)" ///
                   L1_cum_log_conflict "Lagged cumulative log events") ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        stats(ymean ysd N r2 lhs_label exposure fe, ///
              labels("Dep. var. mean" "Dep. var. SD" "Obs." "R-sq." ///
                     "LHS" "Exposure model" "FE") ///
              fmt(%9.4f %9.4f %9.0fc %9.4f %s %s %s)) ///
        title("Conflict signal decomposition: `mode', current vs accumulated exposure") ///
        compress

    esttab `stock_models' using "`proj'/Exhibits/tables/conflict_signal_stock_`mode_tag'.tex", ///
        replace ///
        keep(conflict_any L1_cum_any_conflict conflict_log L1_cum_log_conflict) ///
        order(conflict_any L1_cum_any_conflict conflict_log L1_cum_log_conflict) ///
        coeflabels(conflict_any "Current conflict any" ///
                   L1_cum_any_conflict "Lagged cumulative conflict periods" ///
                   conflict_log "Current log(1+events)" ///
                   L1_cum_log_conflict "Lagged cumulative log events") ///
        se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
        stats(ymean ysd N r2 lhs_label exposure fe, ///
              labels("Dep. var. mean" "Dep. var. SD" "Obs." "R-sq." ///
                     "LHS" "Exposure model" "FE") ///
              fmt(%9.4f %9.4f %9.0fc %9.4f %s %s %s)) ///
        title("Conflict signal decomposition: `mode', current vs accumulated exposure") ///
        compress
}

log close
