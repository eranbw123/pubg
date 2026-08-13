# Stage plan

Thirteen stages, each with its own check script, evidence bundle and single
operator verification command. The canonical definition lives in
`src/pubg_training_bot/stages.py`; live acceptance state lives in
`config/stage-state.yaml`. `docs/stage-status.md` is generated from both.

Rules: implement one stage at a time; never start the next while waiting; a
simulated test is never a live pass for anything that touches PUBG.

| Stage | Title | Live game? | Feasibility gate |
| --- | --- | --- | --- |
| 00 | Foundation, scope lock and doctor | no | - |
| 01 | Live Overwolf sensor feasibility | yes | **hard gate**: no XYZ in Training Mode = project stops |
| 02 | Live frame-capture feasibility | yes | **hard gate**: no usable frames = no heading |
| 03 | Bounded live input feasibility | yes | **hard gate**: input rejected = project stops |
| 04 | Heading and movement calibration | yes | **hard gate**: unreliable heading = no closed loop |
| 05 | Route recorder and inspector | yes | - |
| 06 | Offline controller, replay and simulation | no | - |
| 07 | Live open-area closed-loop navigation | yes | first autonomous movement |
| 08 | Single-floor building entry, rooms and exit | yes | - |
| 09 | Staircase and multi-floor route | yes | - |
| 10 | One-point configured looting | yes | - |
| 11 | Live recovery and perturbation tests | yes | - |
| 12 | Stability, one-command operation, MVP acceptance | yes | - |

## Stage detail

### 00 - Foundation, scope lock and doctor
Executable skeleton with typed contracts, provider interfaces, fakes, the CLI,
the read-only `doctor`, the scope-lock scanner and the stage gate. Nothing
touches the game and no live actuator exists.

### 01 - Live Overwolf sensor feasibility
A minimal Overwolf app registering only the needed documented features, feeding
a token-authenticated loopback WebSocket. Measures update cadence, stationary
noise, observed map/phase/view identifiers, and preserves raw payloads.
**If local XYZ does not appear in Training Mode, the stage is FAILED and the
evidence is preserved. It is not faked.**

### 02 - Live frame-capture feasibility
Benchmarks candidate capture providers against the running game on
successful-frame rate, effective FPS, P50/P95 frame age, black and duplicate
ratios, resolution correctness, focus/unfocus behaviour and overlay bleed.
Produces a contact sheet and calibrates the compass and interaction crops into
a `GameProfile`. No heading OCR yet.

### 03 - Bounded live input feasibility
Introduces the only live actuator in the project, behind `--live`, an arm
hotkey, an emergency-stop hotkey, a foreground guard and a sensor-freshness
guard. Probe: one short forward pulse, one bounded mouse pulse, verify
displacement, verify emergency stop, verify nothing is left held.

### 04 - Heading and movement calibration
The project's largest technical risk. Compass recognition with confidence and
abstention; circular filtering; empirical fitting of heading -> XY displacement
(axis assignment, inversion, scale); mouse-turn sign and gain; closed-loop
`turn_to_heading`. Targets: stationary jitter P95 <= ~2.5 deg, >=10/12 target
headings within ~5 deg, movement-derived agreement within ~10 deg. A target that
proves unrealistic is re-derived from the measured distribution in
`docs/decisions.md`, never silently relaxed.

### 05 - Route recorder and inspector
Global marker hotkeys (start, checkpoint, door, loot, stair start/end, room
transition, end, cancel) usable without leaving the game. Records raw and
normalised events, sensor snapshots, crops, position and heading traces.
Simplifies transit segments while preserving every semantic node. First test is
a trivial open-area route, not the building.

### 06 - Offline controller, replay and simulation
The navigation state machine, target-bearing maths through the fitted
transform, adaptive look-ahead, arrival verification, command expiration, and a
deterministic 2.5D fake world with movement, turning, location delay, heading
noise, blocked movement, doors and Z transitions. Fault injection throughout.

### 07 - Live open-area closed-loop navigation
Five consecutive autonomous completions of the recorded open-area route with no
manual correction after arming.

### 08 - Single-floor building entry, rooms and exit
Door behaviour at recorded door nodes only: arrive, align, check the interaction
region, interact, cross, verify crossing, bounded retries with small yaw
offsets, safe abort. Tested with the door both closed and open.

### 09 - Staircase and multi-floor route
Stair-start/transit/stair-end nodes with expected Z direction and magnitude,
low-speed pulses, narrow heading tolerance, and floor transition confirmed by
evidence before advancing.

### 10 - One-point configured looting
A versioned loot policy with an explicit allowlist. Bounded scan at one recorded
loot node; a weapon first, because weapon state gives independent verification.
Item absent must skip and continue, never stall.

### 11 - Live recovery and perturbation tests
The full bounded ladder L0-L7 under injected faults: start heading and position
offsets, wall contact, dropped location update, heading read failure, first-
attempt door failure, node timeout.

### 12 - Stability, one-command operation and MVP acceptance
One PowerShell launcher that checks the environment, starts the controller,
confirms the bridge, loads the profile and route, and waits disarmed for the
hotkey. Documented, repeatable acceptance run.
