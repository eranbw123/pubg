"""Sensor validity: the gate every actuation decision passes through."""

from __future__ import annotations

import pytest

from pubg_training_bot.domain.enums import (
    BridgeHealth,
    InvalidReason,
    MatchPhase,
    Stance,
    ViewMode,
)
from pubg_training_bot.domain.sensors import (
    ExpectedContext,
    FreshnessPolicy,
    HeadingReading,
    SensorSnapshot,
    Vec3,
)

NOW = 1000.0


def make_snapshot(**overrides) -> SensorSnapshot:
    base = {
        "monotonic_ts": NOW,
        "bridge_health": BridgeHealth.CONNECTED,
        "map_id": "TRAINING",
        "phase": MatchPhase.LANDED,
        "view": ViewMode.FPP,
        "stance": Stance.STANDING,
        "free_view_active": False,
        "foreground": True,
        "raw_position": Vec3(x=10.0, y=20.0, z=30.0),
        "location_age_s": 0.4,
        "heading": HeadingReading(heading_deg=90.0, confidence=0.9, observed_at=NOW - 0.1),
    }
    base.update(overrides)
    return SensorSnapshot(**base)


def test_healthy_snapshot_is_valid_and_confident(
    policy: FreshnessPolicy, expected: ExpectedContext
) -> None:
    result = make_snapshot().evaluate(policy, expected)
    assert result.is_valid
    assert result.invalid_reasons == ()
    assert result.confidence > 0.5


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"location_age_s": 9.0}, InvalidReason.LOCATION_STALE),
        ({"raw_position": None, "location_age_s": None}, InvalidReason.LOCATION_MISSING),
        ({"heading": None}, InvalidReason.HEADING_MISSING),
        ({"map_id": None}, InvalidReason.MAP_MISSING),
        ({"map_id": "ERANGEL"}, InvalidReason.MAP_MISMATCH),
        ({"phase": MatchPhase.LOBBY}, InvalidReason.PHASE_MISMATCH),
        ({"view": ViewMode.TPP}, InvalidReason.VIEW_MISMATCH),
        ({"stance": Stance.PRONE}, InvalidReason.STANCE_MISMATCH),
        ({"free_view_active": True}, InvalidReason.FREE_VIEW_ACTIVE),
        ({"foreground": False}, InvalidReason.NOT_FOREGROUND),
        ({"bridge_health": BridgeHealth.DISCONNECTED}, InvalidReason.BRIDGE_DISCONNECTED),
    ],
)
def test_each_failure_mode_is_named_explicitly(
    policy: FreshnessPolicy, expected: ExpectedContext, overrides: dict, reason: InvalidReason
) -> None:
    result = make_snapshot(**overrides).evaluate(policy, expected)
    assert reason in result.invalid_reasons
    assert not result.is_valid
    assert result.confidence == 0.0, "invalid snapshots must not carry residual confidence"


def test_stale_heading_and_low_confidence_are_distinct_reasons(
    policy: FreshnessPolicy, expected: ExpectedContext
) -> None:
    stale = make_snapshot(
        heading=HeadingReading(heading_deg=12.0, confidence=0.95, observed_at=NOW - 5.0)
    ).evaluate(policy, expected)
    assert InvalidReason.HEADING_STALE in stale.invalid_reasons
    assert InvalidReason.HEADING_LOW_CONFIDENCE not in stale.invalid_reasons

    weak = make_snapshot(
        heading=HeadingReading(heading_deg=12.0, confidence=0.1, observed_at=NOW - 0.05)
    ).evaluate(policy, expected)
    assert InvalidReason.HEADING_LOW_CONFIDENCE in weak.invalid_reasons
    assert InvalidReason.HEADING_STALE not in weak.invalid_reasons


def test_not_armed_is_an_invalid_reason(policy: FreshnessPolicy, expected: ExpectedContext) -> None:
    result = make_snapshot().evaluate(policy, expected, armed=False)
    assert InvalidReason.NOT_ARMED in result.invalid_reasons


def test_frame_requirement_is_opt_in(policy: FreshnessPolicy) -> None:
    without_frames = ExpectedContext(map_id="TRAINING", require_frame=False)
    assert make_snapshot().evaluate(policy, without_frames).is_valid

    with_frames = ExpectedContext(map_id="TRAINING", require_frame=True)
    result = make_snapshot().evaluate(policy, with_frames)
    assert InvalidReason.FRAME_MISSING in result.invalid_reasons

    fresh = make_snapshot(frame_id="f1", frame_age_s=0.1).evaluate(policy, with_frames)
    assert fresh.is_valid
    stale = make_snapshot(frame_id="f1", frame_age_s=5.0).evaluate(policy, with_frames)
    assert InvalidReason.FRAME_STALE in stale.invalid_reasons


def test_heading_requirement_can_be_waived(policy: FreshnessPolicy) -> None:
    context = ExpectedContext(map_id="TRAINING", require_heading=False)
    result = make_snapshot(heading=None).evaluate(policy, context)
    assert result.is_valid


def test_confidence_decreases_as_data_ages(
    policy: FreshnessPolicy, expected: ExpectedContext
) -> None:
    fresh = make_snapshot(location_age_s=0.05).evaluate(policy, expected)
    older = make_snapshot(location_age_s=2.0).evaluate(policy, expected)
    assert fresh.confidence > older.confidence


def test_evaluate_is_pure(policy: FreshnessPolicy, expected: ExpectedContext) -> None:
    snapshot = make_snapshot(foreground=False)
    evaluated = snapshot.evaluate(policy, expected)
    assert snapshot.invalid_reasons == ()
    assert evaluated is not snapshot
    assert evaluated.invalid_reasons != ()


def test_multiple_problems_are_all_reported(
    policy: FreshnessPolicy, expected: ExpectedContext
) -> None:
    result = make_snapshot(
        foreground=False, map_id="ERANGEL", location_age_s=99.0, heading=None
    ).evaluate(policy, expected)
    assert {
        InvalidReason.NOT_FOREGROUND,
        InvalidReason.MAP_MISMATCH,
        InvalidReason.LOCATION_STALE,
        InvalidReason.HEADING_MISSING,
    } <= set(result.invalid_reasons)
