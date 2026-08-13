# pubg

PUBG **Training Mode** teach-and-repeat navigation and looting MVP for Windows.

A human demonstrates one route through one building once; the bot replays it
with a closed feedback loop, recovers from ordinary small deviations, and aborts
safely when its confidence is insufficient.

> **Scope.** This project uses only documented Overwolf game events, visible
> game pixels and ordinary OS-level keyboard/mouse input. It has no combat
> capability, does not read process memory, does not inject code, and does not
> run in public matches. The boundary is enforced in code by
> `src/pubg_training_bot/safety.py`, not merely by documentation.

## Status

Stage 0 of 12 (foundation, scope lock and doctor). Nothing in this build can
send input to the game: no live actuator is registered.

```powershell
python -m pubg_training_bot stage status
```

See [docs/stage-status.md](docs/stage-status.md) for the current gate and
[docs/stages.md](docs/stages.md) for the full plan.

## Quick start

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
powershell -ExecutionPolicy Bypass -File scripts\check-stage-00.ps1
```

The first creates `.venv` and installs the project; the second runs every
Stage 0 gate and writes evidence to `reports\stages\stage-00\`. Neither starts
PUBG, captures the screen, nor produces input.

Then:

```powershell
.\.venv\Scripts\pubg-bot.exe doctor        # environment readiness (read-only)
.\.venv\Scripts\pubg-bot.exe safety scan   # scope lock + live-input interlock
.\.venv\Scripts\pubg-bot.exe stage status  # stage gate
```

## How it works

1. **Teach.** Walk the route once with the recorder running. It captures raw and
   normalised Overwolf events, position and heading traces, selected frames, and
   semantic markers you press hotkeys for (door, stairs, loot, checkpoints).
2. **Simplify.** Transit segments are simplified; semantic nodes are preserved
   exactly.
3. **Repeat.** A waypoint follower drives short bounded movement pulses toward
   the next node, correcting heading against the HUD compass and position
   against the game's own coordinates. Doors, stairs and loot run as explicit
   behaviours at recorded nodes only.
4. **Recover or abort.** A bounded recovery ladder handles small deviations;
   persistent failure releases all controls and writes an evidence bundle.

Position is treated as truth once fresh; heading is treated as an opinion with a
confidence, and the controller abstains rather than guessing. See
[docs/architecture.md](docs/architecture.md).

## Layout

```
src/pubg_training_bot/   Python controller
apps/overwolf-bridge/    Overwolf app (TypeScript)      - Stage 1
config/                  runtime config, game profiles, routes, loot policies
schemas/                 JSON Schema, generated from the pydantic models
scripts/                 bootstrap + per-stage check scripts (PowerShell)
tests/                   pytest suite; no test can touch the game
docs/                    architecture, stages, decisions, risks, protocols
data/local/              recordings, captures, runs        (git-ignored)
reports/                 stage and run evidence            (git-ignored)
```

## Requirements

Windows 11, Python 3.11+ (3.14 verified), PUBG, and - from Stage 1 - Overwolf
with developer mode enabled. Node 20+ and pnpm are needed only for the bridge.

## Safety

Dry-run is the default everywhere. Live input additionally requires an explicit
`--live` flag, an arm hotkey, a foreground guard, fresh-sensor guards and a
registered live actuator, which is introduced only in Stage 3. An emergency-stop
hotkey releases every control and blocks further commands until explicitly
reset.
