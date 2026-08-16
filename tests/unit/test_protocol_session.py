"""Sequence and liveness handling.

The three cases are treated differently on purpose, and that asymmetry is the
whole point of these tests.
"""

from __future__ import annotations

from pubg_training_bot.domain.enums import BridgeHealth
from pubg_training_bot.protocol.session import SessionTracker


def tracker() -> SessionTracker:
    t = SessionTracker(stale_after_s=5.0)
    t.on_connect("session-a", now=100.0)
    return t


def test_first_frame_is_accepted() -> None:
    t = tracker()
    accepted, reason = t.accept(7, now=100.1)
    assert accepted
    assert "first" in reason
    assert t.messages_received == 1


def test_consecutive_frames_are_accepted() -> None:
    t = tracker()
    for seq in range(1, 6):
        assert t.accept(seq, now=100.0 + seq)[0]
    assert t.messages_received == 5
    assert t.sequence_gaps == 0


def test_duplicate_is_dropped_but_counted() -> None:
    """A reconnecting bridge legitimately replays its tail."""
    t = tracker()
    t.accept(1, now=100.1)
    accepted, reason = t.accept(1, now=100.2)
    assert not accepted
    assert "duplicate" in reason
    assert t.duplicates_dropped == 1
    assert t.messages_received == 1


def test_gap_is_accepted_but_counted() -> None:
    """Data that did arrive is still valid; refusing it would lose good samples."""
    t = tracker()
    t.accept(1, now=100.1)
    accepted, _ = t.accept(9, now=100.2)
    assert accepted
    assert t.sequence_gaps == 1
    assert t.messages_received == 2


def test_regression_is_rejected() -> None:
    """Going backwards means two bridges are interleaving into one controller."""
    t = tracker()
    t.accept(10, now=100.1)
    accepted, reason = t.accept(4, now=100.2)
    assert not accepted
    assert "regression" in reason
    assert "another bridge" in reason
    assert t.regressions_rejected == 1
    assert t.last_sequence == 10, "a rejected frame must not move the cursor"


def test_new_session_restarts_numbering() -> None:
    t = tracker()
    t.accept(500, now=100.1)
    t.on_connect("session-b", now=200.0)
    accepted, _ = t.accept(1, now=200.1)
    assert accepted, "a fresh session legitimately restarts at a low sequence"
    assert t.session_id == "session-b"


def test_health_transitions_through_stale_not_straight_to_disconnected() -> None:
    t = tracker()
    t.accept(1, now=100.0)
    assert t.health(now=101.0) is BridgeHealth.CONNECTED
    assert t.health(now=110.0) is BridgeHealth.STALE, "silence is stale, not disconnected"
    t.on_disconnect("socket closed")
    assert t.health(now=111.0) is BridgeHealth.DISCONNECTED


def test_status_snapshot_carries_the_counters() -> None:
    t = tracker()
    t.accept(1, now=100.1)
    t.accept(1, now=100.2)
    t.accept(9, now=100.3)
    t.feature_registration["location"] = True
    t.feature_registration["me"] = False
    status = t.status(now=100.4)
    assert status.messages_received == 2
    assert status.duplicates_dropped == 1
    assert status.sequence_gaps == 1
    assert status.feature_registration == {"location": True, "me": False}
    assert status.health is BridgeHealth.CONNECTED
