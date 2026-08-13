<#
.SYNOPSIS
    Creates the local Python environment for pubg-training-bot.

.DESCRIPTION
    Idempotent. Creates .venv (using uv when available, otherwise the stdlib
    venv module), installs the project in editable mode with dev extras, and
    creates the git-ignored local data directories.

    Touches nothing outside the repository and never contacts the game.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
#>
[CmdletBinding()]
param(
    [switch] $Recreate
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'

Write-Host "pubg-training-bot bootstrap" -ForegroundColor Cyan
Write-Host "repository: $repoRoot"

# --- 1. Locate a suitable interpreter ------------------------------------- #
$hostPython = $null
foreach ($candidate in @('py', 'python')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $hostPython = $candidate; break }
}
if (-not $hostPython) {
    Write-Error "No Python interpreter found on PATH. Install Python 3.11 or newer."
}

$versionText = & $hostPython -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Host "host python: $hostPython ($versionText)"
$parts = $versionText.Split('.')
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) {
    Write-Error "Python 3.11+ required, found $versionText."
}

# --- 2. Create the virtual environment ------------------------------------ #
if ($Recreate -and (Test-Path $venvPath)) {
    Write-Host "removing existing .venv (--Recreate)" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvPath
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not (Test-Path $venvPython)) {
    if ($uv) {
        Write-Host "creating .venv with uv" -ForegroundColor Green
        & uv venv $venvPath
    } else {
        Write-Host "creating .venv with the stdlib venv module (uv not installed)" -ForegroundColor Green
        & $hostPython -m venv $venvPath
    }
    if ($LASTEXITCODE -ne 0) { Write-Error "virtual environment creation failed" }
} else {
    Write-Host ".venv already exists"
}

if (-not (Test-Path $venvPython)) { Write-Error "expected interpreter not found: $venvPython" }

# --- 3. Install the project ----------------------------------------------- #
Write-Host "installing project (editable, with dev extras)" -ForegroundColor Green
if ($uv) {
    $env:VIRTUAL_ENV = $venvPath
    & uv pip install --python $venvPython -e "$repoRoot[dev]"
} else {
    & $venvPython -m pip install --upgrade pip --quiet
    & $venvPython -m pip install -e "$repoRoot[dev]"
}
if ($LASTEXITCODE -ne 0) { Write-Error "dependency installation failed" }

# --- 4. Local (git-ignored) data directories ------------------------------ #
& $venvPython -c "from pubg_training_bot.config.paths import default_paths; [print('created', p) for p in default_paths().ensure_runtime_dirs()]"
if ($LASTEXITCODE -ne 0) { Write-Error "runtime directory creation failed" }

# --- 5. Record the resolved dependency set -------------------------------- #
$freezeDir = Join-Path $repoRoot 'reports\stages\stage-00'
New-Item -ItemType Directory -Force -Path $freezeDir | Out-Null
& $venvPython -m pip freeze | Out-File -FilePath (Join-Path $freezeDir 'pip-freeze.txt') -Encoding utf8

Write-Host ""
Write-Host "bootstrap complete." -ForegroundColor Cyan
Write-Host "next:"
Write-Host "  .\.venv\Scripts\pubg-bot.exe doctor"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\check-stage-00.ps1"
exit 0
