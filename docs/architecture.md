# Architecture

## 1. Problem shape

Replay one demonstrated route through one Training Mode building, using only
documented Overwolf events, visible pixels and ordinary OS input. The hard part
is not path planning - the path is recorded. The hard part is that the two
primary sensors disagree in kind:

| Signal | Source | Rate | Failure mode |
| --- | --- | --- | --- |
| Position (XYZ) | Overwolf game event | ~1 Hz (assumption, measured in Stage 1) | drops out silently |
| Heading | HUD compass pixels | 5-10 Hz target (measured in Stage 2/4) | misreads, or is unreadable |
| Interaction prompt | HUD pixels | on demand | absent when it should be present |

Everything else follows from that: control decisions run at the rate of the
*slowest evidence they depend on*, movement happens in short bounded pulses,
and arrival is confirmed by measurement rather than by prediction.

## 2. Two processes

```
  PUBG (untouched)
        |  documented game events
        v
  Overwolf bridge (TypeScript, apps/overwolf-bridge)   <-- Stage 1
        |  loopback WebSocket, token-authenticated, raw payloads preserved
        v
  Python controller (src/pubg_training_bot)
        |  bounded SendInput commands                   <-- Stage 3
        v
  PUBG (as an ordinary keyboard and mouse would)
```

The bridge never produces input. The controller never reads game memory. The
only channel back into the game is the operating system's normal input path.

## 3. Layers

```
cli/            operator surface (argparse; no game access at Stage 0)
navigation/     state machine: IDLE .. ABORT               (Stage 6)
behaviors/      door, stairs, loot                          (Stages 8-10)
recovery/       bounded recovery ladder L0..L7              (Stage 11)
routes/         route graph, simplification, validation     (Stage 5)
calibration/    coordinate, movement, mouse-turn fitting    (Stage 4)
vision/         compass heading, prompt detection, anchors  (Stage 4+)
capture/        CaptureProvider implementations             (Stage 2)
sensors/        SensorSource implementations                (Stage 1)
actuation/      single-writer actuator + guard chain        (Stage 3)
recording/      route recorder                              (Stage 5)
replay/         offline replay of recorded streams          (Stage 6)
reporting/      stage reports, run bundles, HTML            (ongoing)
domain/         typed contracts + geometry (pure, no I/O)
config/         paths, settings, YAML loading
diagnostics/    read-only environment probes and doctor
safety.py       scope lock and live-input interlock
clock.py        monotonic clock abstraction
stages.py       stage registry and gate
```

Directories marked with a later stage **do not exist yet**. A test asserts
this, so the stage gate cannot be violated by accident.

## 4. Control hierarchy

Deliberately not a single algorithm:

1. **Route layer** - an ordered node/edge graph. The MVP walks one principal
   path; `Route.principal_path()` raises if the graph branches rather than
   silently choosing. The schema already supports branching so A* can be added
   later without a migration.
2. **Local follower** - a pure-pursuit-style waypoint follower adapted to ~1 Hz
   position updates and bounded pulses. Look-ahead is adaptive: large outdoors,
   small in corridors, very small at doors and stairs.
3. **Sensor correction** - position from Overwolf, heading from the HUD, both
   with explicit age and confidence.
4. **Semantic behaviours** - door, stairs, loot. These run only at recorded
   semantic nodes, never opportunistically.
5. **Stuck detection and bounded recovery** - a ladder, not a retry loop.
6. **Fail-safe abort** - releases every control and writes an evidence bundle.

## 5. Design decisions worth stating plainly

**Position is truth; heading is opinion.** Position comes from the game and is
trusted once fresh. Heading comes from pixels and always carries a confidence;
below the threshold the provider abstains and the controller must not move
through narrow geometry.

**Missing data is never filled in.** A dropped location update ages; it does
not repeat the previous value as if current. `SensorSnapshot.evaluate()` returns
an explicit list of `InvalidReason`s, and an invalid snapshot has confidence
exactly 0.0 - confidence can never soften a disqualifying condition.

**All bounds are structural.** `ActuationCommand` cannot be constructed with a
hold longer than the hard ceiling or a lifetime beyond `MAX_COMMAND_LIFETIME_S`.
The actuator re-checks bounds at execution time as defence in depth. There is
no public indefinite key-down anywhere in the API.

**`RELEASE_ALL` is unconditional.** Every guard allows it, including during an
emergency stop. Refusing to let go of a key is the one failure with no safe
fallback.

**Nothing environmental is hardcoded.** Resolution, crops, key bindings, axis
orientation, units and turn gain live in a versioned `GameProfile` with a
fingerprint. A route stores the fingerprint it was recorded under, so replay
against a changed environment is refused rather than attempted.

**Angles never use linear arithmetic.** All angular work goes through
`domain/geometry.py` (`wrap_signed`, `angle_diff`, `circular_stats`). A linear
mean of `[358, 359, 0, 1, 2]` is 144 degrees; the circular mean is 0. That bug
would be invisible in a run report, so it is unit-tested directly.

**Scope is machine-checked.** `safety.py` scans the package for the symbols that
memory reading, injection, packet capture and input libraries require. Stage 0
additionally has *no registered live actuator at all*, so `--live` cannot
degrade into a silent no-op that resembles a successful run.

## 6. Clocks

Control decisions use `time.monotonic()` exclusively, via the `Clock` protocol.
Wall clock appears only in filenames and human-readable logs. `FakeClock` makes
every timing behaviour deterministic in tests, and `sleep()` advances simulated
time instead of blocking.

## 7. Evidence model

Stage evidence lands in `reports/stages/stage-NN/`; run evidence lands in
`data/local/runs/<run-id>/` with the layout fixed by
`domain/run.py::REQUIRED_BUNDLE_FILES`. Both are git-ignored: evidence is
regenerated, not committed.

The report must answer: where did the run fail, what did the controller believe,
which evidence was stale, what command was issued, did progress follow, and
which recovery attempts happened.
