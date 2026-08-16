"""Heading provider interface.

Heading is the project's highest-risk signal (Stage 4 is an explicit go/no-go
gate), so the contract makes abstention the normal, first-class outcome:
``read()`` returns ``None`` when the provider cannot see a bearing it trusts.
No implementation may substitute a guess.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..capture.base import Frame
from ..domain.sensors import HeadingReading


class HeadingProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    available: bool = False
    reads_attempted: int = 0
    reads_accepted: int = 0
    reads_abstained: int = 0
    last_confidence: float | None = None
    #: Path to the last diagnostic crop written to disk, when enabled.
    last_crop_path: str | None = None
    detail: str = ""
    warnings: list[str] = Field(default_factory=list)

    @property
    def abstention_rate(self) -> float | None:
        if self.reads_attempted == 0:
            return None
        return self.reads_abstained / self.reads_attempted


@runtime_checkable
class HeadingProvider(Protocol):
    """Turns a frame into a compass bearing, or abstains."""

    name: str

    def is_available(self) -> bool: ...

    def status(self) -> HeadingProviderStatus: ...

    def read(self, frame: Frame) -> HeadingReading | None:
        """Bearing in ``[0, 360)`` with confidence, or ``None`` to abstain."""
        ...


__all__ = ["HeadingProvider", "HeadingProviderStatus"]
