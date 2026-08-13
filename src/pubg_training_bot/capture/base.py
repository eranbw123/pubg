"""Capture provider interface.

A :class:`Frame` carries its own capture timestamp. "How old is this pixel
data" is a control-safety question, so the age travels with the frame rather
than being assumed to be zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..domain.profile import CropRegion, Rect


@dataclass(frozen=True)
class Frame:
    """One captured image.

    ``pixels`` is intentionally untyped at this layer: Stage 0 has no numpy
    dependency, and providers may hand back a numpy array, a raw buffer or a
    synthetic stand-in. Consumers assert what they need.
    """

    frame_id: str
    #: Controller monotonic seconds at capture time.
    captured_at: float
    width: int
    height: int
    pixels: Any = None
    source_rect: Rect | None = None
    #: True when the provider itself detected a degenerate frame.
    is_black: bool = False
    is_duplicate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def age_seconds(self, now_monotonic: float) -> float:
        return max(0.0, now_monotonic - self.captured_at)


class CaptureStatus(BaseModel):
    """Provider health, surfaced in the live status view and run reports."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    available: bool = False
    running: bool = False
    frames_captured: int = 0
    frames_failed: int = 0
    black_frames: int = 0
    duplicate_frames: int = 0
    effective_fps: float | None = None
    last_frame_age_s: float | None = None
    window_found: bool = False
    window_foreground: bool = False
    window_rect: Rect | None = None
    detail: str = ""
    warnings: list[str] = Field(default_factory=list)


@runtime_checkable
class CaptureProvider(Protocol):
    """Pull-based frame source."""

    name: str

    def is_available(self) -> bool:
        """Whether this provider can run on this machine right now."""
        ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def status(self) -> CaptureStatus: ...

    def grab(self) -> Frame | None:
        """Newest frame, or ``None`` when no valid frame is available.

        Returning ``None`` is required behaviour for a failed capture; a black
        placeholder frame would be indistinguishable from a real black screen.
        """
        ...

    def crop(self, frame: Frame, region: CropRegion) -> Frame | None:
        """Extract a normalised HUD region from ``frame``."""
        ...


__all__ = ["CaptureProvider", "CaptureStatus", "Frame"]
