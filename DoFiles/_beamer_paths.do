* _beamer_paths.do
* Export locations for Beamer-ready project artifacts.
*
* Outputs are written to TWO places:
*   (1) a canonical LOCAL copy under the project's Exhibits/ folder, and
*   (2) the MERGED deck's own asset folders on Dropbox (what the deck reads).
*
* esttab/estout/graph export write to the LOCAL dirs (via the globals below);
* dd_mirror_outputs (called at the end of each generating do-file) copies them
* into the merged deck on Dropbox.
*
* The old codex_beamer / claude_beamer decks are ARCHIVED
* (Dropbox/diversity_discoveries/archive/) -- nothing writes there anymore.

global DD_PROJ          "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
global DD_MERGED_BEAMER "/Users/vasilykorovkin/Dropbox/diversity_discoveries/merged_beamer"

* (1) Canonical local copies.
global DD_FIG_LOCAL "$DD_PROJ/Exhibits/figures"
global DD_TAB_LOCAL "$DD_PROJ/Exhibits/tables"

* (2) Published copies inside the merged deck (Dropbox) -- what the deck reads.
global DD_FIG_DBX "$DD_MERGED_BEAMER/Figures"
global DD_TAB_DBX "$DD_MERGED_BEAMER/TablesFigures"

capture mkdir "$DD_PROJ/Exhibits"
capture mkdir "$DD_FIG_LOCAL"
capture mkdir "$DD_TAB_LOCAL"
capture mkdir "$DD_MERGED_BEAMER"
capture mkdir "$DD_FIG_DBX"
capture mkdir "$DD_TAB_DBX"

* --- Compatibility aliases ------------------------------------------------
* Existing do-files reference $DD_CODEX_* / $DD_CLAUDE_*. Those decks are
* archived; the names now resolve to the LOCAL dirs so every existing
* "esttab ... using $DD_CODEX_TABLES/x.tex" keeps working and lands locally,
* then dd_mirror_outputs publishes it to the merged deck on Dropbox.
global DD_CODEX_TABLES   "$DD_TAB_LOCAL"
global DD_CLAUDE_TABLES  "$DD_TAB_LOCAL"
global DD_CODEX_FIGURES  "$DD_FIG_LOCAL"
global DD_CLAUDE_FIGURES "$DD_FIG_LOCAL"

* --- dd_mirror_outputs ----------------------------------------------------
* Copy all local figures + tables into the merged deck on Dropbox.
* Idempotent; safe (and intended) to call at the end of any generating do-file.
capture program drop dd_mirror_outputs
program define dd_mirror_outputs
    local nf 0
    local figs : dir "$DD_FIG_LOCAL" files "*"
    foreach f of local figs {
        capture copy "$DD_FIG_LOCAL/`f'" "$DD_FIG_DBX/`f'", replace
        local nf = `nf' + 1
    }
    local nt 0
    local tabs : dir "$DD_TAB_LOCAL" files "*.tex"
    foreach t of local tabs {
        capture copy "$DD_TAB_LOCAL/`t'" "$DD_TAB_DBX/`t'", replace
        local nt = `nt' + 1
    }
    display as result "dd_mirror_outputs: synced `nf' figures + `nt' tables -> merged_beamer (Dropbox)"
end
