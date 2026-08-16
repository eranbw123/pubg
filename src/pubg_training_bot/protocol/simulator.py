"""Synthetic bridge that speaks the real wire protocol.

Purpose: prove the probe pipeline works *before* spending a live session on it.
A bug in the receiver, the normaliser or the report generator should surface
here, on the desk, not while the operator is standing in Training Mode.

This is emphatically **not** evidence about the game. Every report produced with
it is stamped ``simulated: true`` and the HTML says so in the verdict, because a
simulated pass that could be mistaken for a live pass is worse than no test at
all.

The emitted payloads use Overwolf's documented shapes, including the nested-JSON
``location`` string, and model the behaviour we expect to have to cope with:
~1 Hz updates with jitter, position noise while stationary, and an occasional
dropped update.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import random
import threading
from dataclasses import dataclass, field

import websockets

from .envelope import PROTOCOL_VERSION


@dataclass
class SimulationProfile:
    """Shape of the synthetic stream. Defaults encode the working assumptions
    that Stage 1's live probe exists to confirm or refute."""

    update_interval_s: float = 1.0
    interval_jitter_s: float = 0.12
    #: Position wobble while the character is motionless, in game units.
    stationary_noise_units: float = 0.35
    walk_speed_units_per_s: float = 250.0
    #: Fraction of location updates that never arrive.
    drop_rate: float = 0.02
    map_id: str = "Erangel_Main"
    phase: str = "landed"
    view: str = "FPP"
    start_x: float = 2300.0
    start_y: float = 5740.0
    start_z: float = 1520.0
    seed: int = 20260813


@dataclass
class SimulatedBridge:
    """Connects to a running :class:`BridgeServer` and feeds it plausible data."""

    port: int
    token: str
    still_seconds: float = 20.0
    duration_s: float = 120.0
    profile: SimulationProfile = field(default_factory=SimulationProfile)
    host: str = "127.0.0.1"

    _thread: threading.Thread | None = field(default=None, init=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    frames_sent: int = field(default=0, init=False)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="simulated-bridge", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout_s)
            self._thread = None

    def _run(self) -> None:
        # A simulator failure must not raise on a daemon thread; the probe
        # reports the absence of data, which is the correct visible outcome.
        with contextlib.suppress(Exception):  # pragma: no cover
            asyncio.run(self._session())

    async def _session(self) -> None:
        uri = f"ws://{self.host}:{self.port}"
        async with websockets.connect(uri) as connection:
            await connection.send(
                json.dumps(
                    {
                        "type": "auth",
                        "protocol_version": PROTOCOL_VERSION,
                        "token": self.token,
                        "bridge_version": "simulator",
                        "session_id": "simulated-session",
                        "overwolf_version": "simulated",
                    }
                )
            )
            response = json.loads(await connection.recv())
            if not response.get("accepted"):
                return

            sequence = 0
            rng = random.Random(self.profile.seed)

            async def send(frame_type: str, raw: dict, feature: str | None = None) -> None:
                nonlocal sequence
                sequence += 1
                await connection.send(
                    json.dumps(
                        {
                            "type": frame_type,
                            "sequence": sequence,
                            "bridge_ts_ms": sequence * 10.0,
                            "source_ts_ms": None,
                            "raw": raw,
                            "normalized": None,
                            "feature": feature,
                        }
                    )
                )
                self.frames_sent += 1

            await send(
                "feature_status",
                {
                    "features": [
                        {"feature": name, "registered": True, "detail": "simulated"}
                        for name in ("location", "me", "phase", "map", "match_info")
                    ],
                    "attempt": 1,
                    "success": True,
                },
            )
            await send("info_update", {"info": {"map": {"map": self.profile.map_id}}}, "map")
            await send("info_update", {"info": {"phase": {"phase": self.profile.phase}}}, "phase")
            await send(
                "info_update",
                {
                    "info": {
                        "me": {
                            "view": self.profile.view,
                            "stance": "stand",
                            "movement": "normal",
                            "freeView": False,
                            "inVehicle": False,
                        }
                    }
                },
                "me",
            )

            loop = asyncio.get_running_loop()
            started = loop.time()
            x, y, z = self.profile.start_x, self.profile.start_y, self.profile.start_z
            heading = 0.0

            while not self._stop.is_set():
                elapsed = loop.time() - started
                if elapsed > self.duration_s + 5.0:
                    break

                interval = max(
                    0.05,
                    self.profile.update_interval_s
                    + rng.uniform(-self.profile.interval_jitter_s, self.profile.interval_jitter_s),
                )
                await asyncio.sleep(interval)

                if elapsed < self.still_seconds:
                    # Motionless: report the same spot with sensor wobble.
                    noise = self.profile.stationary_noise_units
                    px = x + rng.uniform(-noise, noise)
                    py = y + rng.uniform(-noise, noise)
                    pz = z + rng.uniform(-noise / 4, noise / 4)
                else:
                    # Walking: an L-shape, turning once part way through.
                    if elapsed > self.still_seconds + (self.duration_s - self.still_seconds) / 2:
                        heading = 90.0
                    step = self.profile.walk_speed_units_per_s * interval
                    x += step * math.sin(math.radians(heading))
                    y += step * math.cos(math.radians(heading))
                    px, py, pz = x, y, z

                if rng.random() < self.profile.drop_rate:
                    continue  # a dropped update must look stale, not repeated

                await send(
                    "info_update",
                    {
                        "info": {
                            "location": {
                                "location": json.dumps(
                                    {"x": round(px, 2), "y": round(py, 2), "z": round(pz, 2)}
                                )
                            }
                        }
                    },
                    "location",
                )


__all__ = ["SimulatedBridge", "SimulationProfile"]
