"""Angle and 2D geometry primitives.

Heading is a compass bearing in degrees: 0 = north, increasing clockwise, so
90 = east. Every angular operation in the codebase must go through this module
- linear averaging around the 0/359 seam is a known source of silent failure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FULL_TURN = 360.0


def wrap_deg(angle: float) -> float:
    """Wrap to ``[0, 360)``."""
    return angle % FULL_TURN


def wrap_signed(angle: float) -> float:
    """Wrap to ``[-180, 180)``."""
    return (angle + 180.0) % FULL_TURN - 180.0


def angle_diff(target: float, current: float) -> float:
    """Signed shortest rotation from ``current`` to ``target``, in ``[-180, 180)``.

    Positive means "turn clockwise" (increasing compass bearing).
    """
    return wrap_signed(target - current)


def angle_abs_diff(a: float, b: float) -> float:
    """Absolute angular distance in ``[0, 180]``."""
    return abs(wrap_signed(a - b))


def angles_close(a: float, b: float, tolerance_deg: float) -> bool:
    if tolerance_deg < 0:
        raise ValueError("tolerance_deg must be >= 0")
    return angle_abs_diff(a, b) <= tolerance_deg


@dataclass(frozen=True)
class CircularStats:
    """Result of a circular average.

    ``resultant`` is the mean vector length in ``[0, 1]``: 1 means all samples
    agree, 0 means they cancel out and ``mean`` is meaningless.
    """

    mean: float
    resultant: float
    count: int

    @property
    def is_meaningful(self) -> bool:
        return self.count > 0 and self.resultant > 1e-9

    @property
    def std_deg(self) -> float:
        """Circular standard deviation in degrees (inf when samples cancel)."""
        if not self.is_meaningful:
            return math.inf
        return math.degrees(math.sqrt(-2.0 * math.log(self.resultant)))


def circular_stats(
    angles_deg: list[float] | tuple[float, ...],
    weights: list[float] | tuple[float, ...] | None = None,
) -> CircularStats:
    """Weighted circular mean. Never use ``statistics.mean`` on headings."""
    n = len(angles_deg)
    if n == 0:
        return CircularStats(mean=0.0, resultant=0.0, count=0)
    if weights is None:
        weights = [1.0] * n
    if len(weights) != n:
        raise ValueError("weights length must match angles length")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    total = sum(weights)
    if total <= 0:
        return CircularStats(mean=0.0, resultant=0.0, count=n)

    sin_sum = sum(w * math.sin(math.radians(a)) for a, w in zip(angles_deg, weights, strict=True))
    cos_sum = sum(w * math.cos(math.radians(a)) for a, w in zip(angles_deg, weights, strict=True))
    resultant = math.hypot(sin_sum, cos_sum) / total
    if resultant <= 1e-12:
        return CircularStats(mean=0.0, resultant=0.0, count=n)
    mean = wrap_deg(math.degrees(math.atan2(sin_sum, cos_sum)))
    return CircularStats(mean=mean, resultant=resultant, count=n)


def circular_mean(
    angles_deg: list[float] | tuple[float, ...],
    weights: list[float] | tuple[float, ...] | None = None,
) -> float | None:
    """Circular mean in ``[0, 360)``, or ``None`` when undefined."""
    stats = circular_stats(angles_deg, weights)
    return stats.mean if stats.is_meaningful else None


def circular_median_filter(angles_deg: list[float], window: int = 3) -> list[float]:
    """Median-like circular smoothing: each output is the sample in the window
    closest to that window's circular mean. Keeps values real (no invented
    intermediate angles) while rejecting single-sample outliers."""
    if window < 1:
        raise ValueError("window must be >= 1")
    if not angles_deg:
        return []
    half = window // 2
    out: list[float] = []
    for i in range(len(angles_deg)):
        lo = max(0, i - half)
        hi = min(len(angles_deg), i + half + 1)
        chunk = angles_deg[lo:hi]
        mean = circular_mean(chunk)
        if mean is None:
            out.append(angles_deg[i])
        else:
            out.append(min(chunk, key=lambda a: angle_abs_diff(a, mean)))
    return out


# --------------------------------------------------------------------------- #
# Planar geometry (route following)
# --------------------------------------------------------------------------- #
def distance_2d(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(bx - ax, by - ay)


def cross_track_error(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    """Perpendicular distance from point P to the *segment* A->B.

    Returns distance to the nearest endpoint when the projection falls outside
    the segment, which is what a waypoint follower actually needs.
    """
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return distance_2d(px, py, ax, ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    return distance_2d(px, py, ax + t * dx, ay + t * dy)


def project_on_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> tuple[float, float, float]:
    """Return ``(t, x, y)``: clamped projection parameter and projected point."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return 0.0, ax, ay
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    return t, ax + t * dx, ay + t * dy


def perpendicular_distance_to_line(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    """Distance from P to the infinite line A-B (used by Douglas-Peucker)."""
    dx, dy = bx - ax, by - ay
    denom = math.hypot(dx, dy)
    if denom <= 1e-12:
        return distance_2d(px, py, ax, ay)
    return abs(dy * (px - ax) - dx * (py - ay)) / denom


__all__ = [
    "FULL_TURN",
    "CircularStats",
    "angle_abs_diff",
    "angle_diff",
    "angles_close",
    "circular_mean",
    "circular_median_filter",
    "circular_stats",
    "cross_track_error",
    "distance_2d",
    "perpendicular_distance_to_line",
    "project_on_segment",
    "wrap_deg",
    "wrap_signed",
]
