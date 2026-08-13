"""Stage evidence bundles.

Each stage writes ``reports/stages/stage-NN/`` containing a machine-readable
report and a human-readable one. The report states what was verified
*automatically* and what still needs a live observation - the two are never
merged, because a passing simulation is not evidence about the game.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .. import __version__
from ..actuation.registry import list_actuators, live_actuator_available
from ..config.paths import ProjectPaths, default_paths
from ..diagnostics.doctor import DoctorReport, run_doctor
from ..safety import SafetyReport, scan_source
from ..stages import STAGE_BY_ID, StageStatus, load_state


@dataclass(frozen=True)
class PytestSummary:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    ran: bool = False
    command: str = ""

    @property
    def ok(self) -> bool:
        return self.ran and self.failed == 0 and self.errors == 0


class StageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: str
    title: str
    goal: str
    status: StageStatus
    generated_at: str
    bot_version: str
    requires_live_game: bool
    acceptance: list[str] = Field(default_factory=list)
    automated_checks: dict[str, str] = Field(default_factory=dict)
    tests: dict[str, int | bool | str] = Field(default_factory=dict)
    doctor_counts: dict[str, int] = Field(default_factory=dict)
    doctor_failures: list[str] = Field(default_factory=list)
    safety_summary: str = ""
    live_input_possible: bool = False
    open_questions: list[str] = Field(default_factory=list)
    evidence_files: list[str] = Field(default_factory=list)

    @property
    def automated_pass(self) -> bool:
        return all(v == "pass" for v in self.automated_checks.values())


def _markdown(report: StageReport, doctor: DoctorReport, safety: SafetyReport) -> str:
    lines = [
        f"# Stage {report.stage_id} - {report.title}",
        "",
        f"Generated: {report.generated_at}  |  bot version: {report.bot_version}",
        f"Status: **{report.status}**",
        f"Automated result: **{'AUTOMATED PASS' if report.automated_pass else 'FAILED'}**",
        "",
        f"> {report.goal}",
        "",
        "## Automated checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
    ]
    for name, result in report.automated_checks.items():
        lines.append(f"| {name} | `{result}` |")

    tests = report.tests
    lines += [
        "",
        "## Tests",
        "",
        f"- command: `{tests.get('command', 'n/a')}`",
        f"- passed: {tests.get('passed', 0)}, failed: {tests.get('failed', 0)}, "
        f"errors: {tests.get('errors', 0)}, skipped: {tests.get('skipped', 0)}",
        "",
        "## Acceptance criteria",
        "",
    ]
    for item in report.acceptance:
        lines.append(f"- [ ] {item}")

    lines += [
        "",
        "## Safety interlocks",
        "",
        f"- live input possible in this build: **{report.live_input_possible}**",
        "- registered actuators: "
        + ", ".join(f"`{d.key}` (live={d.live})" for d in list_actuators()),
        f"- scope scan: {safety.summary()}",
        "",
        "## Environment (doctor)",
        "",
        "| Check | Status | Value |",
        "| --- | --- | --- |",
    ]
    for check in doctor.checks:
        lines.append(f"| {check.name} | `{check.status}` | {check.value} |")

    if report.open_questions:
        lines += ["", "## Requires live observation", ""]
        for item in report.open_questions:
            lines.append(f"- {item}")

    lines += [
        "",
        "## Files",
        "",
    ]
    for item in report.evidence_files:
        lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"


def generate_stage_report(
    stage_id: str,
    *,
    automated_checks: dict[str, str],
    tests: PytestSummary | None = None,
    open_questions: list[str] | None = None,
    paths: ProjectPaths | None = None,
) -> tuple[StageReport, Path]:
    """Write ``reports/stages/stage-NN/`` and return the report plus its directory."""
    paths = paths or default_paths()
    spec = STAGE_BY_ID.get(stage_id)
    if spec is None:
        raise KeyError(f"unknown stage {stage_id!r}")

    out_dir = paths.stage_report_dir(stage_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    doctor = run_doctor(paths)
    safety = scan_source()
    state = load_state(paths)
    tests = tests or PytestSummary()

    (out_dir / "doctor.json").write_text(doctor.to_json(), encoding="utf-8")
    (out_dir / "doctor.txt").write_text(doctor.to_text(), encoding="utf-8")
    (out_dir / "safety-scan.json").write_text(
        json.dumps(safety.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    report = StageReport(
        stage_id=stage_id,
        title=spec.title,
        goal=spec.goal,
        status=state.record(stage_id).status,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        bot_version=__version__,
        requires_live_game=spec.requires_live_game,
        acceptance=list(spec.acceptance),
        automated_checks=dict(automated_checks),
        tests={
            "ran": tests.ran,
            "passed": tests.passed,
            "failed": tests.failed,
            "errors": tests.errors,
            "skipped": tests.skipped,
            "command": tests.command,
        },
        doctor_counts=doctor.counts,
        doctor_failures=[f"{c.name}: {c.value}" for c in doctor.blocking_failures],
        safety_summary=safety.summary(),
        live_input_possible=live_actuator_available() and bool(safety.input_findings),
        open_questions=open_questions or [],
        evidence_files=[
            "doctor.json",
            "doctor.txt",
            "safety-scan.json",
            "stage-report.json",
            "stage-report.md",
        ],
    )

    (out_dir / "stage-report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    (out_dir / "stage-report.md").write_text(_markdown(report, doctor, safety), encoding="utf-8")
    return report, out_dir


__all__ = ["PytestSummary", "StageReport", "generate_stage_report"]
