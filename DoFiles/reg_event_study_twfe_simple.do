* reg_event_study_twfe_simple.do
* Simple TWFE event-study graphs for conflict onset.
*
* No BJS / dCDH / CSDID / continuous-treatment estimators.
*
* Panel selector:
*   "100-yearly"    = baseline 100 km x year panel
*   "50-yearly"     = experimental 50 km x year panel
*   "50-quarterly"  = experimental 50 km x quarter panel
*   "all"           = run all three sequentially
*
* Quarterly mode uses quarter event time. To keep calendar-time comparability
* with the annual -6/+8 window, defaults are -24/+32 quarters and a 40-quarter
* clean pre-onset window.

clear all
set more off
set matsize 11000

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

* HDFE backend. Switch to reghdfejl after confirming Julia works in Stata.
// local hdfe_cmd "reghdfe"
local hdfe_cmd "reghdfejl"

* -------------------------------------------------------------------
* Clicker
* -------------------------------------------------------------------

// local panel_mode "100-yearly"
// local panel_mode "50-yearly"
// local panel_mode "50-quarterly"
local panel_mode "all"

* FE choice:
*   "rich"   = cell + country-time + biome-time FE
*   "simple" = cell + time FE only
// local fe_mode "rich"
local fe_mode "simple"

* Quarterly-only seasonal hardening:
*   "on"  = add cell x quarter-of-year FE in quarterly rich-FE runs
*   "off" = no cell-season FE
// local quarterly_cell_season_fe "on"
local quarterly_cell_season_fe "off"

* Event-window choice:
*   "compact" = main figure: annual -4/+5 with 5-year clean pre-window;
*               quarterly -8/+12 with 8-quarter clean pre-window
*   "long"    = sensitivity: annual -6/+8 with 10-year clean pre-window;
*               quarterly -24/+32 with 40-quarter clean pre-window
local window_mode "compact"
// local window_mode "long"

if !inlist("`panel_mode'", "100-yearly", "50-yearly", "50-quarterly", "all") {
    di as error "Unknown panel_mode: `panel_mode'"
    error 198
}
if !inlist("`fe_mode'", "rich", "simple") {
    di as error "Unknown fe_mode: `fe_mode'"
    error 198
}
if !inlist("`quarterly_cell_season_fe'", "on", "off") {
    di as error "Unknown quarterly_cell_season_fe: `quarterly_cell_season_fe'"
    error 198
}
if !inlist("`window_mode'", "compact", "long") {
    di as error "Unknown window_mode: `window_mode'"
    error 198
}

capture log close
log using "`proj'/Logs/reg_event_study_twfe_simple.log", replace text

capture mkdir "`proj'/Output"
capture mkdir "`proj'/Output/figures"
capture mkdir "`proj'/Output/figures/event_study"
capture mkdir "`proj'/Output/figures/event_study/twfe_simple"

foreach pkg in reghdfe ftools coefplot estout {
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

if "`panel_mode'" == "all" {
    local modes "100-yearly 50-yearly 50-quarterly"
}
else {
    local modes "`panel_mode'"
}

foreach mode of local modes {

    di _n as text "============================================================"
    di as text "TWFE simple event study: `mode'"
    di as text "============================================================"

    if "`mode'" == "100-yearly" {
        local panel_path "`proj'/Data/analysis/BOLD_regressor_panel.dta"
        local mode_tag "100km_year"
        local est_tag "m100y"
        local panel_freq "year"
        local periods_per_year 1
    }
    else if "`mode'" == "50-yearly" {
        local panel_path "`proj'/Data/analysis/tests_spatial_time/BOLD_regressor_panel_50km_year.dta"
        local mode_tag "50km_year"
        local est_tag "m50y"
        local panel_freq "year"
        local periods_per_year 1
    }
    else if "`mode'" == "50-quarterly" {
        local panel_path "`proj'/Data/analysis/tests_spatial_time/BOLD_regressor_panel_50km_quarter.dta"
        local mode_tag "50km_quarter"
        local est_tag "m50q"
        local panel_freq "quarter"
        local periods_per_year 4
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
        local time_label "quarter"
        local time_title "Quarters from conflict onset"
    }
    else {
        local timevar "year"
        local time_label "year"
        local time_title "Years from conflict onset"
    }
    xtset cell_id_num `timevar'

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
        c.log_gdp_pc_sq#c.protected_share

    * Rich FE are the reg_spec1 preferred structure, with time generalized to
    * year or quarter depending on panel mode.
    egen country_time = group(country_num `timevar')
    egen biome_time   = group(resolve_biome_num `timevar')
    replace country_time = . if missing(country_num)
    replace biome_time   = . if missing(resolve_biome_num)

    if "`fe_mode'" == "rich" {
        local absorb_main "cell_id_num country_time biome_time"
        local extra_fe_title ""
        if "`panel_freq'" == "quarter" & "`quarterly_cell_season_fe'" == "on" {
            egen cell_season = group(cell_id_num quarter)
            local absorb_main "`absorb_main' cell_season"
            local extra_fe_title " + cell-quarter-season FE"
        }
        local rhs_controls "`controls_main' c.road_density_km_per_km2#i.`timevar'"
        local fe_tag "richfe_controls"
        local fe_title "cell + country-time + biome-time FE"
    }
    else {
        local absorb_main "cell_id_num `timevar'"
        local rhs_controls ""
        local extra_fe_title ""
        local fe_tag "simplefe"
        local fe_title "cell + time FE"
    }

    * Compact is the main event-study window. Long keeps the earlier wide
    * window as a sensitivity check.
    if "`window_mode'" == "compact" {
        if "`panel_freq'" == "quarter" {
            local clean_periods = 8
            local lead_periods  = 8
            local lag_periods   = 12
        }
        else {
            local clean_periods = 5
            local lead_periods  = 4
            local lag_periods   = 5
        }
    }
    else {
        local clean_periods = 10 * `periods_per_year'
        local lead_periods  = 6  * `periods_per_year'
        local lag_periods   = 8  * `periods_per_year'
    }

    replace ucdp_any_all = 0 if missing(ucdp_any_all)

    gen byte clean_pre_conflict = 1
    forvalues k = 1/`clean_periods' {
        replace clean_pre_conflict = 0 if L`k'.ucdp_any_all != 0 | missing(L`k'.ucdp_any_all)
    }

    gen byte onset_flag_conflict = (ucdp_any_all == 1 & clean_pre_conflict == 1)
    bysort cell_id_num (`timevar'): egen onset_time_conflict = ///
        min(cond(onset_flag_conflict == 1, `timevar', .))
    gen et_conflict = `timevar' - onset_time_conflict

    di _n as text "Panel file: `panel_path'"
    di as text "Time variable: `timevar'"
    di as text "FE: `fe_title'`extra_fe_title'"
    di as text "HDFE backend: `hdfe_cmd'"
    di as text "Window mode: `window_mode'"
    if "`fe_mode'" == "rich" {
        di as text "Controls: reg_spec1 non-conflict shocks + economic/environmental controls"
        if "`panel_freq'" == "quarter" {
            di as text "Quarterly cell-season FE: `quarterly_cell_season_fe'"
        }
    }
    di as text "Clean pre-window: `clean_periods' `time_label'(s)"
    di as text "Event window: -`lead_periods' to +`lag_periods' `time_label'(s), tau=-1 omitted"

    preserve
        bysort cell_id_num: keep if _n == 1
        count if !missing(onset_time_conflict)
        di as text "Treated cells with clean first conflict onset: " as result r(N)
    restore

    * Build lead/lag dummies. tau=-1 is omitted reference. Never-treated cells
    * have all event dummies equal to zero.
    local plotcoefs ""
    local precoefs ""
    local postcoefs ""
    local postsum ""
    local coeflabels ""

    capture drop lead* lag*
    gen byte lead`lead_periods' = (et_conflict <= -`lead_periods') if !missing(et_conflict)
    replace lead`lead_periods' = 0 if missing(lead`lead_periods')
    local plotcoefs "`plotcoefs' lead`lead_periods'"
    local precoefs "`precoefs' lead`lead_periods'"
    local coeflabels `coeflabels' lead`lead_periods' = "-`lead_periods'+"

    local lastlead = `lead_periods' - 1
    forvalues j = `lastlead'(-1)2 {
        gen byte lead`j' = (et_conflict == -`j') if !missing(et_conflict)
        replace lead`j' = 0 if missing(lead`j')
        local plotcoefs "`plotcoefs' lead`j'"
        local precoefs "`precoefs' lead`j'"
        local coeflabels `coeflabels' lead`j' = "-`j'"
    }

    forvalues j = 0/`lag_periods' {
        if `j' == `lag_periods' {
            gen byte lag`j' = (et_conflict >= `j') if !missing(et_conflict)
            local label "+`j'+"
        }
        else {
            gen byte lag`j' = (et_conflict == `j') if !missing(et_conflict)
            local label "+`j'"
        }
        replace lag`j' = 0 if missing(lag`j')
        local plotcoefs "`plotcoefs' lag`j'"
        local postcoefs "`postcoefs' lag`j'"
        if "`postsum'" == "" {
            local postsum "lag`j'"
        }
        else {
            local postsum "`postsum' + lag`j'"
        }
        local coeflabels `coeflabels' lag`j' = "`label'"
    }

    local xline_pos = `lead_periods' - 0.5

    est clear
    foreach lhs in any_total log1p_total {

        if "`lhs'" == "any_total" {
            local lhs_title "Any BOLD records"
            local ytitle "Effect on 1[total records > 0]"
            local out_stub "any_total"
        }
        else {
            local lhs_title "Log BOLD records"
            local ytitle "Effect on log(1 + total records)"
            local out_stub "log1p_total"
        }

        di _n as text "--- TWFE event study: `mode', `lhs' ---"

        qui `hdfe_cmd' `lhs' `plotcoefs' `rhs_controls', ///
            absorb(`absorb_main') ///
            vce(cluster cell_id_num)

        estimates store twfe_`est_tag'_`out_stub'

        capture test `precoefs'
        if !_rc {
            local pre_p = r(p)
            local pre_p_txt : display %5.3f `pre_p'
            di as text "Joint pre-trend p-value: " as result %6.4f `pre_p'
        }
        else {
            local pre_p_txt "n/a"
        }

        capture test `postcoefs'
        if !_rc {
            local post_p = r(p)
            local post_p_txt : display %5.3f `post_p'
            di as text "Joint post-treatment p-value: " as result %6.4f `post_p'
        }
        else {
            local post_p_txt "n/a"
        }

        capture lincom (`postsum') / (`lag_periods' + 1)
        if !_rc {
            local avg_post = r(estimate)
            local avg_post_se = r(se)
            local avg_post_p = r(p)
            local avg_post_txt : display %6.4f `avg_post'
            local avg_post_se_txt : display %6.4f `avg_post_se'
            local avg_post_p_txt : display %5.3f `avg_post_p'
            di as text "Average displayed post coefficient: " ///
                as result %8.4f `avg_post' ///
                as text " (SE " as result %8.4f `avg_post_se' ///
                as text ", p " as result %6.4f `avg_post_p' as text ")"
        }
        else {
            local avg_post_txt "n/a"
            local avg_post_se_txt "n/a"
            local avg_post_p_txt "n/a"
        }

        local graph_name "g_twfe_`est_tag'_`out_stub'"

        coefplot (twfe_`est_tag'_`out_stub', label("TWFE") ///
                msymbol(O) mcolor(navy) ciopts(lcolor(navy))), ///
            keep(`plotcoefs') ///
            order(`plotcoefs') ///
            coeflabels(`coeflabels') ///
            vertical ///
            yline(0, lpattern(dash) lcolor(black)) ///
            xline(`xline_pos', lpattern(dot) lcolor(gs8)) ///
            xtitle("`time_title' (tau=-1 reference)") ///
            ytitle("`ytitle'") ///
            title("TWFE event study: conflict onset, `lhs_title'", size(medium)) ///
            subtitle("`mode', `fe_title'`extra_fe_title', `window_mode' window", size(small)) ///
            note("Pre-trend joint p=`pre_p_txt'; post joint p=`post_p_txt'; avg post coef=`avg_post_txt' (SE=`avg_post_se_txt', p=`avg_post_p_txt')." ///
                 "Avg post is the simple mean of displayed post-onset coefficients; tau=-1 is reference.", ///
                 size(vsmall)) ///
            msize(vsmall) ciopts(recast(rcap)) ///
            xlabel(, angle(45) labsize(vsmall)) ///
            legend(off) ///
            name(`graph_name', replace)

        graph save "`proj'/Output/figures/event_study/twfe_simple/twfe_`mode_tag'_`fe_tag'_`window_mode'_`out_stub'.gph", replace
        graph export "`proj'/Output/figures/event_study/twfe_simple/twfe_`mode_tag'_`fe_tag'_`window_mode'_`out_stub'.png", ///
            replace width(2600) height(1500)
        graph export "`proj'/Output/figures/event_study/twfe_simple/twfe_`mode_tag'_`fe_tag'_`window_mode'_`out_stub'.pdf", replace
    }
}

log close
