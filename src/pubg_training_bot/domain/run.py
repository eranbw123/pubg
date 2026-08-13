"""Run bundle contracts: what every live run must leave behind.

A run that produced no evidence did not happen, as far as this project is
concerned. The bundle layout is fixed so the report generator and any offline
analysis can rely on it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .. import SCHEMA_VERSION
from .enums import ControlState, RecoveryLevel, RunOutcome

#: Files every completed run bundle contains.
REQUIRED_BUNDLE_FILES: tuple[str, ...] = (
    "manifest.json",
    "events.jsonl",
    "commands.jsonl",
    "states.jsonl",
    "sensor-summary.json",
    "run-summary.json",
    "route.json",
    "game-profile.json",
    "report.html",
)


class StateTransition(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: float
    from_state: ControlState
    to_state: ControlState
    #: Mandatory: an unexplained transition is a bug.
    reason: str
    node_id: str | None = None
    edge_id: str | None = None


class RecoveryAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: float
    level: RecoveryLevel
    node_id: str | None
    reason: str
    succeeded: bool | None = None
    detail: str = ""


class SensorSummary(BaseModel):
    """Aggregate sensor health for the run - the first thing to check when a
    run fails for no obvious reason."""

    model_config = ConfigDict(extra="forbid")

    samples: int = 0
    location_updates: int = 0
    location_interval_p50_s: float | None = None
    location_interval_p95_s: float | None = None
    max_location_gap_s: float | None = None
    heading_samples: int = 0
    heading_abstentions: int = 0
    heading_confidence_p50: float | None = None
    frames_captured: int = 0
    frame_age_p95_s: float | None = None
    invalid_reason_counts: dict[str, int] = Field(default_factory=dict)
    stale_intervals: list[tuple[float, float]] = Field(default_factory=list)


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    run_id: str
    started_at: str
    bot_version: str
    stage: str
    mode: str = "dry-run"
    route_id: str | None = None
    profile_id: str | None = None
    profile_fingerprint: str | None = None
    live_actuation: bool = False
    files: list[str] = Field(default_factory=list)
    host: dict[str, str] = Field(default_factory=dict)


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    run_id: str
    outcome: RunOutcome
    started_at: str
    ended_at: str
    duration_s: float = Field(ge=0)

    route_id: str | None = None
    nodes_total: int = 0
    nodes_reached: int = 0
    last_node_id: str | None = None
    last_state: ControlState = ControlState.IDLE

    commands_issued: int = 0
    commands_executed: int = 0
    commands_rejected: int = 0
    rejection_counts: dict[str, int] = Field(default_factory=dict)

    recovery_attempts: int = 0
    recovery_by_level: dict[str, int] = Field(default_factory=dict)

    abort_reason: str | None = None
    loot_picked: list[str] = Field(default_factory=list)
    sensor_summary: SensorSummary = Field(default_factory=SensorSummary)
    evidence_files: list[str] = Field(default_factory=list)
    #: Set only when a human confirmed the physical outcome in-game.
    live_verified: bool = False


__all__ = [
    "REQUIRED_BUNDLE_FILES",
    "RecoveryAttempt",
    "RunManifest",
    "RunSummary",
    "SensorSummary",
    "StateTransition",
]
