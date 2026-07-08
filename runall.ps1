<#
.SYNOPSIS
  runall.ps1 - PowerShell port of runall.sh for the fragmented-requirements
  test-generation study. Native Windows; no bash required.

.DESCRIPTION
  Generates data (both models, 3 modes, repeats + ablations) and/or evaluates it
  (subjective judges + objective). Fault tolerant (one failed cell never aborts
  the batch; failures are logged) and resumable (the LLM/data caches mean a
  re-run only calls the API for cells not yet computed).

  Runs sequentially on purpose to stay under provider rate limits.

.PARAMETER Stage
  gen | eval | all   (default: all)

.PARAMETER Reqs
  Space- or comma-separated requirement IDs. Defaults to the full 65-ID list
  for THIS dataset (non-contiguous IDs - do NOT use a numeric range).

.PARAMETER Repeats
  Variance repeats for the main condition (default 3 -> repeat_index 0,1,2).

.PARAMETER Judges
  Which subjective judges to run in eval: any of gemini gpt claude (default: gemini gpt).

.PARAMETER Ablations
  $true to also run A0 (no_retrieval) and A1 (no_resolution) (default: $true).

.PARAMETER ReferenceJson
  Path to a frozen, human-validated objective reference (fix A5). If empty,
  objective eval uses a heuristic draft and warns.

.PARAMETER DryRun
  $true prints the commands without executing them.

.EXAMPLE
  # preview the first block
  .\runall.ps1 -Stage gen -Reqs "R1 R100b R102d R103d R2 R21 R22 R23 R24 R25" -DryRun $true

.EXAMPLE
  # run the first block for real
  .\runall.ps1 -Stage gen -Reqs "R1 R100b R102d R103d R2 R21 R22 R23 R24 R25"

.EXAMPLE
  # evaluate everything once generation is done, with a frozen reference
  .\runall.ps1 -Stage eval -ReferenceJson reference.json
#>

param(
  [ValidateSet("gen","eval","all")]
  [string]$Stage = "all",

  [string]$Reqs = "",

  [string]$Modes = "graph vector hybrid",

  [int]$Repeats = 3,

  [string]$Judges = "gemini gpt",

  [bool]$Ablations = $true,

  [string]$AblationMode = "hybrid",

  [bool]$Objective = $true,

  [string]$ReferenceJson = "",

  [string]$DocsDir = "docs",

  [string]$GptDir = "runs",

  [string]$ClaudeDir = "runs_haiku",

  [string]$EvalDir = "evaluations",

  [int]$NumTests = 10,

  [bool]$DryRun = $false
)

# --- The real 65 requirement IDs for THIS dataset (non-contiguous). ----------
# Used when -Reqs is not supplied. Do NOT replace with a numeric range.
$DefaultReqs = @(
  "R1","R100b","R102d","R103d","R2","R21","R22","R23","R24","R25","R26","R29",
  "R3","R30","R31","R31b","R32","R33","R34","R37","R38","R39","R4","R41","R43",
  "R44","R45","R47","R48","R49","R5","R50","R51","R51c","R52c","R58c","R6","R60c",
  "R61","R61c","R62","R63","R64","R65","R69","R7","R70","R71","R71b","R72","R72b",
  "R74","R79b","R80","R81b","R81c","R82b","R83b","R84b","R87b","R91c","R91d",
  "R92c","R93c","R97b"
)

# --- Resolve requirement / mode lists ----------------------------------------
if ([string]::IsNullOrWhiteSpace($Reqs)) {
  $ReqList = $DefaultReqs
} else {
  $ReqList = $Reqs -split '[,\s]+' | Where-Object { $_ -ne "" }
}
$ModeList  = $Modes  -split '[,\s]+' | Where-Object { $_ -ne "" }
$JudgeList = $Judges -split '[,\s]+' | Where-Object { $_ -ne "" }

# --- Logging setup -----------------------------------------------------------
$Ts = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$FailLog = Join-Path $LogDir "failures_$Ts.log"
$RunLog  = Join-Path $LogDir "runall_$Ts.log"
New-Item -ItemType File -Force -Path $FailLog | Out-Null

function Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
  Write-Host $line
  Add-Content -Path $RunLog -Value $line
}
function Fail([string]$msg) {
  Write-Host "FAILED: $msg" -ForegroundColor Red
  Add-Content -Path $FailLog -Value $msg
}

# Run one python command; never aborts the batch; records failures.
function Invoke-Unit([string]$label, [string[]]$argv) {
  if ($DryRun) {
    Write-Host ("DRY: python " + ($argv -join " "))
    return
  }
  & python @argv *>> $RunLog
  if ($LASTEXITCODE -eq 0) {
    Log "ok   $label"
  } else {
    Fail "$label :: python $($argv -join ' ')"
  }
}

# --- Sanity checks -----------------------------------------------------------
if (-not (Test-Path "exp_core.py")) {
  Write-Host "ERROR: run this from the folder that contains exp_core.py and the wrappers." -ForegroundColor Red
  exit 1
}
if (-not (Test-Path ".env")) {
  Write-Host "WARNING: no .env found in $(Get-Location). Scripts expect NEO4J_* and API keys there." -ForegroundColor Yellow
}

Log "=== runall start ==="
Log ("REQS count: {0} | MODES: {1} | REPEATS: {2} | STAGE: {3}" -f $ReqList.Count, ($ModeList -join ','), $Repeats, $Stage)
Log ("ABLATIONS: {0} | JUDGES: {1} | OBJECTIVE: {2}" -f $Ablations, ($JudgeList -join ','), $Objective)
Log "failures -> $FailLog"

# =============================================================================
# STAGE 1 - GENERATION
# =============================================================================
function Generate-For([string]$script, [string]$outdir, [string]$who) {
  Log "--- generation ($who) ---"
  foreach ($req in $ReqList) {
    foreach ($mode in $ModeList) {
      for ($r = 0; $r -lt $Repeats; $r++) {
        Invoke-Unit "$who gen $req $mode full r$r" @(
          $script, "--target-id", $req, "--mode", $mode,
          "--pipeline", "full", "--repeat-index", "$r",
          "--num-tests", "$NumTests", "--out-dir", $outdir
        )
      }
    }
    if ($Ablations) {
      Invoke-Unit "$who gen $req $AblationMode no_resolution r0" @(
        $script, "--target-id", $req, "--mode", $AblationMode,
        "--pipeline", "no_resolution", "--repeat-index", "0",
        "--num-tests", "$NumTests", "--out-dir", $outdir
      )
      Invoke-Unit "$who gen $req $AblationMode no_retrieval r0" @(
        $script, "--target-id", $req, "--mode", $AblationMode,
        "--pipeline", "no_retrieval", "--repeat-index", "0",
        "--num-tests", "$NumTests", "--out-dir", $outdir
      )
    }
  }
}

if ($Stage -eq "all" -or $Stage -eq "gen") {
  Generate-For "03_run_experiment.py"          $GptDir    "GPT"
  Generate-For "03c_run_experiment_claude.py"  $ClaudeDir "Claude"
}

# =============================================================================
# STAGE 2 - EVALUATION
# =============================================================================
# One judge scores EVERY row of BOTH generators. The combined glob matches both
# run directories (with default names runs + runs_haiku, "runs*/*.csv" matches).
if ($Stage -eq "all" -or $Stage -eq "eval") {
  $CombinedGlob = "$GptDir*/*.csv"

  Log "--- subjective evaluation ---"
  foreach ($j in $JudgeList) {
    switch ($j) {
      "gemini" { $script = "05G_evaluate_gemini.py" }
      "gpt"    { $script = "05_evaluate.py" }
      "claude" { $script = "05C_evaluate_claude.py" }
      default  { Fail "unknown judge: $j"; continue }
    }
    Invoke-Unit "judge:$j" @($script, "--input", $CombinedGlob, "--out-dir", $EvalDir)
  }

  if ($Objective) {
    Log "--- objective evaluation ---"
    if (-not [string]::IsNullOrWhiteSpace($ReferenceJson)) {
      Invoke-Unit "objective (frozen ref)" @(
        "06_objective_eval.py", "--input", $CombinedGlob,
        "--reference-json", $ReferenceJson, "--out-dir", $EvalDir
      )
    } else {
      Log "WARNING: no -ReferenceJson set - objective eval uses a heuristic draft (fix A5)."
      Log "         Freeze one: run 06_objective_eval.py --export-reference, validate it,"
      Log "         then re-run with -ReferenceJson reference.json -Stage eval"
      Invoke-Unit "objective (heuristic draft)" @(
        "06_objective_eval.py", "--input", $CombinedGlob,
        "--docs-dir", $DocsDir, "--out-dir", $EvalDir
      )
    }
  }
}

# =============================================================================
# SUMMARY
# =============================================================================
$nfail = 0
if (Test-Path $FailLog) {
  $nfail = (Get-Content $FailLog | Where-Object { $_ -ne "" }).Count
}
Log "=== runall done ==="
if ($nfail -gt 0) {
  Log "There were $nfail failed unit(s). See $FailLog"
  Log "Re-run to retry: cached successful units are skipped, only missing ones call the API."
} else {
  Log "All units completed with no recorded failures."
}
