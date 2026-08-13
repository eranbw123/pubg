<#
.SYNOPSIS
    Stage 0 automated check: foundation, scope lock and doctor.

.DESCRIPTION
    Runs every Stage 0 gate and writes the evidence bundle to
    reports\stages\stage-00\. Read-only with respect to the game: it does not
    start PUBG, does not capture the screen and cannot send input.

    Exit code 0 means AUTOMATED PASS.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check-stage-00.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$reportDir = Join-Path $repoRoot 'reports\stages\stage-00'

if (-not (Test-Path $venvPython)) {
    Write-Host "No .venv found. Run scripts\bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$results = [ordered]@{}
function Record($name, $ok) {
    if ($ok) { $results[$name] = 'pass' } else { $results[$name] = 'fail' }
    $colour = 'Green'
    $label = 'PASS'
    if (-not $ok) { $colour = 'Red'; $label = 'FAIL' }
    Write-Host ("  [{0}] {1}" -f $label, $name) -ForegroundColor $colour
}

Write-Host "Stage 00 - foundation, scope lock and doctor" -ForegroundColor Cyan
Write-Host "repository: $repoRoot"
Write-Host ""

# --- 1. Lint (optional: ruff ships with the dev extra) -------------------- #
Write-Host "lint"
& $venvPython -m ruff check "$repoRoot\src" "$repoRoot\tests" 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'ruff.txt')
$ruffOk = ($LASTEXITCODE -eq 0)
Record 'ruff lint' $ruffOk

Write-Host "format check"
& $venvPython -m ruff format --check "$repoRoot\src" "$repoRoot\tests" 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'ruff-format.txt')
Record 'ruff format' ($LASTEXITCODE -eq 0)

# --- 2. Unit and integration tests ---------------------------------------- #
Write-Host ""
Write-Host "tests"
$junit = Join-Path $reportDir 'pytest-junit.xml'
& $venvPython -m pytest "$repoRoot\tests" -q --junitxml=$junit 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'pytest.txt')
$testsOk = ($LASTEXITCODE -eq 0)

$passed = 0; $failed = 0; $errors = 0; $skipped = 0
if (Test-Path $junit) {
    [xml]$xml = Get-Content $junit
    $suite = $xml.testsuites.testsuite
    if ($null -eq $suite) { $suite = $xml.testsuite }
    if ($suite) {
        $total = [int]$suite.tests
        $failed = [int]$suite.failures
        $errors = [int]$suite.errors
        $skipped = [int]$suite.skipped
        $passed = $total - $failed - $errors - $skipped
    }
}
Record 'unit and integration tests' $testsOk
Write-Host ("  {0} passed, {1} failed, {2} errors, {3} skipped" -f $passed, $failed, $errors, $skipped)

# --- 3. Scope lock and live-input interlock ------------------------------- #
Write-Host ""
Write-Host "safety"
& $venvPython -m pubg_training_bot safety scan | Tee-Object -FilePath (Join-Path $reportDir 'safety.txt')
Record 'scope lock scan' ($LASTEXITCODE -eq 0)

$liveCheck = & $venvPython -c "from pubg_training_bot.actuation import live_actuator_available; print(live_actuator_available())"
Record 'live actuation disabled' ($liveCheck.Trim() -eq 'False')

# --- 4. Schemas match the models ------------------------------------------ #
Write-Host ""
Write-Host "schemas"
& $venvPython -m pubg_training_bot schemas export --check
Record 'json schemas current' ($LASTEXITCODE -eq 0)

# --- 5. Doctor ------------------------------------------------------------- #
Write-Host ""
Write-Host "doctor"
& $venvPython -m pubg_training_bot doctor --out $reportDir
$doctorOk = ($LASTEXITCODE -eq 0)
$doctorJson = Join-Path $reportDir 'doctor.json'
$doctorFailures = 0
if (Test-Path $doctorJson) {
    $doctor = Get-Content $doctorJson -Raw | ConvertFrom-Json
    $doctorFailures = [int]$doctor.counts.fail
}
Record 'doctor report generated' ($doctorOk -and (Test-Path $doctorJson))
Record 'doctor has no blocking failures' ($doctorFailures -eq 0)

# --- 6. CLI starts --------------------------------------------------------- #
Write-Host ""
Write-Host "cli"
& $venvPython -m pubg_training_bot stage status --write-docs | Out-Null
Record 'cli stage status' ($LASTEXITCODE -eq 0)

# --- 7. Stage report ------------------------------------------------------- #
Write-Host ""
Write-Host "stage report"
$checkArgs = @()
foreach ($key in $results.Keys) { $checkArgs += @('--check', ("{0}={1}" -f $key, $results[$key])) }

& $venvPython -m pubg_training_bot stage report --stage 00 `
    --tests-ran --tests-passed $passed --tests-failed $failed `
    --tests-errors $errors --tests-skipped $skipped `
    --tests-command "pytest tests -q" `
    --open-question "Operator must confirm the doctor output matches this machine (display, Overwolf, PUBG paths)." `
    --open-question "Overwolf is not installed on this host; Stage 1 is blocked until it is." `
    @checkArgs
$reportOk = ($LASTEXITCODE -eq 0)

# --- summary --------------------------------------------------------------- #
$failedChecks = @($results.Keys | Where-Object { $results[$_] -eq 'fail' })
Write-Host ""
if ($failedChecks.Count -eq 0 -and $reportOk) {
    Write-Host "STAGE 00: AUTOMATED PASS" -ForegroundColor Green
    Write-Host "evidence: $reportDir"
    exit 0
} else {
    Write-Host "STAGE 00: FAILED" -ForegroundColor Red
    foreach ($name in $failedChecks) { Write-Host "  failed: $name" -ForegroundColor Red }
    Write-Host "evidence: $reportDir"
    exit 1
}
