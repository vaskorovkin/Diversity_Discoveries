version 16
clear all
set more off

* Project root. Edit this line only if the folder moves.
global project "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

global processed_bold "$project/Data/processed/bold"

local infile "$processed_bold/bold_global_fungi_minimal.tsv"
local outfile "$processed_bold/bold_global_fungi_minimal.dta"
local logfile "$processed_bold/bold_global_fungi_summary.log"

capture log close
log using "`logfile'", replace text

import delimited using "`infile'", clear varnames(1) stringcols(_all) ///
    bindquote(strict) encoding(UTF-8)

* Convert selected numeric fields.
destring latitude longitude elev nuc_basecount marker_count, replace force

* Convert ISO date strings to Stata dates.
gen collection_date = daily(collection_date_start, "YMD")
format collection_date %td
gen collection_year = year(collection_date)
gen collection_month = month(collection_date)

gen sequence_date = daily(sequence_upload_date, "YMD")
format sequence_date %td
gen sequence_year = year(sequence_date)

* Basic indicators.
gen has_coord = !missing(latitude, longitude)
gen has_collection_date = !missing(collection_date)
gen has_sequence_date = !missing(sequence_date)
gen has_species = species != ""
gen has_genus = genus != ""
gen has_insdc = insdc_acs != ""

* Crude spatial sanity checks.
gen coord_plausible = inrange(latitude, -90, 90) & inrange(longitude, -180, 180)
replace coord_plausible = 0 if !has_coord

order processid sampleid record_id specimenid kingdom phylum class order family ///
    genus species identification identification_rank marker_code collection_date ///
    collection_year sequence_date sequence_year latitude longitude has_coord ///
    coord_plausible country_ocean country_iso province_state region site

compress
save "`outfile'", replace

display "BOLD global Fungi minimal import"
display "Rows are BOLD sequence/marker records, not necessarily unique specimens."

describe

display "Core counts"
count
count if has_coord
count if coord_plausible
count if has_collection_date
count if has_sequence_date
count if has_species
count if has_genus
count if has_insdc

display "Numeric summaries"
summarize latitude longitude elev nuc_basecount marker_count collection_year sequence_year

display "Top marker codes"
tab marker_code, sort missing

display "Top countries"
tab country_ocean, sort missing

display "Taxonomic rank of identification"
tab identification_rank, sort missing

display "Records by collection year"
tab collection_year if has_collection_date

display "Records by sequence upload year"
tab sequence_year if has_sequence_date

display "Potential duplicate structure"
duplicates report processid
duplicates report specimenid
duplicates report specimenid marker_code

log close
