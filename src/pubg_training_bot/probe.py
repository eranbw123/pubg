"""Stage 1 live sensor probe.

Read-only. It starts a loopback server, waits for the Overwolf bridge, polls the
sensor source for a bounded period and writes an evidence bundle. It cannot send
input: no actuator is constructed anywhere in this module, and Stage 1 registers
none.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .clock import Clock, SystemClock, utc_stamp
from .config.paths import ProjectPaths, default_paths
from .protocol.envelope import generate_session_token
from .protocol.server import ServerConfig
from .reporting.sensor_probe import ProbeSample, SensorProbeReport, build_report, write_probe_bundle
from .sensors.overwolf import OverwolfSensorSource


@dataclass
class ProbeOptions:
    duration_s: float = 120.0
    poll_hz: float = 10.0
    #: The operator is asked to hold still for this long at the start.
    still_seconds: float = 20.0
    #: Give up if the bridge never connects.
    connect_timeout_s: float = 180.0
    host: str = "127.0.0.1"
    port: int = 17311
    token: str = ""
    #: Drive the receiver from the synthetic bridge instead of Overwolf. Proves
    #: the pipeline works without spending a live session; never evidence about
    #: the game, and the resulting report is stamped accordingly.
    simulate: bool = False


def run_sensor_probe(
    options: ProbeOptions,
    *,
    paths: ProjectPaths | None = None,
    clock: Clock | None = None,
    quiet: bool = False,
) -> tuple[SensorProbeReport, Path]:
    paths = paths or default_paths()
    clock = clock or SystemClock()
    token = options.token or generate_session_token()

    config = ServerConfig(host=options.host, port=options.port, token=token)
    source = OverwolfSensorSource(config=config, clock=clock)
    source.start()

    def emit(message: str) -> None:
        if not quiet:
            print(message, flush=True)

    simulator = None
    emit("")
    emit("=" * 70)
    if options.simulate:
        emit("STAGE 1 SENSOR PROBE - SIMULATED (synthetic bridge, PUBG not involved)")
        emit("=" * 70)
        emit("This exercises the receiver, normaliser and report pipeline.")
        emit("It is NOT evidence about the game and cannot be a LIVE PASS.")
    else:
        emit("STAGE 1 SENSOR PROBE - read-only, no input is sent to the game")
        emit("=" * 70)
        emit(f"listening on ws://{options.host}:{options.port}")
        emit(f"session token: {token}")
        emit("")
        emit("In Overwolf: load the unpacked bridge app, then start PUBG Training Mode.")
    emit(f"Waiting up to {options.connect_timeout_s:.0f}s for the bridge to connect...")

    samples: list[ProbeSample] = []
    try:
        if options.simulate:
            from .protocol.simulator import SimulatedBridge

            simulator = SimulatedBridge(
                port=options.port,
                token=token,
                still_seconds=options.still_seconds,
                duration_s=options.duration_s,
            )
            simulator.start()
        deadline = clock.monotonic() + options.connect_timeout_s
        while clock.monotonic() < deadline:
            if source.status().messages_received > 0:
                break
            clock.sleep(0.25)

        connected = source.status().messages_received > 0
        if not connected:
            emit("")
            emit("FAILED: the bridge never connected. Evidence is still written.")
        else:
            emit("")
            emit("Bridge connected.")
            emit(f"HOLD STILL for {options.still_seconds:.0f}s (measuring position noise)...")

        interval = 1.0 / max(options.poll_hz, 0.1)
        start = clock.monotonic()
        end = start + options.duration_s
        announced_walk = False
        last_line = 0.0

        while clock.monotonic() < end:
            now = clock.monotonic()
            snapshot = source.latest()
            if snapshot is not None:
                samples.append(
                    ProbeSample(
                        at=now,
                        position=snapshot.raw_position,
                        location_age_s=snapshot.location_age_s,
                        map_id=snapshot.map_id,
                        phase=str(snapshot.phase),
                        view=str(snapshot.view),
                        stance=str(snapshot.stance),
                        movement=str(snapshot.movement),
                        free_view=snapshot.free_view_active,
                        bridge_health=str(snapshot.bridge_health),
                    )
                )

            elapsed = now - start
            if not announced_walk and elapsed >= options.still_seconds:
                announced_walk = True
                emit("")
                emit("NOW: walk forward, turn, walk again. Keep going until the timer ends.")

            if not quiet and now - last_line >= 1.0:
                last_line = now
                status = source.status()
                position = snapshot.raw_position if snapshot else None
                where = (
                    f"xyz=({position.x:.1f},{position.y:.1f},{position.z:.1f})"
                    if position
                    else "xyz=NONE"
                )
                sys.stdout.write(
                    f"\r  {elapsed:5.1f}/{options.duration_s:.0f}s  "
                    f"frames={status.messages_received:5d}  {where}  "
                    f"map={(snapshot.map_id if snapshot else None) or '?'}  "
                    f"phase={(str(snapshot.phase) if snapshot else '?')}   "
                )
                sys.stdout.flush()

            clock.sleep(interval)

        emit("")
        duration = clock.monotonic() - start
        report = build_report(
            samples=samples,
            observations=source.observations(),
            status=source.status(),
            duration_s=duration,
            poll_hz=options.poll_hz,
            still_seconds=options.still_seconds,
            simulated=options.simulate,
        )
        prefix = "simulated" if options.simulate else "probe"
        out_dir = paths.stage_report_dir("01") / f"{prefix}-{utc_stamp(clock)}"
        written = write_probe_bundle(out_dir, report, samples, source.server.frames)
        emit("")
        for name, path in written.items():
            emit(f"  {name}: {path}")
        return report, out_dir
    finally:
        if simulator is not None:
            simulator.stop()
        source.stop()


__all__ = ["ProbeOptions", "run_sensor_probe"]
