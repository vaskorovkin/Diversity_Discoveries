* reg_publications_gbif_exposure.do
* Conflict -> GBIF cohort-timed dataset-level publication exposure (Option A)
*
* This do-file intentionally separates GBIF Literature API outcomes from
* corrected BOLD specimen-cohort publication-yield regressions. The corrected
* GBIF outcomes are cohort-timed: collection cell-year t receives dataset-linked
* publications only in [t, t + K]. They are still dataset-level exposure, not
* specimen-specific downstream publication yield.

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
do "`proj'/DoFiles/_beamer_paths.do"

capture log close
log using "`proj'/Logs/reg_publications_gbif_exposure.log", replace text

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
* 3. Construct RHS variables, matching reg_spec1.do / reg_publications.do
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
* 4. GBIF publication-exposure outcome summary
* -------------------------------------------------------------------

di as text "================================================================="
di as text "GBIF publication-exposure caveat"
di as text "================================================================="
di as text "GBIF Literature API links are dataset-level. Every occurrence cohort"
di as text "from a linked dataset inherits dataset publication links. The corrected"
di as text "outcomes use collection year -> future publication windows, but remain"
di as text "dataset-citing exposure rather than direct specimen citation/yield."

capture confirm variable gbif_pub_total_0_5yr
if _rc == 0 {
    summarize gbif_pub_total_0_3yr any_gbif_pub_total_0_3yr log1p_gbif_pub_total_0_3yr ///
              gbif_pub_total_0_5yr any_gbif_pub_total_0_5yr log1p_gbif_pub_total_0_5yr ///
              gbif_pub_total_0_10yr any_gbif_pub_total_0_10yr log1p_gbif_pub_total_0_10yr ///
              gbif_pub_plantae_0_5yr any_gbif_pub_plantae_0_5yr log1p_gbif_pub_plantae_0_5yr
}
else {
    di as text "Corrected GBIF cohort-timed panel not found in merged data."
    di as text "Run Scripts/pipeline/30_build_gbif_publication_exposure_panel.py and merge_all_regressors.do first."
}

* -------------------------------------------------------------------
* 5. Runner: same FE/lag/interactions as reg_publications.do, log output
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

capture program drop run_gbif_exposure
program define run_gbif_exposure
    syntax , TITLE(string) ANY(varname) LOG(varname) [PREFIX(string)]
    if "`prefix'" == "" local prefix "gbif_exposure"

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

    foreach y in `any' `log' {
        local dep_label "Any"
        local dep_index 1
        if "`y'" == "`log'" {
            local dep_label "log(1+N)"
            local dep_index 2
        }

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 3 FE -- `dep_label' -- conflict=log(1+events), contemporaneous"
        di as text "-----------------------------------------------------------------"
        cap drop conflict L1_conflict L2_conflict
        gen conflict = log(1 + ucdp_events_all)
        gen L1_conflict = L.conflict
        gen L2_conflict = L2.conflict
        reghdfe `y' conflict forest_loss_share ///
            burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        eststo `prefix'_`dep_index'
        qui estadd ysumm, mean sd
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "log(1+events)"

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 3 FE -- `dep_label' -- conflict=log(1+events), L0-L2"
        di as text "-----------------------------------------------------------------"
        reghdfe `y' conflict L1_conflict L2_conflict ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        local est_col = `dep_index' + 2
        eststo `prefix'_`est_col'
        qui estadd ysumm, mean sd
        add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "log(1+events)"
        lincom conflict + L1_conflict + L2_conflict

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 5 FE -- `dep_label' -- conflict=log(1+events), contemporaneous"
        di as text "-----------------------------------------------------------------"
        reghdfe `y' conflict c.conflict#c.richness_std ///
            forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        eststo `prefix'_t5_`dep_index'
        qui estadd ysumm, mean sd
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "log(1+events)"

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 5 FE -- `dep_label' -- conflict=log(1+events), L0-L2"
        di as text "-----------------------------------------------------------------"
        reghdfe `y' conflict L1_conflict L2_conflict ///
            c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        local est_col = `dep_index' + 2
        eststo `prefix'_t5_`est_col'
        qui estadd ysumm, mean sd
        add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
        add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std)
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "log(1+events)"
        lincom conflict + L1_conflict + L2_conflict
        lincom c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 3 FE -- `dep_label' -- conflict=1[events>0], contemporaneous"
        di as text "-----------------------------------------------------------------"
        drop conflict L1_conflict L2_conflict
        gen conflict = ucdp_any_all
        gen L1_conflict = L.ucdp_any_all
        gen L2_conflict = L2.ucdp_any_all
        reghdfe `y' conflict forest_loss_share ///
            burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        local est_col = `dep_index' + 4
        eststo `prefix'_`est_col'
        qui estadd ysumm, mean sd
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "1[events>0]"

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 3 FE -- `dep_label' -- conflict=1[events>0], L0-L2"
        di as text "-----------------------------------------------------------------"
        reghdfe `y' conflict L1_conflict L2_conflict ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        local est_col = `dep_index' + 6
        eststo `prefix'_`est_col'
        qui estadd ysumm, mean sd
        add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "1[events>0]"
        lincom conflict + L1_conflict + L2_conflict

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 5 FE -- `dep_label' -- conflict=1[events>0], contemporaneous"
        di as text "-----------------------------------------------------------------"
        reghdfe `y' conflict c.conflict#c.richness_std ///
            forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        local est_col = `dep_index' + 4
        eststo `prefix'_t5_`est_col'
        qui estadd ysumm, mean sd
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "1[events>0]"

        di as text "-----------------------------------------------------------------"
        di as text "`title' -- Table 5 FE -- `dep_label' -- conflict=1[events>0], L0-L2"
        di as text "-----------------------------------------------------------------"
        reghdfe `y' conflict L1_conflict L2_conflict ///
            c.conflict#c.richness_std c.L1_conflict#c.richness_std c.L2_conflict#c.richness_std ///
            forest_loss_share burned_share cyclone earthquake ///
            pdsi_anomaly L1_pdsi_anomaly L2_pdsi_anomaly ///
            tmax_anomaly L1_tmax_anomaly L2_tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(cell_id_num country_num#year i.resolve_biome_num#i.year) ///
            vce(cluster cell_id_num)
        local est_col = `dep_index' + 6
        eststo `prefix'_t5_`est_col'
        qui estadd ysumm, mean sd
        add_sum_rows, name(conflict_sum) expr(conflict + L1_conflict + L2_conflict)
        add_sum_rows, name(conflict_rich_sum) expr(c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std)
        qui estadd local fe_cell "\checkmark"
        qui estadd local fe_cy "\checkmark"
        qui estadd local fe_biome_yr "\checkmark"
        qui estadd local conflict_measure "1[events>0]"
        lincom conflict + L1_conflict + L2_conflict
        lincom c.conflict#c.richness_std + c.L1_conflict#c.richness_std + c.L2_conflict#c.richness_std
    }

    esttab `prefix'_1 `prefix'_2 `prefix'_3 `prefix'_4 ///
           `prefix'_5 `prefix'_6 `prefix'_7 `prefix'_8 ///
        using "$DD_CODEX_TABLES/tab_publications_gbif_`prefix'_t3.tex", ///
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

    esttab `prefix'_t5_1 `prefix'_t5_2 `prefix'_t5_3 `prefix'_t5_4 ///
           `prefix'_t5_5 `prefix'_t5_6 `prefix'_t5_7 `prefix'_t5_8 ///
        using "$DD_CODEX_TABLES/tab_publications_gbif_`prefix'_t5.tex", ///
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

* ===================================================================
* Corrected GBIF cohort-timed dataset-level publication exposure tables
* ===================================================================

capture program drop run_gbif_cohort_exposure
program define run_gbif_cohort_exposure
    syntax , TITLE(string) ANY(string) LOG(string) COMPLETE(string) PREFIX(string)

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
    quietly count
    local n_complete = r(N)
    quietly summarize year
    local min_year = r(min)
    local max_year = r(max)
    di as text "Completeness restriction: `complete' == 1"
    di as text "Regression sample after completeness restriction: N=`n_complete', years `min_year'-`max_year'"
    run_gbif_exposure, title(`"`title'"') any(`any') log(`log') prefix(`prefix')
    restore
end

di as text "================================================================="
di as text "Horizon sensitivity: GBIF cohort-timed dataset-publication exposure"
di as text "Primary horizon is 0-5 years; 0-3 and 0-10 years are timing diagnostics."
di as text "Total and Plantae should be identical for this GBIF Plantae-only source."
di as text "================================================================="

run_gbif_cohort_exposure, ///
    any(any_gbif_pub_total_0_3yr) log(log1p_gbif_pub_total_0_3yr) ///
    complete(gbif_pub_complete_0_3yr) ///
    prefix(gbif_total_3yr) ///
    title("GBIF total cohort-timed dataset publication exposure within 3 years")

run_gbif_cohort_exposure, ///
    any(any_gbif_pub_plantae_0_3yr) log(log1p_gbif_pub_plantae_0_3yr) ///
    complete(gbif_pub_complete_0_3yr) ///
    prefix(gbif_plantae_3yr) ///
    title("GBIF Plantae cohort-timed dataset publication exposure within 3 years")

run_gbif_cohort_exposure, ///
    any(any_gbif_pub_total_0_5yr) log(log1p_gbif_pub_total_0_5yr) ///
    complete(gbif_pub_complete_0_5yr) ///
    prefix(gbif_total_5yr) ///
    title("PRIMARY: GBIF total cohort-timed dataset publication exposure within 5 years")

run_gbif_cohort_exposure, ///
    any(any_gbif_pub_plantae_0_5yr) log(log1p_gbif_pub_plantae_0_5yr) ///
    complete(gbif_pub_complete_0_5yr) ///
    prefix(gbif_plantae_5yr) ///
    title("PRIMARY: GBIF Plantae cohort-timed dataset publication exposure within 5 years")

run_gbif_cohort_exposure, ///
    any(any_gbif_pub_total_0_10yr) log(log1p_gbif_pub_total_0_10yr) ///
    complete(gbif_pub_complete_0_10yr) ///
    prefix(gbif_total_10yr) ///
    title("GBIF total cohort-timed dataset publication exposure within 10 years")

run_gbif_cohort_exposure, ///
    any(any_gbif_pub_plantae_0_10yr) log(log1p_gbif_pub_plantae_0_10yr) ///
    complete(gbif_pub_complete_0_10yr) ///
    prefix(gbif_plantae_10yr) ///
    title("GBIF Plantae cohort-timed dataset publication exposure within 10 years")

* ===================================================================
* Legacy publication-year exposure diagnostics
* ===================================================================

local run_legacy_pubyear 0

if `run_legacy_pubyear' == 1 {

run_gbif_exposure, ///
    any(any_pubs_gbif) log(log1p_pubs_gbif) ///
    prefix(legacy_gbif) ///
    title("Legacy GBIF-linked publication-year dataset exposure")

run_gbif_exposure, ///
    any(any_pubs_gbif_plantae) log(log1p_pubs_gbif_plantae) ///
    prefix(legacy_gbif_plantae) ///
    title("Legacy GBIF x Plantae publication-year dataset exposure")

run_gbif_exposure, ///
    any(any_pubs_total) log(log1p_pubs_total) ///
    prefix(legacy_total) ///
    title("Legacy total publication-year exposure (GBIF-dominated diagnostic)")

run_gbif_exposure, ///
    any(any_pubs_plantae) log(log1p_pubs_plantae) ///
    prefix(legacy_plantae) ///
    title("Legacy Plantae publication-year exposure (GBIF-dominated diagnostic)")

}

* Publish all local exhibits to the merged deck on Dropbox.
dd_mirror_outputs

log close
