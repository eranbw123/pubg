"""Actuation guarantees.

The properties tested here are the ones that keep a bug from turning into an
uncontrolled character: dry-run really sends nothing, commands expire, bounds
are enforced, and RELEASE_ALL is never blocked.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pubg_training_bot.actuation import (
    CallableGuard,
    DryRunActuator,
    FakeActuator,
    ForegroundGuard,
    SensorFreshnessGuard,
    create_actuator,
    list_actuators,
    live_actuator_available,
    require_live_actuator,
)
from pubg_training_bot.clock import FakeClock
from pubg_training_bot.domain.actuation import (
    MAX_COMMAND_LIFETIME_S,
    MAX_KEY_HOLD_MS,
    ActuationCommand,
    CommandBounds,
    release_all,
)
from pubg_training_bot.domain.enums import (
    BridgeHealth,
    CommandOutcome,
    CommandType,
    ControlState,
    MatchPhase,
    Stance,
    ViewMode,
)
from pubg_training_bot.domain.sensors import HeadingReading, SensorSnapshot, Vec3


def make_command(clock: FakeClock, **overrides) -> ActuationCommand:
    now = clock.monotonic()
    base = {
        "type": CommandType.KEY_HOLD,
        "key": "forward",
        "hold_ms": 300,
        "reason": "advance along edge",
        "issuing_state": ControlState.ADVANCE_EDGE,
        "issued_at": now,
        "expires_at": now + 1.0,
    }
    base.update(overrides)
    return ActuationCommand(**base)


# --------------------------------------------------------------------------- #
# Command model
# --------------------------------------------------------------------------- #
def test_hold_beyond_hard_ceiling_cannot_be_constructed(clock: FakeClock) -> None:
    with pytest.raises(ValidationError):
        make_command(clock, hold_ms=MAX_KEY_HOLD_MS + 1)


def test_mouse_delta_beyond_ceiling_cannot_be_constructed(clock: FakeClock) -> None:
    with pytest.raises(ValidationError):
        make_command(clock, type=CommandType.MOUSE_MOVE, key=None, hold_ms=None, mouse_dx=10_000)


def test_lifetime_beyond_ceiling_rejected(clock: FakeClock) -> None:
    now = clock.monotonic()
    with pytest.raises(ValidationError):
        make_command(clock, issued_at=now, expires_at=now + MAX_COMMAND_LIFETIME_S + 1)


def test_expiry_before_issue_rejected(clock: FakeClock) -> None:
    now = clock.monotonic()
    with pytest.raises(ValidationError):
        make_command(clock, issued_at=now, expires_at=now - 1)


def test_command_shape_must_match_type(clock: FakeClock) -> None:
    with pytest.raises(ValidationError):
        make_command(clock, type=CommandType.KEY_TAP, key=None)
    with pytest.raises(ValidationError):
        make_command(clock, type=CommandType.KEY_HOLD, hold_ms=0)
    with pytest.raises(ValidationError):
        make_command(clock, type=CommandType.MOUSE_CLICK, key=None, hold_ms=None, button=None)


def test_no_indefinite_key_down_command_exists() -> None:
    values = {c.value for c in CommandType}
    assert values == {"key_tap", "key_hold", "mouse_move", "mouse_click", "release_all"}
    assert not any("down" in v or "press" in v for v in values)


# --------------------------------------------------------------------------- #
# Dry-run guarantee
# --------------------------------------------------------------------------- #
def test_dry_run_never_executes_even_when_armed(clock: FakeClock) -> None:
    actuator = DryRunActuator(clock)
    actuator.arm("test")
    result = actuator.submit(make_command(clock))
    assert result.outcome is CommandOutcome.REJECTED_DRY_RUN
    assert actuator.status().commands_executed == 0
    assert actuator.status().live is False


def test_unarmed_actuator_rejects_everything_but_release(clock: FakeClock) -> None:
    actuator = FakeActuator(clock)
    rejected = actuator.submit(make_command(clock))
    assert rejected.outcome is CommandOutcome.REJECTED_NOT_ARMED

    released = actuator.submit(
        release_all(reason="cleanup", state=ControlState.ABORT, now=clock.monotonic())
    )
    assert released.outcome is CommandOutcome.EXECUTED


def test_armed_fake_executes_and_releases_nothing_held(clock: FakeClock) -> None:
    actuator = FakeActuator(clock)
    actuator.arm("test")
    result = actuator.submit(make_command(clock))
    assert result.outcome is CommandOutcome.EXECUTED
    assert actuator.status().is_clean, "a bounded hold must not leave a key down"


# --------------------------------------------------------------------------- #
# Expiry, bounds, emergency stop
# --------------------------------------------------------------------------- #
def test_expired_command_is_rejected(clock: FakeClock) -> None:
    actuator = FakeActuator(clock)
    actuator.arm("test")
    command = make_command(clock)
    clock.advance(3.0)
    result = actuator.submit(command)
    assert result.outcome is CommandOutcome.REJECTED_EXPIRED
    assert actuator.status().commands_executed == 0


def test_command_outside_configured_bounds_is_rejected(clock: FakeClock) -> None:
    from pubg_training_bot.actuation.recording import RecordingActuator

    actuator = RecordingActuator(
        clock=clock,
        simulate_execution=True,
        command_bounds=CommandBounds(max_key_hold_ms=100),
    )
    actuator.arm("test")
    result = actuator.submit(make_command(clock, hold_ms=900))
    assert result.outcome is CommandOutcome.REJECTED_BOUNDS


def test_emergency_stop_blocks_further_commands_and_releases(clock: FakeClock) -> None:
    actuator = FakeActuator(clock)
    actuator.arm("test")
    actuator.emergency_stop("operator hotkey")

    result = actuator.submit(make_command(clock))
    assert result.outcome is CommandOutcome.REJECTED_PRECONDITION
    assert "emergency" in result.outcome_detail
    assert actuator.status().emergency_stopped
    assert actuator.status().is_clean
    assert actuator.arm("retry") is False, "arming must not clear an emergency stop"

    actuator.reset_emergency_stop("explicit reset")
    assert actuator.arm("retry") is True


def test_release_all_is_never_blocked_by_guards(clock: FakeClock) -> None:
    actuator = FakeActuator(
        clock,
        guards=[CallableGuard(name="never", predicate=lambda: False, failure_reason="denied")],
    )
    actuator.arm("test")
    blocked = actuator.submit(make_command(clock))
    assert blocked.outcome is CommandOutcome.REJECTED_PRECONDITION

    released = actuator.submit(
        release_all(reason="abort", state=ControlState.ABORT, now=clock.monotonic())
    )
    assert released.outcome is CommandOutcome.EXECUTED


def test_disarm_releases_controls(clock: FakeClock) -> None:
    actuator = FakeActuator(clock)
    actuator.arm("test")
    before = actuator.release_all_calls
    actuator.disarm("done")
    assert actuator.release_all_calls > before
    assert actuator.status().armed is False


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
def test_foreground_guard_blocks_when_game_is_not_focused(clock: FakeClock) -> None:
    focused = {"value": True}
    actuator = FakeActuator(clock, guards=[ForegroundGuard(lambda: focused["value"])])
    actuator.arm("test")
    assert actuator.submit(make_command(clock)).outcome is CommandOutcome.EXECUTED

    focused["value"] = False
    blocked = actuator.submit(make_command(clock))
    assert blocked.outcome is CommandOutcome.REJECTED_PRECONDITION
    assert "foreground" in blocked.outcome_detail


def test_sensor_guard_blocks_on_stale_data(clock: FakeClock, policy, expected) -> None:
    state = {"age": 0.2}

    def snapshot() -> SensorSnapshot:
        return SensorSnapshot(
            monotonic_ts=clock.monotonic(),
            bridge_health=BridgeHealth.CONNECTED,
            map_id="TRAINING",
            phase=MatchPhase.LANDED,
            view=ViewMode.FPP,
            stance=Stance.STANDING,
            free_view_active=False,
            foreground=True,
            raw_position=Vec3(x=0, y=0, z=0),
            location_age_s=state["age"],
            heading=HeadingReading(heading_deg=0.0, confidence=0.9, observed_at=clock.monotonic()),
        )

    actuator = FakeActuator(
        clock, guards=[SensorFreshnessGuard(snapshot, policy=policy, expected=expected)]
    )
    actuator.arm("test")
    assert actuator.submit(make_command(clock)).outcome is CommandOutcome.EXECUTED

    state["age"] = 30.0
    blocked = actuator.submit(make_command(clock))
    assert blocked.outcome is CommandOutcome.REJECTED_PRECONDITION
    assert "location_stale" in blocked.outcome_detail


def test_sensor_guard_blocks_when_no_snapshot_exists(clock: FakeClock, policy, expected) -> None:
    actuator = FakeActuator(
        clock, guards=[SensorFreshnessGuard(lambda: None, policy=policy, expected=expected)]
    )
    actuator.arm("test")
    result = actuator.submit(make_command(clock))
    assert result.outcome is CommandOutcome.REJECTED_PRECONDITION
    assert "no sensor snapshot" in result.outcome_detail


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
def test_no_live_actuator_is_registered_at_this_stage() -> None:
    assert live_actuator_available() is False
    assert all(descriptor.live is False for descriptor in list_actuators())
    with pytest.raises(NotImplementedError, match="Stage 3"):
        require_live_actuator()


def test_default_actuator_is_dry_run(clock: FakeClock) -> None:
    actuator = create_actuator(clock=clock)
    assert actuator.live is False
    actuator.arm("test")
    assert actuator.submit(make_command(clock)).outcome is CommandOutcome.REJECTED_DRY_RUN


def test_unknown_actuator_key_raises(clock: FakeClock) -> None:
    with pytest.raises(KeyError):
        create_actuator("sendinput", clock=clock)


def test_recording_actuator_cannot_be_constructed_live(clock: FakeClock) -> None:
    from pubg_training_bot.actuation.recording import RecordingActuator

    with pytest.raises(ValueError, match="never be live"):
        RecordingActuator(clock=clock, live=True)


def test_every_command_is_logged_with_an_outcome(clock: FakeClock) -> None:
    actuator = DryRunActuator(clock)
    actuator.submit(make_command(clock))  # not armed
    actuator.arm("test")
    actuator.submit(make_command(clock))  # dry-run
    assert len(actuator.log) == 2
    assert all(c.outcome is not CommandOutcome.PENDING for c in actuator.log)
    assert all(c.outcome_detail for c in actuator.log)
