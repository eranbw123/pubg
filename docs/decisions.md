# Decision log

Every entry records what was decided, why, and what would overturn it.
Measurements that contradict an assumption are recorded here **and** reflected
in the implementation - never quietly absorbed.

Status values: `active`, `superseded`, `pending measurement`.

---

## D-001 - Build at the repository root, preserving existing files
**Stage 00 | active**

The repository contained only `README.md` (6 bytes) and an untracked, empty
`test.py`. A nested `pubg-training-bot/` directory would add a path level for no
benefit, so the project occupies the repo root and the brief's target layout
maps directly onto it.

Both pre-existing files are preserved: `README.md` is extended rather than
replaced, and `test.py` is untouched and still untracked.

---

## D-002 - pip + venv, not uv (uv is not installed)
**Stage 00 | active**

`uv` is not on this host's PATH. `scripts/bootstrap.ps1` uses `uv` when present
and falls back to the stdlib `venv` module plus pip otherwise, so the choice is
environmental rather than baked in. The resolved dependency set is captured to
`reports/stages/stage-00/pip-freeze.txt` for reproducibility.

Overturned by: installing uv, which the script then picks up automatically.

---

## D-003 - Python 3.14.6 is the only interpreter; all needed wheels exist
**Stage 00 | active**

The host has exactly one interpreter (3.14.6, pip 26.1.2). Because 3.14 is
recent, wheel availability was verified before committing to it - a dependency
without a cp314 wheel would have forced a second interpreter install. Checked
with `pip install --dry-run --only-binary=:all:`:

`pydantic`, `PyYAML`, `pytest`, `numpy`, `opencv-python-headless`, `mss`,
`Pillow`, `websockets`, `jsonschema`, `rapidocr-onnxruntime`, `pywin32` - all
resolve to binary wheels.

`requires-python` is `>=3.11` so the project is not gratuitously pinned to 3.14.

---

## D-004 - Heavy dependencies are optional extras, added by the stage that needs them
**Stage 00 | active**

Stage 0 installs only `pydantic`, `PyYAML` and `jsonschema` (plus `pytest` and
`ruff` for dev). Capture, vision and bridge dependencies are extras
(`.[capture]`, `.[vision]`, `.[bridge]`). A doctor that cannot run because
OpenCV failed to build would be useless precisely when it is needed.

---

## D-005 - argparse, not a CLI framework
**Stage 00 | active**

The CLI is an operator tool. Every dependency it carries is one that must be
installed before `doctor` can report what is missing, so the CLI uses only the
standard library.

---

## D-006 - No live actuator is registered at Stage 0
**Stage 00 | active**

"Dry-run by default" implemented purely as a flag can be defeated by a bug. The
actuator registry contains no live implementation at all, so `--live` cannot
silently become a no-op that looks like a successful run.
`require_live_actuator()` raises a message naming Stage 3.

Additionally `safety.py` scans the package for input-injection symbols
(`SendInput`, `keybd_event`, `mouse_event`, `SetCursorPos`, pyautogui,
pydirectinput, pynput). Stage 0 has zero findings, and the allowlist already
names the future `actuation/live_sendinput.py` so Stage 3 needs no rule change.

Read-only `user32` calls (`GetSystemMetrics`) are explicitly not flagged: the
banned thing is input injection, not the library.

---

## D-007 - FPP, standing, Training Mode, English HUD, 1920x1080 @ 100%
**Stage 00 | active**

FPP removes third-person camera offset and character occlusion from the heading
and prompt-recognition problems. Host display measured at Stage 0: single
monitor, 1920x1080, system DPI 96 (scale 1.0). Captured in
`config/game_profiles/dev-1080p-fpp.yaml`, which is explicitly **uncalibrated** -
`map_id`, crops, FOV and sensitivity are `null` because guessing them would
produce a profile that looks valid and is wrong.

---

## D-008 - Coordinate transform is a general 2x2 matrix, not a named axis convention
**Stage 00 | pending measurement (Stage 04)**

Whether game X is east or north, the handedness, the sign of Z when ascending,
and the unit scale are all unknown. Encoding a guess as "X is east" would make a
wrong assumption invisible. `CoordinateTransform` is therefore a general matrix
with `fitted: false` until Stage 4 fits it from real walk data, and
`GameProfile.missing_for_navigation()` refuses to call the profile ready.

---

## D-009 - Freshness thresholds are provisional and flagged as such
**Stage 00 | pending measurement (Stage 01/02)**

Current values: location 2.5 s, heading 0.6 s, frame 0.5 s, minimum heading
confidence 0.6. Reasoning: if ground position updates arrive at ~1 Hz, 2.5 s
tolerates two missed updates before the controller must stop. Heading at 0.6 s
assumes >=5 useful observations per second.

Both numbers are assumptions. `FreshnessPolicy.provisional` is `True` and the
config file says so in a comment, so no report can present them as measured.
Stage 1 replaces the location budget with a measured interval distribution;
Stage 2 replaces the frame budget.

---

## D-010 - Schemas are generated from the models, never hand-written
**Stage 00 | active**

The TypeScript bridge will validate against `schemas/*.schema.json`. A schema
that has drifted from the Python model is worse than no schema, so the files are
generated by `pubg-bot schemas export` and the stage check runs
`--check` to fail on drift.

---

## D-011 - The stage gate is enforced by code, not by discipline
**Stage 00 | active**

`stages.py` holds the specification; `config/stage-state.yaml` holds acceptance
state; `gate_check()` refuses to accept stage N while an earlier stage is
unaccepted; `docs/stage-status.md` is generated from both so the document cannot
claim a pass the state file does not record. A test asserts that later-stage
packages (`navigation`, `recovery`, `recording`, ...) do not exist yet.

---

## D-012 - Overwolf install status
**Stage 00 | superseded by D-013**

Initially observed absent from all three standard locations
(`%LOCALAPPDATA%\Overwolf`, `%ProgramFiles(x86)%\Overwolf`,
`%ProgramFiles%\Overwolf`), which blocked Stage 1. PUBG was already installed at
`C:\Program Files (x86)\Steam\steamapps\common\PUBG`.

Resolved during Stage 0 - see D-013.

---

## D-013 - Overwolf installed; Stage 1 prerequisite satisfied
**Stage 00 | active**

Overwolf is now installed at `%LOCALAPPDATA%\Overwolf` and `Overwolf.exe` is
running. `doctor` detects both the install path and the process, so risk R-001
is retired.

Two prerequisites remain before Stage 1 can start, and both are environmental
rather than code:

- **Developer mode** must be enabled in Overwolf (Settings -> About -> Development
  Options) so an unpacked app can be loaded. `doctor` cannot observe this - it is
  an application setting, not a filesystem or process fact - so Stage 1's own
  check script will report the load result rather than guessing.
- **pnpm** is still missing (`corepack enable pnpm`), needed for the bridge
  workspace.

Detection deliberately remains path- and process-based rather than reading
Overwolf's own configuration: the doctor is read-only and must not depend on
another application's private file layout.

---

## Pending measurements (assumptions under test)

| Assumption | Replaced by | Stage |
| --- | --- | --- |
| Overwolf exposes local XYZ in Training Mode | live probe | 01 |
| Ground position updates ~1/s | interval histogram | 01 |
| Training Mode map identifier | observed value (never guessed) | 01 |
| Documented events do not expose camera yaw | feature registration result | 01 |
| A capture provider can sustain 5-10 useful FPS | provider benchmark | 02 |
| HUD compass is machine-readable with confidence | recognition benchmark | 04 |
| Axis orientation, inversion, scale, Z sign | transform fit | 04 |
| Mouse-turn sign and degrees-per-unit | turn calibration | 04 |
| `SendInput` with scan codes is accepted by PUBG | bounded live probe | 03 |
