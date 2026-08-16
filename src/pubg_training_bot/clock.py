"""Clock abstraction.

Control decisions use a **monotonic** clock only: wall-clock time can jump
backwards (NTP, DST) and a heading-staleness check that goes negative is a
silent safety failure. Wall clock is used solely for human-readable stamps.

Tests inject :class:`FakeClock` so timing behaviour is deterministic rather
than dependent on real sleeps.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Time source for every timing decision in the controller."""

    def monotonic(self) -> float:
        """Seconds from an arbitrary origin; never decreases."""
        ...

    def wall_time(self) -> datetime:
        """Timezone-aware wall clock, for logs and filenames only."""
        ...

    def sleep(self, seconds: float) -> None:
        """Block for approximately ``seconds``."""
        ...


class SystemClock:
    """Real clock, used at runtime."""

    def monotonic(self) -> float:
        return time.monotonic()

    def wall_time(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class FakeClock:
    """Deterministic clock. ``sleep`` advances time instead of blocking."""

    def __init__(self, start: float = 1000.0, wall_start: datetime | None = None) -> None:
        self._monotonic = float(start)
        self._wall = wall_start or datetime(2026, 1, 1, tzinfo=UTC)

    def monotonic(self) -> float:
        return self._monotonic

    def wall_time(self) -> datetime:
        return self._wall

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("FakeClock cannot move backwards")
        self._monotonic += seconds
        self._wall = self._wall.fromtimestamp(self._wall.timestamp() + seconds, tz=UTC)
        return self._monotonic


def utc_stamp(clock: Clock) -> str:
    """Filesystem-safe UTC stamp, e.g. ``20260813T142530Z``."""
    return clock.wall_time().strftime("%Y%m%dT%H%M%SZ")


__all__ = ["Clock", "FakeClock", "SystemClock", "utc_stamp"]
