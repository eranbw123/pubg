# Risk register

Ranked by the initial feasibility assessment required at Stage 0. Ranking is by
*expected project damage*: how likely the risk is to materialise multiplied by
how much work dies with it. A risk that kills the project at Stage 1 outranks a
risk that costs two days at Stage 9.

Status values: `open`, `retired`, `realised`, `accepted`.

| ID | Risk | Likelihood | Impact | Rank | Stage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| R-001 | Overwolf not installed on this host | was certain (observed) | blocked all live stages | - | 01 | **retired** |
| R-002 | Overwolf exposes no local XYZ in Training Mode | medium | project-ending | 1 | 01 | open |
| R-016 | Overwolf developer access not granted (channel + account whitelist) | medium-high | blocks Stage 1 entirely; remedy is outside our control | 2 | 01 | open |
| R-003 | Heading cannot be read reliably from the HUD | medium-high | project-ending | 3 | 04 | open |
| R-004 | PUBG rejects ordinary bounded OS input | medium | project-ending (no evasion permitted) | 4 | 03 | open |
| R-005 | Coordinate transform is unstable or non-linear | medium | blocks all navigation | 5 | 04 | open |
| R-006 | Frame capture is black, stale or overlay-polluted | medium | blocks heading and prompts | 6 | 02 | open |
| R-007 | Map / phase / view data missing or ambiguous | low-medium | weakens every guard | 7 | 01 | open |
| R-008 | Indoor position accuracy insufficient for narrow geometry | medium-high | blocks Stages 8-9 | 8 | 08 | open |
| R-009 | Door interaction unreliable or non-idempotent | medium | blocks Stage 8 | 9 | 08 | open |
| R-010 | Stair traversal not repeatable | medium-high | blocks Stage 9 | 10 | 09 | open |
| R-011 | Loot pickup cannot be verified | medium | weakens Stage 10 acceptance | 11 | 10 | open |
| R-012 | Position update latency causes overshoot | medium | degrades all navigation | 12 | 06-07 | open |
| R-013 | Recovery masks a systemic failure | medium | false confidence | 13 | 11 | open |
| R-014 | Game update changes HUD or event schema | low per-week, certain eventually | invalidates profile + routes | 14 | any | open |
| R-015 | Python 3.14 lacks wheels for capture/vision deps | - | would have blocked Stage 2 | - | 02 | **retired** |

---

## R-001 - Overwolf not installed (retired)
Observed absent at the start of Stage 0, which blocked Stage 1 outright.
**Retired during Stage 0:** Overwolf is installed at `%LOCALAPPDATA%\Overwolf`
and the process is running; `doctor` detects both.

The residual concern - whether developer mode is enabled so an unpacked app can
be loaded - is tracked separately as R-016, because it is an application setting
the doctor cannot observe.

## R-016 - Overwolf developer access not granted
Installing Overwolf is not sufficient, and this is **not** a settings toggle.
Overwolf's documentation states: *"To develop, load or run unpacked or
unreleased apps, you have to get whitelisted first"*, and separately that
developers must be *"approved by Overwolf"* before accessing developer tools.
Two distinct things are required:

1. **Developers channel** - `Development options` does not appear on the
   production client. Settings -> About -> `Ctrl + Shift + left click` the
   Overwolf logo -> type `Developers` in the channel field -> update and
   relaunch. **Satisfied on this host** (client 0.309.0.11, channel
   `Developers`), and now verified by the doctor rather than asserted.
2. **Account whitelisting** - Overwolf's docs state the account must be approved
   to load unpacked or unreleased apps, requested via `developers@overwolf.com`.
   Loading without it reportedly fails with "Unauthorized App". **Unverified.**

*Effect:* the bridge cannot be loaded at all, so Stage 1 cannot produce
evidence, and every later stage depends on Stage 1. Unlike the other risks in
this register, the remedy is **outside our control and has a human turnaround
time**.

*Mitigation:* test empirically and cheaply before assuming the worst - switch to
the Developers channel first and try loading any unpacked app. If it loads, the
whitelist is not enforced for this account and the risk is retired. If it
returns "Unauthorized App", start the email request immediately, because the
wait is the critical path.

*Detection:* split, because the two halves are not equally observable - an
earlier version of this entry wrongly lumped them together and claimed neither
could be checked.

- **Channel: observable.** It is a machine fact, published at
  `HKLM\SOFTWARE\WOW6432Node\Overwolf\Channel`. The doctor now reports it
  (`overwolf channel`), along with the client version and real install folder.
- **Whitelist: not observable.** It is account state held by Overwolf, not a
  machine fact. The doctor does not represent it at all, and a unit test asserts
  no check mentions it - a green line about something the tool cannot see is
  worse than no line.

*Sources:* [Setting up a development
environment](https://dev.overwolf.com/ow-native/getting-started/onboarding-resources/setting-up-dev-environment/),
[Enabling and using developer
tools](https://dev.overwolf.com/ow-native/guides/dev-tools/use-enable-developer-tools/).

## R-002 - No local XYZ in Training Mode
The whole teach-and-repeat design assumes a position reference. Overwolf's PUBG
provider documents a location payload, but availability in Training Mode
specifically is unverified.

*Mitigation:* Stage 1 is a pure observation stage, ordered first precisely so
this fails cheaply. If XYZ is absent, the stage is marked FAILED with evidence
preserved. There is no fallback that stays within scope - dead reckoning from
issued commands alone cannot close the loop indoors.

## R-003 - Heading unreadable
Position without orientation cannot drive a closed loop: the controller would
know where it is and not which way to walk.

*Mitigation:* four ranked signals (compass recognition; heading inferred from
XYZ displacement while moving; short-term dead reckoning from issued mouse
rotations; route-specific visual checkpoint alignment). The provider abstains
below its confidence threshold instead of guessing. Stage 4 is an explicit
go/no-go gate with numeric targets.

## R-004 - Input rejected
*Mitigation:* only ordinary documented variants may be tried - correct process
integrity level, scan codes rather than virtual keys, relative mouse flags. If
those fail, the evidence is recorded and the project stops at that gate. Looking
for an evasion mechanism is forbidden by `CLAUDE.md` section 4.

## R-005 - Unstable coordinate transform
Axis assignment, inversion, scale and Z sign are all unknown. A transform fitted
in open ground may not hold indoors, and Z units may be non-linear across floors.

*Mitigation:* fit from multiple headings with RMSE recorded; `fitted=false`
until the fit is accepted; runtime turning stays closed-loop so a small gain
error self-corrects instead of accumulating.

## R-006 - Capture unusable
Fullscreen-exclusive presentation, overlay bleed and duplicate frames are all
plausible. *Mitigation:* Stage 2 benchmarks real providers against the running
game and measures black/duplicate ratios explicitly. A failed grab returns
`None`, never a black placeholder that would be indistinguishable from a real
dark scene.

## R-007 - Weak map/phase/view data
Every actuation guard depends on knowing the map, the phase and the view.
*Mitigation:* per-feature registration outcomes are reported individually in
Stage 1; a missing feature degrades the corresponding guard visibly rather than
silently.

## R-008 - Indoor accuracy
A ~1 Hz position update with unknown noise may not resolve a doorway.
*Mitigation:* stationary noise is measured in Stage 1 *before* any route is
recorded; node tolerances are derived from that measurement; critical edges use
shorter pulses and tighter heading gates.

## R-009 - Door interaction
Doors may be open or closed, prompts may not appear, and a repeated interaction
can re-close a door just opened.
*Mitigation:* crossing progress - not prompt recognition - is the primary
evidence; interaction is only attempted at recorded door nodes; retries are
bounded and stop immediately once crossing is confirmed.

## R-010 - Stair repeatability
*Mitigation:* stairs are modelled as explicit start/transit/end nodes with an
expected Z direction and magnitude; floor advancement requires observed Z
evidence; forward movement on stairs is always bounded.

## R-011 - Loot verification
*Mitigation:* a weapon is the first target because weapon state offers
independent confirmation. Otherwise converging evidence (prompt disappearance,
UI change) is required, and failed verification is reported rather than assumed.

## R-012 - Latency-induced overshoot
Acting on a position that is up to a second old causes overshoot near tight
nodes. *Mitigation:* short bounded pulses, adaptive look-ahead that shrinks near
critical nodes, arrival confirmed only by fresh evidence, and measured actuation
latency stored in the profile.

## R-013 - Recovery hiding systemic failure
A recovery ladder that quietly rescues every run makes a broken controller look
healthy. *Mitigation:* recovery counts and levels appear in every run summary;
acceptance criteria count *clean* runs; a rising recovery rate is treated as a
regression.

## R-014 - Game updates
*Mitigation:* profile fingerprints make an environment change a hard validation
failure rather than a mysterious navigation failure. Re-calibration is a
documented, repeatable procedure, not a rewrite.

## R-015 - Python 3.14 wheel availability (retired)
Retired at Stage 0: every planned dependency resolves to a cp314 binary wheel
(see D-003). Had this failed, a second interpreter would have been required
before Stage 2.
