"""Shared fixtures.

Two guarantees enforced here for every test in the suite:

* the default actuator is a non-live one, and
* no test may construct a live actuator, because none is registered.
"""

from __future__ import annotations

import pytest

from pubg_training_bot.actuation import DryRunActuator, FakeActuator
from pubg_training_bot.clock import FakeClock
from pubg_training_bot.config.paths import ProjectPaths, find_repo_root
from pubg_training_bot.domain.enums import MatchPhase, Stance, ViewMode
from pubg_training_bot.domain.sensors import ExpectedContext, FreshnessPolicy


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(start=1000.0)


@pytest.fixture
def dry_run_actuator(clock: FakeClock):
    return DryRunActuator(clock)


@pytest.fixture
def fake_actuator(clock: FakeClock):
    return FakeActuator(clock)


@pytest.fixture
def policy() -> FreshnessPolicy:
    return FreshnessPolicy(
        max_location_age_s=2.5,
        max_heading_age_s=0.6,
        max_frame_age_s=0.5,
        min_heading_confidence=0.6,
    )


@pytest.fixture
def expected() -> ExpectedContext:
    return ExpectedContext(
        map_id="TRAINING",
        view=ViewMode.FPP,
        stance=Stance.STANDING,
        phases=(MatchPhase.PLAYING,),
    )


@pytest.fixture
def repo_paths() -> ProjectPaths:
    return ProjectPaths(root=find_repo_root())


@pytest.fixture
def tmp_paths(tmp_path) -> ProjectPaths:
    """Isolated project tree so tests never mutate the real repo."""
    paths = ProjectPaths(root=tmp_path)
    for directory in (paths.config_dir, paths.docs_dir, paths.schemas_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return paths
