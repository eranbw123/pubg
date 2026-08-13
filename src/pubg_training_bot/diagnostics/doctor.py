"""``pubg-bot doctor`` - environment readiness report.

Read-only by construction: it calls the probes in
:mod:`pubg_training_bot.diagnostics.probes` and the actuator registry, and
nothing else. It never starts the game, focuses a window, or produces input.

Every check carries a ``remedy`` so a failing environment is actionable rather
than merely reported.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .. import __version__
from ..actuation.registry import list_actuators, live_actuator_available
from ..config.paths import ProjectPaths, default_paths
from ..domain.enums import StrEnum
from ..safety import scan_source
from ..stages import current_stage, load_state
from . import probes


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"


class DoctorCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: CheckStatus
    value: str = ""
    detail: str = ""
    remedy: str = ""
    #: Stage that first needs this check to pass.
    needed_by_stage: str | None = None


class DoctorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    bot_version: str
    repo_root: str
    active_stage: str
    checks: list[DoctorCheck] = Field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        result = {status.value: 0 for status in CheckStatus}
        for check in self.checks:
            result[check.status.value] += 1
        return result

    @property
    def blocking_failures(self) -> list[DoctorCheck]:
        return [c for c in self.checks if c.status is CheckStatus.FAIL]

    def to_json(self) -> str:
        payload = self.model_dump(mode="json")
        payload["counts"] = self.counts
        return json.dumps(payload, indent=2, sort_keys=False)

    def to_text(self) -> str:
        width = max((len(c.name) for c in self.checks), default=10)
        symbols = {
            CheckStatus.OK: "[ ok ]",
            CheckStatus.WARN: "[warn]",
            CheckStatus.FAIL: "[FAIL]",
            CheckStatus.INFO: "[info]",
        }
        lines = [
            f"pubg-training-bot doctor  (v{self.bot_version})",
            f"generated: {self.generated_at}",
            f"repo root: {self.repo_root}",
            f"active stage: {self.active_stage}",
            "",
        ]
        for check in self.checks:
            lines.append(f"{symbols[check.status]} {check.name.ljust(width)}  {check.value}")
            if check.detail:
                lines.append(f"{' ' * (width + 9)}{check.detail}")
            if check.status in (CheckStatus.FAIL, CheckStatus.WARN) and check.remedy:
                stage = ""
                if check.needed_by_stage:
                    stage = f" (needed by stage {check.needed_by_stage})"
                lines.append(f"{' ' * (width + 9)}-> {check.remedy}{stage}")
        counts = self.counts
        lines += [
            "",
            f"summary: {counts['ok']} ok, {counts['warn']} warn, "
            f"{counts['fail']} fail, {counts['info']} info",
        ]
        return "\n".join(lines)


def _tool_check(
    name: str,
    command: str,
    *,
    required: bool,
    remedy: str,
    stage: str | None = None,
    args: str = "--version",
) -> DoctorCheck:
    result = probes.command_version(command, args)
    if result.available:
        return DoctorCheck(
            name=name,
            status=CheckStatus.OK,
            value=result.version or "present",
            detail=result.path or "",
        )
    return DoctorCheck(
        name=name,
        status=CheckStatus.FAIL if required else CheckStatus.WARN,
        value="missing",
        detail=result.detail,
        remedy=remedy,
        needed_by_stage=stage,
    )


def run_doctor(paths: ProjectPaths | None = None) -> DoctorReport:
    """Collect every environment check. Performs no state changes."""
    paths = paths or default_paths()
    checks: list[DoctorCheck] = []

    # --- host ---------------------------------------------------------- #
    os_data = probes.os_info()
    checks.append(
        DoctorCheck(
            name="operating system",
            status=CheckStatus.OK if probes.IS_WINDOWS else CheckStatus.FAIL,
            value=f"{os_data['system']} {os_data['release']} ({os_data['version']})",
            detail=f"machine={os_data['machine']}",
            remedy="This project is Windows-only; PUBG and Overwolf require Windows.",
            needed_by_stage="00",
        )
    )
    checks.append(
        DoctorCheck(
            name="architecture",
            status=(
                CheckStatus.OK
                if os_data["processor_architecture"].upper() in {"AMD64", "ARM64"}
                else CheckStatus.WARN
            ),
            value=os_data["processor_architecture"],
        )
    )

    py = probes.python_info()
    py_ok = tuple(int(p) for p in py["version"].split(".")[:2]) >= (3, 11)
    checks.append(
        DoctorCheck(
            name="python",
            status=CheckStatus.OK if py_ok else CheckStatus.FAIL,
            value=f"{py['implementation']} {py['version']}",
            detail=f"{py['executable']} (venv={py['in_virtualenv']})",
            remedy="Python 3.11+ is required.",
            needed_by_stage="00",
        )
    )
    checks.append(
        DoctorCheck(
            name="virtualenv",
            status=CheckStatus.OK if py["in_virtualenv"] == "True" else CheckStatus.WARN,
            value=py["in_virtualenv"],
            detail=py["prefix"],
            remedy="Run scripts/bootstrap.ps1 and use .venv to keep dependencies reproducible.",
            needed_by_stage="00",
        )
    )

    # --- toolchain ----------------------------------------------------- #
    checks.append(
        _tool_check(
            "uv",
            "uv",
            required=False,
            remedy=("Optional. bootstrap.ps1 falls back to venv+pip. Install with: pip install uv"),
        )
    )
    checks.append(
        _tool_check(
            "node",
            "node",
            required=False,
            remedy="Needed to build the Overwolf bridge. Install Node 20+.",
            stage="01",
        )
    )
    checks.append(
        _tool_check(
            "pnpm",
            "pnpm",
            required=False,
            remedy="Needed for the bridge workspace. Enable with: corepack enable pnpm",
            stage="01",
        )
    )
    checks.append(_tool_check("git", "git", required=False, remedy="Install Git for Windows."))

    # --- game environment ---------------------------------------------- #
    overwolf_paths = probes.expand_existing(probes.OVERWOLF_PATH_CANDIDATES)
    overwolf_running = probes.running_processes(probes.OVERWOLF_PROCESS_NAMES)
    checks.append(
        DoctorCheck(
            name="overwolf install",
            status=CheckStatus.OK if overwolf_paths else CheckStatus.WARN,
            value=overwolf_paths[0] if overwolf_paths else "not found",
            detail=(
                f"running: {', '.join(overwolf_running)}" if overwolf_running else "not running"
            ),
            remedy=(
                "Install Overwolf from https://www.overwolf.com/ and enable developer mode. "
                "Stage 1 cannot start without it."
            ),
            needed_by_stage="01",
        )
    )

    pubg_paths = probes.expand_existing(probes.PUBG_PATH_CANDIDATES)
    pubg_running = probes.running_processes(probes.PUBG_PROCESS_NAMES)
    checks.append(
        DoctorCheck(
            name="pubg install",
            status=CheckStatus.OK if pubg_paths else CheckStatus.WARN,
            value=pubg_paths[0] if pubg_paths else "not found",
            detail=f"running: {', '.join(pubg_running)}" if pubg_running else "not running",
            remedy="Install PUBG via Steam, or add its library path to PUBG_PATH_CANDIDATES.",
            needed_by_stage="01",
        )
    )

    display = probes.display_info()
    checks.append(
        DoctorCheck(
            name="display",
            status=CheckStatus.OK if display.width else CheckStatus.WARN,
            value=(
                f"{display.width}x{display.height} @ {display.dpi or '?'}dpi "
                f"(scale {display.scale or '?'})"
            ),
            detail=display.detail,
            remedy="Display metrics are required to build a GameProfile.",
            needed_by_stage="02",
        )
    )

    # --- repository ----------------------------------------------------- #
    git = probes.git_state(paths.root)
    checks.append(
        DoctorCheck(
            name="git state",
            status=CheckStatus.OK if git.is_repo else CheckStatus.WARN,
            value=(f"{git.branch} @ {git.head}" if git.is_repo else "not a repository"),
            detail=(
                f"modified={git.dirty_files} untracked={git.untracked_files}"
                if git.is_repo
                else git.detail
            ),
        )
    )

    missing_dirs = [
        str(p.relative_to(paths.root))
        for p in (paths.config_dir, paths.docs_dir, paths.schemas_dir)
        if not p.exists()
    ]
    checks.append(
        DoctorCheck(
            name="repo layout",
            status=CheckStatus.OK if not missing_dirs else CheckStatus.FAIL,
            value=str(paths.root),
            detail=("complete" if not missing_dirs else f"missing: {', '.join(missing_dirs)}"),
            remedy="Run scripts/bootstrap.ps1 from the repository root.",
            needed_by_stage="00",
        )
    )

    # --- safety interlocks ---------------------------------------------- #
    safety = scan_source()
    checks.append(
        DoctorCheck(
            name="live actuation",
            status=CheckStatus.OK if not live_actuator_available() else CheckStatus.INFO,
            value="DISABLED (no live actuator registered)"
            if not live_actuator_available()
            else "live actuator registered",
            detail="actuators: " + ", ".join(f"{d.key}(live={d.live})" for d in list_actuators()),
            remedy="",
        )
    )
    checks.append(
        DoctorCheck(
            name="scope lock",
            status=CheckStatus.OK if safety.ok else CheckStatus.FAIL,
            value="clean" if safety.ok else "VIOLATION",
            detail=safety.summary(),
            remedy="Remove out-of-scope techniques; see docs/architecture.md section 'Scope lock'.",
            needed_by_stage="00",
        )
    )

    state = load_state(paths)
    stage = current_stage(state)

    return DoctorReport(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        bot_version=__version__,
        repo_root=str(paths.root),
        active_stage=f"{stage.stage_id} - {stage.title}",
        checks=checks,
    )


def write_doctor_report(report: DoctorReport, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "doctor.json"
    text_path = out_dir / "doctor.txt"
    json_path.write_text(report.to_json(), encoding="utf-8")
    text_path.write_text(report.to_text(), encoding="utf-8")
    return {"json": json_path, "text": text_path}


__all__ = ["CheckStatus", "DoctorCheck", "DoctorReport", "run_doctor", "write_doctor_report"]
