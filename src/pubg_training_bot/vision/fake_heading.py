"""Scripted heading provider for deterministic tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..capture.base import Frame
from ..clock import Clock
from ..domain.sensors import HeadingReading
from .heading import HeadingProviderStatus


@dataclass(frozen=True)
class ScriptedHeading:
    """One scripted read. ``heading_deg=None`` models an abstention (the
    provider saw the frame but did not trust what it read)."""

    heading_deg: float | None
    confidence: float = 1.0


@dataclass
class FakeHeadingProvider:
    """Returns scripted readings in order, cycling when exhausted."""

    clock: Clock
    script: list[ScriptedHeading] = field(default_factory=list)
    name: str = "fake-heading"
    available: bool = True
    #: Reads below this confidence abstain, mirroring the real provider's rule.
    min_confidence: float = 0.0

    _attempted: int = field(default=0, init=False)
    _accepted: int = field(default=0, init=False)
    _abstained: int = field(default=0, init=False)
    _last_confidence: float | None = field(default=None, init=False)

    def is_available(self) -> bool:
        return self.available

    def status(self) -> HeadingProviderStatus:
        return HeadingProviderStatus(
            provider=self.name,
            available=self.available,
            reads_attempted=self._attempted,
            reads_accepted=self._accepted,
            reads_abstained=self._abstained,
            last_confidence=self._last_confidence,
            detail="scripted heading; no pixels inspected",
        )

    def read(self, frame: Frame) -> HeadingReading | None:
        entry = (
            self.script[self._attempted % len(self.script)]
            if self.script
            else ScriptedHeading(heading_deg=None, confidence=0.0)
        )
        self._attempted += 1
        self._last_confidence = entry.confidence

        if entry.heading_deg is None or entry.confidence < self.min_confidence:
            self._abstained += 1
            return None

        self._accepted += 1
        return HeadingReading(
            heading_deg=entry.heading_deg % 360.0,
            confidence=entry.confidence,
            observed_at=frame.captured_at,
            source=self.name,
        )


__all__ = ["FakeHeadingProvider", "ScriptedHeading"]
