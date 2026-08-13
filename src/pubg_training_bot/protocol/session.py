"""Per-connection stream health.

Sequence handling is deliberately asymmetric:

* a **duplicate** (same sequence again) is dropped quietly-but-counted, because
  a reconnecting bridge legitimately replays its tail;
* a **gap** (sequence jumps forward) is accepted and counted, because the data
  that did arrive is still valid and refusing it would lose good samples;
* a **regression** (sequence goes backwards without a session change) is
  rejected, because it means two bridges are talking to one controller and
  interleaving their streams would silently corrupt the trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import BridgeHealth
from ..sensors.base import SensorSourceStatus


@dataclass
class SessionTracker:
    """Tracks one bridge session's sequence stream and liveness."""

    #: A frame older than this makes the stream STALE (not disconnected).
    stale_after_s: float = 5.0

    session_id: str = ""
    connected_at: float | None = None
    last_frame_at: float | None = None
    last_sequence: int | None = None

    messages_received: int = 0
    duplicates_dropped: int = 0
    sequence_gaps: int = 0
    regressions_rejected: int = 0
    parse_warnings: int = 0
    feature_registration: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    _connected: bool = field(default=False, init=False)

    # ------------------------------------------------------------------ #
    def on_connect(self, session_id: str, now: float) -> None:
        """Reset per-session counters. A new session legitimately restarts
        sequence numbering at zero."""
        self.session_id = session_id
        self.connected_at = now
        self.last_frame_at = now
        self.last_sequence = None
        self._connected = True

    def on_disconnect(self, detail: str = "") -> None:
        self._connected = False
        self.detail = detail

    def accept(self, sequence: int, now: float) -> tuple[bool, str]:
        """Decide whether a frame should be processed.

        Returns ``(accepted, reason)``. Rejected frames are still counted, so
        the run report shows what was discarded and why.
        """
        self.last_frame_at = now
        if self.last_sequence is None:
            self.last_sequence = sequence
            self.messages_received += 1
            return True, "first frame"

        if sequence == self.last_sequence:
            self.duplicates_dropped += 1
            return False, "duplicate sequence"
        if sequence < self.last_sequence:
            self.regressions_rejected += 1
            return False, (
                f"sequence regression {sequence} < {self.last_sequence}; "
                "another bridge may be connected"
            )
        if sequence > self.last_sequence + 1:
            self.sequence_gaps += 1

        self.last_sequence = sequence
        self.messages_received += 1
        return True, "ok"

    def health(self, now: float) -> BridgeHealth:
        if not self._connected:
            return BridgeHealth.DISCONNECTED
        if self.last_frame_at is None:
            return BridgeHealth.CONNECTING
        if now - self.last_frame_at > self.stale_after_s:
            return BridgeHealth.STALE
        return BridgeHealth.CONNECTED

    def status(self, now: float) -> SensorSourceStatus:
        return SensorSourceStatus(
            health=self.health(now),
            connected_since=self.connected_at,
            last_message_at=self.last_frame_at,
            messages_received=self.messages_received,
            sequence_gaps=self.sequence_gaps,
            duplicates_dropped=self.duplicates_dropped,
            parse_warnings=self.parse_warnings,
            feature_registration=dict(self.feature_registration),
            detail=self.detail,
        )


__all__ = ["SessionTracker"]
