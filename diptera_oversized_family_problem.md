# Oversized Diptera Families In BOLD

Current status: unresolved. Important note: Diptera is not fully complete.
The remaining incomplete piece is Costa Rica (`C-R`) Cecidomyiidae. We should
not treat the capped Costa Rica Cecidomyiidae diagnostic extract as complete.

## Problem

BOLD has a 1,000,000-record download cap per query. Four Diptera families exceed that cap in the BOLD v4 taxonomy-browser family counts:

- Cecidomyiidae: about 2.45M
- Chironomidae: about 2.01M
- Phoridae: about 1.58M
- Sciaridae: about 1.41M

The family-level Diptera downloader therefore starts at Ceratopogonidae and intentionally skips these four over-cap families.

The more current BOLD v5 summary counts are lower than those v4 taxonomy-browser hints but still above the cap for all four at the family level:

- Cecidomyiidae: 2,092,907
- Chironomidae: 1,647,619
- Phoridae: 1,385,577
- Sciaridae: 1,172,067

## Genus Split Attempt

We tried BOLD v4 child-genus lists for these families. The output is in:

`Output/audits/bold_v4_diptera_large_family_genus_splits.csv`

and appended to:

`bold_taxon_size_notes.txt`

This did not solve the problem. The v4 genus lists are not a full decomposition of the over-cap families. For example, Cecidomyiidae has about 2.45M family-level records, but the v4 child-genus list sums to only 33 records.

We also downloaded a capped, non-random Cecidomyiidae extract:

`Data/raw/bold/diptera_by_family/bold_global_diptera_family_cecidomyiidae_capped_records.tsv`

The genus count from that capped file showed that most rows have blank genus:

- blank genus: 987,126 of 1,000,000 rows

So genus is not a practical split variable for Cecidomyiidae.

## Geography Split Attempt

We summarized Cecidomyiidae counts for New World countries/territories. Output:

`Output/audits/bold_cecidomyiidae_new_world_country_summary.csv`

Key results:

- Canada: 192,940
- United States: 97,827
- Mexico: 16,597
- Costa Rica: 1,122,446
- Peru: 80,569
- New World OK-row total: 1,606,045
- New World records with coordinates: 1,604,584

This suggests geography is promising, but Costa Rica alone still exceeds the 1M cap and must be split further, probably by province/state or another BOLD field. Anguilla returned HTTP 400 for the current country string.

## Country Counts

We extracted the top five country/ocean values for the four families using BOLD summary metadata only. Output:

`Output/audits/bold_diptera_oversized_family_top_countries.csv`

Key result: Costa Rica is the dominant country for all four families.

- Cecidomyiidae: Costa Rica 1,122,446; Canada 192,940; United States 97,827; South Africa 83,815; Peru 80,569
- Chironomidae: Costa Rica 578,626; Canada 358,463; United States 145,099; United Kingdom 63,417; South Africa 59,414
- Phoridae: Costa Rica 835,884; Canada 118,654; United States 96,621; Peru 47,852; South Africa 24,988
- Sciaridae: Costa Rica 537,663; Canada 140,765; United States 79,272; Peru 47,949; South Africa 32,656

## Current Interpretation

For these four Diptera families, we do not yet have a complete clean download plan. Current status:

1. Use family-level downloads for Diptera from Ceratopogonidae downward. This part is done locally, aside from stale failed-log entries.
2. Chironomidae, Phoridae, and Sciaridae have country-by-country download scripts; every country-level query for these families is below the cap in the current BOLD summary.
3. Cecidomyiidae has a country-by-country script for all positive country/ocean buckets except Costa Rica.
4. Costa Rica Cecidomyiidae still needs a second split, probably by province/state or another BOLD field, because Costa Rica alone exceeds 1M. A capped diagnostic script exists, but it should not be treated as complete coverage.
5. Audit summed split counts against BOLD v5 family summary counts before treating any over-cap family as complete.

Until then, the capped Cecidomyiidae file is diagnostic only and should not be treated as random or complete.
