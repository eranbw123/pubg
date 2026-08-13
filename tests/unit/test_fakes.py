"""Fake providers.

These exist so every later stage can be developed and tested without the game
running. They must model the *failure* modes too - a fake that only ever
succeeds would hide exactly the bugs these tests need to catch.
"""

from __future__ import annotations

import pytest

from pubg_training_bot.capture import FakeCaptureProvider
from pubg_training_bot.clock import FakeClock, SystemClock, utc_stamp
from pubg_training_bot.domain.profile import CropRegion
from pubg_training_bot.domain.sensors import Vec3
from pubg_training_bot.sensors import FakeSensorSource, ScriptedSample
from pubg_training_bot.vision import FakeHeadingProvider, ScriptedHeading


# --------------------------------------------------------------------------- #
# Clock
# --------------------------------------------------------------------------- #
def test_fake_clock_advances_only_forward() -> None:
    clock = FakeClock(start=10.0)
    assert clock.monotonic() == 10.0
    clock.sleep(2.5)
    assert clock.monotonic() == 12.5
    with pytest.raises(ValueError):
        clock.advance(-1.0)


def test_fake_clock_wall_time_tracks_monotonic() -> None:
    clock = FakeClock()
    before = clock.wall_time()
    clock.advance(60.0)
    assert (clock.wall_time() - before).total_seconds() == pytest.approx(60.0)


def test_system_clock_is_monotonic_and_stamps() -> None:
    clock = SystemClock()
    first = clock.monotonic()
    assert clock.monotonic() >= first
    assert utc_stamp(clock).endswith("Z")


# --------------------------------------------------------------------------- #
# Sensor source
# --------------------------------------------------------------------------- #
def test_fake_sensor_source_replays_timeline(clock: FakeClock) -> None:
    source = FakeSensorSource(
        clock=clock,
        samples=[
            ScriptedSample(at=0.0, position=Vec3(x=0, y=0, z=0), heading_deg=0.0),
            ScriptedSample(at=1.0, position=Vec3(x=0, y=5, z=0), heading_deg=0.0),
        ],
    )
    assert source.latest() is None, "no data before start()"
    source.start()

    first = source.latest()
    assert first is not None
    assert first.raw_position == Vec3(x=0, y=0, z=0)
    assert first.location_age_s == pytest.approx(0.0)

    clock.advance(1.0)
    second = source.latest()
    assert second is not None
    assert second.raw_position == Vec3(x=0, y=5, z=0)


def test_dropped_location_update_ages_instead_of_freezing(clock: FakeClock) -> None:
    """A missing update must look stale, never like an unchanged position."""
    source = FakeSensorSource(
        clock=clock,
        samples=[
            ScriptedSample(at=0.0, position=Vec3(x=0, y=0, z=0), heading_deg=0.0),
            ScriptedSample(at=1.0, position=None, heading_deg=0.0),  # dropped update
        ],
    )
    source.start()
    clock.advance(4.0)
    snapshot = source.latest()
    assert snapshot is not None
    assert snapshot.raw_position == Vec3(x=0, y=0, z=0)
    assert snapshot.location_age_s == pytest.approx(4.0)


def test_sensor_source_status_and_message_drain(clock: FakeClock) -> None:
    source = FakeSensorSource(clock=clock, samples=[ScriptedSample(at=0.0)])
    assert source.status().health.value == "disconnected"
    source.start()
    assert source.status().health.value == "connected"
    assert source.drain_messages() == []
    source.stop()


# --------------------------------------------------------------------------- #
# Capture provider
# --------------------------------------------------------------------------- #
def test_fake_capture_provider_emits_frames_with_age(clock: FakeClock) -> None:
    provider = FakeCaptureProvider(clock=clock, width=1920, height=1080)
    assert provider.grab() is None, "no frames before start()"
    provider.start()

    frame = provider.grab()
    assert frame is not None
    assert (frame.width, frame.height) == (1920, 1080)
    clock.advance(0.25)
    assert frame.age_seconds(clock.monotonic()) == pytest.approx(0.25)


def test_failed_grab_returns_none_not_a_black_placeholder(clock: FakeClock) -> None:
    provider = FakeCaptureProvider(clock=clock, scripted_pixels=[None, "frame"])
    provider.start()
    assert provider.grab() is None
    assert provider.status().frames_failed == 1
    assert provider.grab() is not None


def test_black_and_duplicate_frames_are_flagged(clock: FakeClock) -> None:
    provider = FakeCaptureProvider(
        clock=clock, black_frame_indices=frozenset({1}), duplicate_frame_indices=frozenset({2})
    )
    provider.start()
    first = provider.grab()
    second = provider.grab()
    assert first is not None and first.is_black
    assert second is not None and second.is_duplicate
    status = provider.status()
    assert status.black_frames == 1
    assert status.duplicate_frames == 1


def test_crop_uses_normalised_coordinates(clock: FakeClock) -> None:
    provider = FakeCaptureProvider(clock=clock, width=1000, height=500)
    provider.start()
    frame = provider.grab()
    assert frame is not None
    crop = provider.crop(frame, CropRegion(x=0.1, y=0.2, width=0.5, height=0.25))
    assert crop is not None
    assert (crop.width, crop.height) == (500, 125)
    assert crop.source_rect is not None
    assert (crop.source_rect.left, crop.source_rect.top) == (100, 100)
    assert crop.captured_at == frame.captured_at, "a crop is as old as its frame"


# --------------------------------------------------------------------------- #
# Heading provider
# --------------------------------------------------------------------------- #
def test_heading_provider_abstains_instead_of_guessing(clock: FakeClock) -> None:
    capture = FakeCaptureProvider(clock=clock)
    capture.start()
    frame = capture.grab()
    assert frame is not None

    provider = FakeHeadingProvider(
        clock=clock,
        script=[ScriptedHeading(heading_deg=90.0, confidence=0.9), ScriptedHeading(None, 0.0)],
    )
    good = provider.read(frame)
    assert good is not None
    assert good.heading_deg == pytest.approx(90.0)

    assert provider.read(frame) is None
    status = provider.status()
    assert status.reads_accepted == 1
    assert status.reads_abstained == 1
    assert status.abstention_rate == pytest.approx(0.5)


def test_heading_provider_respects_confidence_floor(clock: FakeClock) -> None:
    capture = FakeCaptureProvider(clock=clock)
    capture.start()
    frame = capture.grab()
    assert frame is not None

    provider = FakeHeadingProvider(
        clock=clock,
        script=[ScriptedHeading(heading_deg=42.0, confidence=0.3)],
        min_confidence=0.6,
    )
    assert provider.read(frame) is None
    assert provider.status().reads_abstained == 1


def test_heading_reading_is_wrapped_into_range(clock: FakeClock) -> None:
    capture = FakeCaptureProvider(clock=clock)
    capture.start()
    frame = capture.grab()
    assert frame is not None
    provider = FakeHeadingProvider(clock=clock, script=[ScriptedHeading(heading_deg=725.0)])
    reading = provider.read(frame)
    assert reading is not None
    assert 0.0 <= reading.heading_deg < 360.0
    assert reading.heading_deg == pytest.approx(5.0)
