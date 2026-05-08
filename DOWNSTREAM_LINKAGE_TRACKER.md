# Downstream Linkage Tracker (Options A & B)

Coordinator file for two parallel agent workstreams that link the established
sampling-shock results (`reg_spec1.do`, `reg_foreign_collecting.do`) to
downstream discovery outcomes. See `Notes/downstream_discovery_linkage_note.tex`
for the full framing.

## Context: Three established facts

(a) Conflict reduces biodiversity sampling, robust to saturated FE; cumulative
L0–L2 effect is 2–3× contemporaneous.
(b) The effect is amplified in biodiverse cells (negative `Conflict×Richness`).
(c) Conflict selectively deters foreign collectors; domestic collecting is
unaffected.

BIN-discovery regressions show conflict reduces new BIN discovery, but the
effect is mediated almost entirely by sampling volume. We need a
discovery-side outcome that goes beyond raw sampling.

## Two parallel workstreams

| | **Option A: Publication linkage** | **Option B: Natural products** |
|---|---|---|
| BOLD chain | `insdc_acs` → NCBI Entrez `elink` → PubMed | species name → LOTUS/COCONUT/KNApSAcK |
| GBIF chain | `datasetKey` / occurrence → GBIF Literature API → publications | species name → LOTUS/COCONUT/KNApSAcK |
| BOLD-strong taxa | Chordata, Fungi, Mollusca, some Insecta | Fungi, some Insecta (alkaloids/venoms) |
| GBIF-strong taxa | **Plantae** | **Plantae** |
| Owner agent | **Window 1 (this window)** | **Window 2 (separate window)** |
| Outputs to | `Data/processed/discovery/publications/` | `Data/processed/discovery/natural_products/` |

**Two upstream pipelines, two downstream measurement systems.** The
project already has both BOLD (`bold_minimal_records.csv`,
`bold_grid100_cell_year_panel_collection_2005_2025.csv`) and GBIF Plantae
(`gbif_plantae_preserved_material_cell_year_panel_2005_2025.csv`) feeding
the regression panel `BOLD_regressor_panel.dta`. Both options must use
both upstream pipelines:

- **Option A** has *two* linkage subtasks — BOLD specimens to PubMed via
  GenBank accessions, and GBIF specimens to publications via the GBIF
  Literature API. The final cell × year publication-count panel is the
  **union** of both chains. Decomposing by source (BOLD-linked vs
  GBIF-linked publications) is a useful robustness check.
- **Option B** uses *one* shared species universe drawn from both BOLD and
  GBIF. The species → compound join is identical regardless of upstream
  source. For plants, GBIF should dominate the species universe (~3× the
  BOLD plant coverage). For animals and fungi, BOLD dominates.

**Both options run on every taxon where they produce signal.** Per-taxon
coverage is heterogeneous and should be reported, not used as a sample
restriction:

| Taxon | Option A coverage (`insdc_acs`, measured) | Option B coverage (NP-DBs) |
|---|---|---|
| Chordata | 73% | sparse |
| Mollusca | 83% | sparse (some marine invertebrates) |
| Insecta | 18% | sparse (some venoms, alkaloids) |
| Fungi | 86% | strong (mycotoxins, antibiotics) |
| Plantae | 73% | strong (LOTUS/COCONUT are plant-heavy) |
| Bacteria | 44% | (not in scope) |
| Other Animalia phyla (Annelida, Mollusca, Cnidaria, etc.) | 70–99% | sparse |
| Non-Insecta Arthropoda classes (Arachnida, Malacostraca, …) | 52–95% | (Arachnida venoms only) |

Measured from `Output/audits/insdc_acs_coverage_by_taxon.csv` over 20.16M
BOLD records in `bold_minimal_records.csv`. The earlier a-priori figures
(Chordata 87% / Mollusca 73% / Plantae 28% / Fungi 95% / Insecta 17–46%)
have been replaced — the largest discrepancy was Plantae, where actual
BOLD→GenBank linkage is ~2.6× the prior estimate, making BOLD a viable
second linkage chain for plants alongside the GBIF Literature API.

**Fungi has dense coverage in both pipelines** and is therefore the one
taxon where a within-taxon consistency check is possible — does the same
upstream conflict-shock produce a measurable decline in *both* publication
output (Option A) and natural-product-relevant species sampled (Option B)?
This is a consistency check, not the main scope. Each option's headline
results should be reported per kingdom/phylum across all taxa where the
pipeline returns signal.

## Status

### Option A — Publication linkage

**Subtask A1: BOLD → GenBank → PubMed (animals + fungi mainly)**
- [x] Re-extract `insdc_acs` from raw BOLD TSVs (modify
      `Scripts/pipeline_utils.py`, add field to `MINIMAL_FIELDS`)
- [x] Re-run `00_build_bold_minimal.py` to refresh
      `Data/processed/bold/bold_minimal_records.csv`
      (20,160,076 rows; 5,428,354 with `insdc_acs` = 26.93% pooled)
- [x] Audit per-taxon `insdc_acs` fill rate →
      `Output/audits/insdc_acs_coverage.csv` (14 source_groups) and
      `Output/audits/insdc_acs_coverage_by_taxon.csv` (4 kingdoms,
      25 Animalia phyla, 10 Arthropoda classes). Plantae 73% / Chordata
      73% / Mollusca 83% / Fungi 86% / Insecta 18%; Insecta is the only
      class dragging Arthropoda's kingdom-level fill down. Costa Rica
      Cecidomyiidae capped file is a near-empty diagnostic (0.0014%) —
      exclude from elink.
- [x] Build NCBI publication-linkage pipeline in batched/resumable mode
      (`Scripts/20_link_bold_to_pubmed.py`). The original Entrez
      `epost`/`elink` path was tested but proved unreliable for
      per-accession attribution because NCBI often returns collapsed
      batch-level linksets. The production path therefore uses GenBank
      `efetch` flat files and parses per-record `PUBMED` references, with
      optional `--skip-elink-screen`, atomic chunk writes, repair mode, and
      failure logging.
- [x] Output: `Data/processed/discovery/publications/bold_accession_to_pubmed.csv`
      (10,461 chunks; 5,230,497 accessions; 5,239,623 accession-PMID/blank
      rows after repair; 1,983,992 accessions with at least one PMID).
      Persistent unresolved NCBI `400` failures are documented in
      `bold_pubmed_efetch_failures_remaining.csv` (5,435 accessions,
      0.104% of linked-accession universe).

**Subtask A2: GBIF Plantae → GBIF Literature API (plants)**
- [x] Audit GBIF preserved-material occurrences for `datasetKey` /
      `gbifID` coverage in the existing
      `gbif_plantae_preserved_material_minimal.csv`. The minimal file uses
      normalized `dataset_key` / `gbif_id` columns. First 1,000 rows are 100%
      filled for both; full file has 15,097,585 rows, 15,097,564 non-empty
      `dataset_key` values (99.999861%), and 100% non-empty `gbif_id`.
- [x] Write pipeline: occurrence dataset_key → GBIF Literature API
      (`api.gbif.org/v1/literature/search?gbifDatasetKey=...`) → citing publications
      (`Scripts/21_link_gbif_datasets_to_publications.py`). This is
      dataset-level attribution: every occurrence in a linked dataset
      inherits dataset-citing publication links. Interpret as dataset
      publication exposure, not direct specimen citation.
- [ ] Output: `Data/processed/discovery/publications/gbif_dataset_to_pubs.csv`

**Subtask A3: Unified panel and regressions**
- [ ] Build cell × year publication-count panel →
      `Data/processed/discovery/publications/pubs_cell_year_panel.csv`
      (union of A1 + A2; per-kingdom/per-phylum breakdowns: Chordata,
      Mollusca, Insecta, Fungi, Plantae, others; also `source = bold|gbif`)
- [ ] Stata regressions mirroring `reg_spec1.do` Tables 3 + 5 with new LHS,
      run pooled and per-kingdom (and per-phylum for Arthropoda); also
      decompose by source as a robustness check
- [ ] Fungi subset re-run for consistency check with Option B

### Option B — Natural products
- [x] Download LOTUS dump (Wikidata-linked) →
      `Data/raw/natural_products/lotus/` (Zenodo v11, 260413_frozen.csv.gz
      + 260413_frozen_metadata.csv.gz; Scripts/22_download_lotus.py)
- [x] Download COCONUT dump (largest aggregated NP collection) →
      `Data/raw/natural_products/coconut/` (COCONUT 2.0,
      coconut_csv-05-2026.zip 208 MB; Scripts/22b_download_coconut.py)
- [ ] Add KNApSAcK as supplementary (especially for plant secondary
      metabolites and animal-derived compounds: venoms, marine invertebrate
      metabolites, insect alkaloids — sparse but real)
- [x] Build species → compound mapping (LOTUS + COCONUT as co-equal
      primary sources, dedup compounds via InChIKey across DBs) →
      `Data/processed/discovery/natural_products/species_compound_pairs.csv`
      (long format, 1,324,226 rows) and
      `Data/processed/discovery/natural_products/species_to_compounds.csv`
      (per-species summary, 58,546 species; 26,430 Plantae, 3,596 Fungi,
      2,505 Animalia; 26,015 unknown kingdom from COCONUT-only entries
      in the initial pass — finalized to ~few hundred after Script 25
      backfill). Cross-source overlap: 33,510 species in both DBs,
      189,768 compounds in both. Median 7 compounds per species;
      max 6,168. Script 23 writes initial pairs/summary;
      Script 25 rewrites both with backfilled kingdoms.
      Scripts/23_build_species_to_compounds.py
- [x] Build the **shared species universe** (BOLD ∪ GBIF, the samplable
      set; species in NP-DBs but not BOLD/GBIF excluded since they can't
      enter cell-year regressions):
      - BOLD records with BIN consensus recovery (1.55M unnamed records
        in named BINs assigned plurality species; no concordance threshold)
      - GBIF Plantae preserved-material (12.1M with binomial species)
      - Outputs:
        `Data/processed/discovery/shared/shared_species_universe.csv`
        (742,864 species; 435K Animalia, 265K Plantae, 37K Fungi, 6K Bacteria;
        32,988 NP-DB matches at 4.4% by exact name) and
        `Data/processed/discovery/shared/bin_consensus_lookup.csv`
        (414K BINs with `consensus_species, kingdom, genus, concordance,
        is_strict`; 371K strict at ≥80%; persisted by 26 so B7 doesn't
        re-stream BOLD)
      - Scripts/26_build_shared_species_universe.py;
        Scripts/audit_bin_species_consensus.py for source-group BIN audit
- [x] Download GBIF Backbone Taxonomy →
      `Data/raw/gbif/backbone/backbone.zip` (926 MB, Taxon.tsv 2.1 GB
      uncompressed, 7.7M taxa with synonym→accepted mappings;
      Scripts/24_download_gbif_backbone.py)
- [x] Taxonomic name harmonization via GBIF backbone (single authority
      incorporating WCVP, Index Fungorum, Catalogue of Life):
      - Step 1: gbifid_lookup (31,176 LOTUS species via organism_taxonomy_gbifid)
      - Step 2: name_match_exact (517,348 species via canonicalName)
      - Step 3: name_match_fuzzy (2,658 species via GBIF /v1/species/match API)
      - 41,052 synonym redirects; 551,182 of 768,422 names resolved (71.7%)
      - NP→universe linkage: 56.3% → 71.3% (+8,767 NP species; +6,796 Plantae,
        +1,217 Fungi, +490 Animalia)
      - Output: `Data/processed/discovery/shared/species_name_resolution.csv`
      - Scripts/25_resolve_species_names.py
- [x] Build cell × year × source_group "chemical potential" panel
      (Scripts/27_build_chemical_potential_panel.py; streams BOLD 20M +
      GBIF 15M with on-the-fly EPSG:6933 / 100km gridding matching 26):
      - Schema: n_records, n_species_sampled, n_species_with_compounds,
        n_compounds_total, n_unique_compounds (InChIKey-deduped from
        species_compound_pairs.csv), share_np_species, per-kingdom
        breakdowns (animalia/plantae/fungi), and four robustness
        columns: `_strict` (BIN consensus ≥80%), `_no_fuzzy` (drops
        GBIF API matches), `_no_bin` / `_named_only` (drops BIN-recovered
        records entirely)
      - Output:
        `Data/processed/discovery/natural_products/cell_year_chemical_potential.csv`
        (246,348 rows: 49K bold + 91K gbif_plantae + 106K combined cell-years)
      - Findings: signal is plant-driven via GBIF (mean 19.1 NP species
        per combined cell-year, 82% nonzero); BOLD adds sparse animal/fungi
        signal (mean 0.98). Robustness columns confirm signal does not
        depend on aggressive name resolution.
- [x] Stata regressions (DoFiles/reg_natural_products.do, 7 tables):
      - NP1: NP species count (extensive + intensive), Table 3 FE structure,
        both conflict measures. Conflict reduces NP sampling: -0.045***
        (intensive, log events, with lags); cumulative L0-L2 -0.058**
      - NP2: NP share + compound diversity. NP share effect is insignificant —
        conflict does not shift composition away from NP species
      - NP3: Conflict × Richness interaction with NP LHS. Interaction small
        and insignificant
      - NP4: Source decomposition. GBIF drives the signal (cumulative
        -0.083***); BOLD is sparse but BOLD NP share is significant (-0.014**)
      - NP5: Name-resolution robustness (strict BIN, no fuzzy, no BIN,
        named only). All four variants give near-identical coefficients
      - NP6: **Stacked NP vs non-NP direct differential test**. Each
        cell-year stacked as 2 rows (NP species, non-NP species), all
        controls and FEs interacted with type. Conflict × NP interaction
        is zero across all specs — clean null on disproportionality.
        Conflict reduces all species sampling uniformly; NP decline is
        volume-driven.
      - NP7: **Intensive-margin benchmark**. Adds sampling effort control
        (log(1+total_records)) and restricts to total>0. Sampling control
        barely attenuates conflict (-0.037→-0.036). On intensive margin,
        cumulative effect persists at -0.053*. NP share on intensive margin:
        cumulative -0.015** — small compositional shift among active
        collectors.
      - Merge extension: DoFiles/merge_all_regressors.do imports
        chemical-potential panel (combined + BOLD/GBIF decomposition)
        with `have_chempot` guard. Handles Stata 32-char name truncation.
        Zero-fills NP vars for master-only cell-years.
- [x] GBIF Plantae–only regressions (DoFiles/reg_natural_products_gbif.do,
      5 tables): GP1 NP species count (-0.028***, cumul -0.046***), GP2
      share null + compounds -0.085***, GP3 Conflict × Plant Richness
      interaction -0.021*** (stronger than NP3 with IUCN richness), GP4
      stacked null, GP5 10-col intensive-margin benchmark — conflict
      effect -0.083*** on rec>0 sample vanishes with GBIF effort control.
- [x] Pipeline fixes: _no_bin ≡ _named_only bug fixed in Script 27
      (distinct species_no_bin set); kingdom backfill consolidated into
      Script 25 (species-level via GBIF backbone + genus-level via
      genus_to_kingdom map, cross-kingdom homonyms skipped). Script 23
      writes initial outputs only; 25 finalizes. Linear run order:
      22, 22b → 23 → 24 → 25 → 26 → 27. Unknown kingdom: 26K → 8K
      (species pass) → low-hundreds (genus pass).
- [ ] Fungi subset re-run for consistency check with Option A

## Coordination

- Both agents update this file as steps complete (check the boxes).
- Major findings → write a short `Notes/<option_name>_findings_note.tex` so
  the other agent can read it.
- Final deliverable: a joint `Notes/downstream_synthesis_note.tex` comparing
  the fungi cross-validation results from both pipelines.
- Do not modify each other's directories
  (`Data/processed/discovery/publications/` vs
  `Data/processed/discovery/natural_products/`).
- Shared species universe lives in
  `Data/processed/discovery/shared/shared_species_universe.csv`. If both
  agents need it, the first to need it builds it; the second reads.
- Companion shared artifacts (also written by Window B): the per-BIN
  consensus lookup `bin_consensus_lookup.csv` and the GBIF-backbone name
  resolution `species_name_resolution.csv`. Window A may read these for
  taxonomic cleanup but should not rewrite them.

## Workflow

Each agent works in atomic tasks pasted one at a time by the user. Each
task results in a single artifact (script, patch, or note) that the agent
writes and stops. The user runs all Python scripts and Stata do-files
manually in a separate terminal and pastes results back. Read-only checks
(Read, ls, grep, head/wc) are fine. Do not auto-run long pipelines.

## Existing assets to reuse

- `Data/analysis/BOLD_regressor_panel.dta` — cell-year panel with all
  regressors already merged
- `Data/processed/bold/bold_minimal_records.csv` — BOLD specimen-level
  records, all kingdoms
- `Data/processed/gbif/plantae/gbif_plantae_preserved_material_minimal.csv`
  — GBIF Plantae herbarium occurrences (primary plant source)
- `DoFiles/reg_spec1.do` — Tables 3, 5 fixed-effect structure to mirror
- `DoFiles/reg_spec1_gbif_plantae.do` — GBIF plant mirror with pre-period
  richness controls; natural template for Option B's plant slice
- `DoFiles/reg_foreign_collecting.do` — FC3, FC5 templates if foreign-vs-
  domestic dimension matters
- `Scripts/00_build_bold_minimal.py` + `Scripts/pipeline_utils.py` — minimal
  build pipeline
- `Scripts/19_extract_gbif_plantae_species_universe.py` — species universe
  extraction template
- `Scripts/06_build_cell_year_panel.py` — cell × year aggregation template
