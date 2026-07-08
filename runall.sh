#!/usr/bin/env bash
# ============================================================================
# runall.sh — end-to-end experiment runner for the fragmented-requirements
# test-generation study.
#
# Design goals:
#   * FAULT TOLERANT: one failed requirement never aborts the batch. Failures
#     are logged to a file and can be re-run afterwards.
#   * RESUMABLE: thanks to the LLM/data caches, re-running this script only
#     actually calls the API for the units that are still missing; everything
#     already generated is served from cache for free.
#   * BALANCED: Claude is run on ALL requirements (not just a hand-picked
#     subset), exactly like GPT.
#   * REPRODUCIBLE: every row carries model/pipeline/repeatIndex/promptVersion;
#     every run writes a *_metadata.json.
#
# It does NOT parallelize on purpose: sequential calls keep you well under the
# providers' rate limits. If you want speed, raise PARALLEL below (see notes).
#
# Usage:
#   chmod +x runall.sh
#   ./runall.sh                 # full run with defaults
#   REQS="R1 R2 R5" ./runall.sh # only these requirements
#   STAGE=gen ./runall.sh       # only generation
#   STAGE=eval ./runall.sh      # only evaluation (generation already done)
#   DRY_RUN=1 ./runall.sh       # print the commands without executing them
# ============================================================================

set -uo pipefail   # NOTE: intentionally NO `-e` — we handle errors per-unit.

# ----------------------------------------------------------------------------
# CONFIG (override any of these via environment variables)
# ----------------------------------------------------------------------------

# Requirement ids. Default: R1..R65. If your ids are not contiguous, set REQS
# explicitly, e.g.  REQS="R1 R2 R5 R12 R70" ./runall.sh
REQS="${REQS:-$(seq -f "R%g" 1 65)}"

# Retrieval modes for the main comparison (RQ1).
MODES="${MODES:-graph vector hybrid}"

# Number of variance repeats for the MAIN condition (full pipeline).
# repeat_index 0..(REPEATS-1). Set to 1 for a single pass, 3 for variance.
REPEATS="${REPEATS:-3}"

# Which stage(s) to run: gen | eval | all
STAGE="${STAGE:-all}"

# Ablations (RQ3). Set ABLATIONS=0 to skip.
ABLATIONS="${ABLATIONS:-1}"
# For the ablations we use a single representative mode (hybrid) and a single
# repeat, since they answer "does the resolution/retrieval layer matter", not
# "how variable is it".
ABLATION_MODE="${ABLATION_MODE:-hybrid}"

# Evaluation: which judges to run. Space-separated subset of: gemini gpt claude
# Default: all three (gemini = neutral primary; gpt/claude = robustness cross-check).
# Default: gemini (neutral primary) + gpt (robustness cross-check).
# The Claude judge is omitted by default (it grades one of the generators' own
# family, and the Anthropic budget is reserved for generation). Add it back with
# JUDGES="gemini gpt claude" if you want the third judge.
JUDGES="${JUDGES:-gemini gpt}"

# Run the objective (document-grounded) evaluation too?
OBJECTIVE="${OBJECTIVE:-1}"
# Frozen, human-validated reference JSON (fix A5). If empty, the objective
# evaluator falls back to an on-the-fly heuristic draft and warns.
REFERENCE_JSON="${REFERENCE_JSON:-}"
DOCS_DIR="${DOCS_DIR:-docs}"

# Output directories.
GPT_DIR="${GPT_DIR:-runs}"
CLAUDE_DIR="${CLAUDE_DIR:-runs_haiku}"
EVAL_DIR="${EVAL_DIR:-evaluations}"

# num tests per requirement
NUM_TESTS="${NUM_TESTS:-10}"

# Dry run: print commands, do not execute.
DRY_RUN="${DRY_RUN:-0}"

# ----------------------------------------------------------------------------
# Bookkeeping
# ----------------------------------------------------------------------------
TS="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
FAIL_LOG="$LOG_DIR/failures_${TS}.log"
RUN_LOG="$LOG_DIR/runall_${TS}.log"
: > "$FAIL_LOG"

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$RUN_LOG"; }
fail() { echo "FAILED: $*" | tee -a "$FAIL_LOG" >&2; }

# run <label> <command...>  — never aborts the batch; records failures.
run() {
  local label="$1"; shift
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "DRY: $*"
    return 0
  fi
  if "$@" >>"$RUN_LOG" 2>&1; then
    log "ok   $label"
  else
    fail "$label :: $*"
  fi
}

# ----------------------------------------------------------------------------
# Sanity checks
# ----------------------------------------------------------------------------
if [[ ! -f exp_core.py ]]; then
  echo "ERROR: run this from the directory that contains exp_core.py and the wrappers." >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "WARNING: no .env found in $(pwd). The scripts expect NEO4J_* and API keys there." >&2
fi

log "=== runall start ==="
log "REQS count: $(echo $REQS | wc -w) | MODES: $MODES | REPEATS: $REPEATS | STAGE: $STAGE"
log "ABLATIONS: $ABLATIONS | JUDGES: $JUDGES | OBJECTIVE: $OBJECTIVE"
log "failures -> $FAIL_LOG"

# ============================================================================
# STAGE 1 — GENERATION
# ============================================================================
generate_for() {
  # $1 = script, $2 = out-dir, $3 = provider label (for logging)
  local script="$1" outdir="$2" who="$3"
  log "--- generation ($who) ---"

  for REQ in $REQS; do
    # Main comparison: 3 modes x REPEATS repeats, full pipeline.
    for MODE in $MODES; do
      for ((R=0; R<REPEATS; R++)); do
        run "$who gen $REQ $MODE full r$R" \
          python "$script" --target-id "$REQ" --mode "$MODE" \
            --pipeline full --repeat-index "$R" \
            --num-tests "$NUM_TESTS" --out-dir "$outdir"
      done
    done

    # Ablations (RQ3): single mode, single repeat, two ablation pipelines.
    if [[ "$ABLATIONS" == "1" ]]; then
      run "$who gen $REQ $ABLATION_MODE no_resolution r0" \
        python "$script" --target-id "$REQ" --mode "$ABLATION_MODE" \
          --pipeline no_resolution --repeat-index 0 \
          --num-tests "$NUM_TESTS" --out-dir "$outdir"
      # no_retrieval ignores the graph, so mode is nominal; run once.
      run "$who gen $REQ $ABLATION_MODE no_retrieval r0" \
        python "$script" --target-id "$REQ" --mode "$ABLATION_MODE" \
          --pipeline no_retrieval --repeat-index 0 \
          --num-tests "$NUM_TESTS" --out-dir "$outdir"
    fi
  done
}

if [[ "$STAGE" == "all" || "$STAGE" == "gen" ]]; then
  generate_for "03_run_experiment.py"                     "$GPT_DIR"    "GPT"
  generate_for "03c_run_experiment_claude.py"            "$CLAUDE_DIR" "Claude"
fi

# ============================================================================
# STAGE 2 — EVALUATION
# ============================================================================
# One judge scores EVERY row of BOTH generators. We point --input at a single
# combined glob that matches both run directories, so the comparison is
# apples-to-apples. With the default names (runs, runs_haiku) the glob
# "runs*/*.csv" matches both.

if [[ "$STAGE" == "all" || "$STAGE" == "eval" ]]; then
  log "--- subjective evaluation ---"
  # Prefer a single combined glob when the dir names share a prefix (runs, runs_haiku).
  COMBINED_GLOB="${GPT_DIR%/}*/*.csv"
  for j in $JUDGES; do
    case "$j" in
      gemini) script="05G_evaluate_gemini.py" ;;
      gpt)    script="05_evaluate.py" ;;
      claude) script="05C_evaluate_claude.py" ;;
      *) fail "unknown judge: $j"; continue ;;
    esac
    run "judge:$j (combined)" \
      python "$script" --input "$COMBINED_GLOB" --out-dir "$EVAL_DIR"
  done

  # Objective, document-grounded evaluation (model-agnostic, no LLM).
  if [[ "$OBJECTIVE" == "1" ]]; then
    log "--- objective evaluation ---"
    if [[ -n "$REFERENCE_JSON" ]]; then
      run "objective (frozen ref)" \
        python 06_objective_eval.py --input "$COMBINED_GLOB" \
          --reference-json "$REFERENCE_JSON" --out-dir "$EVAL_DIR"
    else
      log "WARNING: no REFERENCE_JSON set — objective eval uses a heuristic draft (fix A5)."
      log "         To freeze a reference: run once with --export-reference, validate it,"
      log "         then re-run with REFERENCE_JSON=reference.json ./runall.sh STAGE=eval"
      run "objective (heuristic draft)" \
        python 06_objective_eval.py --input "$COMBINED_GLOB" \
          --docs-dir "$DOCS_DIR" --out-dir "$EVAL_DIR"
    fi
  fi
fi

# ============================================================================
# SUMMARY
# ============================================================================
NFAIL=$(grep -c . "$FAIL_LOG" 2>/dev/null | head -n1)
NFAIL="${NFAIL:-0}"
log "=== runall done ==="
if [[ "$NFAIL" -gt 0 ]]; then
  log "There were $NFAIL failed unit(s). See $FAIL_LOG"
  log "Re-run just the failures: the cache means successful units won't be recomputed."
  log "Tip: STAGE=gen ./runall.sh re-attempts generation; already-done units are cache hits."
else
  log "All units completed with no recorded failures."
fi
