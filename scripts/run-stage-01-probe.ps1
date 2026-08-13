<#
.SYNOPSIS
    Stage 1 LIVE probe: measures what PUBG Training Mode actually exposes.

.DESCRIPTION
    Read-only. Starts the loopback receiver, tells you how to load the Overwolf
    bridge, records for a bounded period and writes an evidence bundle.

    No input is sent to the game at any point: this build registers no live
    actuator, and `pubg-bot safety scan` proves it.

.PARAMETER Duration
    Seconds to record after the bridge connects. Default 120.

.PARAMETER Still
    Opening seconds you spend motionless, used to measure the position noise
    floor. Default 20.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run-stage-01-probe.ps1
#>
[CmdletBinding()]
param(
    [double] $Duration = 120,
    [double] $Still = 20,
    [int]    $Port = 17311,
    [switch] $SkipBuild
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$distDir = Join-Path $repoRoot 'apps\overwolf-bridge\dist'
$env:Path = "$env:APPDATA\npm;$env:Path"

if (-not (Test-Path $venvPython)) {
    Write-Host "No .venv found. Run scripts\bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " STAGE 1 LIVE SENSOR PROBE" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# --- 1. Environment --------------------------------------------------------- #
Write-Host ""
Write-Host "Environment:" -ForegroundColor White
& $venvPython -m pubg_training_bot doctor 2>&1 |
    Select-String -Pattern 'overwolf|pubg install|summary' | ForEach-Object { "  $_" }

# --- 2. Build the unpacked app ---------------------------------------------- #
if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "Building the bridge..." -ForegroundColor White
    & pnpm --dir (Join-Path $repoRoot 'apps\overwolf-bridge') build 2>&1 | Select-Object -Last 2
}
if (-not (Test-Path (Join-Path $distDir 'manifest.json'))) {
    Write-Host "Bridge is not built. Run: pnpm --dir apps\overwolf-bridge build" -ForegroundColor Red
    exit 1
}

# --- 3. Instructions -------------------------------------------------------- #
Write-Host ""
Write-Host "----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " ONE-TIME SETUP (skip if you have already loaded the bridge)" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " 1. Overwolf -> Settings -> About -> Development options"
Write-Host " 2. 'Load unpacked extension' and select EXACTLY this folder:"
Write-Host ""
Write-Host "      $distDir" -ForegroundColor Green
Write-Host ""
Write-Host "    If you get 'Unauthorized App', your Overwolf account is not"
Write-Host "    whitelisted for development (risk R-016). Request it from"
Write-Host "    developers@overwolf.com - nothing below will work until then."
Write-Host " 3. Open the bridge's debug window from the Overwolf dock and paste"
Write-Host "    the session token printed below, then press 'Save & reconnect'."
Write-Host ""
Write-Host "----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " DURING THE PROBE" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host " 1. Start PUBG and enter TRAINING MODE (FPP, standing)."
Write-Host " 2. Hold still for the first $Still seconds - do not touch the mouse."
Write-Host " 3. Then walk forward, turn, and walk again until the timer ends."
Write-Host ""
Write-Host "The bot sends no input. You are driving the whole time."
Write-Host ""
Read-Host "Press Enter when Overwolf is running and you are ready"

# --- 4. Record --------------------------------------------------------------- #
& $venvPython -m pubg_training_bot probe sensors `
    --duration $Duration --still $Still --port $Port --connect-timeout 300
$probeExit = $LASTEXITCODE

Write-Host ""
if ($probeExit -eq 0) {
    Write-Host "STAGE 01 PROBE: LIVE PASS" -ForegroundColor Green
    Write-Host "Open the report.html listed above and confirm the position trace"
    Write-Host "matches the path you actually walked."
} else {
    Write-Host "STAGE 01 PROBE: FAILED" -ForegroundColor Red
    Write-Host "The evidence bundle is still written - do not delete it."
}
exit $probeExit
