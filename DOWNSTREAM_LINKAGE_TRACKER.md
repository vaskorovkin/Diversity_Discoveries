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
- [ ] Build NCBI Entrez `elink` pipeline (nuccore → pubmed) in batched mode
- [ ] Output: `Data/processed/discovery/publications/bold_accession_to_pubmed.csv`

**Subtask A2: GBIF Plantae → GBIF Literature API (plants)**
- [ ] Audit GBIF preserved-material occurrences for `datasetKey` /
      `gbifID` coverage in the existing
      `gbif_plantae_preserved_material_minimal.csv`
- [ ] Build pipeline: occurrence → datasetKey → GBIF Literature API
      (`api.gbif.org/v1/literature?gbifDatasetKey=...`) → citing publications
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
- [ ] Download LOTUS dump (cleanest, Wikidata-linked) →
      `Data/raw/natural_products/lotus/`
- [ ] Add COCONUT and KNApSAcK as supplementary (especially for
      animal-derived compounds: venoms, marine invertebrate metabolites,
      insect alkaloids — sparse but real)
- [ ] Build species → compound count map →
      `Data/processed/discovery/natural_products/species_to_compounds.csv`
- [ ] Build the **shared species universe** across all upstream pipelines:
      - BOLD records (from `bold_minimal_records.csv`, all kingdoms)
      - GBIF Plantae preserved-material (from
        `gbif_plantae_preserved_material_minimal.csv`)
      - GBIF Plantae human-observation (if present, separate column)
      - Output: `Data/processed/discovery/shared/shared_species_universe.csv`
        with columns: species_name, kingdom, n_records_bold,
        n_records_gbif_pm, n_records_gbif_ho, cells_present, source_priority
      - Plants will be GBIF-dominated (~3× BOLD coverage); animals/fungi
        BOLD-dominated. Use existing
        `Scripts/19_extract_gbif_plantae_species_universe.py` as a template
- [ ] Taxonomic name harmonization (WCVP/POWO for plants, MycoBank for fungi,
      NCBI Taxonomy as fallback for animals)
- [ ] Build cell-level "chemical potential" measure per kingdom (richness ×
      mean compound yield in the cell's species pool)
- [ ] Stata regressions: does conflict reduce sampling of chemically valuable
      species disproportionately? Run pooled and per-kingdom (Plantae, Fungi,
      Animalia). For plants, the natural mirror is `reg_spec1_gbif_plantae.do`
      since the GBIF plant panel and pre-period richness controls are already
      in the merged regression panel. Report per-kingdom NP-DB coverage as
      a robustness statistic
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
