"""Stage 1 probe analysis.

The analysis must be honest in both directions: it may not declare success
without evidence, and it may not declare noise "measured" from a single
distinct position.
"""

from __future__ import annotations

import json

import pytest

from pubg_training_bot.domain.sensors import Vec3
from pubg_training_bot.reporting.sensor_probe import (
    ProbeSample,
    build_report,
    interval_stats,
    stationary_noise,
    write_probe_bundle,
)


class FakeStatus:
    messages_received = 120
    duplicates_dropped = 2
    sequence_gaps = 1
    feature_registration = {"location": True, "me": True, "map": True, "phase": True}


def sample(at: float, position: Vec3 | None, **overrides) -> ProbeSample:
    base = {
        "location_age_s": 0.2,
        "map_id": "Erangel_Main",
        "phase": "landed",
        "view": "fpp",
        "stance": "standing",
        "movement": "walking",
        "free_view": False,
        "bridge_health": "connected",
    }
    base.update(overrides)
    return ProbeSample(at=at, position=position, **base)


# --------------------------------------------------------------------------- #
def test_interval_stats_percentiles_and_histogram() -> None:
    stats = interval_stats([1.0, 1.0, 1.0, 1.0, 3.0])
    assert stats.count == 5
    assert stats.p50_s == pytest.approx(1.0)
    assert stats.max_s == pytest.approx(3.0)
    assert stats.implied_hz == pytest.approx(1.0)
    assert stats.histogram["1.0-1.5s"] == 4
    # Buckets are half-open [lo, hi), so 3.0 lands in the 3.0-5.0 bucket.
    assert stats.histogram["3.0-5.0s"] == 1


def test_interval_stats_on_empty_input_claims_nothing() -> None:
    stats = interval_stats([])
    assert stats.count == 0
    assert stats.p50_s is None
    assert stats.implied_hz is None


def test_stationary_noise_uses_distinct_positions_only() -> None:
    """Polling at 10 Hz against a 1 Hz sensor must not inflate the sample count."""
    samples = [sample(i * 0.1, Vec3(x=100.0, y=200.0, z=50.0)) for i in range(30)]
    noise = stationary_noise(samples, window_s=3.0)
    assert noise.samples == 1, "30 polls of one unchanged position is one observation"
    assert not noise.measured
    assert "not enough" in noise.detail


def test_stationary_noise_measures_spread() -> None:
    positions = [
        Vec3(x=100.0, y=200.0, z=50.0),
        Vec3(x=100.6, y=200.0, z=50.0),
        Vec3(x=99.4, y=200.0, z=50.2),
        Vec3(x=100.0, y=200.8, z=49.9),
    ]
    samples = [sample(i * 1.0, p) for i, p in enumerate(positions)]
    noise = stationary_noise(samples, window_s=10.0)
    assert noise.measured
    assert noise.samples == 4
    assert noise.max_xy_deviation_units is not None
    assert 0.0 < noise.max_xy_deviation_units < 2.0
    assert noise.z_range_units == pytest.approx(0.3, abs=1e-6)
    assert noise.centroid is not None


def test_report_passes_when_every_signal_is_present() -> None:
    samples = [
        sample(0.0, Vec3(x=0.0, y=0.0, z=10.0)),
        sample(1.0, Vec3(x=0.4, y=0.0, z=10.0)),
        sample(2.0, Vec3(x=10.0, y=0.0, z=10.0)),
        sample(3.0, Vec3(x=20.0, y=5.0, z=10.0)),
    ]
    report = build_report(
        samples=samples,
        observations={
            "position_intervals": [1.0, 1.0, 1.0],
            "position_updates": 4,
            "observed_maps": ["Erangel_Main"],
            "observed_phases": ["landed"],
            "observed_views": ["fpp"],
            "warnings": [],
        },
        status=FakeStatus(),
        duration_s=4.0,
        poll_hz=10.0,
        still_seconds=2.0,
    )
    assert report.passed
    assert report.acceptance["xyz updates arrived"]
    assert report.acceptance["movement changed position"]
    assert report.total_path_length_units > 0
    assert report.first_position == (0.0, 0.0, 10.0)
    assert report.last_position == (20.0, 5.0, 10.0)


def test_report_fails_loudly_when_no_position_arrived() -> None:
    """The project's top feasibility risk must fail, not degrade quietly."""
    report = build_report(
        samples=[sample(0.0, None), sample(1.0, None)],
        observations={
            "position_intervals": [],
            "position_updates": 0,
            "observed_maps": ["Erangel_Main"],
            "observed_phases": ["landed"],
            "observed_views": ["fpp"],
            "warnings": [],
        },
        status=FakeStatus(),
        duration_s=2.0,
        poll_hz=10.0,
        still_seconds=1.0,
    )
    assert not report.passed
    assert report.acceptance["xyz updates arrived"] is False
    assert any("NO POSITION DATA" in note for note in report.notes)
    assert any("R-002" in note for note in report.notes)


def test_report_flags_a_cadence_slower_than_the_working_assumption() -> None:
    report = build_report(
        samples=[sample(0.0, Vec3(x=0, y=0, z=0)), sample(3.0, Vec3(x=5, y=0, z=0))],
        observations={
            "position_intervals": [3.0, 3.2, 2.9],
            "position_updates": 3,
            "observed_maps": ["m"],
            "observed_phases": ["landed"],
            "observed_views": ["fpp"],
            "warnings": [],
        },
        status=FakeStatus(),
        duration_s=9.0,
        poll_hz=10.0,
        still_seconds=1.0,
    )
    assert any("slower than the ~1 Hz" in note for note in report.notes)
    assert any("D-009" in note for note in report.notes)


def test_missing_identifiers_fail_their_own_criteria() -> None:
    report = build_report(
        samples=[sample(0.0, Vec3(x=1, y=1, z=1))],
        observations={
            "position_intervals": [1.0],
            "position_updates": 1,
            "observed_maps": [],
            "observed_phases": [],
            "observed_views": [],
            "warnings": [{"field": "phase", "code": "unknown_phase_value", "detail": "x"}],
        },
        status=FakeStatus(),
        duration_s=1.0,
        poll_hz=10.0,
        still_seconds=0.5,
    )
    assert report.acceptance["map observed"] is False
    assert report.acceptance["phase observed"] is False
    assert report.acceptance["view observed"] is False
    assert not report.passed
    assert any("parse warning" in note for note in report.notes)


def test_bundle_contains_every_evidence_file(tmp_path) -> None:
    samples = [
        sample(0.0, Vec3(x=0.0, y=0.0, z=1.0)),
        sample(1.0, Vec3(x=1.0, y=2.0, z=1.0)),
        sample(2.0, None),
    ]
    report = build_report(
        samples=samples,
        observations={
            "position_intervals": [1.0],
            "position_updates": 2,
            "observed_maps": ["Erangel_Main"],
            "observed_phases": ["landed"],
            "observed_views": ["fpp"],
            "warnings": [],
        },
        status=FakeStatus(),
        duration_s=2.0,
        poll_hz=10.0,
        still_seconds=1.0,
    )
    written = write_probe_bundle(
        tmp_path / "probe", report, samples, [{"type": "info_update", "sequence": 1}]
    )
    for path in written.values():
        assert path.exists()

    json.loads(written["json"].read_text(encoding="utf-8"))
    html = written["html"].read_text(encoding="utf-8")
    assert "Stage 1" in html
    assert "svg" in html, "the position trace must be plotted"
    trace = written["trace"].read_text(encoding="utf-8").splitlines()
    assert trace[0].startswith("t,x,y,z")
    assert len(trace) == 4, "header plus one row per sample, including the empty one"
    events = written["events"].read_text(encoding="utf-8").strip().splitlines()
    assert len(events) == 1
