"""Live sensor source backed by the Overwolf bridge.

Implements the same :class:`SensorSource` contract as the fake, so everything
downstream is unaware of which one it is talking to.

The rule that matters here: **last known values persist, but their age is
always truthful.** A location that stopped updating four seconds ago is still
reported, carrying ``location_age_s = 4.0``, so the freshness policy can reject
it. Nothing is ever refreshed just because a different feature updated.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from ..clock import Clock, SystemClock
from ..domain.bridge import BridgeMessage, ParseWarning
from ..domain.enums import MatchPhase, MessageType, MovementState, Stance, ViewMode
from ..domain.sensors import SensorSnapshot, Vec3
from ..protocol.envelope import BridgeFrame
from ..protocol.normalize import normalize_update
from ..protocol.server import BridgeServer, ServerConfig
from .base import SensorSourceStatus


@dataclass
class _State:
    """Last known value of each field, each with its own observation time."""

    position: Vec3 | None = None
    position_at: float | None = None
    #: Kept so the probe can measure the true update interval distribution.
    position_intervals: list[float] = field(default_factory=list)
    position_updates: int = 0

    map_id: str | None = None
    phase: MatchPhase = MatchPhase.UNKNOWN
    view: ViewMode = ViewMode.UNKNOWN
    stance: Stance = Stance.UNKNOWN
    movement: MovementState = MovementState.UNKNOWN
    free_view: bool | None = None

    observed_phases: set[str] = field(default_factory=set)
    observed_views: set[str] = field(default_factory=set)
    observed_maps: set[str] = field(default_factory=set)
    warnings: list[ParseWarning] = field(default_factory=list)


@dataclass
class OverwolfSensorSource:
    """Owns a :class:`BridgeServer` and turns its frames into snapshots."""

    config: ServerConfig
    clock: Clock = field(default_factory=SystemClock)
    #: Whether PUBG is the foreground window. Injected so this class stays
    #: testable and free of OS calls; Stage 2 supplies the real implementation.
    foreground_probe: object | None = None

    server: BridgeServer = field(init=False)
    _state: _State = field(default_factory=_State, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _messages: list[BridgeMessage] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.server = BridgeServer(config=self.config, clock=self.clock, on_frame=self._on_frame)

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self.server.start()

    def stop(self) -> None:
        self.server.stop()

    def status(self) -> SensorSourceStatus:
        return self.server.tracker.status(self.clock.monotonic())

    def drain_messages(self) -> list[BridgeMessage]:
        with self._lock:
            drained, self._messages = self._messages, []
        return drained

    # ------------------------------------------------------------------ #
    def _on_frame(self, frame: BridgeFrame, now: float) -> None:
        update = normalize_update(frame.raw)

        with self._lock:
            state = self._state
            if update.position is not None:
                if state.position_at is not None:
                    state.position_intervals.append(now - state.position_at)
                state.position = update.position
                state.position_at = now
                state.position_updates += 1
            if update.map_id is not None:
                state.map_id = update.map_id
                state.observed_maps.add(update.map_id)
            if update.phase is not None:
                state.phase = update.phase
                state.observed_phases.add(str(update.phase))
            if update.view is not None:
                state.view = update.view
                state.observed_views.add(str(update.view))
            if update.stance is not None:
                state.stance = update.stance
            if update.movement is not None:
                state.movement = update.movement
            if update.free_view is not None:
                state.free_view = update.free_view
            state.warnings.extend(update.warnings)

            self._messages.append(
                BridgeMessage(
                    sequence=frame.sequence,
                    session_id=self.server.tracker.session_id,
                    type=_message_type(frame.type),
                    source_timestamp=(frame.source_ts_ms / 1000.0 if frame.source_ts_ms else None),
                    bridge_monotonic_ts=frame.bridge_ts_ms / 1000.0,
                    controller_receive_ts=now,
                    raw=frame.raw,
                    normalized=frame.normalized,
                    parse_warnings=update.warnings,
                )
            )

        self.server.tracker.parse_warnings += len(update.warnings)

    def latest(self) -> SensorSnapshot | None:
        now = self.clock.monotonic()
        with self._lock:
            state = self._state
            if state.position_at is None and state.map_id is None:
                return None
            position = state.position
            position_at = state.position_at
            map_id = state.map_id
            phase, view, stance = state.phase, state.view, state.stance
            movement, free_view = state.movement, state.free_view

        return SensorSnapshot(
            monotonic_ts=now,
            bridge_health=self.server.tracker.health(now),
            map_id=map_id,
            phase=phase,
            view=view,
            stance=stance,
            movement=movement,
            free_view_active=free_view,
            foreground=self._foreground(),
            raw_position=position,
            # Age is measured from the last actual update, never reset by
            # unrelated features arriving.
            location_age_s=(None if position_at is None else max(0.0, now - position_at)),
            heading=None,  # Heading arrives in Stage 4; abstaining until then.
        )

    def _foreground(self) -> bool:
        probe = self.foreground_probe
        if probe is None:
            # Unknown, not True: Stage 2 supplies real window detection, and
            # asserting foreground here would weaken an actuation guard.
            return False
        return bool(probe())

    # ------------------------------------------------------------------ #
    def observations(self) -> dict[str, object]:
        """Everything the Stage 1 probe report needs."""
        with self._lock:
            state = self._state
            return {
                "position_updates": state.position_updates,
                "position_intervals": list(state.position_intervals),
                "observed_maps": sorted(state.observed_maps),
                "observed_phases": sorted(state.observed_phases),
                "observed_views": sorted(state.observed_views),
                "last_position": state.position.as_tuple() if state.position else None,
                "warnings": [w.model_dump(mode="json") for w in state.warnings],
            }


def _message_type(raw_type: str) -> MessageType:
    try:
        return MessageType(raw_type)
    except ValueError:
        return MessageType.UNKNOWN


__all__ = ["OverwolfSensorSource"]
