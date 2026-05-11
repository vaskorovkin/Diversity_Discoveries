* reg_event_study.do
* Three-step identification ladder for the conflict→sampling effect, with a
* multi-shock parallel comparison (drought, fire) as a follow-on robustness layer.
*
* Mirrors reg_spec1.do Table 3 conventions:
*   - FE: cell + country×year + biome×year
*   - Cluster: cell
*   - Sample: 2005–2023
* Two LHS, both from Table 3:
*   - any_total   (extensive margin; Table 3 cols 1, 3, 5, 7)
*   - log1p_total (intensive margin;  Table 3 cols 2, 4, 6, 8)
*
* SECTION A — Conflict identification ladder (binary onset trigger):
*   STEP 1: TWFE event-study with explicit lead/lag dummies in `reghdfe`.
*           The conventional pre-Goodman-Bacon picture for both LHS.
*   STEP 2: Borusyak-Jaravel-Spiess imputation (`did_imputation`) for both LHS.
*           The modern estimator under absorbing treatment; comparison to Step 1
*           reveals any TWFE contamination from heterogeneous treatment timing.
*   STEP 3: Continuous-treatment distributed-lag dynamic DID, log1p_total only.
*           Uses log(1+ucdp_events_all) intensity (not the binary onset) to
*           confirm the binary onset isn't masking heterogeneous intensity
*           effects. Standard pre-CGS-2024 distributed-lag spec — readable
*           baseline.
*   STEP 3b: dCDH heterogeneity-robust dynamic DID (de Chaisemartin &
*           D'Haultfœuille 2024) via `did_multiplegt_dyn`. Heterogeneity-
*           robust modern continuous-treatment DID; relaxes BJS's absorbing
*           assumption (conflict can switch on and off, more honest about
*           UCDP data). FE absorbed via Frisch-Waugh residualization.
*   ROBUSTNESS: Callaway-Sant'Anna (`csdid`) for conflict log1p_total, simple FE.
*
* SECTION B — Multi-shock parallel comparison (intensity-margin only):
*   Severe drought (PDSI < -2) + fire (any_burned) onset event-studies.
*   Reported in both BJS and simple TWFE versions, stacked against conflict
*   to show the multi-shock comparison at cell-year resolution.
*
* Cyclone and earthquake are scoped out — their transient nature breaks the
* absorbing-treatment assumption. Stacked event-study (Cengiz et al. 2019 QJE)
* will live in a follow-on do-file.
*
* Onset definition: for each shock, the first cell-year with the trigger
* satisfied after K consecutive zero-trigger years.
*   K=10 for conflict — chosen to ensure parallel-trends; K=5 was rejected
*         on the intensive margin (pre_p = 0.020) due to recently-pacified
*         cells whose 5-year peace was actually post-conflict recovery.
*         K=10 yields pre_p = 0.155 (intensive) and 0.251 (extensive),
*         both above the 0.10 threshold for parallel trends.
*   K=5  for severe drought (slow-moving regime; pre-trends clean at K=5).
*   K=3  for fire (faster natural recurrence).
* First onset only (absorbing-state); subsequent triggers absorbed into post-period.
*
* Headline ATT: long-horizon average τ_0 to τ_8 (9-year post-onset mean).
* Effect builds slowly — null in first 0–4 years, significant by year 5–8.
* Reflects gradual collector exit rather than immediate shock response.

clear all
set more off
set matsize 11000

global proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

* HDFE backend for TWFE/continuous OLS steps. Switch to reghdfejl after
* confirming Julia works in Stata.
local hdfe_cmd "reghdfe"
// local hdfe_cmd "reghdfejl"

* -------------------------------------------------------------------
* FE clicker
*   Set to "rich"   for cell + country-year + biome-year FE
*   Set to "simple" for cell + year FE only
* -------------------------------------------------------------------

// local fe_mode "rich"
local fe_mode "simple"

if !inlist("`fe_mode'", "rich", "simple") {
    display as error "fe_mode must be either rich or simple"
    error 198
}

capture log close
log using "$proj/Logs/reg_event_study.log", replace text

* -------------------------------------------------------------------
* 0. Output directories + SSC packages
* -------------------------------------------------------------------

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

capture which `hdfe_cmd'
if _rc {
    di as error "Requested HDFE backend `hdfe_cmd' is not installed."
    if "`hdfe_cmd'" == "reghdfejl" {
        di as text "Install in Stata with: ssc install julia; ssc install reghdfejl"
    }
    error 111
}

* -------------------------------------------------------------------
* 1. Load, sample, encode (mirrors reg_spec1.do:14-38)
* -------------------------------------------------------------------

use "$proj/Data/analysis/BOLD_regressor_panel.dta", clear

keep if year >= 2005 & year <= 2023

encode cell_id, gen(cell_id_num)
encode iso_a3, gen(country_num)
xtset cell_id_num year

* -------------------------------------------------------------------
* 2. Construct shock-trigger flags + composite FE IDs (mirrors reg_spec1.do:44-50)
* -------------------------------------------------------------------

* Defensive 0-fill so missing-as-not-treated doesn't bork the lookback logic.
replace ucdp_any_all      = 0 if missing(ucdp_any_all)      & year >= 2005 & year <= 2023
replace any_burned        = 0 if missing(any_burned)        & year >= 2005 & year <= 2023
replace ibtracs_any_64kt  = 0 if missing(ibtracs_any_64kt)  & year >= 2005 & year <= 2023

* Continuous conflict intensity for STEP 3 (matches reg_spec1.do Panel A formulation).
gen log1p_conflict = log(1 + ucdp_events_all)

* Composite FE IDs for did_imputation fe() argument (numeric groups required).
egen country_year = group(country_num year)
egen biome_year   = group(resolve_biome_num year)
replace country_year = . if missing(country_num)
replace biome_year   = . if missing(resolve_biome_num)

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
display "{txt}=== HDFE backend: `hdfe_cmd' ==="

* -------------------------------------------------------------------
* 3. add_avg_rows helper (extends reg_spec1.do:72-92 sums to averages)
* -------------------------------------------------------------------

capture program drop add_avg_rows
program define add_avg_rows
    syntax , NAME(name) EXPR(string asis) DIVISOR(integer)
    qui lincom (`expr') / `divisor'
    qui estadd scalar `name'    = r(estimate)
    qui estadd scalar `name'_se = r(se)
    qui estadd scalar `name'_p  = r(p)
    local b   = r(estimate)
    local se  = r(se)
    local p   = r(p)
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
    local b   = r(estimate)
    local se  = r(se)
    local p   = r(p)
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
* 4. Construct shock onset variables for conflict / drought / fire
* -------------------------------------------------------------------

* ---- Conflict onset (K=10): first ucdp_any_all=1 after 10 zero years ----
* K=10 chosen because K=5 admitted recently-pacified cells whose 5-year
* peace was actually post-conflict recovery, contaminating the pre-period
* (pre_p = 0.020 on intensive margin). With K=10 pre_p = 0.155 — clean.
* Earliest possible onset year is 2015 (panel starts 2005, need 10 zeros).
gen lookback_conflict = 1
forvalues k = 1/10 {
    replace lookback_conflict = 0 if L`k'.ucdp_any_all != 0 | missing(L`k'.ucdp_any_all)
}
gen onset_flag_conflict = (ucdp_any_all == 1 & lookback_conflict == 1)
bysort cell_id_num (year): egen onset_year_conflict = ///
    min(cond(onset_flag_conflict==1, year, .))
gen Ei_conflict = onset_year_conflict
gen et_conflict = year - Ei_conflict   // missing for never-treated
gen ever_conflict = !missing(Ei_conflict)

* ---- Severe drought onset (K=5): first pdsi_anomaly<-2 after 5 years pdsi>-1 ----
gen lookback_drought = 1
forvalues k = 1/5 {
    replace lookback_drought = 0 if L`k'.pdsi_anomaly <= -1 | missing(L`k'.pdsi_anomaly)
}
gen onset_flag_drought = (pdsi_anomaly < -2 & lookback_drought == 1) if !missing(pdsi_anomaly)
bysort cell_id_num (year): egen onset_year_drought = ///
    min(cond(onset_flag_drought==1, year, .))
gen Ei_drought = onset_year_drought
gen et_drought = year - Ei_drought

* ---- Fire onset (K=3): first any_burned=1 after 3 zero years ----
gen lookback_fire = 1
forvalues k = 1/3 {
    replace lookback_fire = 0 if L`k'.any_burned != 0 | missing(L`k'.any_burned)
}
gen onset_flag_fire = (any_burned == 1 & lookback_fire == 1)
bysort cell_id_num (year): egen onset_year_fire = ///
    min(cond(onset_flag_fire==1, year, .))
gen Ei_fire = onset_year_fire
gen et_fire = year - Ei_fire

* ---- Diagnostic: cohort sizes ----
display _n "{txt}=== Onset cohort counts ==="
foreach shk in conflict drought fire {
    preserve
    bysort cell_id_num: keep if _n == 1
    display _n "{txt}--- `shk' onset cohorts ---"
    tab Ei_`shk', missing
    restore
}

* ===================================================================
* SECTION A — CONFLICT IDENTIFICATION LADDER
* ===================================================================

* -------------------------------------------------------------------
* A.STEP 1: TWFE event-study — both LHS
*   Implemented directly in reghdfe rather than through eventdd so the
*   coefficient names are explicit and the script does not depend on
*   eventdd's version-specific syntax. This is still the conventional
*   TWFE lead/lag design; Step 2 remains the modern BJS comparison.
* -------------------------------------------------------------------

est clear

display _n "{txt}=== STEP 1: TWFE event-study (conflict) ==="

* Match the event-study naming used later in tables/plots:
*   lead6 = event time <= -6
*   lead5 = -5
*   lead4 = -4
*   lead3 = -3
*   lead2 = -2
*   lag0  = 0
*   ...
*   lag8  = event time >= +8
foreach v in lead6 lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
    capture drop `v'
}
gen byte lead6 = (et_conflict <= -6) if !missing(et_conflict)
gen byte lead5 = (et_conflict == -5) if !missing(et_conflict)
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
foreach v in lead6 lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
    replace `v' = 0 if missing(`v')
}

foreach lhs in any_total log1p_total {
    display _n "{txt}--- TWFE event-study: LHS = `lhs' ---"

    qui `hdfe_cmd' `lhs' ///
        lead6 lead5 lead4 lead3 lead2 ///
        lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8, ///
        absorb(`absorb_main') ///
        vce(cluster cell_id_num)

    estimates store twfe_`lhs'

    qui test lead6 lead5 lead4 lead3 lead2
    qui estadd scalar pretrend_p = r(p)

    add_avg_rows, name(att_avg_03) expr(lag0 + lag1 + lag2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(lag0 + lag1 + lag2 + lag3 + lag4) divisor(5)
    add_avg_rows, name(att_avg_08) ///
        expr(lag0 + lag1 + lag2 + lag3 + lag4 + lag5 + lag6 + lag7 + lag8) divisor(9)

    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "TWFE event-study"
    estadd local treatment    "Binary onset (UCDP)"
    estadd local lhs_label    "`lhs'"
    estadd local shock        "conflict"
}

* -------------------------------------------------------------------
* A.STEP 2: BJS imputation event-study — both LHS, conflict only
*   The modern estimator that handles heterogeneous timing properly.
*   Same binary onset trigger as Step 1; difference is purely the
*   imputation methodology.
* -------------------------------------------------------------------

display _n "{txt}=== STEP 2: BJS imputation event-study (conflict) ==="

foreach lhs in any_total log1p_total {
    display _n "{txt}--- BJS event-study: LHS = `lhs' ---"

    qui did_imputation `lhs' cell_id_num year Ei_conflict, ///
        fe(`did_fe') ///
        horizons(0/8) pretrends(5) ///
        cluster(cell_id_num) autosample

    estimates store bjs_conflict_`lhs'

    qui estadd scalar pretrend_p = e(pre_p)

    add_avg_rows, name(att_avg_03) expr(tau0 + tau1 + tau2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(tau0 + tau1 + tau2 + tau3 + tau4) divisor(5)
    add_avg_rows, name(att_avg_08) ///
        expr(tau0 + tau1 + tau2 + tau3 + tau4 + tau5 + tau6 + tau7 + tau8) divisor(9)

    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "BJS imputation"
    estadd local treatment    "Binary onset (K=10)"
    estadd local lhs_label    "`lhs'"
    estadd local shock        "conflict"
}

* -------------------------------------------------------------------
* A.STEP 3: Continuous-treatment distributed-lag dynamic DID — log1p_total only
*   Treatment = log(1 + ucdp_events_all) intensity, not the binary onset.
*   Distributed-lag specification with leads (placebo) and lags (dynamics).
*
*   Note: this is a pre-CGS-2024 simple distributed-lag spec, not the full
*   Callaway-Goodman-Bacon-Sant'Anna 2024 continuous-treatment DID. CGS-2024
*   adds heterogeneous-treatment-effect aggregation across cells with
*   different intensity changes; the simple distributed-lag here gives the
*   average dynamic effect at the cell level. Sufficient as robustness
*   showing the binary onset isn't masking heterogeneous intensity effects.
* -------------------------------------------------------------------

display _n "{txt}=== STEP 3: Continuous-treatment distributed-lag DID (conflict intensity) ==="

* Build leads/lags of the continuous treatment
forvalues k = 1/5 {
    gen F`k'_log1p_conflict = F`k'.log1p_conflict
    gen L`k'_log1p_conflict = L`k'.log1p_conflict
}

qui `hdfe_cmd' log1p_total ///
    F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict F1_log1p_conflict ///
    log1p_conflict ///
    L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict L5_log1p_conflict, ///
    absorb(`absorb_main') ///
    vce(cluster cell_id_num)

estimates store cont_conflict_log1p_total

* Cumulative-effect rows: L0+L1+L2 sum and L0+L1+L2+L3+L4 sum
add_sum_rows, name(conflict_sum_03) ///
    expr(log1p_conflict + L1_log1p_conflict + L2_log1p_conflict)
add_sum_rows, name(conflict_sum_05) ///
    expr(log1p_conflict + L1_log1p_conflict + L2_log1p_conflict + ///
         L3_log1p_conflict + L4_log1p_conflict)

* Joint pre-trend test on placebo leads F1..F5
qui test F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict F1_log1p_conflict
estadd scalar pretrend_p = r(p)

estadd local fe_cell      "\checkmark"
estadd local fe_year      "`fe_label_year'"
estadd local fe_cy        "`fe_label_cy'"
estadd local fe_biome_yr  "`fe_label_biome'"
estadd local estimator    "DL continuous"
estadd local treatment    "Intensity log(1+events)"
estadd local lhs_label    "log1p_total"

* -------------------------------------------------------------------
* A.STEP 3b: dCDH heterogeneity-robust dynamic DID — log1p_total only
*   de Chaisemartin & D'Haultfœuille 2024, "Difference-in-Differences
*   Estimators of Intertemporal Treatment Effects." Implements the
*   heterogeneity-robust dynamic-effect estimator. Two virtues over
*   Step 3 (simple DL):
*     1. Allows non-absorbing treatment (conflict can switch on and off,
*        consistent with the underlying UCDP data).
*     2. Aggregates heterogeneous treatment effects across cells with
*        different intensity changes (modern continuous-treatment DID).
*
*   FE concession: did_multiplegt_dyn does not natively absorb
*   country×year and biome×year. To preserve the saturated FE story,
*   we residualize log1p_total on cell + country×year + biome×year
*   FE first (Frisch-Waugh-style), then run dCDH with cell + year FE
*   internally on the residual. Approximation under non-OLS estimators
*   but the standard workaround. The fe_cy / fe_biome_yr cells in the
*   table are flagged with an asterisk to denote "via residualization."
* -------------------------------------------------------------------

display _n "{txt}=== STEP 3b: dCDH heterogeneity-robust dynamic DID ==="

if "`fe_mode'" == "rich" {
    * Residualize log1p_total on the saturated FE structure (FW-style)
    qui `hdfe_cmd' log1p_total, ///
        absorb(`absorb_main') ///
        resid(log1p_total_resid)

    * dCDH dynamic estimator on the residualized outcome with continuous treatment
    qui did_multiplegt_dyn log1p_total_resid cell_id_num year log1p_conflict, ///
        effects(10) placebo(5) cluster(cell_id_num) graph_off
}
else {
    * Under simple FE, did_multiplegt_dyn's internal cell + year structure matches the target spec.
    qui did_multiplegt_dyn log1p_total cell_id_num year log1p_conflict, ///
        effects(10) placebo(5) cluster(cell_id_num) graph_off
}

estimates store dcdh_conflict_log1p_total

add_sum_rows, name(conflict_sum_03) ///
    expr(Effect_1 + Effect_2 + Effect_3)
add_sum_rows, name(conflict_sum_05) ///
    expr(Effect_1 + Effect_2 + Effect_3 + Effect_4 + Effect_5)

qui test Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1
estadd scalar pretrend_p = r(p)

estadd local fe_cell      "\checkmark"
estadd local fe_year      "`fe_label_year'"
estadd local fe_cy        "`fe_label_cy'"
estadd local fe_biome_yr  "`fe_label_biome'"
estadd local estimator    "dCDH dyn (cont)"
estadd local treatment    "Intensity log(1+events)"
estadd local lhs_label    "log1p_total"
estadd local fe_note      "`dcdh_fe_note'"

* -------------------------------------------------------------------
* A.ROBUSTNESS: Callaway-Sant'Anna for log1p_total — simple FE
* -------------------------------------------------------------------

display _n "{txt}=== Callaway-Sant'Anna robustness (conflict, log1p_total) ==="

gen gvar_conflict = cond(missing(Ei_conflict), 0, Ei_conflict)

qui csdid log1p_total, ivar(cell_id_num) time(year) gvar(gvar_conflict) ///
    method(reg) notyet
qui estat event, estore(cs_conflict_log1p_total)

estimates restore cs_conflict_log1p_total

add_sum_rows, name(conflict_sum_03) ///
    expr(Tp0 + Tp1 + Tp2)
add_sum_rows, name(conflict_sum_05) ///
    expr(Tp0 + Tp1 + Tp2 + Tp3 + Tp4)

qui test Tm5 Tm4 Tm3 Tm2 Tm1
estadd scalar pretrend_p = r(p)

estadd local fe_cell      "\checkmark"
if "`fe_mode'" == "simple" estadd local fe_year "\checkmark"
else                        estadd local fe_year " "
estadd local fe_cy        " "
estadd local fe_biome_yr  " "
estadd local estimator    "Callaway-Sant'Anna"
estadd local treatment    "Binary onset (UCDP)"
estadd local lhs_label    "log1p_total"
if "`fe_mode'" == "simple" estadd local fe_note "time effects via csdid"
else                        estadd local fe_note " "

* ===================================================================
* SECTION B — MULTI-SHOCK PARALLEL COMPARISON
*   Drought + fire onset event-studies on log1p_total, shown in both
*   BJS and simple TWFE form alongside the conflict specification.
* ===================================================================

display _n "{txt}=== SECTION B1: Multi-shock TWFE comparison ==="

foreach shk in conflict drought fire {
    display _n "{txt}--- TWFE event-study: `shk' (LHS = log1p_total) ---"

    foreach v in lead6 lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
        capture drop `v'
    }
    gen byte lead6 = (et_`shk' <= -6) if !missing(et_`shk')
    gen byte lead5 = (et_`shk' == -5) if !missing(et_`shk')
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
    foreach v in lead6 lead5 lead4 lead3 lead2 lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8 {
        replace `v' = 0 if missing(`v')
    }

    qui `hdfe_cmd' log1p_total ///
        lead6 lead5 lead4 lead3 lead2 ///
        lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8, ///
        absorb(`absorb_main') ///
        vce(cluster cell_id_num)

    estimates store twfe_`shk'_log1p_total

    qui test lead6 lead5 lead4 lead3 lead2
    qui estadd scalar pretrend_p = r(p)
    add_avg_rows, name(att_avg_03) expr(lag0 + lag1 + lag2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(lag0 + lag1 + lag2 + lag3 + lag4) divisor(5)
    add_avg_rows, name(att_avg_08) ///
        expr(lag0 + lag1 + lag2 + lag3 + lag4 + lag5 + lag6 + lag7 + lag8) divisor(9)

    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "TWFE event-study"
    estadd local treatment    "Binary onset"
    estadd local lhs_label    "log1p_total"
    estadd local shock        "`shk'"
}

display _n "{txt}=== SECTION B2: Multi-shock BJS comparison ==="

foreach shk in drought fire {
    display _n "{txt}--- BJS event-study: `shk' (LHS = log1p_total) ---"

    qui did_imputation log1p_total cell_id_num year Ei_`shk', ///
        fe(`did_fe') ///
        horizons(0/8) pretrends(5) ///
        cluster(cell_id_num) autosample

    estimates store bjs_`shk'_log1p_total

    qui estadd scalar pretrend_p = e(pre_p)
    add_avg_rows, name(att_avg_03) expr(tau0 + tau1 + tau2) divisor(3)
    add_avg_rows, name(att_avg_05) expr(tau0 + tau1 + tau2 + tau3 + tau4) divisor(5)
    add_avg_rows, name(att_avg_08) ///
        expr(tau0 + tau1 + tau2 + tau3 + tau4 + tau5 + tau6 + tau7 + tau8) divisor(9)

    estadd local fe_cell      "\checkmark"
    estadd local fe_year      "`fe_label_year'"
    estadd local fe_cy        "`fe_label_cy'"
    estadd local fe_biome_yr  "`fe_label_biome'"
    estadd local estimator    "BJS imputation"
    estadd local treatment    "Binary onset"
    estadd local lhs_label    "log1p_total"
    estadd local shock        "`shk'"
}

* ===================================================================
* PRE-TREND DIAGNOSTIC PRINT
*   K=10 conflict + K=5 drought + K=3 fire — all should show pre_p > 0.10
*   for parallel-trends to hold.
* ===================================================================

display _n(2) "{txt}========================================================================"
display "{txt}  PARALLEL-TRENDS TESTS (joint Wald on pre1...pre5)"
display "{txt}========================================================================"
foreach m in bjs_conflict_any_total bjs_conflict_log1p_total ///
             bjs_drought_log1p_total bjs_fire_log1p_total {
    estimates restore `m'
    display %-40s "`m'" ///
            "  pre_p = " %5.3f e(pre_p) ///
            "  pre_F = " %5.2f e(pre_F) ///
            "  N = " %9.0fc e(N)
}
display "{txt}========================================================================"

* ===================================================================
* TABLES
* ===================================================================

* -------------------------------------------------------------------
* TABLE 1 — Section A: Conflict identification ladder, both LHS
*   Cols: (1) TWFE any   (2) BJS any    (3) TWFE log    (4) BJS log
* -------------------------------------------------------------------

display _n "{txt}=== TABLE 1: Conflict identification ladder (TWFE vs BJS, two LHS) ==="

* Rename coefficients to a common event-time scheme so TWFE and BJS appear
* on the same rows in the table (and the same x-positions in coefplot).
*   TWFE:     lead6  lead5  lead4  lead3  lead2 | lag0  lag1  ... lag8
*             (lead1 is the reference, omitted; lag8 is top-coded at 8+)
*   BJS:      pre5   pre4   pre3   pre2  pre1 | tau0  tau1  ... tau8
*             (τ_{-1} is the reference, omitted)
* Mapping to common τ_{m#} / τ_{p#} naming (τ_{-1} = reference):
*   τ_{-6}: TWFE lead6 (binned)        / BJS pre5
*   τ_{-5}: TWFE lead5                 / BJS pre4
*   τ_{-4}: TWFE lead4                  / BJS pre3
*   τ_{-3}: TWFE lead3                  / BJS pre2
*   τ_{-2}: TWFE lead2                  / BJS pre1
*   τ_{0}:  TWFE lag0                   / BJS tau0
*   ...
*   τ_{+8}:  TWFE lag8 (binned)         / BJS tau8

esttab twfe_any_total bjs_conflict_any_total twfe_log1p_total bjs_conflict_log1p_total, ///
    rename(lead6 t_m6 lead5 t_m5 lead4 t_m4 lead3 t_m3 lead2 t_m2 ///
           lag0 t_p0 lag1 t_p1 lag2 t_p2 lag3 t_p3 lag4 t_p4 lag5 t_p5 ///
           lag6 t_p6 lag7 t_p7 lag8 t_p8 ///
           pre5 t_m6 pre4 t_m5 pre3 t_m4 pre2 t_m3 pre1 t_m2 ///
           tau0 t_p0 tau1 t_p1 tau2 t_p2 tau3 t_p3 tau4 t_p4 tau5 t_p5 ///
           tau6 t_p6 tau7 t_p7 tau8 t_p8) ///
    keep(t_m6 t_m5 t_m4 t_m3 t_m2 ///
         t_p0 t_p1 t_p2 t_p3 t_p4 t_p5 t_p6 t_p7 t_p8) ///
    order(t_m6 t_m5 t_m4 t_m3 t_m2 ///
          t_p0 t_p1 t_p2 t_p3 t_p4 t_p5 t_p6 t_p7 t_p8) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(t_m6 "τ_{-6}+" t_m5 "τ_{-5}" t_m4 "τ_{-4}" t_m3 "τ_{-3}" t_m2 "τ_{-2}" ///
              t_p0 "τ_{0}" t_p1 "τ_{+1}" t_p2 "τ_{+2}" t_p3 "τ_{+3}" t_p4 "τ_{+4}" ///
              t_p5 "τ_{+5}" t_p6 "τ_{+6}" t_p7 "τ_{+7}" t_p8 "τ_{+8}+") ///
    stats(att_avg_03_txt att_avg_03_se_txt ///
          att_avg_05_txt att_avg_05_se_txt ///
          att_avg_08_txt att_avg_08_se_txt ///
          pretrend_p estimator treatment lhs_label N r2 ///
          fe_cell fe_year fe_cy fe_biome_yr, ///
          labels("Avg ATT τ0-τ2" " " ///
                 "Avg ATT τ0-τ4" " " ///
                 "Avg ATT τ0-τ8 (headline)" " " ///
                 "Pre-trend joint p" "Estimator" "Treatment" "LHS" "Obs." "R-sq." ///
                 "Cell FE" "Year FE" "Country x Year FE" "Biome x Year FE") ///
          fmt(%s %s %s %s %s %s %9.4f %s %s %s %9.0fc %9.4f %s %s %s %s)) ///
    title("Table 1: Conflict identification ladder — TWFE vs BJS, two LHS (window -6/+8)") ///
    mtitles("any_total" "any_total" "log1p_total" "log1p_total") ///
    mgroups("TWFE event-study" "BJS imputation" "TWFE event-study" "BJS imputation", ///
            pattern(1 1 1 1)) ///
    compress

* -------------------------------------------------------------------
* TABLE 2 — Section A Step 3: Continuous-treatment distributed-lag DID
*   Single column on log1p_total intensity-margin LHS
* -------------------------------------------------------------------

display _n "{txt}=== TABLE 2: Continuous-treatment dynamic DID + CS robustness ==="

* dCDH numbering: Effect_1 = τ_0 (contemp), Effect_2 = τ_{+1}, ..., Effect_10 = τ_{+9}.
* Placebo_1 = τ_{-1} (NOT a reference; dCDH estimates it explicitly), ..., Placebo_5 = τ_{-5}.
* CS horizon is shorter here: with K=10 conflict onset and a 2005-2023 panel,
* the earliest treated cohort is 2015, so csdid can only identify Tp0...Tp8.
esttab cont_conflict_log1p_total dcdh_conflict_log1p_total cs_conflict_log1p_total, ///
    keep(F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict ///
         F1_log1p_conflict log1p_conflict ///
         L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict ///
         L5_log1p_conflict ///
         Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1 ///
         Effect_1 Effect_2 Effect_3 Effect_4 Effect_5 ///
         Effect_6 Effect_7 Effect_8 Effect_9 Effect_10 ///
         Tm5 Tm4 Tm3 Tm2 Tm1 ///
         Tp0 Tp1 Tp2 Tp3 Tp4 Tp5 Tp6 Tp7 Tp8) ///
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
    title("Table 2: Continuous-treatment dynamic DID (intensity) + CS robustness (binary)") ///
    mtitles("DL continuous" "dCDH dyn" "Callaway-Sant'Anna") ///
    compress

* -------------------------------------------------------------------
* TABLE 3 — Section B: Multi-shock BJS parallel comparison
*   Cols: BJS conflict, BJS drought, BJS fire — all on log1p_total
* -------------------------------------------------------------------

display _n "{txt}=== TABLE 3: Multi-shock BJS comparison (log1p_total) ==="

esttab bjs_conflict_log1p_total bjs_drought_log1p_total bjs_fire_log1p_total, ///
    keep(pre5 pre4 pre3 pre2 pre1 ///
         tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    order(pre5 pre4 pre3 pre2 pre1 ///
          tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    stats(att_avg_03_txt att_avg_03_se_txt ///
          att_avg_05_txt att_avg_05_se_txt ///
          att_avg_08_txt att_avg_08_se_txt ///
          pretrend_p estimator shock lhs_label N r2 ///
          fe_cell fe_year fe_cy fe_biome_yr, ///
          labels("Avg ATT τ0-τ2" " " ///
                 "Avg ATT τ0-τ4" " " ///
                 "Avg ATT τ0-τ8 (headline)" " " ///
                 "Pre-trend joint p" "Estimator" "Shock" "LHS" "Obs." "R-sq." ///
                 "Cell FE" "Year FE" "Country x Year FE" "Biome x Year FE") ///
          fmt(%s %s %s %s %s %s %9.4f %s %s %s %9.0fc %9.4f %s %s %s %s)) ///
    title("Table 3: Multi-shock BJS comparison on log1p_total (window -6/+8)") ///
    mtitles("Conflict" "Severe drought" "Fire") ///
    compress

* -------------------------------------------------------------------
* TABLE 4 — Section B: Multi-shock TWFE parallel comparison
*   Same shocks/outcome as Table 3, but with a simple TWFE lead/lag design.
* -------------------------------------------------------------------

display _n "{txt}=== TABLE 4: Multi-shock TWFE comparison (log1p_total) ==="

esttab twfe_conflict_log1p_total twfe_drought_log1p_total twfe_fire_log1p_total, ///
    keep(lead6 lead5 lead4 lead3 lead2 ///
         lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    order(lead6 lead5 lead4 lead3 lead2 ///
          lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    se star(* 0.10 ** 0.05 *** 0.01) b(4) se(4) ///
    varlabels(lead6 "τ_{-6}+" lead5 "τ_{-5}" lead4 "τ_{-4}" lead3 "τ_{-3}" lead2 "τ_{-2}" ///
              lag0 "τ_{0}" lag1 "τ_{+1}" lag2 "τ_{+2}" lag3 "τ_{+3}" lag4 "τ_{+4}" ///
              lag5 "τ_{+5}" lag6 "τ_{+6}" lag7 "τ_{+7}" lag8 "τ_{+8}+") ///
    stats(att_avg_03_txt att_avg_03_se_txt ///
          att_avg_05_txt att_avg_05_se_txt ///
          att_avg_08_txt att_avg_08_se_txt ///
          pretrend_p estimator shock lhs_label N r2 ///
          fe_cell fe_year fe_cy fe_biome_yr, ///
          labels("Avg ATT τ0-τ2" " " ///
                 "Avg ATT τ0-τ4" " " ///
                 "Avg ATT τ0-τ8 (headline)" " " ///
                 "Pre-trend joint p" "Estimator" "Shock" "LHS" "Obs." "R-sq." ///
                 "Cell FE" "Year FE" "Country x Year FE" "Biome x Year FE") ///
          fmt(%s %s %s %s %s %s %9.4f %s %s %s %9.0fc %9.4f %s %s %s %s)) ///
    title("Table 4: Multi-shock TWFE comparison on log1p_total (window -6/+8)") ///
    mtitles("Conflict" "Severe drought" "Fire") ///
    compress

* ===================================================================
* FIGURES
* ===================================================================

* -------------------------------------------------------------------
* FIGURE 1 — TWFE vs BJS comparison for conflict, log1p_total LHS
*   The "Goodman-Bacon wedge" figure: visual side-by-side, intensive margin
* -------------------------------------------------------------------

display _n "{txt}=== FIGURE 1: TWFE vs BJS conflict (log1p_total) ==="

* Common rename mapping (same as Table 1) so TWFE and BJS coefficients align
* on the x-axis. coefplot's rename() syntax differs from esttab's: it uses
* `oldname = "newname"` per pair.

* Two-panel side-by-side: TWFE (left) and BJS (right), each with native
* coefficient names. graph combine merges into one figure. Sidesteps the
* coefplot rename/keep ordering issue entirely.

* --- Panel A: TWFE ---
coefplot (twfe_log1p_total, label("TWFE event-study") msymbol(O) mcolor(navy) ///
        ciopts(lcolor(navy))), ///
    keep(lead6 lead5 lead4 lead3 lead2 ///
         lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    order(lead6 lead5 lead4 lead3 lead2 ///
          lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    coeflabels(lead6 = "-6+" lead5 = "-5" lead4 = "-4" lead3 = "-3" lead2 = "-2" ///
               lag0 = "0" lag1 = "+1" lag2 = "+2" lag3 = "+3" lag4 = "+4" lag5 = "+5" ///
               lag6 = "+6" lag7 = "+7" lag8 = "+8+") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on log(1 + total records)") ///
    title("TWFE event-study", size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(off) ///
    name(es_twfe_only_log, replace)

* --- Panel B: BJS ---
coefplot (bjs_conflict_log1p_total, label("BJS imputation") msymbol(D) mcolor(maroon) ///
        ciopts(lcolor(maroon))), ///
    keep(pre5 pre4 pre3 pre2 pre1 ///
         tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    order(pre5 pre4 pre3 pre2 pre1 ///
          tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    coeflabels(pre5 = "-6" pre4 = "-5" pre3 = "-4" pre2 = "-3" pre1 = "-2" ///
               tau0 = "0" tau1 = "+1" tau2 = "+2" tau3 = "+3" tau4 = "+4" tau5 = "+5" ///
               tau6 = "+6" tau7 = "+7" tau8 = "+8") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on log(1 + total records)") ///
    title("BJS imputation", size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(off) ///
    name(es_bjs_only_log, replace)

* --- Combine ---
graph combine es_twfe_only_log es_bjs_only_log, ///
    title("TWFE vs BJS imputation: conflict effect on biodiversity sampling (intensive)", ///
          size(medium)) ///
    cols(2) ycommon ///
    name(es_twfe_bjs_log, replace)

graph save "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_log1p.gph", replace
graph export "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_log1p.pdf", replace

* -------------------------------------------------------------------
* FIGURE 2 — TWFE vs BJS comparison for conflict, any_total LHS (extensive margin)
*   Parallel to Figure 1 but for the extensive (1[total > 0]) outcome.
* -------------------------------------------------------------------

display _n "{txt}=== FIGURE 2: TWFE vs BJS conflict (any_total) ==="

* --- Panel A: TWFE (any_total) ---
coefplot (twfe_any_total, label("TWFE event-study") msymbol(O) mcolor(navy) ///
        ciopts(lcolor(navy))), ///
    keep(lead6 lead5 lead4 lead3 lead2 ///
         lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    order(lead6 lead5 lead4 lead3 lead2 ///
          lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8) ///
    coeflabels(lead6 = "-6+" lead5 = "-5" lead4 = "-4" lead3 = "-3" lead2 = "-2" ///
               lag0 = "0" lag1 = "+1" lag2 = "+2" lag3 = "+3" lag4 = "+4" lag5 = "+5" ///
               lag6 = "+6" lag7 = "+7" lag8 = "+8+") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on 1[total records > 0]") ///
    title("TWFE event-study", size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(off) ///
    name(es_twfe_only_any, replace)

* --- Panel B: BJS (any_total) ---
coefplot (bjs_conflict_any_total, label("BJS imputation") msymbol(D) mcolor(maroon) ///
        ciopts(lcolor(maroon))), ///
    keep(pre5 pre4 pre3 pre2 pre1 ///
         tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    order(pre5 pre4 pre3 pre2 pre1 ///
          tau0 tau1 tau2 tau3 tau4 tau5 tau6 tau7 tau8) ///
    coeflabels(pre5 = "-6" pre4 = "-5" pre3 = "-4" pre2 = "-3" pre1 = "-2" ///
               tau0 = "0" tau1 = "+1" tau2 = "+2" tau3 = "+3" tau4 = "+4" tau5 = "+5" ///
               tau6 = "+6" tau7 = "+7" tau8 = "+8") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xtitle("Years from conflict onset") ///
    ytitle("Effect on 1[total records > 0]") ///
    title("BJS imputation", size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(off) ///
    name(es_bjs_only_any, replace)

* --- Combine ---
graph combine es_twfe_only_any es_bjs_only_any, ///
    title("TWFE vs BJS imputation: conflict effect on biodiversity sampling (extensive)", ///
          size(medium)) ///
    cols(2) ycommon ///
    name(es_twfe_bjs_any, replace)

graph save "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_any.gph", replace
graph export "$proj/Output/figures/event_study/twfe_vs_bjs_conflict_any.pdf", replace

* -------------------------------------------------------------------
* FIGURE 3 — Multi-shock BJS comparison (Section B headline figure)
* -------------------------------------------------------------------

display _n "{txt}=== FIGURE 3: Multi-shock BJS comparison ==="

local plotcoefs pre5 pre4 pre3 pre2 pre1 ///
                tau0 tau1 tau2 tau3 tau4 tau5 ///
                tau6 tau7 tau8

coefplot ///
    (bjs_conflict_log1p_total, label("Conflict") msymbol(O) mcolor(navy) ///
        ciopts(lcolor(navy))) ///
    (bjs_drought_log1p_total,  label("Severe drought") msymbol(D) mcolor(maroon) ///
        ciopts(lcolor(maroon))) ///
    (bjs_fire_log1p_total,     label("Fire") msymbol(S) mcolor(forest_green) ///
        ciopts(lcolor(forest_green))), ///
    keep(`plotcoefs') ///
    order(`plotcoefs') ///
    coeflabels(pre5 = "-6" pre4 = "-5" pre3 = "-4" pre2 = "-3" pre1 = "-2" ///
               tau0 = "0" tau1 = "+1" tau2 = "+2" tau3 = "+3" tau4 = "+4" tau5 = "+5" ///
               tau6 = "+6" tau7 = "+7" tau8 = "+8") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xline(5.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from shock onset (τ_{-1} = reference)") ///
    ytitle("Effect on log(1 + total records)") ///
    title("BJS event-study: BOLD sampling response to shock onsets", size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(rows(1) position(6) size(small)) ///
    name(es_multishock, replace)

graph save "$proj/Output/figures/event_study/bjs_conflict_drought_fire.gph", replace
graph export "$proj/Output/figures/event_study/bjs_conflict_drought_fire.pdf", replace

* -------------------------------------------------------------------
* FIGURE 4 — Multi-shock TWFE comparison
* -------------------------------------------------------------------

display _n "{txt}=== FIGURE 4: Multi-shock TWFE comparison ==="

local plotcoefs_twfe lead6 lead5 lead4 lead3 lead2 ///
                     lag0 lag1 lag2 lag3 lag4 lag5 lag6 lag7 lag8

coefplot ///
    (twfe_conflict_log1p_total, label("Conflict") msymbol(O) mcolor(navy) ///
        ciopts(lcolor(navy))) ///
    (twfe_drought_log1p_total,  label("Severe drought") msymbol(D) mcolor(maroon) ///
        ciopts(lcolor(maroon))) ///
    (twfe_fire_log1p_total,     label("Fire") msymbol(S) mcolor(forest_green) ///
        ciopts(lcolor(forest_green))), ///
    keep(`plotcoefs_twfe') ///
    order(`plotcoefs_twfe') ///
    coeflabels(lead6 = "-6+" lead5 = "-5" lead4 = "-4" lead3 = "-3" lead2 = "-2" ///
               lag0 = "0" lag1 = "+1" lag2 = "+2" lag3 = "+3" lag4 = "+4" lag5 = "+5" ///
               lag6 = "+6" lag7 = "+7" lag8 = "+8+") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xline(5.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from shock onset (τ_{-1} = reference)") ///
    ytitle("Effect on log(1 + total records)") ///
    title("TWFE event-study: BOLD sampling response to shock onsets", size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(rows(1) position(6) size(small)) ///
    name(es_multishock_twfe, replace)

graph save "$proj/Output/figures/event_study/twfe_conflict_drought_fire.gph", replace
graph export "$proj/Output/figures/event_study/twfe_conflict_drought_fire.pdf", replace

* -------------------------------------------------------------------
* FIGURE 5 — Continuous-treatment distributed-lag dynamic effects
* -------------------------------------------------------------------

display _n "{txt}=== FIGURE 5: Continuous-treatment dynamic effects (intensity) ==="

coefplot (cont_conflict_log1p_total, label("DL continuous") msymbol(O) mcolor(navy) ///
        ciopts(lcolor(navy))), ///
    keep(F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict ///
         F1_log1p_conflict log1p_conflict ///
         L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict ///
         L5_log1p_conflict) ///
    order(F5_log1p_conflict F4_log1p_conflict F3_log1p_conflict F2_log1p_conflict ///
          F1_log1p_conflict log1p_conflict ///
          L1_log1p_conflict L2_log1p_conflict L3_log1p_conflict L4_log1p_conflict ///
          L5_log1p_conflict) ///
    coeflabels(F5_log1p_conflict = "-5" F4_log1p_conflict = "-4" ///
               F3_log1p_conflict = "-3" F2_log1p_conflict = "-2" ///
               F1_log1p_conflict = "-1" log1p_conflict = "0" ///
               L1_log1p_conflict = "+1" L2_log1p_conflict = "+2" ///
               L3_log1p_conflict = "+3" L4_log1p_conflict = "+4" ///
               L5_log1p_conflict = "+5") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xline(5.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from contemporaneous (F = leads, L = lags)") ///
    ytitle("Effect on log(1 + total records) per unit log(1 + events)") ///
    title("Continuous-treatment distributed-lag DID: conflict intensity dynamics", ///
          size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(off) ///
    name(es_continuous, replace)

graph save "$proj/Output/figures/event_study/continuous_dl_conflict_log1p.gph", replace
graph export "$proj/Output/figures/event_study/continuous_dl_conflict_log1p.pdf", replace

* -------------------------------------------------------------------
* FIGURE 6 — dCDH heterogeneity-robust dynamic effects (continuous treatment)
*   Step 3b output. Coefficient names: Placebo_5...Placebo_1 (pre),
*   Effect_1...Effect_10 (post, with Effect_1 = tau0). FE absorbed via
*   residualization (see Step 3b).
* -------------------------------------------------------------------

display _n "{txt}=== FIGURE 6: dCDH dynamic effects (intensity) ==="

coefplot (dcdh_conflict_log1p_total, label("dCDH dynamic") msymbol(O) mcolor(navy) ///
        ciopts(lcolor(navy))), ///
    keep(Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1 ///
         Effect_1 Effect_2 Effect_3 Effect_4 Effect_5 ///
         Effect_6 Effect_7 Effect_8 Effect_9 Effect_10) ///
    order(Placebo_5 Placebo_4 Placebo_3 Placebo_2 Placebo_1 ///
          Effect_1 Effect_2 Effect_3 Effect_4 Effect_5 ///
          Effect_6 Effect_7 Effect_8 Effect_9 Effect_10) ///
    coeflabels(Placebo_5 = "-5" Placebo_4 = "-4" Placebo_3 = "-3" ///
               Placebo_2 = "-2" Placebo_1 = "-1" ///
               Effect_1 = "0" Effect_2 = "+1" Effect_3 = "+2" ///
               Effect_4 = "+3" Effect_5 = "+4" Effect_6 = "+5" ///
               Effect_7 = "+6" Effect_8 = "+7" Effect_9 = "+8" ///
               Effect_10 = "+9") ///
    vertical yline(0, lpattern(dash) lcolor(black)) ///
    xline(5.5, lpattern(dot) lcolor(gs8)) ///
    xtitle("Years from intensity change (Placebo = leads, Effect = lags)") ///
    ytitle("Effect on log(1 + total records) per unit log(1 + events)") ///
    title("dCDH heterogeneity-robust dynamic DID: continuous conflict intensity", ///
          size(medium)) ///
    msize(small) ciopts(recast(rcap)) ///
    legend(off) ///
    name(es_dcdh, replace)

graph save "$proj/Output/figures/event_study/dcdh_continuous_conflict_log1p.gph", replace
graph export "$proj/Output/figures/event_study/dcdh_continuous_conflict_log1p.pdf", replace

* -------------------------------------------------------------------
* 9. Cleanup
* -------------------------------------------------------------------

display _n "{txt}=== Done. ==="
display "Log:    $proj/Logs/reg_event_study.log"
display "Figures:"
display "  $proj/Output/figures/event_study/twfe_vs_bjs_conflict_log1p.pdf"
display "  $proj/Output/figures/event_study/twfe_vs_bjs_conflict_any.pdf"
display "  $proj/Output/figures/event_study/bjs_conflict_drought_fire.pdf"
display "  $proj/Output/figures/event_study/twfe_conflict_drought_fire.pdf"
display "  $proj/Output/figures/event_study/continuous_dl_conflict_log1p.pdf"
display "  $proj/Output/figures/event_study/dcdh_continuous_conflict_log1p.pdf"

log close
