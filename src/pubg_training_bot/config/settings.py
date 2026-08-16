"""Application configuration model.

Every threshold that affects safety or control lives here, never as a literal
in control code. Thresholds that have not yet been measured against the real
game are marked ``provisional`` so reports can say so out loud.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..domain.sensors import FreshnessPolicy


class SafetySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    #: Dry-run is the default everywhere; ``--live`` is required to change it.
    dry_run: bool = True
    #: Live runs additionally require an explicit Training-Mode acknowledgement.
    require_training_mode_ack: bool = True
    require_foreground: bool = True
    #: Watchdog: no fresh sensor data for this long releases all controls.
    watchdog_timeout_s: float = Field(default=2.0, gt=0)
    max_run_duration_s: float = Field(default=600.0, gt=0)


class HotkeySettings(BaseModel):
    """Global hotkeys. Registered by the controller in later stages; declared
    now so the key map is reviewable in one place."""

    model_config = ConfigDict(frozen=True)

    arm: str = "f9"
    emergency_stop: str = "f10"
    marker_route_start: str = "f5"
    marker_checkpoint: str = "f6"
    marker_door: str = "f7"
    marker_loot: str = "f8"
    marker_stair_start: str = "ctrl+f5"
    marker_stair_end: str = "ctrl+f6"
    marker_room_transition: str = "ctrl+f7"
    marker_route_end: str = "ctrl+f8"
    cancel_recording: str = "ctrl+f12"


class BridgeSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    #: Loopback only. Never bind to a routable interface.
    host: str = "127.0.0.1"
    port: int = Field(default=17311, gt=1024, lt=65536)
    #: Empty means "generate a fresh session token at startup".
    session_token: str = ""
    heartbeat_interval_s: float = Field(default=1.0, gt=0)
    heartbeat_timeout_s: float = Field(default=5.0, gt=0)
    reconnect_backoff_s: float = Field(default=1.0, gt=0)


class CaptureSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "none"
    target_fps: float = Field(default=8.0, gt=0)
    save_full_frames_on: tuple[str, ...] = ("state_change", "semantic_node", "failure")
    periodic_full_frame_interval_s: float = Field(default=10.0, gt=0)


class NavigationSettings(BaseModel):
    """Placeholders until Stage 6 implements the controller; kept here so the
    numbers are configuration from the first line of that stage."""

    model_config = ConfigDict(frozen=True)

    tick_interval_s: float = Field(default=0.1, gt=0)
    heading_align_tolerance_deg: float = Field(default=8.0, gt=0)
    critical_heading_tolerance_deg: float = Field(default=4.0, gt=0)
    default_pulse_ms: int = Field(default=350, gt=0)
    critical_pulse_ms: int = Field(default=150, gt=0)


class LoggingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: str = "INFO"
    jsonl: bool = True
    console: bool = True


class AppConfig(BaseModel):
    """Root configuration object."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    active_profile: str | None = None
    active_route: str | None = None

    safety: SafetySettings = Field(default_factory=SafetySettings)
    hotkeys: HotkeySettings = Field(default_factory=HotkeySettings)
    bridge: BridgeSettings = Field(default_factory=BridgeSettings)
    capture: CaptureSettings = Field(default_factory=CaptureSettings)
    freshness: FreshnessPolicy = Field(default_factory=FreshnessPolicy)
    navigation: NavigationSettings = Field(default_factory=NavigationSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def provisional_values(self) -> tuple[str, ...]:
        """Settings that are still guesses rather than measurements."""
        pending: list[str] = []
        if self.freshness.provisional:
            pending.append("freshness thresholds (measure in Stage 1/2)")
        if self.capture.provider == "none":
            pending.append("capture provider (benchmark in Stage 2)")
        if self.active_profile is None:
            pending.append("active game profile (create in Stage 2)")
        if self.active_route is None:
            pending.append("active route (record in Stage 5)")
        return tuple(pending)


__all__ = [
    "AppConfig",
    "BridgeSettings",
    "CaptureSettings",
    "HotkeySettings",
    "LoggingSettings",
    "NavigationSettings",
    "SafetySettings",
]
