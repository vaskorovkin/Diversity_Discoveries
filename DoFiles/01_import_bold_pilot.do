version 16
clear all
set more off

* Project root. Edit this line only if the folder moves.
global project "/Users/vasilykorovkin/Documents/Diversity_Discoveries"

global raw_bold "$project/Data/raw/bold"
global processed_bold "$project/Data/processed/bold"

* This file was created from the BOLD Portal API pilot:
* tax:family:Trochilidae; geo:country/ocean:Costa Rica
local infile "$processed_bold/bold_trochilidae_costa_rica_minimal.tsv"
local outfile "$processed_bold/bold_trochilidae_costa_rica_minimal.dta"

import delimited using "`infile'", clear varnames(1) stringcols(_all) ///
    bindquote(strict) encoding(UTF-8)

* Convert numeric fields imported as strings.
destring latitude longitude, replace force

* Convert ISO collection date string to Stata daily date.
gen collection_date = daily(collection_date_start, "YMD")
format collection_date %td
gen year = year(collection_date)
gen month = month(collection_date)

* Basic geography/date checks.
gen has_coord = !missing(latitude, longitude)
gen has_date = !missing(collection_date)

order processid species collection_date_start collection_date year month ///
    latitude longitude has_coord country province_state marker_code

compress
save "`outfile'", replace

describe
summarize latitude longitude year
tab year
tab species
