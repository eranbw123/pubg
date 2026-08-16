<#
.SYNOPSIS
    Stage 1 automated check: bridge builds, contracts hold, nothing can send input.

.DESCRIPTION
    Everything here runs without PUBG, Overwolf or a network. It proves the code
    is correct and loadable; it does NOT prove what Training Mode exposes. That
    requires the live probe (scripts\run-stage-01-probe.ps1) and is deliberately
    a separate step - a passing simulation is not evidence about the game.

    Exit code 0 means AUTOMATED PASS.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$bridgeDir = Join-Path $repoRoot 'apps\overwolf-bridge'
$distDir = Join-Path $bridgeDir 'dist'
$reportDir = Join-Path $repoRoot 'reports\stages\stage-01'

if (-not (Test-Path $venvPython)) {
    Write-Host "No .venv found. Run scripts\bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$env:Path = "$env:APPDATA\npm;$env:Path"

$results = [ordered]@{}
function Record($name, $ok) {
    if ($ok) { $results[$name] = 'pass' } else { $results[$name] = 'fail' }
    $colour = 'Green'; $label = 'PASS'
    if (-not $ok) { $colour = 'Red'; $label = 'FAIL' }
    Write-Host ("  [{0}] {1}" -f $label, $name) -ForegroundColor $colour
}

Write-Host "Stage 01 - live Overwolf sensor feasibility (automated portion)" -ForegroundColor Cyan
Write-Host ""

# --- Python ---------------------------------------------------------------- #
Write-Host "python lint and format"
& $venvPython -m ruff check "$repoRoot\src" "$repoRoot\tests" 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'ruff.txt')
Record 'ruff lint' ($LASTEXITCODE -eq 0)
& $venvPython -m ruff format --check "$repoRoot\src" "$repoRoot\tests" | Out-Null
Record 'ruff format' ($LASTEXITCODE -eq 0)

Write-Host ""
Write-Host "python tests"
$junit = Join-Path $reportDir 'pytest-junit.xml'
& $venvPython -m pytest "$repoRoot\tests" -q --junitxml=$junit 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'pytest.txt')
Record 'python tests' ($LASTEXITCODE -eq 0)

$passed = 0; $failed = 0; $errors = 0; $skipped = 0
if (Test-Path $junit) {
    [xml]$xml = Get-Content $junit
    $suite = $xml.testsuites.testsuite
    if ($null -eq $suite) { $suite = $xml.testsuite }
    if ($suite) {
        $failed = [int]$suite.failures; $errors = [int]$suite.errors; $skipped = [int]$suite.skipped
        $passed = [int]$suite.tests - $failed - $errors - $skipped
    }
}
Write-Host ("  {0} passed, {1} failed, {2} errors, {3} skipped" -f $passed, $failed, $errors, $skipped)

# --- Overwolf bridge -------------------------------------------------------- #
Write-Host ""
Write-Host "overwolf bridge"
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    Record 'pnpm available' $false
} else {
    Record 'pnpm available' $true
    & pnpm --dir $bridgeDir typecheck 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'tsc.txt') | Out-Null
    Record 'bridge typecheck' ($LASTEXITCODE -eq 0)

    & pnpm --dir $bridgeDir test 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'vitest.txt')
    Record 'bridge tests' ($LASTEXITCODE -eq 0)

    & pnpm --dir $bridgeDir build 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'bridge-build.txt')
    Record 'bridge build' ($LASTEXITCODE -eq 0)
}

# The unpacked app is only loadable if every one of these is present.
$required = @('manifest.json', 'background.html', 'background.js', 'debug.html', 'debug.js',
              'icons\icon.png', 'icons\icon_gray.png')
$missing = @($required | Where-Object { -not (Test-Path (Join-Path $distDir $_)) })
Record 'unpacked app is complete' ($missing.Count -eq 0)
if ($missing.Count -gt 0) { Write-Host ("    missing: {0}" -f ($missing -join ', ')) -ForegroundColor Red }

# The manifest must target PUBG's class id, not the instance id.
$manifestOk = $false
if (Test-Path (Join-Path $distDir 'manifest.json')) {
    $manifest = Get-Content (Join-Path $distDir 'manifest.json') -Raw | ConvertFrom-Json
    $manifestOk = ($manifest.data.game_targeting.game_ids -contains 10906)
}
Record 'manifest targets PUBG class id 10906' $manifestOk

# --- Safety ----------------------------------------------------------------- #
Write-Host ""
Write-Host "safety"
& $venvPython -m pubg_training_bot safety scan | Tee-Object -FilePath (Join-Path $reportDir 'safety.txt') | Out-Null
Record 'scope lock scan' ($LASTEXITCODE -eq 0)

$live = & $venvPython -c "from pubg_training_bot.actuation import live_actuator_available; print(live_actuator_available())"
Record 'live actuation still disabled' ($live.Trim() -eq 'False')

# The bridge must contain no input API of any kind.
$bridgeSource = Get-ChildItem "$bridgeDir\src" -Filter *.ts -Recurse | Get-Content -Raw
$inputSymbols = @('inputTracking', 'sendKeyStroke', 'simulateKey', 'robotjs')
$found = @($inputSymbols | Where-Object { $bridgeSource -match $_ })
Record 'bridge contains no input API' ($found.Count -eq 0)

& $venvPython -m pubg_training_bot schemas export --check | Out-Null
Record 'json schemas current' ($LASTEXITCODE -eq 0)

# --- Stage report ----------------------------------------------------------- #
Write-Host ""
Write-Host "stage report"
$checkArgs = @()
foreach ($key in $results.Keys) { $checkArgs += @('--check', ("{0}={1}" -f $key, $results[$key])) }

& $venvPython -m pubg_training_bot stage report --stage 01 `
    --tests-ran --tests-passed $passed --tests-failed $failed `
    --tests-errors $errors --tests-skipped $skipped `
    --tests-command "pytest tests -q + vitest run" `
    --open-question "Does PUBG Training Mode actually deliver the 'location' feature? (risk R-002 - unanswerable without the live probe)" `
    --open-question "What map/phase/view identifiers does Training Mode report? Must be observed, never guessed." `
    --open-question "What is the real location update cadence and stationary noise floor? Freshness thresholds (D-009) depend on it." `
    --open-question "Is this Overwolf account whitelisted to load unpacked apps? (risk R-016)" `
    @checkArgs | Out-Null
$reportOk = ($LASTEXITCODE -eq 0)

$failedChecks = @($results.Keys | Where-Object { $results[$_] -eq 'fail' })
Write-Host ""
if ($failedChecks.Count -eq 0 -and $reportOk) {
    Write-Host "STAGE 01 (automated): AUTOMATED PASS" -ForegroundColor Green
    Write-Host ""
    Write-Host "This proves the code is correct and the app is loadable." -ForegroundColor Yellow
    Write-Host "It proves NOTHING about what Training Mode exposes. For that, run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run-stage-01-probe.ps1"
    Write-Host "evidence: $reportDir"
    exit 0
} else {
    Write-Host "STAGE 01 (automated): FAILED" -ForegroundColor Red
    foreach ($name in $failedChecks) { Write-Host "  failed: $name" -ForegroundColor Red }
    Write-Host "evidence: $reportDir"
    exit 1
}
