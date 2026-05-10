* reg_event_study_publications_5yr.do
* Conflict -> downstream corrected BOLD publication-yield outcomes
* Uses:
*   - any_bold_pub_total_0_5yr
*   - log1p_bold_pub_total_0_5yr
*
* Publication outcomes require bold_pub_complete_0_5yr == 1, so the usable
* outcome sample ends before the full panel endpoint. For that reason the
* conflict onset rule uses K=5 rather than K=10, and the event-study window is
* shortened to -5/+8.

clear all
set more off
set matsize 11000

global proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

* -------------------------------------------------------------------
* FE clicker
*   Set to "rich"   for cell + country-year + biome-year FE
*   Set to "simple" for cell + year FE only
* -------------------------------------------------------------------

* local fe_mode "rich"
local fe_mode "simple"

if !inlist("`fe_mode'", "rich", "simple") {
    display as error "fe_mode must be either rich or simple"
    error 198
}

capture log close
log using "$proj/Logs/reg_event_study_publications_5yr.log", replace text

capture mkdir "$proj/Output"
capture mkdir "$proj/Output/figures"
capture mkdir "$proj/Output/figures/event_study"

foreach pkg in did_imputation did_multiplegt_dyn csdid drdid coefplot ///
               matsort estout reghdfe ftools {
    capture which `pkg'
    if _rc {
        display as text "Installing `pkg' from SSC ..."
        capture ssc install `pkg', replace
    }
}

use "$proj/Data/analysis/BOLD_regressor_panel.dta", clear
keep if year >= 2005 & year <= 2023

capture confirm variable bold_pub_complete_0_5yr
if _rc {
    display as error "bold_pub_complete_0_5yr not found in BOLD_regressor_panel.dta"
    error 111
}

keep if bold_pub_complete_0_5yr == 1

encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)
xtset cell_id_num year

replace ucdp_any_all      = 0 if missing(ucdp_any_all)
replace any_burned        = 0 if missing(any_burned)
replace ibtracs_any_64kt  = 0 if missing(ibtracs_any_64kt)

summarize bold_pub_total_0_5yr any_bold_pub_total_0_5yr log1p_bold_pub_total_0_5yr

gen log1p_conflict = log(1 + ucdp_events_all)
egen country_year = group(country_num year)
egen biome_year   = group(resolve_biome_num year)

if "`fe_mode'" == "rich" {
    local absorb_main "cell_id_num country_year biome_year"
    local did_fe "cell_id_num country_year biome_year"
    local fe_label_year " "
    local fe_label_cy "\checkmark"
    local fe_label_biome "\checkmark"
    local fe_mode_label "cell + country-year + biome-year FE"
    local dcdh_fe_note "* via residualization"
}
else {
    local absorb_main "cell_id_num year"
    local did_fe "cell_id_num year"
    local fe_label_year "\checkmark"
    local fe_label_cy " "
    local fe_label_biome " "
    local fe_mode_label "cell + year FE"
    local dcdh_fe_note " "
}

display _n "{txt}=== FE mode: `fe_mode_label' ==="

* Short estimate names to stay below Stata's internal _est_* name limit.
local est_twfe_any      "twfe_anypub"
local est_twfe_log      "twfe_logpub"
local est_bjs_any       "bjs_anypub"
local est_bjs_log       "bjs_logpub"
local est_cont          "cont_logpub"
local est_dcdh          "dcdh_logpub"
local est_cs            "cs_logpub"
local est_twfe_conflict "twfe_c_logpub"
local est_twfe_drought  "twfe_d_logpub"
local est_twfe_fire     "twfe_f_logpub"
local est_bjs_drought   "bjs_d_logpub"
local est_bjs_fire      "bjs_f_logpub"

capture program drop add_avg_rows
program define add_avg_rows
    syntax , NAME(name) EXPR(string asis) DIVISOR(integer)
    qui lincom (`expr') / `divisor'
    qui estadd scalar `name'    = r(estimate)
    qui estadd scalar `name'_se = r(se)
    qui estadd scalar `name'_p  = r(p)
    local b = r(estimate)
    local se = r(se)
    local p = r(p)
    local star ""
    if `p' < 0.01      local star "***"
    else if `p' < 0.05 local star "**"
    else if `p' < 0.10 local star "*"
    local btxt  : display %9.4f `b'
    local btxt  = strtrim("`btxt'")
    local setxt : display %9.4f `se'
    local setxt = strtrim("`setxt'")
    qui estadd local `name'_txt    "`btxt'`star'"
    qui estadd local `name'_se_txt "(`setxt')"
end

capture program drop add_sum_rows
program define add_sum_rows
    syntax , NAME(name) EXPR(string asis)
    qui lincom `expr'
    qui estadd scalar `name'    = r(estimate)
    qui estadd scalar `name'_se = r(se)
    qui estadd scalar `name'_p  = r(p)
    local b = r(estimate)
    local se = r(se)
    local p = r(p)
    local star ""
    if `p' < 0.01      local star "***"
    else if `p' < 0.05 local star "**"
    else if `p' < 0.10 local star "*"
    local btxt  : display %9.4f `b'
    local btxt  = strtrim("`btxt'")
    local setxt : display %9.4f `se'
    local setxt = strtrim("`setxt'")
    qui estadd local `name'_txt    "`btxt'`star'"
    qui estadd local `name'_se_txt "(`setxt')"
end

* -------------------------------------------------------------------
* Onset construction
* -------------------------------------------------------------------

* Conflict uses K=5 here because the complete 5-year publication sample ends
* earlier than the full panel, making K=10 too restrictive for dynamics.
gen lookback_conflict = 1
forvalues k = 1/5 {
    replace lookback_conflict = 0 if L`k'.ucdp_any_all != 0 | missing(L`k'.ucdp_any_all)
}
gen onset_flag_conflict = (ucdp_any_all == 1 & lookback_conflict == 1)
bysort cell_id_num (year): egen onset_year_conflict = ///
    min(cond(onset_flag_conflict == 1, year, .))
gen Ei_conflict = onset_year_conflict
gen et_conflict = year - Ei_conflict

gen lookback_drought = 1
forvalues k = 1/5 {
    replace lookback_drought = 0 if L`k'.pdsi_anomaly <= -1 | missing(L`k'.pdsi_anomaly)
}
gen onset_flag_drought = (pdsi_anomaly < -2 & lookback_drought == 1) if !missing(pdsi_anomaly)
bysort cell_id_num (year): egen onset_year_drought = ///
    min(cond(onset_flag_drought == 1, year, .))
gen Ei_drought = onset_year_drought
gen et_drought = year - Ei_drought

gen lookback_fire = 1
forvalues k = 1/3 {
    replace lookback_fire = 0 if L`k'.any_burned != 0 | missing(L`k'.any_burned)
}
gen onset_flag_fire = (any_burned == 1 & lookback_fire == 1)
bysort cell_id_num (year): egen onset_year_fire = ///
    min(cond(onset_flag_fire == 1, year, .))
gen Ei_fire = onset_year_fire
gen et_fire = year - Ei_fire

est clear

* -------------------------------------------------------------------
* Step 1: TWFE event study
* -------------------------------------------------------------------

display _n "{txt}=== STEP 1: TWFE event-study (5yr publications) ==="

foreach v in lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
    capture drop `v'
}
gen byte lead5 = (et_conflict <= -5) if !missing(et_conflict)
gen byte lead4 = (et_conflict == -4) if !missing(et_conflict)
gen byte lead3 = (et_conflict == -3) if !missing(et_conflict)
gen byte lead2 = (et_conflict == -2) if !missing(et_conflict)
gen byte lag0  = (et_conflict == 0)  if !missing(et_conflict)
gen byte lag1  = (et_conflict == 1)  if !missing(et_conflict)
gen byte lag2  = (et_conflict == 2)  if !missing(et_conflict)
gen byte lag3  = (et_conflict == 3)  if !missing(et_conflict)
gen byte lag4  = (et_conflict == 4)  if !missing(et_conflict)
gen byte lag5  = (et_conflict == 5)  if !missing(et_conflict)
gen byte lag6  = (et_conflict == 6)  if !missing(et_conflict)
gen byte lag7  = (et_conflict == 7)  if !missing(et_conflict)
gen byte lag8  = (et_conflict >= 8)  if !missing(et_conflict)
foreach v in lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
    replace `v' = 0 if missing(`v')
}

foreach lhs in any_bold_pub_total_0_5yr log1p_bold_pub_total_0_5yr {
    qui reghdfe `lhs' ///
        lead5 lead4 lead3 lead2 ///
        lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8, ///
        absorb(`absorb_main') ///
        vce(cluster cell_id_num)
    if "`lhs'" == "any_bold_pub_total_0_5yr" estimates store `est_twfe_any'
    else                                      estimates store `est_twfe_log'
    qui test lead5 lead4 lead3 lead2
    qui estadd scalar pretrend_p = r(p)
    add_avg_rows, name(att_avg_03) expr(lag0 + lag1 + lag2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(lag0 + lag1 + lag2 + lag3 + lag4) divisor(5)
    add_avg_rows, name(att_avg_08) expr(lag0 + lag1 + lag2 + lag3 + lag4 + lag5 + lag6 + lag7 + lag8) divisor(9)
    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "TWFE event-study"
    estadd local treatment    "Binary onset (UCDP, K=5)"
    estadd local lhs_label    "`lhs'"
    estadd local shock        "conflict"
}

* -------------------------------------------------------------------
* Step 2: BJS event study
* -------------------------------------------------------------------

display _n "{txt}=== STEP 2: BJS event-study (5yr publications) ==="

foreach lhs in any_bold_pub_total_0_5yr log1p_bold_pub_total_0_5yr {
    qui did_imputation `lhs' cell_id_num year Ei_conflict, ///
        fe(`did_fe') horizons(0/8) pretrends(4) ///
        cluster(cell_id_num) autosample
    if "`lhs'" == "any_bold_pub_total_0_5yr" estimates store `est_bjs_any'
    else                                      estimates store `est_bjs_log'
    qui estadd scalar pretrend_p = e(pre_p)
    add_avg_rows, name(att_avg_03) expr(tau0 + tau1 + tau2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(tau0 + tau1 + tau2 + tau3 + tau4) divisor(5)
    add_avg_rows, name(att_avg_08) expr(tau0 + tau1 + tau2 + tau3 + tau4 + tau5 + tau6 + tau7 + tau8) divisor(9)
    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "BJS imputation"
    estadd local treatment    "Binary onset (K=5)"
    estadd local lhs_label    "`lhs'"
    estadd local shock        "conflict"
}

* -------------------------------------------------------------------
* Step 3: continuous conflict intensity
* -------------------------------------------------------------------

display _n "{txt}=== STEP 3: DL continuous DID (log publications) ==="

forvalues k = 1/5 {
    capture drop F`k'_log1p_conflict
    capture drop L`k'_log1p_conflict
    gen F`k'_log1p_conflict = F`k'.log1p_conflict
    gen L`k'_log1p_conflict = L`k'.log1p_conflict
}

qui reghdfe log1p_bold_pub_total_0_5yr ///
    F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict F1_log1p_conflict ///
    log1p_conflict ///
    L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict L5_log1p_conflict, ///
    absorb(`absorb_main') ///
    vce(cluster cell_id_num)
estimates store `est_cont'
add_sum_rows, name(conflict_sum_03) expr(log1p_conflict + L1_log1p_conflict + L2_log1p_conflict)
add_sum_rows, name(conflict_sum_05) expr(log1p_conflict + L1_log1p_conflict + L2_log1p_conflict + L3_log1p_conflict + L4_log1p_conflict)
qui test F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict F1_log1p_conflict
estadd scalar pretrend_p = r(p)
estadd local fe_cell      "\checkmark"
estadd local fe_year      "`fe_label_year'"
estadd local fe_cy        "`fe_label_cy'"
estadd local fe_biome_yr  "`fe_label_biome'"
estadd local estimator    "DL continuous"
estadd local treatment    "Intensity log(1+events)"
estadd local lhs_label    "log1p_bold_pub_total_0_5yr"

* -------------------------------------------------------------------
* Step 3b: dCDH continuous DID
* -------------------------------------------------------------------

display _n "{txt}=== STEP 3b: dCDH dynamic DID (log publications) ==="

if "`fe_mode'" == "rich" {
    capture drop log1p_pub_resid
    qui reghdfe log1p_bold_pub_total_0_5yr, absorb(`absorb_main') resid(log1p_pub_resid)
    qui did_multiplegt_dyn log1p_pub_resid cell_id_num year log1p_conflict, ///
        effects(10) placebo(5) cluster(cell_id_num) graph_off
}
else {
    qui did_multiplegt_dyn log1p_bold_pub_total_0_5yr cell_id_num year log1p_conflict, ///
        effects(10) placebo(5) cluster(cell_id_num) graph_off
}
estimates store `est_dcdh'
add_sum_rows, name(conflict_sum_03) expr(Effect_1 + Effect_2 + Effect_3)
add_sum_rows, name(conflict_sum_05) expr(Effect_1 + Effect_2 + Effect_3 + Effect_4 + Effect_5)
qui test Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1
estadd scalar pretrend_p = r(p)
estadd local fe_cell      "\checkmark"
estadd local fe_year      "`fe_label_year'"
estadd local fe_cy        "`fe_label_cy'"
estadd local fe_biome_yr  "`fe_label_biome'"
estadd local estimator    "dCDH dyn (cont)"
estadd local treatment    "Intensity log(1+events)"
estadd local lhs_label    "log1p_bold_pub_total_0_5yr"
estadd local fe_note      "`dcdh_fe_note'"

* -------------------------------------------------------------------
* CS DID robustness
* -------------------------------------------------------------------

display _n "{txt}=== Callaway-Sant'Anna robustness (log publications) ==="

capture drop gvar_conflict
gen gvar_conflict = cond(missing(Ei_conflict), 0, Ei_conflict)

qui csdid log1p_bold_pub_total_0_5yr, ivar(cell_id_num) time(year) gvar(gvar_conflict) ///
    method(reg) notyet
qui estat event, estore(`est_cs')
estimates restore `est_cs'
add_sum_rows, name(conflict_sum_03) expr(Tp0 + Tp1 + Tp2)
add_sum_rows, name(conflict_sum_05) expr(Tp0 + Tp1 + Tp2 + Tp3 + Tp4)
qui test Tm5 Tm4 Tm3 Tm2 Tm1
estadd scalar pretrend_p = r(p)
estadd local fe_cell      "\checkmark"
if "`fe_mode'" == "simple" estadd local fe_year "\checkmark"
else                        estadd local fe_year " "
estadd local fe_cy        " "
estadd local fe_biome_yr  " "
estadd local estimator    "Callaway-Sant'Anna"
estadd local treatment    "Binary onset (UCDP, K=5)"
estadd local lhs_label    "log1p_bold_pub_total_0_5yr"
if "`fe_mode'" == "simple" estadd local fe_note "time effects via csdid"
else                        estadd local fe_note " "

* -------------------------------------------------------------------
* Multi-shock TWFE / BJS on log publications
* -------------------------------------------------------------------

display _n "{txt}=== SECTION B1: Multi-shock TWFE comparison ==="

foreach shk in conflict drought fire {
    foreach v in lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
        capture drop `v'
    }
    gen byte lead5 = (et_`shk' <= -5) if !missing(et_`shk')
    gen byte lead4 = (et_`shk' == -4) if !missing(et_`shk')
    gen byte lead3 = (et_`shk' == -3) if !missing(et_`shk')
    gen byte lead2 = (et_`shk' == -2) if !missing(et_`shk')
    gen byte lag0  = (et_`shk' == 0)  if !missing(et_`shk')
    gen byte lag1  = (et_`shk' == 1)  if !missing(et_`shk')
    gen byte lag2  = (et_`shk' == 2)  if !missing(et_`shk')
    gen byte lag3  = (et_`shk' == 3)  if !missing(et_`shk')
    gen byte lag4  = (et_`shk' == 4)  if !missing(et_`shk')
    gen byte lag5  = (et_`shk' == 5)  if !missing(et_`shk')
    gen byte lag6  = (et_`shk' == 6)  if !missing(et_`shk')
    gen byte lag7  = (et_`shk' == 7)  if !missing(et_`shk')
    gen byte lag8  = (et_`shk' >= 8)  if !missing(et_`shk')
    foreach v in lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
        replace `v' = 0 if missing(`v')
    }

    qui reghdfe log1p_bold_pub_total_0_5yr ///
        lead5 lead4 lead3 lead2 ///
        lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8, ///
        absorb(`absorb_main') ///
        vce(cluster cell_id_num)
    if "`shk'" == "conflict" estimates store `est_twfe_conflict'
    else if "`shk'" == "drought" estimates store `est_twfe_drought'
    else estimates store `est_twfe_fire'
    qui test lead5 lead4 lead3 lead2
    qui estadd scalar pretrend_p = r(p)
    add_avg_rows, name(att_avg_03) expr(lag0 + lag1 + lag2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(lag0 + lag1 + lag2 + lag3 + lag4) divisor(5)
    add_avg_rows, name(att_avg_08) expr(lag0 + lag1 + lag2 + lag3 + lag4 + lag5 + lag6 + lag7 + lag8) divisor(9)
    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "TWFE event-study"
    estadd local treatment    "Binary onset"
    estadd local lhs_label    "log1p_bold_pub_total_0_5yr"
    estadd local shock        "`shk'"
}

display _n "{txt}=== SECTION B2: Multi-shock BJS comparison ==="

foreach shk in drought fire {
    qui did_imputation log1p_bold_pub_total_0_5yr cell_id_num year Ei_`shk', ///
        fe(`did_fe') horizons(0/8) pretrends(4) ///
        cluster(cell_id_num) autosample
    if "`shk'" == "drought" estimates store `est_bjs_drought'
    else                    estimates store `est_bjs_fire'
    qui estadd scalar pretrend_p = e(pre_p)
    add_avg_rows, name(att_avg_03) expr(tau0 + tau1 + tau2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(tau0 + tau1 + tau2 + tau3 + tau4) divisor(5)
    add_avg_rows, name(att_avg_08) expr(tau0 + tau1 + tau2 + tau3 + tau4 + tau5 + tau6 + tau7 + tau8) divisor(9)
    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "BJS imputation"
    estadd local treatment    "Binary onset"
    estadd local lhs_label    "log1p_bold_pub_total_0_5yr"
    estadd local shock        "`shk'"
}

display _n(2) "{txt}========================================================================"
display "{txt}  PARALLEL-TRENDS TESTS (joint Wald on pre1...pre4)"
display "{txt}========================================================================"
foreach m in `est_bjs_any' `est_bjs_log' `est_bjs_drought' `est_bjs_fire' {
    estimates restore `m'
    display %-40s "`m'" "  pre_p = " %5.3f e(pre_p) "  pre_F = " %5.2f e(pre_F) "  N = " %9.0fc e(N)
}
display "{txt}========================================================================"

* -------------------------------------------------------------------
* Table 1
* -------------------------------------------------------------------

esttab `est_twfe_any' `est_bjs_any' `est_twfe_log' `est_bjs_log', ///
    rename(lead5 t_m5 lead4 t_m4 lead3 t_m3 lead2 t_m2 ///
           lag0 t_p0 lag1 t_p1 lag2 t_p2 lag3 t_p3 lag4 t_p4 lag5 t_p5 ///
           lag6 t_p6 lag7 t_p7 lag8 t_p8 ///
           pre4 t_m5 pre3 t_m4 pre2 t_m3 pre1 t_m2 ///
           tau0 t_p0 tau1 t_p1 tau2 t_p2 tau3 t_p3 tau4 t_p4 tau5 t_p5 ///
           tau6 t_p6 tau7 t_p7 tau8 t_p8) ///
    keep(t_m5 t_m4 t_m3 t_m2 t_p0 t_p1 t_p2 t_p3 t_p4 t_p5 t_p6 t_p7 t_p8) ///
    order(t_m5 t_m4 t_m3 t_m2 t_p0 t_p1 t_p2 t_p3 t_p4 t_p5 t_p6 t_p7 t_p8) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(t_m5 "tau_-5+" t_m4 "tau_-4" t_m3 "tau_-3" t_m2 "tau_-2" ///
              t_p0 "tau_0" t_p1 "tau_+1" t_p2 "tau_+2" t_p3 "tau_+3" t_p4 "tau_+4" ///
              t_p5 "tau_+5" t_p6 "tau_+6" t_p7 "tau_+7" t_p8 "tau_+8+") ///
    stats(att_avg_03_txt att_avg_03_se_txt ///
          att_avg_05_txt att_avg_05_se_txt ///
          att_avg_08_txt att_avg_08_se_txt ///
          pretrend_p estimator treatment lhs_label N r2 ///
          fe_cell fe_year fe_cy fe_biome_yr, ///
          labels("Avg ATT tau0-tau2" " " ///
                 "Avg ATT tau0-tau4" " " ///
                 "Avg ATT tau0-tau8 (headline)" " " ///
                 "Pre-trend joint p" "Estimator" "Treatment" "LHS" "Obs." "R-sq." ///
                 "Cell FE" "Year FE" "Country x Year FE" "Biome x Year FE") ///
          fmt(%s %s %s %s %s %s %9.4f %s %s %s %9.0fc %9.4f %s %s %s %s)) ///
    title("Table 1: 5yr publication-yield conflict identification ladder (window -5/+8)") ///
    mtitles("any_bold_pub_total_0_5yr" "any_bold_pub_total_0_5yr" "log1p_bold_pub_total_0_5yr" "log1p_bold_pub_total_0_5yr") ///
    mgroups("TWFE event-study" "BJS imputation" "TWFE event-study" "BJS imputation", pattern(1 1 1 1)) ///
    compress

* -------------------------------------------------------------------
* Table 2
* -------------------------------------------------------------------

esttab `est_cont' `est_dcdh' `est_cs', ///
    keep(F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict ///
         F1_log1p_conflict log1p_conflict ///
         L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict ///
         L5_log1p_conflict ///
         Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1 ///
         Effect_1 Effect_2 Effect_3 Effect_4 Effect_5 ///
         Effect_6 Effect_7 Effect_8 Effect_9 Effect_10 ///
         Tm5 Tm4 Tm3 Tm2 Tm1 Tp0 Tp1 Tp2 Tp3 Tp4 Tp5 Tp6 Tp7 Tp8) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    stats(conflict_sum_03_txt conflict_sum_03_se_txt ///
          conflict_sum_05_txt conflict_sum_05_se_txt ///
          pretrend_p estimator treatment lhs_label N r2 ///
          fe_cell fe_year fe_cy fe_biome_yr fe_note, ///
          labels("Sum L0-L2" " " ///
                 "Sum L0-L4" " " ///
                 "Pre-trend joint p" "Estimator" "Treatment" "LHS" "Obs." "R-sq." ///
                 "Cell FE" "Year FE" "Country x Year FE" "Biome x Year FE" "FE note") ///
          fmt(%s %s %s %s %9.4f %s %s %s %9.0fc %9.4f %s %s %s %s %s)) ///
    title("Table 2: 5yr publication-yield continuous DID + CS robustness") ///
    mtitles("DL continuous" "dCDH dyn" "Callaway-Sant'Anna") ///
    compress

* -------------------------------------------------------------------
* Table 3
* -------------------------------------------------------------------

esttab `est_bjs_log' `est_bjs_drought' `est_bjs_fire', ///
    keep(pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    order(pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    stats(att_avg_03_txt att_avg_03_se_txt ///
          att_avg_05_txt att_avg_05_se_txt ///
          att_avg_08_txt att_avg_08_se_txt ///
          pretrend_p estimator shock lhs_label N r2 ///
          fe_cell fe_year fe_cy fe_biome_yr, ///
          labels("Avg ATT tau0-tau2" " " ///
                 "Avg ATT tau0-tau4" " " ///
                 "Avg ATT tau0-tau8 (headline)" " " ///
                 "Pre-trend joint p" "Estimator" "Shock" "LHS" "Obs." "R-sq." ///
                 "Cell FE" "Year FE" "Country x Year FE" "Biome x Year FE") ///
          fmt(%s %s %s %s %s %s %9.4f %s %s %s %9.0fc %9.4f %s %s %s %s)) ///
    title("Table 3: 5yr publication-yield multi-shock BJS comparison (window -5/+8)") ///
    mtitles("Conflict" "Severe drought" "Fire") ///
    compress

* -------------------------------------------------------------------
* Table 4
* -------------------------------------------------------------------

esttab `est_twfe_conflict' `est_twfe_drought' `est_twfe_fire', ///
    keep(lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    order(lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(lead5 "tau_-5+" lead4 "tau_-4" lead3 "tau_-3" lead2 "tau_-2" ///
              lag0 "tau_0" lag1 "tau_+1" lag2 "tau_+2" lag3 "tau_+3" lag4 "tau_+4" ///
              lag5 "tau_+5" lag6 "tau_+6" lag7 "tau_+7" lag8 "tau_+8+") ///
    stats(att_avg_03_txt att_avg_03_se_txt ///
          att_avg_05_txt att_avg_05_se_txt ///
          att_avg_08_txt att_avg_08_se_txt ///
          pretrend_p estimator shock lhs_label N r2 ///
          fe_cell fe_year fe_cy fe_biome_yr, ///
          labels("Avg ATT tau0-tau2" " " ///
                 "Avg ATT tau0-tau4" " " ///
                 "Avg ATT tau0-tau8 (headline)" " " ///
                 "Pre-trend joint p" "Estimator" "Shock" "LHS" "Obs." "R-sq." ///
                 "Cell FE" "Year FE" "Country x Year FE" "Biome x Year FE") ///
          fmt(%s %s %s %s %s %s %9.4f %s %s %s %9.0fc %9.4f %s %s %s %s)) ///
    title("Table 4: 5yr publication-yield multi-shock TWFE comparison (window -5/+8)") ///
    mtitles("Conflict" "Severe drought" "Fire") ///
    compress

* -------------------------------------------------------------------
* Figure 1
* -------------------------------------------------------------------

coefplot (`est_twfe_log', label("TWFE event-study") msymbol(O) mcolor(navy) ciopts(lcolor(navy))), ///
    keep(lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    order(lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    coeflabels(lead5 = "-5+" lead4 = "-4" lead3 = "-3" lead2 = "-2" ///
               lag0 = "0" lag1 = "+1" lag2 = "+2" lag3 = "+3" lag4 = "+4" lag5 = "+5" ///
               lag6 = "+6" lag7 = "+7" lag8 = "+8+") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on log(1 + 5yr publications)") ///
    title("TWFE event-study", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_pub5_twfe_log, replace)

coefplot (`est_bjs_log', label("BJS imputation") msymbol(D) mcolor(maroon) ciopts(lcolor(maroon))), ///
    keep(pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    order(pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    coeflabels(pre4 = "-5" pre3 = "-4" pre2 = "-3" pre1 = "-2" ///
               tau0 = "0" tau1 = "+1" tau2 = "+2" tau3 = "+3" tau4 = "+4" tau5 = "+5" ///
               tau6 = "+6" tau7 = "+7" tau8 = "+8") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on log(1 + 5yr publications)") ///
    title("BJS imputation", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_pub5_bjs_log, replace)

graph combine es_pub5_twfe_log es_pub5_bjs_log, ///
    title("TWFE vs BJS: conflict effect on 5yr publication yield (intensive)", size(medium)) ///
    cols(2) ycommon name(es_pub5_conflict_log, replace)
graph save "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_pub5_log1p.gph", replace
graph export "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_pub5_log1p.pdf", replace

* -------------------------------------------------------------------
* Figure 2
* -------------------------------------------------------------------

coefplot (`est_twfe_any', label("TWFE event-study") msymbol(O) mcolor(navy) ciopts(lcolor(navy))), ///
    keep(lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    order(lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    coeflabels(lead5 = "-5+" lead4 = "-4" lead3 = "-3" lead2 = "-2" ///
               lag0 = "0" lag1 = "+1" lag2 = "+2" lag3 = "+3" lag4 = "+4" lag5 = "+5" ///
               lag6 = "+6" lag7 = "+7" lag8 = "+8+") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on 1[5yr publications > 0]") ///
    title("TWFE event-study", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_pub5_twfe_any, replace)

coefplot (`est_bjs_any', label("BJS imputation") msymbol(D) mcolor(maroon) ciopts(lcolor(maroon))), ///
    keep(pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    order(pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    coeflabels(pre4 = "-5" pre3 = "-4" pre2 = "-3" pre1 = "-2" ///
               tau0 = "0" tau1 = "+1" tau2 = "+2" tau3 = "+3" tau4 = "+4" tau5 = "+5" ///
               tau6 = "+6" tau7 = "+7" tau8 = "+8") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on 1[5yr publications > 0]") ///
    title("BJS imputation", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_pub5_bjs_any, replace)

graph combine es_pub5_twfe_any es_pub5_bjs_any, ///
    title("TWFE vs BJS: conflict effect on 5yr publication yield (extensive)", size(medium)) ///
    cols(2) ycommon name(es_pub5_conflict_any, replace)
graph save "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_pub5_any.gph", replace
graph export "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_pub5_any.pdf", replace

* -------------------------------------------------------------------
* Figure 3
* -------------------------------------------------------------------

local plotcoefs pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8

coefplot ///
    (`est_bjs_log',      label("Conflict") msymbol(O) mcolor(navy) ciopts(lcolor(navy))) ///
    (`est_bjs_drought',  label("Severe drought") msymbol(D) mcolor(maroon) ciopts(lcolor(maroon))) ///
    (`est_bjs_fire',     label("Fire") msymbol(S) mcolor(forest_green) ciopts(lcolor(forest_green))), ///
    keep(`plotcoefs') order(`plotcoefs') ///
    coeflabels(pre4 = "-5" pre3 = "-4" pre2 = "-3" pre1 = "-2" ///
               tau0 = "0" tau1 = "+1" tau2 = "+2" tau3 = "+3" tau4 = "+4" tau5 = "+5" ///
               tau6 = "+6" tau7 = "+7" tau8 = "+8") ///
    vertical yline(0, lpattern(dash) lcolor(black)) xline(4.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from shock onset (tau_-1 = reference)") ///
    ytitle("Effect on log(1 + 5yr publications)") ///
    title("BJS event-study: 5yr publication-yield response to shock onsets", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(rows(1) position(6) size(small)) ///
    name(es_pub5_multishock_bjs, replace)
graph save "$proj/Output/figures/event_study/bjs_conflict_drought_fire_pub5.gph", replace
graph export "$proj/Output/figures/event_study/bjs_conflict_drought_fire_pub5.pdf", replace

* -------------------------------------------------------------------
* Figure 4
* -------------------------------------------------------------------

local plotcoefs_twfe lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8

coefplot ///
    (`est_twfe_conflict', label("Conflict") msymbol(O) mcolor(navy) ciopts(lcolor(navy))) ///
    (`est_twfe_drought',  label("Severe drought") msymbol(D) mcolor(maroon) ciopts(lcolor(maroon))) ///
    (`est_twfe_fire',     label("Fire") msymbol(S) mcolor(forest_green) ciopts(lcolor(forest_green))), ///
    keep(`plotcoefs_twfe') order(`plotcoefs_twfe') ///
    coeflabels(lead5 = "-5+" lead4 = "-4" lead3 = "-3" lead2 = "-2" ///
               lag0 = "0" lag1 = "+1" lag2 = "+2" lag3 = "+3" lag4 = "+4" lag5 = "+5" ///
               lag6 = "+6" lag7 = "+7" lag8 = "+8+") ///
    vertical yline(0, lpattern(dash) lcolor(black)) xline(4.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from shock onset (tau_-1 = reference)") ///
    ytitle("Effect on log(1 + 5yr publications)") ///
    title("TWFE event-study: 5yr publication-yield response to shock onsets", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(rows(1) position(6) size(small)) ///
    name(es_pub5_multishock_twfe, replace)
graph save "$proj/Output/figures/event_study/twfe_conflict_drought_fire_pub5.gph", replace
graph export "$proj/Output/figures/event_study/twfe_conflict_drought_fire_pub5.pdf", replace

* -------------------------------------------------------------------
* Figure 5
* -------------------------------------------------------------------

coefplot (`est_cont', label("DL continuous") msymbol(O) mcolor(navy) ciopts(lcolor(navy))), ///
    keep(F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict ///
         F1_log1p_conflict log1p_conflict ///
         L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict ///
         L5_log1p_conflict) ///
    order(F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict ///
          F1_log1p_conflict log1p_conflict ///
          L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict ///
          L5_log1p_conflict) ///
    coeflabels(F5_log1p_conflict = "-5" F4_log1p_conflict = "-4" F3_log1p_conflict = "-3" ///
               F2_log1p_conflict = "-2" F1_log1p_conflict = "-1" log1p_conflict = "0" ///
               L1_log1p_conflict = "+1" L2_log1p_conflict = "+2" L3_log1p_conflict = "+3" ///
               L4_log1p_conflict = "+4" L5_log1p_conflict = "+5") ///
    vertical yline(0, lpattern(dash) lcolor(black)) xline(5.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from contemporaneous (F = leads, L = lags)") ///
    ytitle("Effect on log(1 + 5yr publications) per unit log(1 + events)") ///
    title("Continuous-treatment DL DID: conflict intensity and 5yr publication yield", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_pub5_continuous, replace)
graph save "$proj/Output/figures/event_study/continuous_dl_conflict_pub5_log1p.gph", replace
graph export "$proj/Output/figures/event_study/continuous_dl_conflict_pub5_log1p.pdf", replace

* -------------------------------------------------------------------
* Figure 6
* -------------------------------------------------------------------

coefplot (`est_dcdh', label("dCDH dynamic") msymbol(O) mcolor(navy) ciopts(lcolor(navy))), ///
    keep(Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1 ///
         Effect_1 Effect_2 Effect_3 Effect_4 Effect_5 Effect_6 Effect_7 Effect_8 Effect_9 Effect_10) ///
    order(Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1 ///
          Effect_1 Effect_2 Effect_3 Effect_4 Effect_5 Effect_6 Effect_7 Effect_8 Effect_9 Effect_10) ///
    coeflabels(Placebo_5 = "-5" Placebo_4 = "-4" Placebo_3 = "-3" Placebo_2 = "-2" Placebo_1 = "-1" ///
               Effect_1 = "0" Effect_2 = "+1" Effect_3 = "+2" Effect_4 = "+3" Effect_5 = "+4" ///
               Effect_6 = "+5" Effect_7 = "+6" Effect_8 = "+7" Effect_9 = "+8" Effect_10 = "+9") ///
    vertical yline(0, lpattern(dash) lcolor(black)) xline(5.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from intensity change (Placebo = leads, Effect = lags)") ///
    ytitle("Effect on log(1 + 5yr publications) per unit log(1 + events)") ///
    title("dCDH continuous DID: conflict intensity and 5yr publication yield", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_pub5_dcdh, replace)
graph save "$proj/Output/figures/event_study/dcdh_continuous_conflict_pub5_log1p.gph", replace
graph export "$proj/Output/figures/event_study/dcdh_continuous_conflict_pub5_log1p.pdf", replace

display _n "{txt}=== Done. ==="
display "Log:    $proj/Logs/reg_event_study_publications_5yr.log"
display "Figures:"
display "  $proj/Output/figures/event_study/twfe_vs_bjs_conflict_pub5_log1p.pdf"
display "  $proj/Output/figures/event_study/twfe_vs_bjs_conflict_pub5_any.pdf"
display "  $proj/Output/figures/event_study/bjs_conflict_drought_fire_pub5.pdf"
display "  $proj/Output/figures/event_study/twfe_conflict_drought_fire_pub5.pdf"
display "  $proj/Output/figures/event_study/continuous_dl_conflict_pub5_log1p.pdf"
display "  $proj/Output/figures/event_study/dcdh_continuous_conflict_pub5_log1p.pdf"

log close
