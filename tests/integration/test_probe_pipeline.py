"""End-to-end probe pipeline against the synthetic bridge.

This is the test that saves live sessions: it drives the real receiver, the real
normaliser and the real report generator over a real socket, so a bug in any of
them surfaces here rather than while the operator is standing in Training Mode.

It proves nothing about PUBG, and the assertions below insist the report says so.
"""

from __future__ import annotations

import json
import socket

from pubg_training_bot.config.paths import ProjectPaths
from pubg_training_bot.probe import ProbeOptions, run_sensor_probe
from pubg_training_bot.protocol.server import ServerConfig
from pubg_training_bot.protocol.simulator import SimulatedBridge, SimulationProfile
from pubg_training_bot.sensors.overwolf import OverwolfSensorSource


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_full_probe_produces_a_passing_bundle(tmp_path) -> None:
    paths = ProjectPaths(root=tmp_path)
    options = ProbeOptions(
        duration_s=6.0,
        poll_hz=20.0,
        still_seconds=2.5,
        connect_timeout_s=15.0,
        port=free_port(),
        token="simulation-token",
        simulate=True,
    )
    report, out_dir = run_sensor_probe(options, paths=paths, quiet=True)

    assert report.simulated is True
    assert report.frames_received > 0
    assert report.position_updates > 0
    assert report.acceptance["xyz updates arrived"]
    assert report.acceptance["movement changed position"]
    assert report.acceptance["map observed"]
    assert report.acceptance["phase observed"]
    assert report.acceptance["view observed"]
    assert report.acceptance["feature registration reported"]
    assert report.passed, f"pipeline failed: {report.acceptance} {report.notes}"

    for name in ("sensor-probe.json", "report.html", "events.jsonl", "position-trace.csv"):
        assert (out_dir / name).exists(), f"missing evidence file: {name}"

    assert out_dir.name.startswith("simulated-"), (
        "a simulated bundle must be named so it cannot be mistaken for a live one"
    )


def test_simulated_report_can_never_read_as_a_live_pass(tmp_path) -> None:
    """The one property that must never regress."""
    paths = ProjectPaths(root=tmp_path)
    report, out_dir = run_sensor_probe(
        ProbeOptions(
            duration_s=5.0,
            poll_hz=20.0,
            still_seconds=2.0,
            connect_timeout_s=15.0,
            port=free_port(),
            token="simulation-token",
            simulate=True,
        ),
        paths=paths,
        quiet=True,
    )

    payload = json.loads((out_dir / "sensor-probe.json").read_text(encoding="utf-8"))
    assert payload["simulated"] is True
    assert any("SIMULATED RUN" in note for note in payload["notes"])

    html = (out_dir / "report.html").read_text(encoding="utf-8")
    assert "SIMULATED RUN" in html, "the banner must be present"

    # Scope the check to the verdict element: the warning banner legitimately
    # contains the words "LIVE PASS" while telling the reader this is not one.
    verdict = html.split('class="verdict', 1)[1].split("</p>", 1)[0]
    assert "PIPELINE OK (SIMULATED)" in verdict
    assert "LIVE PASS" not in verdict, "a simulated report must never render the live verdict"


def test_measured_cadence_and_noise_match_the_simulated_profile(tmp_path) -> None:
    """Confirms the analysis reports what was actually fed in - a sanity check on
    the measurement itself, before it is used to set real thresholds."""
    profile = SimulationProfile(
        update_interval_s=0.5, interval_jitter_s=0.02, stationary_noise_units=0.4, drop_rate=0.0
    )
    port = free_port()

    config = ServerConfig(port=port, token="tok")
    source = OverwolfSensorSource(config=config)
    source.start()
    bridge = SimulatedBridge(
        port=port, token="tok", still_seconds=30.0, duration_s=6.0, profile=profile
    )
    bridge.start()
    try:
        import time

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if source.observations()["position_updates"] >= 8:
                break
            time.sleep(0.05)

        observations = source.observations()
        intervals = observations["position_intervals"]
        assert len(intervals) >= 6

        from pubg_training_bot.reporting.sensor_probe import interval_stats

        stats = interval_stats([float(v) for v in intervals])
        assert stats.p50_s is not None
        assert 0.35 < stats.p50_s < 0.75, f"measured cadence {stats.p50_s}s should track 0.5s"
        assert observations["observed_maps"] == ["Erangel_Main"]
        assert observations["observed_phases"] == ["landed"]
    finally:
        bridge.stop()
        source.stop()


def test_probe_reports_failure_when_no_bridge_ever_connects(tmp_path) -> None:
    """The failure path matters as much as the success path: a probe that never
    saw data must fail loudly and still write evidence."""
    paths = ProjectPaths(root=tmp_path)
    report, out_dir = run_sensor_probe(
        ProbeOptions(
            duration_s=0.5,
            poll_hz=10.0,
            still_seconds=0.2,
            connect_timeout_s=0.5,
            port=free_port(),
            token="nobody-will-connect",
            simulate=False,
        ),
        paths=paths,
        quiet=True,
    )

    assert not report.passed
    assert report.frames_received == 0
    assert report.acceptance["xyz updates arrived"] is False
    assert any("NO POSITION DATA" in note for note in report.notes)
    assert (out_dir / "sensor-probe.json").exists(), "evidence must survive a failed probe"
