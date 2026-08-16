# Live test protocol

Rules for any test that involves the running game.

## Standing rules

1. **Training Mode only.** Never a public match, at any stage, for any reason.
2. Every live test starts **disarmed**. Nothing may move before the arm hotkey.
3. The emergency-stop hotkey (`F10` by default) is tested at the start of every
   live session that can produce input, before anything else.
4. Keep a hand on the keyboard. Alt-Tab away from PUBG stops actuation via the
   foreground guard; the emergency stop is the deliberate abort.
5. If anything looks wrong, press the emergency stop first and diagnose from the
   evidence bundle afterwards. Never "let it finish to see what happens".
6. A live test result is `LIVE PASS` or `FAILED`. There is no partial pass, and
   a simulation never counts as a live pass.
7. One variable at a time. Changing the route and the tolerance in the same run
   makes the result uninterpretable.

## Before any live session

```powershell
python -m pubg_training_bot doctor
```

Confirm: PUBG detected, Overwolf detected (Stage 1+), display matches the active
`GameProfile`, live actuation state is what you expect for this stage.

Then confirm in game: Training Mode, FPP, standing, free-look not held, the
resolution/FOV/sensitivity/language recorded in the profile, and the key
bindings recorded in the profile.

## Before the first live session of a stage

Where a stage offers a pipeline dry run, use it. It costs nothing and stops you
discovering a code bug while standing in Training Mode:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dry-run-stage-01-probe.ps1
```

A dry run exercises the code path with synthetic data. It is never evidence
about the game, and its report says so - `PIPELINE OK (SIMULATED)`, never
`LIVE PASS`.

## Session structure

1. Run the stage's check script; confirm `AUTOMATED PASS`.
2. Start the controller **disarmed**.
3. Enter Training Mode, position the character as the stage requires.
4. Arm with the hotkey.
5. Observe. Do not touch the keyboard unless aborting.
6. Let the run finish or abort it.
7. Read the generated report before running again.

## Per-stage operator actions

| Stage | What the operator does | What the evidence must show |
| --- | --- | --- |
| 00 | Run one command. No game needed. | doctor output matches this machine |
| 01 | Enter Training Mode; stand still ~30 s; walk forward; turn; walk again | XYZ present, cadence measured, stationary noise measured, map/phase/view observed |
| 02 | Stand in Training Mode with the HUD visible; alt-tab once when asked | real frames at the correct resolution, compass and prompt regions visible, frame age measured |
| 03 | Stand in open ground; arm; watch one short pulse; press emergency stop | position changed, camera moved, nothing left held, e-stop blocked further commands |
| 04 | Stand in open ground; let the calibration sequence run | heading jitter, turn accuracy, transform fit RMSE |
| 05 | Walk a simple L-shaped route pressing marker hotkeys | recorded trace matches the walk, markers preserved |
| 07 | Position in the start region; arm | five consecutive completions, no manual correction |
| 08 | Same, with the door closed; then repeat with it open | 3+ runs each, crossing verified, no repeated interaction |
| 09 | Same, including the staircase | Z transition observed before floor advance |
| 10 | Same, item present; then item removed | pickup verified; absence skipped without stalling |
| 11 | Apply the listed perturbation before arming | recovery attempts visible and bounded |
| 12 | Run the single launcher | full route, disarmed start, clean bundle |

## Recording a failure

Do not summarise from memory. Keep:

- the run bundle directory (`data/local/runs/<run-id>/`),
- what you physically observed, in one sentence,
- what you expected instead.

The controller's own belief is already in `states.jsonl` and `commands.jsonl`;
your sentence supplies the ground truth those cannot contain.

## Stage 0 verification (no game required)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check-stage-00.ps1
```

Expected: `STAGE 00: AUTOMATED PASS`, with evidence in
`reports\stages\stage-00\`. PUBG must not launch, no window may be focused, and
no input may be produced.
