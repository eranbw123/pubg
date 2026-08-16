# CLAUDE.md - persistent operating rules for this repository

This file is loaded into every session. It encodes the rules that must survive
context loss. Read `docs/stage-status.md` before doing anything else.

## 1. What this project is

A Windows-only MVP that replays **one** recorded route through **one** building
in **PUBG Training Mode**, using teach-and-repeat: a human demonstrates the
route once, the bot replays it with a closed feedback loop, and gives up safely
when confidence drops.

It is not a generic navigation system, not an aimbot, and not a cheat. It has no
combat capability of any kind and never will.

## 2. Stage gate - the rule that overrides everything else

Work happens **one stage at a time**. The stage list lives in
`src/pubg_training_bot/stages.py`; the accepted state lives in
`config/stage-state.yaml`.

- Implement stage N only. Never start stage N+1 "while waiting".
- After implementing: run the stage check script, generate the stage report,
  and stop with a single verification command for the operator.
- Advance only when the operator replies `PASS N`.
- On failure: stay in the current stage, read the evidence, find the actual root
  cause, patch, rerun the automated checks, and stop again.

```powershell
python -m pubg_training_bot stage status          # where are we
python -m pubg_training_bot stage set --stage NN --status accepted
```

`stage set --status accepted` refuses to accept a stage while an earlier one is
unaccepted. Do not work around it.

## 3. Status vocabulary

Report status using exactly one of these, and nothing softer:

`AUTOMATED PASS` | `LIVE PASS` | `READY FOR LIVE TEST` | `FAILED` | `UNKNOWN`

Never write "should work", "appears to work", or "is probably fine". A simulated
test is never a live pass for any component that touches PUBG.

## 4. Scope lock - permitted means

Allowed: documented Overwolf game events; visible game pixels; ordinary OS-level
keyboard and mouse input; locally recorded route data; local deterministic
algorithms.

Forbidden, without exception: process-memory reading, packet interception, DLL
or process injection, Unreal Engine internal hooks, kernel drivers, anti-cheat
interference, hidden-player or hidden-item information, opponent detection,
aiming, firing, combat logic, recoil control, public-match automation, landing
or parachuting, generic map-wide looting, arbitrary-building reconstruction,
visual SLAM, 3D reconstruction, neural-network training, cloud services, an LLM
in the runtime controller.

This is enforced by `src/pubg_training_bot/safety.py`, which scans the package
for the symbols those techniques require. `pubg-bot safety scan` must exit 0.

If ordinary documented input is rejected by the game, record the evidence and
**stop at that feasibility gate**. Do not look for an evasion mechanism.

## 5. Safety invariants (do not weaken)

- Dry-run is the default. Live input requires an explicit `--live` flag, an
  explicit arm hotkey, and a registered live actuator.
- The actuator is the single writer of input. Only bounded verbs exist: tap,
  bounded hold, bounded relative mouse move, click, release-all. There is no
  public indefinite key-down.
- Every command expires. Every command is logged with its outcome.
- Controls are released on completion, abort, exception, sensor timeout, focus
  loss and emergency stop.
- No actuation when: location/heading/frame data is stale, map or view mismatch,
  PUBG not foreground, bridge disconnected, or not armed.
- No automated test may send real input. Live probes live in explicit
  `scripts/check-stage-NN.ps1` scripts with all guards enabled.

## 6. Evidence rules

- Measure before claiming. Thresholds are configuration derived from
  measurements, never literals buried in control code.
- Never invent a sensor value. Missing data stays missing so freshness checks
  can see it; low-confidence vision abstains rather than guessing.
- Preserve raw payloads before normalisation. Overwolf nests JSON in strings and
  the original must survive into the run bundle.
- Every live run produces a run bundle (manifest, events, commands, states,
  sensor summary, run summary, screenshots, route + profile snapshot, HTML
  report).
- If a measurement contradicts an assumption, record it in `docs/decisions.md`
  and change the implementation. Do not quietly relax a threshold; propose the
  revision with the measured distribution behind it.

## 7. Repository conventions

- Python 3.11+, `src/` layout, package `pubg_training_bot`. Pydantic v2 models
  for every persisted contract; `schemas/` is generated from them (never
  hand-edited) via `pubg-bot schemas export`.
- Windows PowerShell 5.1 for scripts: no `&&`, no ternary, no null-coalescing.
- Tests: `pytest`, deterministic `FakeClock`, fake sensor/capture/heading/
  actuator providers. Real input is impossible in the test suite.
- `data/local/**` and `reports/**` are git-ignored. Only tiny sanitised
  synthetic fixtures are committed.
- Never delete, reset or overwrite pre-existing repository work. Check
  `git status` before modifying anything.

## 8. Useful commands

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
powershell -ExecutionPolicy Bypass -File scripts\check-stage-00.ps1
python -m pubg_training_bot doctor
python -m pubg_training_bot safety scan
python -m pubg_training_bot schemas export --check
python -m pubg_training_bot stage status
```
