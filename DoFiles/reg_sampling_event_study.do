* reg_sampling_event_study.do
* TWFE diagnostic lead/lag graphs for conflict -> BOLD sampling activity.
*
* Mirrors reg_publications_gbif_exposure_event_study.do, but uses BOLD
* sampling volume as the outcome rather than downstream publication exposure.

global proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture confirm variable log1p_total
if _rc != 0 {
    use "$proj/Data/analysis/BOLD_regressor_panel.dta", clear
}

capture program drop sampling_conflict_leadlag
program define sampling_conflict_leadlag
    syntax , GRAPH(string) NAME(name) PRE(integer) POST(integer) [SIMPLE]

    preserve

    keep if year >= 2005 & year <= 2024

    capture confirm variable cell_id_num
    if _rc != 0 encode cell_id, gen(cell_id_num)
    capture confirm variable country_num
    if _rc != 0 encode iso_a3, gen(country_num)
    xtset cell_id_num year

    capture confirm variable burned_share
    if _rc != 0 gen burned_share = burned_area_km2 / cell_area_km2
    capture confirm variable cyclone
    if _rc != 0 {
        gen cyclone = ibtracs_any_64kt
        replace cyclone = 0 if missing(cyclone)
    }
    capture confirm variable earthquake
    if _rc != 0 {
        gen earthquake = (comcat_events_m6 > 0) if !missing(comcat_events_m6)
        replace earthquake = 0 if missing(earthquake)
    }
    capture confirm variable log_gdp_pc
    if _rc != 0 gen log_gdp_pc = log(gdp_pcap_current_usd)
    capture confirm variable log_gdp_pc_sq
    if _rc != 0 gen log_gdp_pc_sq = log_gdp_pc^2

    forvalues k = 1/20 {
        capture drop uc_any_f`k'
        capture drop uc_any_l`k'
    }
    capture drop uc_any_0

    local event_vars
    forvalues k = `pre'(-1)2 {
        gen uc_any_f`k' = F`k'.ucdp_any_all
        local event_vars `event_vars' uc_any_f`k'
    }

    gen uc_any_0 = ucdp_any_all
    local event_vars `event_vars' uc_any_0

    forvalues k = 1/`post' {
        gen uc_any_l`k' = L`k'.ucdp_any_all
        local event_vars `event_vars' uc_any_l`k'
    }

    keep if year >= 2005 & year <= 2023

    di as text "================================================================="
    di as text "TWFE lead/lag graph: annual ucdp_any_all -> log1p_total"
    di as text "Reference period: ucdp_any_all at t=-1 is omitted"
    di as text "Window: -`pre' to +`post'; exact leads/lags, no endpoint binning"
    if "`simple'" == "" {
        di as text "Fixed effects: cell, country-year, biome-year"
        local fe_absorb "cell_id_num country_num#year i.resolve_biome_num#i.year"
        local fe_subtitle "Cell FE, country-year FE, biome-year FE; clustered by cell"
        local graph_title "BOLD sampling: annual conflict lead/lag (-`pre'/+`post')"
    }
    else {
        di as text "Fixed effects: cell and year only"
        local fe_absorb "cell_id_num year"
        local fe_subtitle "Cell FE and year FE only; no controls; clustered by cell"
        local graph_title "BOLD sampling: annual conflict lead/lag (-`pre'/+`post'), cell/year FE"
    }
    di as text "================================================================="

    if "`simple'" == "" {
        reghdfe log1p_total `event_vars' ///
            forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year, ///
            absorb(`fe_absorb') ///
            vce(cluster cell_id_num)
    }
    else {
        reghdfe log1p_total `event_vars', ///
            absorb(`fe_absorb') ///
            vce(cluster cell_id_num)
    }
    tempvar es_sample
    gen byte `es_sample' = e(sample)
    local n_obs : display %12.0fc e(N)
    local n_obs = strtrim("`n_obs'")
    capture estimates drop __sampling_es_tmp
    estimates store __sampling_es_tmp

    if "`simple'" == "" {
        reghdfe log1p_total ucdp_any_all ///
            forest_loss_share burned_share cyclone earthquake pdsi_anomaly tmax_anomaly log1p_ntl ///
            protected_share c.log_gdp_pc#c.protected_share ///
            c.log_gdp_pc_sq#c.protected_share ///
            c.road_density_km_per_km2#i.year ///
            if `es_sample', ///
            absorb(`fe_absorb') ///
            vce(cluster cell_id_num)
    }
    else {
        reghdfe log1p_total ucdp_any_all if `es_sample', ///
            absorb(`fe_absorb') ///
            vce(cluster cell_id_num)
    }
    local twfe_b = _b[ucdp_any_all]
    local twfe_se = _se[ucdp_any_all]
    local twfe_b_fmt : display %6.3f `twfe_b'
    local twfe_se_fmt : display %6.3f `twfe_se'
    local twfe_b_fmt = strtrim("`twfe_b_fmt'")
    local twfe_se_fmt = strtrim("`twfe_se_fmt'")
    estimates restore __sampling_es_tmp
    estimates drop __sampling_es_tmp

    tempfile escoef
    tempname posth
    postfile `posth' str12 term int rel double b se lo hi using `escoef', replace

    forvalues k = `pre'(-1)2 {
        capture quietly lincom uc_any_f`k'
        if _rc == 0 {
            post `posth' ("uc_any_f`k'") (-`k') (r(estimate)) (r(se)) ///
                (r(estimate) - 1.96*r(se)) (r(estimate) + 1.96*r(se))
        }
        else {
            post `posth' ("uc_any_f`k'") (-`k') (.) (.) (.) (.)
        }
    }

    capture quietly lincom uc_any_0
    if _rc == 0 {
        post `posth' ("uc_any_0") (0) (r(estimate)) (r(se)) ///
            (r(estimate) - 1.96*r(se)) (r(estimate) + 1.96*r(se))
    }
    else {
        post `posth' ("uc_any_0") (0) (.) (.) (.) (.)
    }

    forvalues k = 1/`post' {
        capture quietly lincom uc_any_l`k'
        if _rc == 0 {
            post `posth' ("uc_any_l`k'") (`k') (r(estimate)) (r(se)) ///
                (r(estimate) - 1.96*r(se)) (r(estimate) + 1.96*r(se))
        }
        else {
            post `posth' ("uc_any_l`k'") (`k') (.) (.) (.) (.)
        }
    }
    postclose `posth'

    use `escoef', clear
    set obs `=_N + 1'
    replace term = "base" in L
    replace rel = -1 in L
    replace b = 0 in L
    replace se = 0 in L
    replace lo = 0 in L
    replace hi = 0 in L
    sort rel

    twoway ///
        (rcap lo hi rel, lcolor(navy%45)) ///
        (connected b rel, mcolor(navy) lcolor(navy) msymbol(O)), ///
        yline(0, lpattern(dash) lcolor(gs8)) ///
        yline(`twfe_b', lpattern(shortdash) lcolor(dkgreen)) ///
        xline(-1, lpattern(shortdash) lcolor(gs10)) ///
        xlabel(-`pre'(1)`post') ///
        xtitle("Years relative to annual conflict indicator") ///
        ytitle("Effect on log(1 + BOLD records)") ///
        title("`graph_title'") ///
        subtitle("`fe_subtitle'" "Observations: `n_obs'; static TWFE: `twfe_b_fmt' (`twfe_se_fmt')") ///
        legend(off) ///
        name(`name', replace)
    graph export "`graph'", replace width(2000)
    di as text "Wrote annual-conflict lead/lag graph: `graph'"

    restore
end

capture mkdir "$proj/Exhibits"
capture mkdir "$proj/Exhibits/figures"

* Short-window diagnostic: -3/+3
sampling_conflict_leadlag, name(g_sampling_rich_m3p3) pre(3) post(3) ///
    graph("$proj/Exhibits/figures/sampling_ucdp_any_leadlag_m3_p3.png")
sampling_conflict_leadlag, name(g_sampling_simple_m3p3) pre(3) post(3) ///
    graph("$proj/Exhibits/figures/sampling_ucdp_any_leadlag_m3_p3_cell_year_fe.png") simple

* Long-post diagnostic: -5/+10
sampling_conflict_leadlag, name(g_sampling_rich_m5p10) pre(5) post(10) ///
    graph("$proj/Exhibits/figures/sampling_ucdp_any_leadlag_m5_p10.png")
sampling_conflict_leadlag, name(g_sampling_simple_m5p10) pre(5) post(10) ///
    graph("$proj/Exhibits/figures/sampling_ucdp_any_leadlag_m5_p10_cell_year_fe.png") simple
