<#
.SYNOPSIS
    Stage 1 pipeline dry run: the probe driven by a synthetic bridge, no game.

.DESCRIPTION
    Runs the real receiver, normaliser and report generator against a simulated
    Overwolf bridge over a real loopback socket. Use it to confirm the plumbing
    works on this machine BEFORE spending a live Training Mode session on it.

    This is NOT evidence about PUBG. The generated report is stamped
    "SIMULATED" and renders "PIPELINE OK (SIMULATED)" rather than "LIVE PASS";
    a test asserts it can never render the live verdict. Stage 1 acceptance
    still requires scripts\run-stage-01-probe.ps1 with the game running.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\dry-run-stage-01-probe.ps1
#>
[CmdletBinding()]
param(
    [double] $Duration = 25,
    [double] $Still = 8
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Host "No .venv found. Run scripts\bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Stage 1 pipeline DRY RUN - synthetic bridge, PUBG not involved" -ForegroundColor Yellow
Write-Host "Nothing is required of you; this takes about $Duration seconds." -ForegroundColor Yellow
Write-Host ""

& $venvPython -m pubg_training_bot probe sensors `
    --simulate --duration $Duration --still $Still --connect-timeout 20
$exit = $LASTEXITCODE

Write-Host ""
if ($exit -eq 0) {
    Write-Host "Pipeline works on this machine." -ForegroundColor Green
    Write-Host "Stage 1 still needs the LIVE probe to be accepted:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run-stage-01-probe.ps1"
} else {
    Write-Host "Pipeline dry run FAILED - fix this before attempting a live session." -ForegroundColor Red
}
exit $exit
