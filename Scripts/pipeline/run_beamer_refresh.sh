#!/usr/bin/env bash
# Sequentially refresh Beamer-ready Stata exports.
# Portable: uses printf (works under both bash and zsh).

set +e

PROJECT_ROOT="/Users/vasilykorovkin/Documents/Diversity_Discoveries"
STATA="/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp"
STAMP="$(date '+%Y%m%d_%H%M%S')"
MASTER_LOG="$PROJECT_ROOT/Logs/beamer_refresh_${STAMP}.log"
STATUS_TSV="$PROJECT_ROOT/Logs/beamer_refresh_status_${STAMP}.tsv"

mkdir -p "$PROJECT_ROOT/Logs"

DOFILES=(
  "DoFiles/reg_spec1.do"
  "DoFiles/reg_spec_organisms.do"
  "DoFiles/reg_spec_bin.do"
  "DoFiles/reg_spec1_acled.do"
  "DoFiles/reg_spec1_acled_table3_definitions.do"
  "DoFiles/reg_conflict_signal_decomposition.do"
  "DoFiles/desc_foreign_collecting.do"
  "DoFiles/reg_foreign_collecting.do"
  "DoFiles/reg_publications.do"
  "DoFiles/reg_publications_gbif_exposure.do"
  "DoFiles/reg_natural_products_gbif.do"
  "DoFiles/reg_natural_products.do"
  "DoFiles/reg_event_study.do"
  "DoFiles/reg_event_study_bin_new.do"
  "DoFiles/reg_event_study_publications_5yr.do"
  "DoFiles/reg_event_study_natural_products_gbif.do"
  "DoFiles/reg_event_study_twfe_simple.do"
  "DoFiles/reg_event_study_twfe_simple_acled_africa.do"
)

{
  printf '%s\n' "Beamer refresh started: $(date)"
  printf '%s\n' "Project root: $PROJECT_ROOT"
  printf '%s\n' "Master log: $MASTER_LOG"
  printf '%s\n' "Status TSV: $STATUS_TSV"
  printf '%s\n' "Stata executable: $STATA"
  printf '\n'
} >> "$MASTER_LOG"

printf 'timestamp\tdofile\tstatus\texit_code\telapsed_seconds\n' > "$STATUS_TSV"

cd "$PROJECT_ROOT" || exit 1

failures=0
started=0
if [[ -z "$START_AT" ]]; then
  started=1
else
  printf '%s\n' "START_AT requested: $START_AT" >> "$MASTER_LOG"
fi

for dofile in "${DOFILES[@]}"; do
  if [[ "$started" -eq 0 ]]; then
    if [[ "$dofile" == "$START_AT" ]]; then
      started=1
    else
      continue
    fi
  fi

  start_epoch="$(date '+%s')"
  {
    printf '\n'
    printf '%s\n' "============================================================"
    printf '%s\n' "START: $dofile"
    printf '%s\n' "TIME:  $(date)"
    printf '%s\n' "============================================================"
  } >> "$MASTER_LOG"

  "$STATA" -b do "$dofile" >> "$MASTER_LOG" 2>&1
  rc="$?"

  end_epoch="$(date '+%s')"
  elapsed="$(( end_epoch - start_epoch ))"

  if [[ "$rc" -eq 0 ]]; then
    step_status="ok"
  else
    step_status="failed"
    failures="$(( failures + 1 ))"
  fi

  {
    printf '%s\n' "END:   $dofile"
    printf '%s\n' "TIME:  $(date)"
    printf '%s\n' "STATUS: $step_status (exit $rc, ${elapsed}s)"
  } >> "$MASTER_LOG"
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$dofile" "$step_status" "$rc" "$elapsed" >> "$STATUS_TSV"
done

{
  printf '\n'
  printf '%s\n' "============================================================"
  printf '%s\n' "Beamer refresh finished: $(date)"
  printf '%s\n' "Failures: $failures"
  printf '%s\n' "Status TSV: $STATUS_TSV"
  printf '%s\n' "============================================================"
} >> "$MASTER_LOG"

if [[ "$failures" -eq 0 ]]; then
  exit 0
fi
exit 1
