* reg_event_study_combined_shocks.do
* Combined-shock event studies for the UPSTREAM BOLD-sampling outcome (log1p_total).
* Companion to reg_event_study.do Section B, which OVERLAYS three separate
* single-shock event studies. This file instead estimates the shocks JOINTLY:
*
*   GRAPH 1 — "Horse race": conflict, drought, and fire event-time dummies in ONE
*             regression, so each shock's path is identified NET OF the other two.
*             Answers the slide-13 question ("is it conflict, or just generic
*             disturbance?") in its strongest form. Diagnostics confirm the three
*             shocks are near-uncorrelated (|phi| <= 0.16), so collinearity is not
*             a concern and the conflict path can be cleanly isolated.
*
*   GRAPH 2 — "Any shock" benchmark: a SINGLE composite onset (=1 at the first year
*             ANY of conflict/drought/fire fires, after K=5 years with no shock of
*             any kind). The generic-disturbance foil. NOTE: the composite is ~95%
*             drought/fire by composition (only ~4% of onsets carry conflict), so it
*             measures the average environmental disturbance, NOT a balanced average;
*             the figure note discloses the composition, and the clean-control pool
*             is thin (~68% of cell-years are ever-shocked). Interpret as a contrast
*             to the conflict-specific path in Graph 1.
*
* Onset run-in is SHOCK-SPECIFIC (conflict K=10, drought K=5, fire K=3), as in the
* original reg_event_study.do; the composite "any shock" uses its own 5-year clean
* run-in. Estimator: the horse race is TWFE (a clean joint BJS for three
* simultaneous treatments is not well-defined); the single-treatment "any shock"
* adds a BJS panel as a robustness check. FE: simple (cell + year), cluster cell.
* Event window: -6/+8, tau_{-1} = reference. Graphs only (no tables).

clear all
set more off
set matsize 11000

global proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
do "$proj/DoFiles/_beamer_paths.do"

local hdfe_cmd "reghdfe"

* Simple FE (matches slide-13 spec). Rich option kept commented for parity.
local absorb_main "cell_id_num year"
// local absorb_main "cell_id_num country_year biome_year"

capture log close
log using "$proj/Logs/reg_event_study_combined_shocks.log", replace text

* -------------------------------------------------------------------
* 0. Output dirs + packages
* -------------------------------------------------------------------
capture mkdir "$proj/Output"
capture mkdir "$proj/Output/figures"
capture mkdir "$proj/Output/figures/event_study"
global codex_figures "$DD_CODEX_FIGURES"

foreach pkg in did_imputation coefplot reghdfe ftools estout {
    capture which `pkg'
    if _rc {
        display as text "Installing `pkg' from SSC ..."
        capture ssc install `pkg', replace
    }
}

* -------------------------------------------------------------------
* 1. Load, sample, encode (mirrors reg_event_study.do)
* -------------------------------------------------------------------
use "$proj/Data/analysis/BOLD_regressor_panel.dta", clear
keep if year >= 2005 & year <= 2023
encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)
xtset cell_id_num year

* Defensive 0-fill so missing-as-not-treated doesn't bork the lookback logic.
replace ucdp_any_all = 0 if missing(ucdp_any_all) & year >= 2005 & year <= 2023
replace any_burned   = 0 if missing(any_burned)   & year >= 2005 & year <= 2023

* -------------------------------------------------------------------
* 2. Per-shock onsets (SHOCK-SPECIFIC K: conflict=10, drought=5, fire=3),
*    identical construction and K to the original reg_event_study.do.
* -------------------------------------------------------------------
* ---- Conflict onset (K=10) ----
gen lookback_conflict = 1
forvalues k = 1/10 {
    replace lookback_conflict = 0 if L`k'.ucdp_any_all != 0 | missing(L`k'.ucdp_any_all)
}
gen onset_flag_conflict = (ucdp_any_all == 1 & lookback_conflict == 1)
bysort cell_id_num (year): egen onset_year_conflict = min(cond(onset_flag_conflict==1, year, .))
gen Ei_conflict = onset_year_conflict
gen et_conflict = year - Ei_conflict

* ---- Severe drought onset (K=5): pdsi_anomaly < -2 after 5 years pdsi > -1 ----
gen lookback_drought = 1
forvalues k = 1/5 {
    replace lookback_drought = 0 if L`k'.pdsi_anomaly <= -1 | missing(L`k'.pdsi_anomaly)
}
gen onset_flag_drought = (pdsi_anomaly < -2 & lookback_drought == 1) if !missing(pdsi_anomaly)
bysort cell_id_num (year): egen onset_year_drought = min(cond(onset_flag_drought==1, year, .))
gen Ei_drought = onset_year_drought
gen et_drought = year - Ei_drought

* ---- Fire onset (K=3) ----
gen lookback_fire = 1
forvalues k = 1/3 {
    replace lookback_fire = 0 if L`k'.any_burned != 0 | missing(L`k'.any_burned)
}
gen onset_flag_fire = (any_burned == 1 & lookback_fire == 1)
bysort cell_id_num (year): egen onset_year_fire = min(cond(onset_flag_fire==1, year, .))
gen Ei_fire = onset_year_fire
gen et_fire = year - Ei_fire

* -------------------------------------------------------------------
* 3. Composite "any shock" onset (K=5): first year any trigger fires after
*    5 consecutive years with NO shock of any kind.
* -------------------------------------------------------------------
* Note: missing pdsi -> not severe drought (missing > -2 is false in Stata).
gen byte shock_any = (ucdp_any_all == 1) | (pdsi_anomaly < -2) | (any_burned == 1)
gen lookback_any = 1
forvalues k = 1/5 {
    replace lookback_any = 0 if L`k'.shock_any != 0 | missing(L`k'.shock_any)
}
gen onset_flag_any = (shock_any == 1 & lookback_any == 1)
bysort cell_id_num (year): egen onset_year_any = min(cond(onset_flag_any==1, year, .))
gen Ei_any = onset_year_any
gen et_any = year - Ei_any

* -------------------------------------------------------------------
* 4. Composition / coverage diagnostic (for the Graph-2 note + verification)
* -------------------------------------------------------------------
display _n "{txt}=== Composite 'any shock' onset diagnostics ==="
count if onset_flag_any == 1
local n_onset = r(N)
gen byte _trig_drought = (pdsi_anomaly < -2)
quietly summarize ucdp_any_all   if onset_flag_any == 1, meanonly
local sh_conflict = round(100*r(mean))
quietly summarize _trig_drought  if onset_flag_any == 1, meanonly
local sh_drought  = round(100*r(mean))
quietly summarize any_burned     if onset_flag_any == 1, meanonly
local sh_fire     = round(100*r(mean))
quietly summarize shock_any
local sh_ever     = round(100*r(mean))
display as text "Composite onset events: `n_onset'"
display as text "At onset, share active:  conflict `sh_conflict'%  drought `sh_drought'%  fire `sh_fire'%"
display as text "Cell-years ever shocked: `sh_ever'%"
drop _trig_drought

* -------------------------------------------------------------------
* 5. Distinct event-time dummies per shock (prefix c_/d_/f_/a_).
*    tau_{-1} (lead1) omitted = reference. lead6 = <=-6, lag8 = >=+8.
* -------------------------------------------------------------------
local evt "lead6 lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8"

foreach shk in conflict drought fire any {
    local p = substr("`shk'", 1, 1)
    foreach v of local evt {
        capture drop `p'_`v'
    }
    gen byte `p'_lead6 = (et_`shk' <= -6) if !missing(et_`shk')
    gen byte `p'_lead5 = (et_`shk' == -5) if !missing(et_`shk')
    gen byte `p'_lead4 = (et_`shk' == -4) if !missing(et_`shk')
    gen byte `p'_lead3 = (et_`shk' == -3) if !missing(et_`shk')
    gen byte `p'_lead2 = (et_`shk' == -2) if !missing(et_`shk')
    gen byte `p'_lag0  = (et_`shk' == 0)  if !missing(et_`shk')
    gen byte `p'_lag1  = (et_`shk' == 1)  if !missing(et_`shk')
    gen byte `p'_lag2  = (et_`shk' == 2)  if !missing(et_`shk')
    gen byte `p'_lag3  = (et_`shk' == 3)  if !missing(et_`shk')
    gen byte `p'_lag4  = (et_`shk' == 4)  if !missing(et_`shk')
    gen byte `p'_lag5  = (et_`shk' == 5)  if !missing(et_`shk')
    gen byte `p'_lag6  = (et_`shk' == 6)  if !missing(et_`shk')
    gen byte `p'_lag7  = (et_`shk' == 7)  if !missing(et_`shk')
    gen byte `p'_lag8  = (et_`shk' >= 8)  if !missing(et_`shk')
    foreach v of local evt {
        replace `p'_`v' = 0 if missing(`p'_`v')
    }
}

local c_coefs c_lead6 c_lead5 c_lead4 c_lead3 c_lead2 c_lag0 c_lag1 c_lag2 c_lag3 c_lag4 c_lag5 c_lag6 c_lag7 c_lag8
local d_coefs d_lead6 d_lead5 d_lead4 d_lead3 d_lead2 d_lag0 d_lag1 d_lag2 d_lag3 d_lag4 d_lag5 d_lag6 d_lag7 d_lag8
local f_coefs f_lead6 f_lead5 f_lead4 f_lead3 f_lead2 f_lag0 f_lag1 f_lag2 f_lag3 f_lag4 f_lag5 f_lag6 f_lag7 f_lag8
local a_coefs a_lead6 a_lead5 a_lead4 a_lead3 a_lead2 a_lag0 a_lag1 a_lag2 a_lag3 a_lag4 a_lag5 a_lag6 a_lag7 a_lag8

* Common event-time labels. coefplot aligns series by coefficient label, so we
* rename every shock's prefixed dummies (c_/d_/f_/a_) EXPLICITLY onto a shared
* label set (wildcard rename does not collapse them — it leaves them disjoint).
local labs -6+ -5 -4 -3 -2 0 +1 +2 +3 +4 +5 +6 +7 +8+
local relabel ""
local i = 0
foreach v of local evt {
    local ++i
    local lab : word `i' of `labs'
    foreach p in c d f a {
        local relabel `relabel' `p'_`v' = "`lab'"
    }
}
local axisorder "-6+" "-5" "-4" "-3" "-2" "0" "+1" "+2" "+3" "+4" "+5" "+6" "+7" "+8+"

* ===================================================================
* GRAPH 1 — Horse race (joint regression; each path net of the others)
* ===================================================================
display _n "{txt}=== GRAPH 1: combined-shock horse race ==="

qui `hdfe_cmd' log1p_total `c_coefs' `d_coefs' `f_coefs', ///
    absorb(`absorb_main') vce(cluster cell_id_num)
estimates store hr

qui test c_lead6 c_lead5 c_lead4 c_lead3 c_lead2
display as text "Horse race pre-trend p (conflict leads) = " %5.3f r(p)
qui test d_lead6 d_lead5 d_lead4 d_lead3 d_lead2
display as text "Horse race pre-trend p (drought leads)  = " %5.3f r(p)
qui test f_lead6 f_lead5 f_lead4 f_lead3 f_lead2
display as text "Horse race pre-trend p (fire leads)     = " %5.3f r(p)

coefplot ///
    (hr, keep(`c_coefs') label("Conflict") msymbol(O) mcolor(navy) ciopts(lcolor(navy))) ///
    (hr, keep(`d_coefs') label("Severe drought") msymbol(D) mcolor(maroon) ciopts(lcolor(maroon))) ///
    (hr, keep(`f_coefs') label("Fire") msymbol(S) mcolor(forest_green) ciopts(lcolor(forest_green))), ///
    rename(`relabel') ///
    order(`axisorder') ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xline(5.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from shock onset (τ_{-1} = reference)") ///
    ytitle("Effect on log(1 + total records)") ///
    title("TWFE horse race: each shock net of the others (BOLD sampling)", size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(rows(1) position(6) size(small)) ///
    name(es_horserace, replace)

graph save   "$proj/Output/figures/event_study/twfe_horserace_sampling.gph", replace
graph export "$proj/Output/figures/event_study/twfe_horserace_sampling.pdf", replace
graph export "$codex_figures/twfe_horserace_sampling.pdf", replace

* ===================================================================
* GRAPH 2 — "Any shock" generic-disturbance benchmark: TWFE vs BJS
*   The composite is a SINGLE absorbing treatment, so BJS (did_imputation)
*   is well-defined and builds a clean never/not-yet-treated counterfactual,
*   avoiding the forbidden-comparison bias a thin clean-control pool (68%
*   ever-shocked) inflicts on TWFE. The single-shock components are drought
*   weak/negative and fire flat, so a positive TWFE composite path would be
*   internally inconsistent; divergence from BJS here diagnoses it as a TWFE
*   artifact rather than a real "disturbance boosts sampling" effect.
* ===================================================================
display _n "{txt}=== GRAPH 2: 'any shock' benchmark (TWFE vs BJS) ==="

* --- TWFE ---
qui `hdfe_cmd' log1p_total `a_coefs', ///
    absorb(`absorb_main') vce(cluster cell_id_num)
estimates store anyshock
qui test a_lead6 a_lead5 a_lead4 a_lead3 a_lead2
display as text "Any-shock TWFE pre-trend p (leads) = " %5.3f r(p)

* --- BJS imputation on the composite onset (Ei_any; missing = never-treated) ---
qui did_imputation log1p_total cell_id_num year Ei_any, ///
    fe(cell_id_num year) horizons(0/8) pretrends(5) ///
    cluster(cell_id_num) autosample
estimates store bjs_any
display as text "Any-shock BJS pre-trend p = " %5.3f e(pre_p)

local note2 "Composite onset = first conflict/drought/fire after 5 clean years. At onset: `sh_conflict'% conflict, `sh_drought'% drought, `sh_fire'% fire; `sh_ever'% of cell-years ever shocked (thin clean-control pool -> TWFE forbidden-comparison risk)."

* --- Panel A: TWFE ---
coefplot (anyshock, label("TWFE event-study") msymbol(O) mcolor(navy) ciopts(lcolor(navy))), ///
    keep(`a_coefs') order(`a_coefs') ///
    coeflabels(a_lead6 = "-6+" a_lead5 = "-5" a_lead4 = "-4" a_lead3 = "-3" a_lead2 = "-2" ///
               a_lag0 = "0" a_lag1 = "+1" a_lag2 = "+2" a_lag3 = "+3" a_lag4 = "+4" a_lag5 = "+5" ///
               a_lag6 = "+6" a_lag7 = "+7" a_lag8 = "+8+") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from any-shock onset") ///
    ytitle("Effect on log(1 + total records)") ///
    title("TWFE event-study", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_anyshock_twfe, replace)

* --- Panel B: BJS ---
coefplot (bjs_any, label("BJS imputation") msymbol(D) mcolor(maroon) ciopts(lcolor(maroon))), ///
    keep(pre5 pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    order(pre5 pre4 pre3 pre2 pre1 tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    coeflabels(pre5 = "-6" pre4 = "-5" pre3 = "-4" pre2 = "-3" pre1 = "-2" ///
               tau0 = "0" tau1 = "+1" tau2 = "+2" tau3 = "+3" tau4 = "+4" tau5 = "+5" ///
               tau6 = "+6" tau7 = "+7" tau8 = "+8") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from any-shock onset") ///
    ytitle("Effect on log(1 + total records)") ///
    title("BJS imputation", size(medium)) ///
    msize(small) ciopts(recast(rcap)) legend(off) ///
    name(es_anyshock_bjs, replace)

* --- Combine ---
graph combine es_anyshock_twfe es_anyshock_bjs, ///
    title("TWFE vs BJS: 'any shock' generic-disturbance benchmark (sampling)", size(medium)) ///
    note("`note2'", size(vsmall)) ///
    cols(2) ycommon ///
    name(es_anyshock, replace)

graph save   "$proj/Output/figures/event_study/twfe_anyshock_sampling.gph", replace
graph export "$proj/Output/figures/event_study/twfe_anyshock_sampling.pdf", replace
graph export "$codex_figures/twfe_anyshock_sampling.pdf", replace

* -------------------------------------------------------------------
display _n "{txt}=== Done. ==="
display "Log:    $proj/Logs/reg_event_study_combined_shocks.log"
display "Figures:"
display "  $proj/Output/figures/event_study/twfe_horserace_sampling.pdf"
display "  $proj/Output/figures/event_study/twfe_anyshock_sampling.pdf"

* Publish local exhibits to the merged deck on Dropbox.
dd_mirror_outputs

log close
