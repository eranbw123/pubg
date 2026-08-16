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

**pnpm** was installed at the same time (see D-014).

One prerequisite remains, and it turned out to be larger than expected: Overwolf
requires **developer access**, which is a channel switch *plus* account
approval, not a settings toggle. Tracked as R-016 and now the second-highest
risk in the register.

Superseded in part by D-015: detection is now registry-based, not path-based.

---

## D-026 - R-002 materialised: Overwolf does not provide live position for PUBG
**Stage 01 | active - STAGE 1 FAILED**

The project's top feasibility risk has been realised. Overwolf's Game Events
Provider never delivered the `location` feature, in any game state, across the
whole live session on 2026-08-16.

### Evidence

Roughly ten probe runs, several hundred `getInfo` snapshots, GEP 311.2.2,
Overwolf 0.309.0.11, across every reachable state - lobby, airfield, aircraft,
landed, loading_screen, and Training Mode:

| Signal | Observed |
| --- | --- |
| `location` | **0 occurrences of any kind** |
| `onInfoUpdates2` push events | **0, in any run** |
| `match_info.map` | works: `Range_Main` (Training Mode), `Baltic_Main` (Erangel) |
| `game_info.phase` | updates in public matches; stuck at `loading_screen` in Training Mode |
| `me.view` | works (`TPP`) |
| `me.movement`, `me.bodyPosition` | `null` in Training Mode |
| `me.health` | stuck at `{"health":0}` throughout |

Registration succeeded every time - often on attempt 1 - and Overwolf itself
returned `supportedFeatures: ["location","me","phase","map","match_info"]`. The
feature is advertised as supported and never populated.

The operator moved in both Training Mode and a live match. Position never
appeared.

### Honest caveat

We never received a single `onInfoUpdates2` event, and I cannot fully explain
why. Overwolf's own trace confirms the listeners were registered
(`Game event listener added 'onInfoUpdates2' [PUBG Bridge,background]`). If
`location` were delivered exclusively by push and never included in `getInfo`,
a broken push channel alone would produce these symptoms.

That caveat does not change the outcome: with zero push events and zero
`location` values in hundreds of polled snapshots, there is no path from this
provider to a live position stream. It does mean the conclusion is "this
provider does not deliver position to us" rather than a proven statement about
PUBG's provider in general.

### Consequence

Stage 1 is **FAILED**. Position is the primary sensor for teach-and-repeat; the
route layer, the waypoint follower, arrival verification and stuck detection all
consume it. Without it the design does not degrade - it does not function.

Per the operating contract this is a feasibility gate, and the project stops
here rather than routing around it. No fallback is started speculatively.

---

## D-024 - Memory reading is refused, permanently, and not for rules reasons
**Stage 01 | active**

Raised as a fallback if Overwolf access is denied: read only the player's own
X/Y/Z from PUBG's process memory, on the argument that coordinates are neither
deep nor secret.

Refused. The objection is not the sensitivity of the data - it is the technique:

- PUBG runs **BattlEye**, a kernel-mode anti-cheat. It tracks handles opened
  against the game process and bans on the *act*, not the volume: reading once
  is treated the same as reading five thousand times.
- BattlEye issues **hardware-ID bans**, so the cost is not a throwaway account.
- It is item one on this project's own forbidden list (`CLAUDE.md` section 4),
  written before any of this was inconvenient.

"Only the coordinates" is not a mitigating detail. `ReadProcessMemory` against a
protected game is the same call an ESP cheat makes, and the anti-cheat cannot
and does not distinguish intent.

`safety.py` already fails the build on these symbols. That check stays.

---

## D-025 - Overwolf's policy names this exact app as ineligible
**Stage 01 | active**

Overwolf defines a private app as one "aimed for personal/small scale/private
use, not planned to be published on the Overwolf Appstore, **and/or built for
the sole purpose of being a faceless bridge to another service**", and states it
does not approve them.

The second clause describes our bridge precisely - it is a faceless bridge
feeding a local controller. So the app is disqualified twice over, and no
amount of rewording the request changes that. Sending the short enquiry is still
worth one email, but the expected answer is no.

---

## D-023 - A synthetic bridge, so live sessions are not spent debugging our code
**Stage 01 | active**

A live Training Mode session is expensive: it needs the game running, the
operator standing still on cue, and Overwolf developer access. Discovering a bug
in the receiver or the report generator *during* one wastes it.

`protocol/simulator.py` speaks the real wire protocol over a real loopback
socket and emits Overwolf's documented payload shapes - including the nested
JSON `location` string, ~1 Hz jittered updates, stationary noise and occasional
dropped updates. `pubg-bot probe sensors --simulate` drives the entire pipeline
with it.

The obvious danger is a simulated pass being mistaken for a live one, which the
operating contract forbids outright. Four independent guards:

1. the report carries `simulated: true`;
2. the bundle directory is named `simulated-<stamp>` rather than `probe-<stamp>`;
3. the HTML renders `PIPELINE OK (SIMULATED)` and a warning banner, never
   `LIVE PASS`, and the CLI prints the same;
4. a test asserts the verdict element can never contain the live wording.

What it proves: the plumbing works. What it does not prove: anything at all
about PUBG. Stage 1 acceptance still requires the live probe.

---

## D-016 - PUBG class ID is 10906, verified two independent ways
**Stage 01 | active**

The manifest needs the **class** id, not the instance id, and the two differ by
a factor of ten. Confirmed from both directions rather than trusted once:

- The host's own `%LOCALAPPDATA%\Overwolf\GamesList.*.xml` lists
  `PLAYERUNKNOWN'S BATTLEGROUNDS` at instance id **109061**. Overwolf's rule is
  `classId = floor(instanceId / 10)` -> **10906**.
- Overwolf's official PUBG sample manifest uses `"game_ids": [10906]`.

`isPubg()` in the bridge accepts either shape, because `getRunningGameInfo` and
`onGameInfoUpdated` return different objects: it prefers `classId` and falls
back to `floor(id / 10)`. `check-stage-01.ps1` asserts the built manifest
targets 10906, so a regression here fails the stage rather than producing an app
that silently never sees the game.

Also present: `PLAYERUNKNOWN'S BATTLEGROUNDS (Test Server)` at 212401 (class
21240). Not targeted - Training Mode runs in the main client.

---

## D-017 - Register five features; decline the rest explicitly
**Stage 01 | active**

Overwolf documents 15 PUBG features. We register five: `location`, `me`,
`phase`, `map`, `match_info`.

The other ten are listed in `DECLINED_FEATURES` with a reason each, and a test
asserts the combat and roster ones (`kill`, `death`, `killer`, `revived`,
`roster`, `team`) are never requested. Out-of-scope data is not merely unused -
it never enters the process. That is a stronger property than filtering later,
and it is checkable.

---

## D-018 - MatchPhase uses PUBG's own vocabulary
**Stage 01 | active - supersedes the Stage 0 placeholder**

The Stage 0 enum guessed at `loading/lobby/playing/finished`. PUBG actually
reports `lobby`, `loading_screen`, `airfield`, `aircraft`, `freefly`, `landed`.

The enum now carries the real values. A generic mapping would have hidden
exactly what Stage 1 exists to discover: which phase Training Mode reports.
`ExpectedContext` now defaults to `phases=(LANDED,)` - the only phase in which
the character is on the ground and controllable.

An undocumented value (plausible in Training Mode) becomes `UNKNOWN` **plus a
warning**, never a coerced documented value.

---

## D-019 - No documented weapon or inventory feature; Stage 10's plan needs revisiting
**Stage 01 | active - contradicts a Stage 0 assumption**

The project brief proposed verifying loot pickup via "live weapon state", and
`SensorSnapshot` carries a `WeaponState` field for it.

Overwolf's documented PUBG feature list contains **no weapon, inventory or
equipped-item feature**. The 15 features are `gep_internal`, `kill`, `revived`,
`death`, `killer`, `match`, `match_info`, `rank`, `counters`, `location`, `me`,
`team`, `phase`, `map`, `roster`. The closest, `me`, exposes `aiming` state but
not what is held.

Consequences, recorded now rather than discovered at Stage 10:

- `WeaponState` stays in the model but is never populated from the bridge. It is
  not removed, because Stage 1's live probe may reveal undocumented keys.
- Risk R-011 (loot verification) is raised: the preferred verification channel
  appears not to exist, so Stage 10 will likely need converging visual evidence
  (prompt disappearance plus a UI change) instead.

This is exactly the "record every observed contradiction" case: the assumption
was reasonable and appears to be wrong, so it is written down before it costs a
stage.

---

## D-020 - The bridge normalises, but the controller re-derives
**Stage 01 | active**

Both sides parse the payloads. The bridge's `normalized` field is advisory and
travels alongside the raw payload; the controller ignores it and re-derives
everything from `raw` itself.

Two reasons: a bug in the TypeScript normaliser cannot silently become the
controller's belief, and a recorded run can be re-parsed months later against a
corrected Python normaliser without re-running the game.

---

## D-021 - Sequence policy is deliberately asymmetric
**Stage 01 | active**

- **Duplicate** -> dropped and counted. A reconnecting bridge legitimately
  replays its tail.
- **Gap** -> accepted and counted. The frames that did arrive are still valid;
  refusing them would discard good samples to punish a loss we cannot undo.
- **Regression** -> rejected. Sequence going backwards without a new session
  means two bridges are feeding one controller, and interleaving their streams
  would corrupt the trace in a way no later analysis could detect.

---

## D-022 - Toolchain specifics found the hard way
**Stage 01 | active**

- The Overwolf types package is `@overwolf/types`, not `@types/overwolf`
  (which does not exist on npm).
- pnpm 11 requires build scripts to be approved. `esbuild` (a vitest
  dependency) needs its postinstall, declared in `pnpm-workspace.yaml` under
  `allowBuilds`. The shipped Overwolf app itself has **no runtime
  dependencies** - it is plain compiled JavaScript.
- `overwolf.windows.getMainWindow()` is synchronous and returns the window; it
  does not take a callback.

---

## D-015 - Overwolf detection reads the registry; the channel IS checkable
**Stage 00 | active - corrects D-013**

D-013 asserted that developer mode "cannot be observed" by the doctor. That was
wrong, and inspecting the machine proved it: the release channel is published at
`HKLM\SOFTWARE\WOW6432Node\Overwolf\Channel`, alongside `CurrentVersion` and
`InstallFolder`.

Two consequences:

- **Path scanning was also misleading.** `%LOCALAPPDATA%\Overwolf` is user data;
  the client installs to `C:\Program Files (x86)\Overwolf\`. The old check
  reported the user-data folder as "the install" and knew no version. The doctor
  now reads the registry first and falls back to the path scan.
- **A new `overwolf channel` check.** `Development options` is absent outside the
  Developers channel, which is precisely the symptom that prompted this - the
  operator could not find the setting because the production client does not
  have it.

The developer **whitelist** remains genuinely unobservable: it is account state
held by Overwolf, not a machine fact. It is therefore absent from `OverwolfInfo`
entirely, and `test_overwolf_probe_reports_channel_without_claiming_whitelist`
asserts that no doctor check mentions it. The distinction is the point: report
what is measurable, stay silent about what is not, and never let a green line
imply knowledge the tool does not have.

Observed on this host: Overwolf 0.309.0.11, channel `Developers`, install folder
`C:\Program Files (x86)\Overwolf\`.

---

## D-014 - pnpm installed via npm, not corepack
**Stage 00 | active**

`corepack enable pnpm` fails on this host with
`EPERM: operation not permitted, open 'C:\Program Files\nodejs\pnpx'` - corepack
writes its shims into the Node installation directory, which requires an
elevated shell.

`npm install -g pnpm` installs to the user-writable global prefix
(`%APPDATA%\npm`) and needs no elevation, so that is what was used. pnpm 11.21.0
is installed and detected by the doctor.

The doctor's remedy text still suggests `corepack enable pnpm`, which is the
upstream-recommended route and works fine in an elevated shell; the npm route is
recorded here as the fallback that avoids elevation.

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
