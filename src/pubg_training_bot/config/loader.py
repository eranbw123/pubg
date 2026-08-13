"""YAML loading for config, game profiles and routes.

Unknown keys are rejected (``extra="forbid"`` on the models): a typo in a
threshold name must fail loudly at load time, not silently leave the default in
place while the operator believes they changed it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..domain.profile import GameProfile
from ..domain.route import Route
from .paths import ProjectPaths, default_paths
from .settings import AppConfig


class ConfigError(RuntimeError):
    """Raised for a missing or invalid configuration document."""


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return loaded


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge; ``override`` wins. Lists are replaced, not concatenated."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    path: Path | None = None,
    *,
    overrides: dict[str, Any] | None = None,
    paths: ProjectPaths | None = None,
) -> AppConfig:
    """Load ``config/default.yaml`` (or ``path``) with optional overrides."""
    paths = paths or default_paths()
    source = path or (paths.config_dir / "default.yaml")
    data = read_yaml(source)
    if overrides:
        data = deep_merge(data, overrides)
    try:
        return AppConfig.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise ConfigError(f"invalid configuration in {source}:\n{exc}") from exc


def load_game_profile(
    name_or_path: str | Path,
    *,
    paths: ProjectPaths | None = None,
) -> GameProfile:
    paths = paths or default_paths()
    candidate = Path(name_or_path)
    if not candidate.suffix:
        candidate = paths.game_profiles_dir / f"{name_or_path}.yaml"
    elif not candidate.is_absolute() and not candidate.exists():
        candidate = paths.game_profiles_dir / candidate
    data = read_yaml(candidate)
    try:
        return GameProfile.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"invalid game profile in {candidate}:\n{exc}") from exc


def load_route(name_or_path: str | Path, *, paths: ProjectPaths | None = None) -> Route:
    """Load a route from ``config/routes`` or ``data/local/routes``."""
    paths = paths or default_paths()
    candidate = Path(name_or_path)
    if not candidate.exists() and not candidate.suffix:
        for directory in (paths.routes_config_dir, paths.routes_dir):
            for suffix in (".yaml", ".json"):
                trial = directory / f"{name_or_path}{suffix}"
                if trial.exists():
                    candidate = trial
                    break
            if candidate.exists():
                break
    if not candidate.exists():
        raise ConfigError(f"route not found: {name_or_path}")

    if candidate.suffix == ".json":
        import json

        data = json.loads(candidate.read_text(encoding="utf-8"))
    else:
        data = read_yaml(candidate)
    try:
        return Route.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"invalid route in {candidate}:\n{exc}") from exc


__all__ = [
    "ConfigError",
    "deep_merge",
    "load_config",
    "load_game_profile",
    "load_route",
    "read_yaml",
]
