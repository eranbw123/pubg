# Overwolf bridge - NOT IMPLEMENTED YET (Stage 1)

This directory is a placeholder. It is deliberately empty of code: implementing
it now would violate the stage gate, and the PUBG game identifier, the available
documented features and their payload shapes must be looked up against current
Overwolf documentation at implementation time rather than guessed.

## What it will do (Stage 1)

- Register only the documented PUBG features the controller needs.
- Receive initial game info plus subsequent info updates and events.
- **Preserve raw payloads verbatim** before any normalisation - Overwolf nests
  JSON inside strings and the original must reach the run bundle intact.
- Normalise location, map, phase, view, stance, movement, free-view and weapon
  state, attaching sequence numbers and timestamps.
- Report per-feature registration outcomes, so a refused feature is visible
  rather than silently absent.
- Send messages to the Python controller over a token-authenticated WebSocket
  bound to `127.0.0.1` only, with heartbeat and automatic reconnect.
- Optionally provide a low-rate screenshot fallback.
- Expose a small toggleable debug window.

## What it will never do

Produce game input. The bridge is a sensor. The only path back into the game is
the Python controller's actuator.

## Contract

Messages must validate against
[`schemas/bridge-message.schema.json`](../../schemas/bridge-message.schema.json),
generated from `src/pubg_training_bot/domain/bridge.py`.

## Prerequisites

Overwolf installed with developer mode enabled, plus Node 20+ and pnpm
(`corepack enable pnpm`). `pubg-bot doctor` reports all three. On this host
Overwolf is **not** installed - see risk R-001.
