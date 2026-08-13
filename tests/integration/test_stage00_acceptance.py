"""Stage 0 acceptance, end to end.

Mirrors what scripts/check-stage-00.ps1 does, so the acceptance criteria are
verified by the test suite and not only by a shell script.
"""

from __future__ import annotations

import json

import pytest

from pubg_training_bot.actuation import create_actuator, live_actuator_available
from pubg_training_bot.clock import FakeClock
from pubg_training_bot.config import load_config, load_game_profile
from pubg_training_bot.config.paths import ProjectPaths
from pubg_training_bot.diagnostics.doctor import run_doctor
from pubg_training_bot.domain.actuation import ActuationCommand
from pubg_training_bot.domain.enums import CommandOutcome, CommandType, ControlState
from pubg_training_bot.reporting.stage_report import PytestSummary, generate_stage_report
from pubg_training_bot.safety import scan_source
from pubg_training_bot.schema_export import export_schemas
from pubg_training_bot.stages import StageStatus, load_state, set_status, write_status_doc


def test_package_imports_and_exposes_a_version() -> None:
    import pubg_training_bot

    assert pubg_training_bot.__version__
    assert pubg_training_bot.SCHEMA_VERSION >= 1


def test_project_documents_exist(repo_paths: ProjectPaths) -> None:
    required = [
        "CLAUDE.md",
        "README.md",
        "docs/architecture.md",
        "docs/stages.md",
        "docs/stage-status.md",
        "docs/decisions.md",
        "docs/risk-register.md",
        "docs/live-test-protocol.md",
        "docs/troubleshooting.md",
        "config/default.yaml",
        "scripts/bootstrap.ps1",
        "scripts/check-stage-00.ps1",
    ]
    missing = [name for name in required if not (repo_paths.root / name).exists()]
    assert missing == [], f"missing documents: {missing}"


def test_config_and_profile_load_together(repo_paths: ProjectPaths) -> None:
    config = load_config(paths=repo_paths)
    profile = load_game_profile("dev-1080p-fpp", paths=repo_paths)
    assert config.safety.dry_run is True
    assert profile.missing_for_navigation()


def test_live_input_is_impossible_in_this_build(repo_paths: ProjectPaths) -> None:
    """The Stage 0 headline guarantee, checked three independent ways."""
    assert live_actuator_available() is False
    report = scan_source()
    assert report.input_findings == []
    assert report.live_input_possible is False

    clock = FakeClock()
    actuator = create_actuator(clock=clock)
    actuator.arm("acceptance test")
    command = ActuationCommand(
        type=CommandType.KEY_TAP,
        key="forward",
        reason="acceptance test",
        issuing_state=ControlState.IDLE,
        issued_at=clock.monotonic(),
        expires_at=clock.monotonic() + 1.0,
    )
    assert actuator.submit(command).outcome is CommandOutcome.REJECTED_DRY_RUN


def test_doctor_runs_clean_enough_to_proceed(repo_paths: ProjectPaths) -> None:
    report = run_doctor(repo_paths)
    blocking = [c.name for c in report.blocking_failures]
    assert blocking == [], f"doctor reports blocking failures: {blocking}"


def test_schemas_are_current(repo_paths: ProjectPaths) -> None:
    _, drifted = export_schemas(repo_paths, check_only=True)
    assert drifted == []


def test_stage_report_generation_in_an_isolated_tree(tmp_paths: ProjectPaths) -> None:
    report, out_dir = generate_stage_report(
        "00",
        automated_checks={"unit tests": "pass", "scope scan": "pass"},
        tests=PytestSummary(passed=42, ran=True, command="pytest"),
        open_questions=["operator must run the verification command"],
        paths=tmp_paths,
    )
    assert report.automated_pass
    assert report.live_input_possible is False
    for name in ("stage-report.json", "stage-report.md", "doctor.json", "safety-scan.json"):
        assert (out_dir / name).exists()

    payload = json.loads((out_dir / "stage-report.json").read_text(encoding="utf-8"))
    assert payload["stage_id"] == "00"
    assert payload["tests"]["passed"] == 42
    markdown = (out_dir / "stage-report.md").read_text(encoding="utf-8")
    assert "AUTOMATED PASS" in markdown
    assert "Requires live observation" in markdown


def test_failed_check_makes_the_stage_report_fail(tmp_paths: ProjectPaths) -> None:
    report, _ = generate_stage_report(
        "00", automated_checks={"unit tests": "fail"}, paths=tmp_paths
    )
    assert not report.automated_pass


def test_stage_gate_prevents_skipping_ahead(tmp_paths: ProjectPaths) -> None:
    from pubg_training_bot.cli.main import main as cli_main

    set_status("00", StageStatus.READY_FOR_LIVE_TEST, paths=tmp_paths)
    state = load_state(tmp_paths)
    assert not state.is_accepted("00")

    # A later stage cannot be accepted while stage 00 is not.
    from pubg_training_bot.stages import gate_check

    allowed, why = gate_check("01", state)
    assert not allowed and "stage 00" in why
    assert callable(cli_main)


def test_status_doc_regenerates_deterministically(tmp_paths: ProjectPaths) -> None:
    set_status("00", StageStatus.READY_FOR_LIVE_TEST, paths=tmp_paths)
    first = write_status_doc(tmp_paths).read_text(encoding="utf-8")
    second = write_status_doc(tmp_paths).read_text(encoding="utf-8")
    # Only the generated timestamp line may differ.
    strip = lambda text: [ln for ln in text.splitlines() if not ln.startswith("Generated:")]  # noqa: E731
    assert strip(first) == strip(second)


@pytest.mark.parametrize("stage_id", ["01", "02", "03"])
def test_future_stages_have_no_implementation(stage_id: str) -> None:
    """Guards against implementing later stages while waiting for acceptance."""
    from pubg_training_bot.stages import STAGE_BY_ID

    spec = STAGE_BY_ID[stage_id]
    assert spec.requires_live_game is True
    assert load_state().record(stage_id).status is not StageStatus.ACCEPTED
