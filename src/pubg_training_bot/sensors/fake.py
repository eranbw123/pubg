"""Scripted sensor source for deterministic tests and offline development."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..clock import Clock
from ..domain.bridge import BridgeMessage
from ..domain.enums import BridgeHealth, MatchPhase, MovementState, Stance, ViewMode
from ..domain.sensors import HeadingReading, SensorSnapshot, Vec3
from .base import SensorSourceStatus


@dataclass
class ScriptedSample:
    """One entry in a fake sensor timeline.

    ``at`` is a monotonic offset from source start. ``position=None`` models a
    dropped location update - which the controller must treat as staleness, not
    as "unchanged position".
    """

    at: float
    position: Vec3 | None = None
    heading_deg: float | None = None
    heading_confidence: float = 1.0
    foreground: bool = True
    map_id: str | None = "TRAINING"
    phase: MatchPhase = MatchPhase.LANDED
    view: ViewMode = ViewMode.FPP
    stance: Stance = Stance.STANDING
    movement: MovementState = MovementState.IDLE
    free_view_active: bool = False
    bridge_health: BridgeHealth = BridgeHealth.CONNECTED


@dataclass
class FakeSensorSource:
    """Replays a fixed timeline against an injected clock.

    Holds the last known position and reports its true age, exactly as a live
    source must: staleness is visible, never hidden.
    """

    clock: Clock
    samples: list[ScriptedSample] = field(default_factory=list)
    messages: list[BridgeMessage] = field(default_factory=list)

    _started_at: float | None = field(default=None, init=False)
    _cursor: int = field(default=0, init=False)
    _last_position: Vec3 | None = field(default=None, init=False)
    _last_position_at: float | None = field(default=None, init=False)
    _last_sample: ScriptedSample | None = field(default=None, init=False)
    _latest: SensorSnapshot | None = field(default=None, init=False)
    _pending: list[BridgeMessage] = field(default_factory=list, init=False)
    _running: bool = field(default=False, init=False)

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self._started_at = self.clock.monotonic()
        self._running = True
        self._pending = list(self.messages)

    def stop(self) -> None:
        self._running = False

    def status(self) -> SensorSourceStatus:
        health = (
            self._last_sample.bridge_health
            if self._last_sample
            else (BridgeHealth.CONNECTED if self._running else BridgeHealth.DISCONNECTED)
        )
        return SensorSourceStatus(
            health=health,
            connected_since=self._started_at,
            last_message_at=self._last_position_at,
            messages_received=self._cursor,
            detail="fake sensor source",
        )

    def latest(self) -> SensorSnapshot | None:
        self._pump()
        return self._latest

    def drain_messages(self) -> list[BridgeMessage]:
        drained, self._pending = self._pending, []
        return drained

    # ------------------------------------------------------------------ #
    def _pump(self) -> None:
        if not self._running or self._started_at is None:
            return
        now = self.clock.monotonic()
        elapsed = now - self._started_at

        while self._cursor < len(self.samples) and self.samples[self._cursor].at <= elapsed:
            sample = self.samples[self._cursor]
            self._cursor += 1
            self._last_sample = sample
            if sample.position is not None:
                self._last_position = sample.position
                self._last_position_at = self._started_at + sample.at

        sample = self._last_sample
        if sample is None:
            self._latest = None
            return

        heading = None
        if sample.heading_deg is not None:
            heading = HeadingReading(
                heading_deg=sample.heading_deg % 360.0,
                confidence=sample.heading_confidence,
                observed_at=self._started_at + sample.at,
                source="fake",
            )

        self._latest = SensorSnapshot(
            monotonic_ts=now,
            bridge_health=sample.bridge_health,
            map_id=sample.map_id,
            phase=sample.phase,
            view=sample.view,
            stance=sample.stance,
            movement=sample.movement,
            free_view_active=sample.free_view_active,
            foreground=sample.foreground,
            raw_position=self._last_position,
            location_age_s=(
                None if self._last_position_at is None else max(0.0, now - self._last_position_at)
            ),
            heading=heading,
        )


__all__ = ["FakeSensorSource", "ScriptedSample"]
