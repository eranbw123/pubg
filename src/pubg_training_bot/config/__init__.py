"""Configuration: paths, settings model and YAML loading."""

from .loader import (
    ConfigError,
    deep_merge,
    load_config,
    load_game_profile,
    load_route,
    read_yaml,
)
from .paths import ProjectPaths, default_paths, find_repo_root
from .settings import (
    AppConfig,
    BridgeSettings,
    CaptureSettings,
    HotkeySettings,
    LoggingSettings,
    NavigationSettings,
    SafetySettings,
)

__all__ = [
    "AppConfig",
    "BridgeSettings",
    "CaptureSettings",
    "ConfigError",
    "HotkeySettings",
    "LoggingSettings",
    "NavigationSettings",
    "ProjectPaths",
    "SafetySettings",
    "deep_merge",
    "default_paths",
    "find_repo_root",
    "load_config",
    "load_game_profile",
    "load_route",
    "read_yaml",
]
