# Stage status

<!-- GENERATED FILE - edit config/stage-state.yaml or src/pubg_training_bot/stages.py
     and regenerate with: pubg-bot stage status --write-docs -->

Generated: 2026-08-13T15:05:41+00:00
Active stage: **00 - Foundation, scope lock and doctor**

| Stage | Title | Status | Live test | Accepted | Notes |
| --- | --- | --- | --- | --- | --- |
| 00 | Foundation, scope lock and doctor | `ready_for_live_test` | no | - | Implemented and automated-checked; awaiting operator verification of scripts/check-stage-00.ps1 |
| 01 | Live Overwolf sensor feasibility | `not_started` | yes | - |  |
| 02 | Live frame-capture feasibility | `not_started` | yes | - |  |
| 03 | Bounded live input feasibility | `not_started` | yes | - |  |
| 04 | Heading and movement calibration | `not_started` | yes | - |  |
| 05 | Route recorder and inspector | `not_started` | yes | - |  |
| 06 | Offline controller, replay and simulation | `not_started` | no | - |  |
| 07 | Live open-area closed-loop navigation | `not_started` | yes | - |  |
| 08 | Single-floor building entry, rooms and exit | `not_started` | yes | - |  |
| 09 | Staircase and multi-floor route | `not_started` | yes | - |  |
| 10 | One-point configured looting | `not_started` | yes | - |  |
| 11 | Live recovery and perturbation tests | `not_started` | yes | - |  |
| 12 | Stability, one-command operation and MVP acceptance | `not_started` | yes | - |  |

## Acceptance criteria

### Stage 00 - Foundation, scope lock and doctor (`ready_for_live_test`)

Executable foundation with no game access and no possibility of input.

- [ ] project installs and the CLI starts
- [ ] doctor produces JSON and human-readable output
- [ ] fake sensor/capture/heading/actuator tests pass
- [ ] live input is impossible by default (no live actuator registered)
- [ ] documentation reflects the actual repository
- [ ] later stages are not implemented

Evidence:
- `reports/stages/stage-00/stage-report.md`
- `reports/stages/stage-00/doctor.txt`

### Stage 01 - Live Overwolf sensor feasibility (`not_started`)

Prove what data PUBG Training Mode actually exposes through Overwolf.

- [ ] bridge connects over authenticated loopback WebSocket
- [ ] per-feature registration outcome is visible
- [ ] map, phase and view are observed
- [ ] XYZ updates arrive and change when walking
- [ ] stationary noise baseline and update cadence are measured
- [ ] malformed payloads are preserved and reported, not hidden
- [ ] no input is generated

### Stage 02 - Live frame-capture feasibility (`not_started`)

Prove a reliable frame stream and calibratable HUD crops.

- [ ] real PUBG frames captured at the correct resolution
- [ ] compass and interaction regions visible in saved crops
- [ ] capture rate and frame latency measured (P50/P95)
- [ ] black/duplicate/wrong-window frames detected, never silently used
- [ ] GameProfile saved and reloadable
- [ ] no input is generated

### Stage 03 - Bounded live input feasibility (`not_started`)

Prove permitted external input can move and turn the character safely.

- [ ] no input occurs before arming
- [ ] one short forward pulse changes position
- [ ] one bounded mouse pulse changes the camera
- [ ] emergency stop prevents further commands
- [ ] focus loss and sensor loss stop actuation
- [ ] no key remains held after any exit path

### Stage 04 - Heading and movement calibration (`not_started`)

Obtain a trustworthy heading signal and fit coordinate/turn transforms.

- [ ] stationary heading jitter P95 <= ~2.5 deg (or a measured, justified revision)
- [ ] >=10 of 12 distributed target headings reached within ~5 deg
- [ ] movement-derived heading agrees within ~10 deg
- [ ] wraparound near north behaves correctly
- [ ] low-confidence reads abstain instead of fabricating a bearing

### Stage 05 - Route recorder and inspector (`not_started`)

Record and inspect a human demonstration.

- [ ] marker hotkeys work without leaving the game
- [ ] recorded samples align with actual movement
- [ ] semantic markers survive simplification
- [ ] route visualisation is understandable
- [ ] route validation rejects incompatible profiles
- [ ] no autonomous movement occurs

### Stage 06 - Offline controller, replay and simulation (`not_started`)

Implement and test the navigation state machine without live risk.

- [ ] synthetic route completes in the fake world
- [ ] stale sensors abort; blocked movement enters bounded recovery
- [ ] delayed location updates cause no runaway movement
- [ ] obsolete commands cannot execute
- [ ] replay is deterministic
- [ ] no real input is possible during standard checks

### Stage 07 - Live open-area closed-loop navigation (`not_started`)

Autonomously replay the simple open-area route.

- [ ] five consecutive completions from the defined start region
- [ ] no manual correction after arming
- [ ] endpoint reached inside tolerance
- [ ] no indefinite key holds and no heading oscillation
- [ ] emergency stop works; every run produces evidence

### Stage 08 - Single-floor building entry, rooms and exit (`not_started`)

Navigate one simple single-floor building route.

- [ ] >=3 successful closed-door runs and >=3 open-door runs
- [ ] no repeated interaction after crossing
- [ ] failed crossing recognised; bounded retry then safe abort
- [ ] room traversal and exit evidenced

### Stage 09 - Staircase and multi-floor route (`not_started`)

Extend the route through one staircase and another floor.

- [ ] five consecutive complete building runs including the staircase
- [ ] expected Z transition observed before advancing floors
- [ ] no indefinite forward movement on stairs
- [ ] small alignment failure recovered; unrecoverable failure aborts safely

### Stage 10 - One-point configured looting (`not_started`)

Pick one configured item at a recorded loot node and continue.

- [ ] >=8 of 10 runs with the item present pick it and finish
- [ ] 3 runs with the item absent skip it and finish
- [ ] disallowed prompts never trigger pickup
- [ ] scan is time bounded and failed verification is reported

### Stage 11 - Live recovery and perturbation tests (`not_started`)

Make ordinary small deviations survivable.

- [ ] >=8 of 10 predefined perturbed runs complete
- [ ] every recovery attempt visible in logs; no unbounded loop
- [ ] persistent failure aborts and releases all controls
- [ ] failure bundle is diagnosable

### Stage 12 - Stability, one-command operation and MVP acceptance (`not_started`)

Turn the prototype into the first stable MVP.

- [ ] single launcher performs checks, starts disarmed and waits for the hotkey
- [ ] documented repeatable acceptance run
- [ ] stable success rate across consecutive runs
