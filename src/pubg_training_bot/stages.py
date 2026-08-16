"""Stage registry and stage-gate state.

The stage *specification* (what each stage must prove) is code, so it cannot
drift from the plan. The stage *state* (what has actually been accepted) lives
in ``config/stage-state.yaml`` and only advances when a live test passes.

``docs/stage-status.md`` is generated from both, so the document can never
claim a stage passed that the state file does not record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .config.paths import ProjectPaths, default_paths
from .domain.enums import StrEnum


class StageStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    #: Code written and automated checks pass; awaiting the human live test.
    READY_FOR_LIVE_TEST = "ready_for_live_test"
    ACCEPTED = "accepted"
    FAILED = "failed"
    #: Cannot proceed until an external prerequisite is satisfied.
    BLOCKED = "blocked"


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    title: str
    goal: str
    acceptance: tuple[str, ...]
    #: True when acceptance requires observing the running game.
    requires_live_game: bool


STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        "00",
        "Foundation, scope lock and doctor",
        "Executable foundation with no game access and no possibility of input.",
        (
            "project installs and the CLI starts",
            "doctor produces JSON and human-readable output",
            "fake sensor/capture/heading/actuator tests pass",
            "live input is impossible by default (no live actuator registered)",
            "documentation reflects the actual repository",
            "later stages are not implemented",
        ),
        requires_live_game=False,
    ),
    StageSpec(
        "01",
        "Live Overwolf sensor feasibility",
        "Prove what data PUBG Training Mode actually exposes through Overwolf.",
        (
            "bridge connects over authenticated loopback WebSocket",
            "per-feature registration outcome is visible",
            "map, phase and view are observed",
            "XYZ updates arrive and change when walking",
            "stationary noise baseline and update cadence are measured",
            "malformed payloads are preserved and reported, not hidden",
            "no input is generated",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "02",
        "Live frame-capture feasibility",
        "Prove a reliable frame stream and calibratable HUD crops.",
        (
            "real PUBG frames captured at the correct resolution",
            "compass and interaction regions visible in saved crops",
            "capture rate and frame latency measured (P50/P95)",
            "black/duplicate/wrong-window frames detected, never silently used",
            "GameProfile saved and reloadable",
            "no input is generated",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "03",
        "Bounded live input feasibility",
        "Prove permitted external input can move and turn the character safely.",
        (
            "no input occurs before arming",
            "one short forward pulse changes position",
            "one bounded mouse pulse changes the camera",
            "emergency stop prevents further commands",
            "focus loss and sensor loss stop actuation",
            "no key remains held after any exit path",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "04",
        "Heading and movement calibration",
        "Obtain a trustworthy heading signal and fit coordinate/turn transforms.",
        (
            "stationary heading jitter P95 <= ~2.5 deg (or a measured, justified revision)",
            ">=10 of 12 distributed target headings reached within ~5 deg",
            "movement-derived heading agrees within ~10 deg",
            "wraparound near north behaves correctly",
            "low-confidence reads abstain instead of fabricating a bearing",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "05",
        "Route recorder and inspector",
        "Record and inspect a human demonstration.",
        (
            "marker hotkeys work without leaving the game",
            "recorded samples align with actual movement",
            "semantic markers survive simplification",
            "route visualisation is understandable",
            "route validation rejects incompatible profiles",
            "no autonomous movement occurs",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "06",
        "Offline controller, replay and simulation",
        "Implement and test the navigation state machine without live risk.",
        (
            "synthetic route completes in the fake world",
            "stale sensors abort; blocked movement enters bounded recovery",
            "delayed location updates cause no runaway movement",
            "obsolete commands cannot execute",
            "replay is deterministic",
            "no real input is possible during standard checks",
        ),
        requires_live_game=False,
    ),
    StageSpec(
        "07",
        "Live open-area closed-loop navigation",
        "Autonomously replay the simple open-area route.",
        (
            "five consecutive completions from the defined start region",
            "no manual correction after arming",
            "endpoint reached inside tolerance",
            "no indefinite key holds and no heading oscillation",
            "emergency stop works; every run produces evidence",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "08",
        "Single-floor building entry, rooms and exit",
        "Navigate one simple single-floor building route.",
        (
            ">=3 successful closed-door runs and >=3 open-door runs",
            "no repeated interaction after crossing",
            "failed crossing recognised; bounded retry then safe abort",
            "room traversal and exit evidenced",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "09",
        "Staircase and multi-floor route",
        "Extend the route through one staircase and another floor.",
        (
            "five consecutive complete building runs including the staircase",
            "expected Z transition observed before advancing floors",
            "no indefinite forward movement on stairs",
            "small alignment failure recovered; unrecoverable failure aborts safely",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "10",
        "One-point configured looting",
        "Pick one configured item at a recorded loot node and continue.",
        (
            ">=8 of 10 runs with the item present pick it and finish",
            "3 runs with the item absent skip it and finish",
            "disallowed prompts never trigger pickup",
            "scan is time bounded and failed verification is reported",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "11",
        "Live recovery and perturbation tests",
        "Make ordinary small deviations survivable.",
        (
            ">=8 of 10 predefined perturbed runs complete",
            "every recovery attempt visible in logs; no unbounded loop",
            "persistent failure aborts and releases all controls",
            "failure bundle is diagnosable",
        ),
        requires_live_game=True,
    ),
    StageSpec(
        "12",
        "Stability, one-command operation and MVP acceptance",
        "Turn the prototype into the first stable MVP.",
        (
            "single launcher performs checks, starts disarmed and waits for the hotkey",
            "documented repeatable acceptance run",
            "stable success rate across consecutive runs",
        ),
        requires_live_game=True,
    ),
)

STAGE_BY_ID: dict[str, StageSpec] = {s.stage_id: s for s in STAGES}


class StageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StageStatus = StageStatus.NOT_STARTED
    updated_at: str | None = None
    accepted_at: str | None = None
    notes: str = ""
    evidence: list[str] = Field(default_factory=list)
    #: Reason a stage is blocked or failed; required for those statuses.
    blocker: str = ""


class StageState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    stages: dict[str, StageRecord] = Field(default_factory=dict)

    def record(self, stage_id: str) -> StageRecord:
        return self.stages.get(stage_id, StageRecord())

    def is_accepted(self, stage_id: str) -> bool:
        return self.record(stage_id).status is StageStatus.ACCEPTED


def state_path(paths: ProjectPaths | None = None) -> Path:
    return (paths or default_paths()).config_dir / "stage-state.yaml"


def load_state(paths: ProjectPaths | None = None) -> StageState:
    path = state_path(paths)
    if not path.exists():
        return StageState()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return StageState.model_validate(data)


def save_state(state: StageState, paths: ProjectPaths | None = None) -> Path:
    path = state_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = state.model_dump(mode="json", exclude_defaults=False)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=True, default_flow_style=False),
        encoding="utf-8",
    )
    return path


def set_status(
    stage_id: str,
    status: StageStatus,
    *,
    notes: str = "",
    blocker: str = "",
    evidence: list[str] | None = None,
    paths: ProjectPaths | None = None,
) -> StageState:
    if stage_id not in STAGE_BY_ID:
        raise KeyError(f"unknown stage {stage_id!r}")
    state = load_state(paths)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    record = state.record(stage_id)
    state.stages[stage_id] = StageRecord(
        status=status,
        updated_at=now,
        accepted_at=now if status is StageStatus.ACCEPTED else record.accepted_at,
        notes=notes or record.notes,
        evidence=evidence if evidence is not None else record.evidence,
        blocker=blocker,
    )
    save_state(state, paths)
    return state


def gate_check(stage_id: str, state: StageState | None = None) -> tuple[bool, str]:
    """May work on ``stage_id`` begin? Returns ``(allowed, explanation)``."""
    if stage_id not in STAGE_BY_ID:
        return False, f"unknown stage {stage_id!r}"
    state = state or load_state()
    for spec in STAGES:
        if spec.stage_id == stage_id:
            break
        if not state.is_accepted(spec.stage_id):
            return False, (
                f"stage {spec.stage_id} ({spec.title}) is "
                f"{state.record(spec.stage_id).status}, not accepted"
            )
    return True, "all previous stages accepted"


def current_stage(state: StageState | None = None) -> StageSpec:
    """The first stage that is not accepted."""
    state = state or load_state()
    for spec in STAGES:
        if not state.is_accepted(spec.stage_id):
            return spec
    return STAGES[-1]


def render_status_markdown(state: StageState | None = None) -> str:
    state = state or load_state()
    now = datetime.now(UTC).isoformat(timespec="seconds")
    active = current_stage(state)

    lines = [
        "# Stage status",
        "",
        "<!-- GENERATED FILE - edit config/stage-state.yaml or src/pubg_training_bot/stages.py",
        "     and regenerate with: pubg-bot stage status --write-docs -->",
        "",
        f"Generated: {now}",
        f"Active stage: **{active.stage_id} - {active.title}**",
        "",
        "| Stage | Title | Status | Live test | Accepted | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for spec in STAGES:
        record = state.record(spec.stage_id)
        note = record.blocker or record.notes or ""
        lines.append(
            f"| {spec.stage_id} | {spec.title} | `{record.status}` | "
            f"{'yes' if spec.requires_live_game else 'no'} | "
            f"{record.accepted_at or '-'} | {note.replace('|', '/')} |"
        )

    lines += ["", "## Acceptance criteria", ""]
    for spec in STAGES:
        record = state.record(spec.stage_id)
        lines.append(f"### Stage {spec.stage_id} - {spec.title} (`{record.status}`)")
        lines.append("")
        lines.append(f"{spec.goal}")
        lines.append("")
        for item in spec.acceptance:
            lines.append(f"- [{'x' if record.status is StageStatus.ACCEPTED else ' '}] {item}")
        if record.evidence:
            lines.append("")
            lines.append("Evidence:")
            for item in record.evidence:
                lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_status_doc(paths: ProjectPaths | None = None, state: StageState | None = None) -> Path:
    paths = paths or default_paths()
    # Load through the same paths as the target document, so writing an isolated
    # tree's status cannot accidentally render the real repository's state.
    state = state or load_state(paths)
    target = paths.docs_dir / "stage-status.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_status_markdown(state), encoding="utf-8")
    return target


__all__ = [
    "STAGES",
    "STAGE_BY_ID",
    "StageRecord",
    "StageSpec",
    "StageState",
    "StageStatus",
    "current_stage",
    "gate_check",
    "load_state",
    "render_status_markdown",
    "save_state",
    "set_status",
    "state_path",
    "write_status_doc",
]
