"""Sensor source interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from ..domain.bridge import BridgeMessage
from ..domain.enums import BridgeHealth
from ..domain.sensors import SensorSnapshot


class SensorSourceStatus(BaseModel):
    """Health of the underlying transport, independent of the data it carries."""

    model_config = ConfigDict(frozen=True)

    health: BridgeHealth = BridgeHealth.DISCONNECTED
    connected_since: float | None = None
    last_message_at: float | None = None
    messages_received: int = 0
    sequence_gaps: int = 0
    duplicates_dropped: int = 0
    parse_warnings: int = 0
    #: Per documented Overwolf feature: True registered, False refused.
    feature_registration: dict[str, bool] = {}
    detail: str = ""


@runtime_checkable
class SensorSource(Protocol):
    """Produces :class:`SensorSnapshot` values.

    Implementations must never invent data: a missing location stays ``None``
    so freshness evaluation can flag it, rather than being carried forward as
    if it were current.
    """

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def status(self) -> SensorSourceStatus:
        """Transport health; safe to call at any time."""
        ...

    def latest(self) -> SensorSnapshot | None:
        """Most recent snapshot, or ``None`` before the first one arrives."""
        ...

    def drain_messages(self) -> list[BridgeMessage]:
        """Raw messages received since the last call, for the run bundle."""
        ...


__all__ = ["SensorSource", "SensorSourceStatus"]
