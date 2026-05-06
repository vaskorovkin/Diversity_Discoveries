* desc_foreign_collecting.do
* Descriptive analysis of foreign vs domestic collecting in BOLD

clear all
set more off

local proj "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

capture log close
log using "`proj'/Logs/desc_foreign_collecting.log", replace text

use "`proj'/Data/analysis/BOLD_regressor_panel.dta", clear

keep if year >= 2005 & year <= 2023

* ===================================================================
* 1. Coverage and basic stats
* ===================================================================

di _n "=== FOREIGN COLLECTING DATA COVERAGE ==="
count
count if !missing(foreign_share)
count if records_classified > 0
count if records_with_collectors > 0

di _n "=== SUMMARY: foreign_share (cell-years with classified collectors) ==="
sum foreign_share, detail

di _n "=== SUMMARY: record counts ==="
sum records_total records_with_collectors records_classified records_unclassified ///
    if records_classified > 0, detail

di _n "=== SUMMARY: collector counts ==="
sum n_collectors_foreign n_collectors_domestic ///
    if records_classified > 0, detail

* ===================================================================
* 2. Domestic / regional / distant breakdown
* ===================================================================

di _n "=== RECORD-LEVEL BREAKDOWN (categorical) ==="
sum records_domestic records_foreign_regional records_foreign_distant ///
    records_collab if records_classified > 0, detail

di _n "=== SCORE-LEVEL BREAKDOWN (fractional) ==="
sum domestic_score_sum regional_score_sum distant_score_sum ///
    if fc_scored > 0, detail

di _n "=== SHARE DISTRIBUTIONS ==="
sum foreign_share regional_share distant_share domestic_share collab_share ///
    if !missing(foreign_share), detail

* ===================================================================
* 3. Foreign share by continent
* ===================================================================

di _n "=== FOREIGN SHARE BY CONTINENT ==="
tabstat foreign_share regional_share distant_share if !missing(foreign_share), ///
    by(continent) stat(mean median count) format(%9.3f) nototal

* ===================================================================
* 4. Foreign share by country (top 20 by classified records)
* ===================================================================

di _n "=== TOP 20 COUNTRIES BY CLASSIFIED RECORDS ==="
preserve
    keep if !missing(foreign_share)
    collapse (mean) foreign_share regional_share distant_share collab_share ///
        (sum) records_classified records_domestic records_foreign_regional ///
        records_foreign_distant records_collab ///
        n_collectors_foreign n_collectors_domestic ///
        (count) n_cellyears = foreign_share, by(iso_a3 country)
    gsort -records_classified
    list iso_a3 country records_classified foreign_share regional_share ///
        distant_share collab_share n_cellyears in 1/20, noobs clean
restore

* ===================================================================
* 5. Time trends
* ===================================================================

di _n "=== FOREIGN SHARE BY YEAR ==="
tabstat foreign_share regional_share distant_share if !missing(foreign_share), ///
    by(year) stat(mean count) format(%9.3f) nototal

di _n "=== MEAN SHARES BY YEAR (weighted by classified records) ==="
preserve
    keep if !missing(foreign_share) & records_classified > 0
    collapse (mean) foreign_share regional_share distant_share collab_share ///
        [aweight = records_classified], by(year)
    list, noobs clean
restore

* ===================================================================
* 6. Foreign share by income group
* ===================================================================

di _n "=== FOREIGN SHARE BY GDP QUARTILE ==="
gen log_gdp_pc = log(gdp_pcap_current_usd)
xtile gdp_q4 = log_gdp_pc if !missing(foreign_share), nq(4)
label define gdp_q4_lbl 1 "Q1 (poorest)" 2 "Q2" 3 "Q3" 4 "Q4 (richest)"
label values gdp_q4 gdp_q4_lbl
tabstat foreign_share regional_share distant_share if !missing(foreign_share), ///
    by(gdp_q4) stat(mean median count) format(%9.3f) nototal

* ===================================================================
* 7. Foreign share by biodiversity richness
* ===================================================================

di _n "=== FOREIGN SHARE BY SPECIES RICHNESS QUARTILE ==="
xtile rich_q4 = richness_total if !missing(foreign_share), nq(4)
label define rich_q4_lbl 1 "Q1 (least rich)" 2 "Q2" 3 "Q3" 4 "Q4 (most rich)"
label values rich_q4 rich_q4_lbl
tabstat foreign_share regional_share distant_share if !missing(foreign_share), ///
    by(rich_q4) stat(mean median count) format(%9.3f) nototal

* ===================================================================
* 8. Cross-tab: GDP x biodiversity
* ===================================================================

di _n "=== MEAN FOREIGN SHARE: GDP QUARTILE x RICHNESS QUARTILE ==="
table gdp_q4 rich_q4 if !missing(foreign_share), c(mean foreign_share) format(%9.3f)

di _n "=== MEAN DISTANT SHARE: GDP QUARTILE x RICHNESS QUARTILE ==="
table gdp_q4 rich_q4 if !missing(distant_share), c(mean distant_share) format(%9.3f)

* ===================================================================
* 9. Correlations
* ===================================================================

di _n "=== CORRELATIONS WITH FOREIGN SHARE ==="
pwcorr foreign_share regional_share distant_share collab_share ///
    log_gdp_pc richness_total protected_share ///
    road_density_km_per_km2 log1p_ntl ///
    if !missing(foreign_share), star(0.05) obs

* ===================================================================
* 10. Hotspot/biome patterns
* ===================================================================

di _n "=== FOREIGN SHARE BY BIODIVERSITY HOTSPOT STATUS ==="
tabstat foreign_share distant_share if !missing(foreign_share), ///
    by(cepf_hotspot_any) stat(mean count) format(%9.3f) nototal

di _n "=== FOREIGN SHARE BY BIOME (top 10 by cell-years) ==="
preserve
    keep if !missing(foreign_share)
    collapse (mean) foreign_share regional_share distant_share ///
        (count) n = foreign_share, by(resolve_biome_name)
    gsort -n
    list resolve_biome_name foreign_share regional_share distant_share n ///
        in 1/10, noobs clean
restore

* ===================================================================
* 11. Protected area interaction
* ===================================================================

di _n "=== FOREIGN SHARE BY PROTECTED AREA COVERAGE ==="
gen pa_cat = 0 if !missing(protected_share)
replace pa_cat = 1 if protected_share > 0 & protected_share <= 0.25
replace pa_cat = 2 if protected_share > 0.25 & protected_share <= 0.75
replace pa_cat = 3 if protected_share > 0.75 & !missing(protected_share)
label define pa_cat_lbl 0 "No PA" 1 "1-25% PA" 2 "25-75% PA" 3 "75%+ PA"
label values pa_cat pa_cat_lbl
tabstat foreign_share distant_share collab_share if !missing(foreign_share), ///
    by(pa_cat) stat(mean count) format(%9.3f) nototal

* ===================================================================
* 12. Collaboration patterns
* ===================================================================

di _n "=== COLLABORATION RATE BY CONTINENT ==="
tabstat collab_share if !missing(collab_share), by(continent) ///
    stat(mean median count) format(%9.3f) nototal

di _n "=== COLLABORATION RATE BY GDP QUARTILE ==="
tabstat collab_share if !missing(collab_share), by(gdp_q4) ///
    stat(mean median count) format(%9.3f) nototal

* ===================================================================
* 13. Histograms
* ===================================================================

histogram foreign_share if !missing(foreign_share), ///
    width(0.05) fraction ///
    title("Distribution of Foreign Collecting Share") ///
    xtitle("Foreign Share") ytitle("Fraction of cell-years") ///
    note("Cell-years with classified collectors, 2005-2023")
graph export "`proj'/Exhibits/figures/foreign_collecting_share_hist.png", replace width(1200)

histogram distant_share if !missing(distant_share), ///
    width(0.05) fraction ///
    title("Distribution of Distant (Cross-Continent) Collecting Share") ///
    xtitle("Distant Share") ytitle("Fraction of cell-years") ///
    note("Cell-years with classified collectors, 2005-2023")
graph export "`proj'/Exhibits/figures/foreign_collecting_distant_share_hist.png", replace width(1200)

* ===================================================================
* 14. Binscatter: foreign share vs GDP and richness
* ===================================================================

capture which binscatter
if _rc == 0 {
    binscatter foreign_share log_gdp_pc if !missing(foreign_share), ///
        nquantiles(20) ///
        title("Foreign Collecting Share vs GDP per capita") ///
        xtitle("Log GDP per capita") ytitle("Foreign Share")
    graph export "`proj'/Exhibits/figures/foreign_collecting_vs_gdp_binscatter.png", replace width(1200)

    binscatter distant_share log_gdp_pc if !missing(distant_share), ///
        nquantiles(20) ///
        title("Distant Collecting Share vs GDP per capita") ///
        xtitle("Log GDP per capita") ytitle("Distant Share")
    graph export "`proj'/Exhibits/figures/distant_collecting_vs_gdp_binscatter.png", replace width(1200)

    binscatter foreign_share richness_total if !missing(foreign_share), ///
        nquantiles(20) ///
        title("Foreign Collecting Share vs Species Richness") ///
        xtitle("Species Richness (mammals+amphibians+reptiles+birds)") ///
        ytitle("Foreign Share")
    graph export "`proj'/Exhibits/figures/foreign_collecting_vs_richness_binscatter.png", replace width(1200)

    binscatter collab_share log_gdp_pc if !missing(collab_share), ///
        nquantiles(20) ///
        title("Collaboration Share vs GDP per capita") ///
        xtitle("Log GDP per capita") ytitle("Collaboration Share")
    graph export "`proj'/Exhibits/figures/collab_share_vs_gdp_binscatter.png", replace width(1200)
}
else {
    di "binscatter not installed — skipping binscatter plots"
    di "Install with: ssc install binscatter"
}

di _n "=== DONE ==="

log close
