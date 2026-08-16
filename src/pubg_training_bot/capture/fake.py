"""Synthetic capture provider.

Generates deterministic frames without touching the screen, so vision and
controller tests never depend on a running game. It also models the failure
modes real providers exhibit: dropped grabs, black frames and duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..clock import Clock
from ..domain.profile import CropRegion, Rect
from .base import CaptureStatus, Frame


@dataclass
class FakeCaptureProvider:
    """Emits frames from a scripted list, cycling when exhausted."""

    clock: Clock
    width: int = 1920
    height: int = 1080
    name: str = "fake"
    #: Payload per frame; ``None`` entries simulate a failed grab.
    scripted_pixels: list[Any] | None = None
    #: 1-based indices (into the emitted sequence) that should be black.
    black_frame_indices: frozenset[int] = frozenset()
    duplicate_frame_indices: frozenset[int] = frozenset()
    available: bool = True

    _running: bool = field(default=False, init=False)
    #: Advances on every grab attempt, so a scripted failure does not stall the
    #: script on its own entry forever.
    _cursor: int = field(default=0, init=False)
    _count: int = field(default=0, init=False)
    _failed: int = field(default=0, init=False)
    _black: int = field(default=0, init=False)
    _duplicates: int = field(default=0, init=False)
    _last_frame: Frame | None = field(default=None, init=False)

    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        return self.available

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def status(self) -> CaptureStatus:
        now = self.clock.monotonic()
        return CaptureStatus(
            provider=self.name,
            available=self.available,
            running=self._running,
            frames_captured=self._count,
            frames_failed=self._failed,
            black_frames=self._black,
            duplicate_frames=self._duplicates,
            last_frame_age_s=(self._last_frame.age_seconds(now) if self._last_frame else None),
            window_found=True,
            window_foreground=True,
            window_rect=Rect(left=0, top=0, width=self.width, height=self.height),
            detail="synthetic frames; no screen access",
        )

    def grab(self) -> Frame | None:
        if not self._running:
            return None
        index = self._count + 1
        payload: Any = None
        if self.scripted_pixels:
            payload = self.scripted_pixels[self._cursor % len(self.scripted_pixels)]
            self._cursor += 1
            if payload is None:
                self._failed += 1
                return None
        else:
            self._cursor += 1

        is_black = index in self.black_frame_indices
        is_duplicate = index in self.duplicate_frame_indices
        self._count += 1
        if is_black:
            self._black += 1
        if is_duplicate:
            self._duplicates += 1

        frame = Frame(
            frame_id=f"{self.name}-{index:06d}",
            captured_at=self.clock.monotonic(),
            width=self.width,
            height=self.height,
            pixels=payload,
            source_rect=Rect(left=0, top=0, width=self.width, height=self.height),
            is_black=is_black,
            is_duplicate=is_duplicate,
            metadata={"synthetic": True, "index": index},
        )
        self._last_frame = frame
        return frame

    def crop(self, frame: Frame, region: CropRegion) -> Frame | None:
        rect = region.to_pixels(Rect(left=0, top=0, width=frame.width, height=frame.height))
        return Frame(
            frame_id=f"{frame.frame_id}-crop",
            captured_at=frame.captured_at,
            width=rect.width,
            height=rect.height,
            pixels=frame.pixels,
            source_rect=rect,
            metadata={**frame.metadata, "crop": region.model_dump(mode="json")},
        )


__all__ = ["FakeCaptureProvider"]
