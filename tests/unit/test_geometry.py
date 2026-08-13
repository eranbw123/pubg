"""Angle and geometry maths.

The 0/359 seam is the single most likely place for a silent heading bug, so
wraparound is tested explicitly rather than incidentally.
"""

from __future__ import annotations

import math

import pytest

from pubg_training_bot.domain.geometry import (
    angle_abs_diff,
    angle_diff,
    angles_close,
    circular_mean,
    circular_median_filter,
    circular_stats,
    cross_track_error,
    perpendicular_distance_to_line,
    project_on_segment,
    wrap_deg,
    wrap_signed,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (359.9, 359.9), (360, 0), (361, 1), (-1, 359), (-360, 0), (720.5, 0.5)],
)
def test_wrap_deg(value: float, expected: float) -> None:
    assert wrap_deg(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (179, 179), (180, -180), (181, -179), (-181, 179), (359, -1)],
)
def test_wrap_signed(value: float, expected: float) -> None:
    assert wrap_signed(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("target", "current", "expected"),
    [
        (10, 350, 20),  # crosses north forwards
        (350, 10, -20),  # crosses north backwards
        (0, 180, -180),
        (90, 0, 90),
        (0, 90, -90),
    ],
)
def test_angle_diff_takes_the_short_way(target: float, current: float, expected: float) -> None:
    assert angle_diff(target, current) == pytest.approx(expected)


def test_angle_diff_never_exceeds_half_turn() -> None:
    for target in range(0, 360, 7):
        for current in range(0, 360, 11):
            assert -180.0 <= angle_diff(target, current) < 180.0


def test_angle_abs_diff_symmetric() -> None:
    for a in range(0, 360, 13):
        for b in range(0, 360, 17):
            assert angle_abs_diff(a, b) == pytest.approx(angle_abs_diff(b, a))
            assert 0.0 <= angle_abs_diff(a, b) <= 180.0


def test_angles_close_across_north() -> None:
    assert angles_close(359.0, 1.0, tolerance_deg=3.0)
    assert not angles_close(359.0, 5.0, tolerance_deg=3.0)
    with pytest.raises(ValueError):
        angles_close(0.0, 0.0, tolerance_deg=-1.0)


def test_circular_mean_across_north_beats_linear_average() -> None:
    samples = [358.0, 359.0, 0.0, 1.0, 2.0]
    mean = circular_mean(samples)
    assert mean is not None
    assert angle_abs_diff(mean, 0.0) < 0.5
    # A linear average would land near 144 degrees - the bug this guards.
    assert abs(sum(samples) / len(samples) - mean) > 100


def test_circular_mean_of_opposites_is_undefined() -> None:
    assert circular_mean([0.0, 180.0]) is None
    stats = circular_stats([0.0, 180.0])
    assert not stats.is_meaningful
    assert stats.std_deg == math.inf


def test_circular_mean_empty_and_weighted() -> None:
    assert circular_mean([]) is None
    weighted = circular_mean([0.0, 90.0], weights=[9.0, 1.0])
    assert weighted is not None
    assert weighted < 15.0  # pulled strongly toward the heavy sample

    with pytest.raises(ValueError):
        circular_mean([0.0, 90.0], weights=[1.0])
    with pytest.raises(ValueError):
        circular_mean([0.0], weights=[-1.0])


def test_circular_stats_resultant_reflects_agreement() -> None:
    tight = circular_stats([10.0, 11.0, 9.0])
    loose = circular_stats([10.0, 120.0, 250.0])
    assert tight.resultant > 0.99
    assert loose.resultant < tight.resultant
    assert tight.std_deg < loose.std_deg


def test_circular_median_filter_rejects_outlier_and_keeps_real_values() -> None:
    samples = [10.0, 11.0, 200.0, 12.0, 11.0]
    filtered = circular_median_filter(samples, window=3)
    assert len(filtered) == len(samples)
    assert filtered[2] != 200.0
    # Output values are always samples that were actually observed.
    assert set(filtered).issubset(set(samples))


def test_circular_median_filter_handles_wraparound() -> None:
    samples = [359.0, 0.0, 1.0, 180.0, 0.5]
    filtered = circular_median_filter(samples, window=3)
    assert filtered[3] != 180.0
    with pytest.raises(ValueError):
        circular_median_filter(samples, window=0)


def test_cross_track_error_on_and_off_segment() -> None:
    assert cross_track_error(5, 0, 0, 0, 10, 0) == pytest.approx(0.0)
    assert cross_track_error(5, 3, 0, 0, 10, 0) == pytest.approx(3.0)
    # Beyond the endpoint the distance is to the endpoint, not the infinite line.
    assert cross_track_error(20, 0, 0, 0, 10, 0) == pytest.approx(10.0)
    assert perpendicular_distance_to_line(20, 0, 0, 0, 10, 0) == pytest.approx(0.0)


def test_cross_track_error_degenerate_segment() -> None:
    assert cross_track_error(3, 4, 1, 1, 1, 1) == pytest.approx(math.hypot(2, 3))


def test_project_on_segment_clamps() -> None:
    t, x, y = project_on_segment(5, 5, 0, 0, 10, 0)
    assert (t, x, y) == pytest.approx((0.5, 5.0, 0.0))
    t, x, y = project_on_segment(-5, 0, 0, 0, 10, 0)
    assert t == pytest.approx(0.0)
    t, x, y = project_on_segment(50, 0, 0, 0, 10, 0)
    assert t == pytest.approx(1.0)
