# Overwolf developer whitelist request

Draft email for `developers@overwolf.com`, required by risk R-016 before the
bridge can be loaded as an unpacked app.

**It discloses the automation purpose deliberately.** The Overwolf app is
sensor-only, but it exists to feed a controller that sends synthetic input to
PUBG. Describing only the bridge would be misleading, and approval obtained that
way is worth little - it can be withdrawn once the full picture emerges, after
the project has been built on top of it.

Replace the bracketed fields before sending.

---

**Subject:** Developer whitelist request - local, sensor-only PUBG app for a Training Mode navigation project

Hello,

I would like to request developer whitelisting for my Overwolf account so I can
load an unpacked app during local development.

**Account:** [your Overwolf account email]
**Name:** [your name]
**Overwolf client:** 0.309.0.11, Developers channel
**App name:** PUBG Training Bridge (personal project, not intended for the store)

**What the app does**

It is a sensor bridge, and nothing else. It:

- targets PUBG only (game class id 10906);
- registers five documented Game Events Provider features: `location`, `me`,
  `phase`, `map`, `match_info`;
- forwards those payloads to a Python process on `127.0.0.1` over a
  token-authenticated WebSocket;
- has one small debug window showing connection status and the last payload.

It requests only the `GameInfo` permission, makes no external network requests,
stores nothing remotely, and contains no input, overlay-interaction or
key-simulation code of any kind.

**What it is part of, so you can judge the whole thing**

The bridge feeds a personal research project that navigates a **recorded route
in PUBG Training Mode**. A human walks a route once; a local controller then
replays it, using position from your GEP `location` feature for navigation and
ordinary operating-system keyboard and mouse input to move the character. I want
to be upfront that this is game automation, since that is the part you would
reasonably want to know about before granting access.

Deliberate boundaries, enforced in the code rather than only intended:

- **Training Mode only**, solo. No public or ranked matches at any point.
- **No combat capability**: no aiming, firing, recoil control, opponent
  detection, or use of any hidden information. The combat and roster GEP
  features (`kill`, `death`, `killer`, `revived`, `team`, `roster`) are
  explicitly *not* requested.
- **No memory reading, DLL or process injection, packet interception, engine
  hooks, kernel drivers, or anti-cheat interference.** The project uses only
  documented Overwolf events, visible pixels, and ordinary OS input APIs. A
  static check in the build fails the project if any of those techniques appear
  in the source.
- The Overwolf app never produces input. The only path back into the game is a
  separate local process using standard OS input, which is a deliberate
  separation.

**What I am asking for**

Only the ability to load the app unpacked on my own machine for development. I
am not requesting store distribution and have no plans to publish it.

I am happy to send the manifest, the app source, or a short recording of it
running, and equally happy to hear if this is not something you want on the
platform - I would rather know now than build further on access that would
later be withdrawn.

Thank you for your time,
[your name]
[your Overwolf account email]

---

## If they decline

That is a legitimate outcome, not a problem to route around. It would mean
Stage 1 cannot be completed as designed, and the project stops at that
feasibility gate (the same rule that applies if PUBG rejects ordinary input at
Stage 3). Record the response in `docs/decisions.md` and mark R-016 as realised.
