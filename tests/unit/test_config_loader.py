"""Configuration loading.

A typo in a threshold name must fail loudly, because the silent alternative is
an operator believing they raised a safety margin that never changed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pubg_training_bot.config import (
    ConfigError,
    deep_merge,
    load_config,
    load_game_profile,
    load_route,
)
from pubg_training_bot.config.paths import ProjectPaths, find_repo_root


def test_shipped_default_config_loads(repo_paths: ProjectPaths) -> None:
    config = load_config(paths=repo_paths)
    assert config.version == 1
    assert config.safety.dry_run is True, "dry-run must be the shipped default"
    assert config.bridge.host == "127.0.0.1"
    assert config.freshness.provisional is True


def test_default_config_declares_its_unmeasured_values(repo_paths: ProjectPaths) -> None:
    pending = load_config(paths=repo_paths).provisional_values()
    assert any("freshness" in p for p in pending)
    assert any("capture provider" in p for p in pending)
    assert any("route" in p for p in pending)


def test_overrides_are_applied(repo_paths: ProjectPaths) -> None:
    config = load_config(paths=repo_paths, overrides={"safety": {"dry_run": False}})
    assert config.safety.dry_run is False
    # Sibling keys survive a partial override.
    assert config.safety.require_foreground is True


def test_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 1\nsafty:\n  dry_run: false\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid configuration"):
        load_config(bad)


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: [1, 2\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(bad)


def test_non_mapping_document_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "list.yaml"
    bad.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(bad)


def test_out_of_range_value_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "cfg.yaml"
    bad.write_text("version: 1\nfreshness:\n  max_location_age_s: -1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad)


def test_deep_merge_semantics() -> None:
    base = {"a": {"b": 1, "c": 2}, "list": [1, 2]}
    override = {"a": {"c": 3}, "list": [9]}
    merged = deep_merge(base, override)
    assert merged == {"a": {"b": 1, "c": 3}, "list": [9]}
    assert base == {"a": {"b": 1, "c": 2}, "list": [1, 2]}, "merge must not mutate its input"


def test_game_profile_loads_by_name(repo_paths: ProjectPaths) -> None:
    profile = load_game_profile("dev-1080p-fpp", paths=repo_paths)
    assert profile.profile_id == "dev-1080p-fpp"
    assert (profile.screen_width, profile.screen_height) == (1920, 1080)
    assert profile.fingerprint.startswith("gp1:")


def test_missing_route_is_reported(repo_paths: ProjectPaths) -> None:
    with pytest.raises(ConfigError, match="route not found"):
        load_route("no-such-route", paths=repo_paths)


def test_repo_root_discovery_finds_the_project(repo_paths: ProjectPaths) -> None:
    root = find_repo_root()
    assert (root / "pyproject.toml").exists()
    assert repo_paths.config_dir.exists()
    assert repo_paths.docs_dir.exists()


def test_repo_root_can_be_overridden_by_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PUBG_BOT_ROOT", str(tmp_path))
    assert find_repo_root() == tmp_path.resolve()


def test_ensure_runtime_dirs_creates_ignored_local_tree(tmp_path: Path) -> None:
    paths = ProjectPaths(root=tmp_path)
    created = paths.ensure_runtime_dirs()
    assert created, "first call must create directories"
    assert paths.runs_dir.exists()
    assert paths.captures_dir.exists()
    assert paths.ensure_runtime_dirs() == [], "second call must be a no-op"
