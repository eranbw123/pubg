# Troubleshooting

Grouped by the symptom you actually see. Stage 0 entries are the ones that can
occur today; later sections are filled in by the stage that can produce them.

## Setup

**`scripts\bootstrap.ps1` fails with "No Python interpreter found"**
Python is not on PATH. Install Python 3.11+ and reopen the shell. Verify with
`py --version`.

**`bootstrap.ps1` cannot create `.venv`**
Usually a stale or partially created directory. Re-run with `-Recreate`:
`powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 -Recreate`

**"running scripts is disabled on this system"**
Use the documented invocation, which does not change machine policy:
`powershell -ExecutionPolicy Bypass -File scripts\...`

**`pubg-bot` is not recognised**
The console script only exists inside the venv. Use either
`.\.venv\Scripts\pubg-bot.exe ...` or `.\.venv\Scripts\python.exe -m pubg_training_bot ...`

**Dependency install fails on a wheel build**
Every planned dependency has a binary wheel for this interpreter (D-003). A
build attempt means pip fell back to a source distribution - check the pinned
version and network access rather than installing a compiler.

## Doctor output

**`overwolf install: not found`**
Install Overwolf and enable developer mode before Stage 1. Not a Stage 0
failure, since Stage 0 does not touch the game. If Overwolf is installed
somewhere unusual, add the path to `OVERWOLF_PATH_CANDIDATES` in
`src/pubg_training_bot/diagnostics/probes.py`.

**"Development options" is missing from Settings -> About**
You are on the production Overwolf channel, where it does not appear. Switch
channel: Settings -> About -> `Ctrl + Shift + left click` the Overwolf logo ->
type `Developers` in the channel field -> update and relaunch.

**"Unauthorized App" when loading the unpacked bridge (Stage 1)**
The Overwolf account is not whitelisted for development. Request it from
`developers@overwolf.com`. This is an approval with a human turnaround time, not
a setting, which is why R-016 ranks second in the risk register - it gates
Stage 1 and everything after it.

**`corepack enable pnpm` fails with `EPERM ... C:\Program Files\nodejs\pnpx`**
corepack writes shims into the Node install directory and needs an elevated
shell. Either run it as administrator, or use the no-elevation route:
`npm install -g pnpm` (installs to `%APPDATA%\npm`). See D-014.

**`pubg install: not found`**
The Steam library is somewhere unusual. Add the path to `PUBG_PATH_CANDIDATES`
in `src/pubg_training_bot/diagnostics/probes.py`.

**`virtualenv: False`**
You are running the system interpreter. Harmless for `doctor`, but the stage
check scripts require `.venv` so the dependency set is reproducible.

**`display` shows the wrong resolution or scale**
The probe reports values as seen by a DPI-unaware process and does not change
process DPI awareness (that is a global, irreversible side effect). Stage 2
handles DPI correctly when it owns the capture window.

**`scope lock: VIOLATION`**
The package now contains a symbol from a forbidden technique or an input API
outside the allowlist. `pubg-bot safety scan` prints file and line. This is
never something to work around - remove the code.

## Stage gate

**"refusing to accept stage NN"**
An earlier stage is not accepted. Check `python -m pubg_training_bot stage
status`. The gate is deliberate; do not edit `config/stage-state.yaml` by hand
to get past it.

**`docs/stage-status.md` looks out of date**
It is generated. Regenerate with
`python -m pubg_training_bot stage status --write-docs`.

**"json schemas are stale"**
A pydantic contract changed without regenerating. Run
`python -m pubg_training_bot schemas export` and commit the result.

**Test failure: "later-stage packages must not exist yet"**
A future stage's package was created early. Remove it; the stage gate exists
because out-of-order work cannot be verified against the game.

## Tests

**Tests pass individually but fail together**
Look for state written into the real repository. Tests that write must use the
`tmp_paths` fixture, not `default_paths()`.

**A test appears to want the game running**
It should not exist. No automated test may send real input or require PUBG.
Live probes belong in `scripts/check-stage-NN.ps1` with all guards enabled.

## Sensors, capture, input, navigation

Filled in by Stages 1, 2, 3 and 6-12 respectively, from failures actually
observed rather than anticipated.
