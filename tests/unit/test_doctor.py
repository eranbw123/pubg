"""Doctor behaviour.

The doctor must be safe to run at any time: read-only, never actuating, and
still complete when parts of the environment are missing.
"""

from __future__ import annotations

import json

from pubg_training_bot.config.paths import ProjectPaths
from pubg_training_bot.diagnostics.doctor import CheckStatus, run_doctor, write_doctor_report

REQUIRED_CHECKS = {
    "operating system",
    "architecture",
    "python",
    "virtualenv",
    "uv",
    "node",
    "pnpm",
    "git",
    "overwolf install",
    "overwolf channel",
    "pubg install",
    "display",
    "git state",
    "repo layout",
    "live actuation",
    "scope lock",
}


def test_doctor_reports_every_required_check(repo_paths: ProjectPaths) -> None:
    report = run_doctor(repo_paths)
    names = {check.name for check in report.checks}
    assert names >= REQUIRED_CHECKS, f"missing checks: {REQUIRED_CHECKS - names}"


def test_doctor_states_that_live_actuation_is_disabled(repo_paths: ProjectPaths) -> None:
    report = run_doctor(repo_paths)
    check = next(c for c in report.checks if c.name == "live actuation")
    assert check.status is CheckStatus.OK
    assert "DISABLED" in check.value


def test_doctor_confirms_scope_is_clean(repo_paths: ProjectPaths) -> None:
    report = run_doctor(repo_paths)
    check = next(c for c in report.checks if c.name == "scope lock")
    assert check.status is CheckStatus.OK
    assert check.value == "clean"


def test_doctor_json_is_parseable_and_carries_counts(repo_paths: ProjectPaths) -> None:
    report = run_doctor(repo_paths)
    payload = json.loads(report.to_json())
    assert payload["bot_version"]
    assert payload["active_stage"].startswith("0")
    assert set(payload["counts"]) == {"ok", "warn", "fail", "info"}
    assert sum(payload["counts"].values()) == len(payload["checks"])


def test_doctor_text_is_human_readable(repo_paths: ProjectPaths) -> None:
    text = run_doctor(repo_paths).to_text()
    assert "pubg-training-bot doctor" in text
    assert "summary:" in text
    assert "live actuation" in text


def test_failing_checks_carry_a_remedy(repo_paths: ProjectPaths) -> None:
    report = run_doctor(repo_paths)
    for check in report.checks:
        if check.status in (CheckStatus.FAIL, CheckStatus.WARN):
            assert check.remedy, f"{check.name} must explain how to fix it"


def test_doctor_writes_both_formats(repo_paths: ProjectPaths, tmp_path) -> None:
    written = write_doctor_report(run_doctor(repo_paths), tmp_path / "out")
    assert written["json"].exists() and written["text"].exists()
    json.loads(written["json"].read_text(encoding="utf-8"))


def test_doctor_never_touches_the_actuator(repo_paths: ProjectPaths, monkeypatch) -> None:
    """A doctor run must not construct an actuator, let alone submit a command."""
    import pubg_training_bot.actuation.registry as registry

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("doctor must not create an actuator")

    monkeypatch.setattr(registry, "create_actuator", explode)
    run_doctor(repo_paths)


def test_overwolf_probe_reports_channel_without_claiming_whitelist(monkeypatch) -> None:
    """The release channel is observable; the developer whitelist is not.

    Conflating them would let the doctor print a reassuring line about something
    it cannot actually see.
    """
    from pubg_training_bot.diagnostics import probes

    info = probes.OverwolfInfo(
        installed=True,
        install_folder=r"C:\Program Files (x86)\Overwolf",
        version="0.309.0.11",
        channel="Developers",
        running=True,
        source="registry",
    )
    assert info.is_developer_channel

    monkeypatch.setattr(probes, "overwolf_info", lambda: info)
    report = run_doctor()
    channel = next(c for c in report.checks if c.name == "overwolf channel")
    assert channel.status is CheckStatus.OK
    assert channel.value == "Developers"

    fields = set(probes.OverwolfInfo.__dataclass_fields__)
    assert "whitelisted" not in fields
    assert not any("whitelist" in c.value.lower() for c in report.checks)


def test_production_channel_is_flagged_with_a_remedy(monkeypatch) -> None:
    from pubg_training_bot.diagnostics import probes

    monkeypatch.setattr(
        probes,
        "overwolf_info",
        lambda: probes.OverwolfInfo(installed=True, channel="Production", source="registry"),
    )
    report = run_doctor()
    channel = next(c for c in report.checks if c.name == "overwolf channel")
    assert channel.status is CheckStatus.WARN
    assert "Developers" in channel.remedy


def test_missing_overwolf_is_a_warning_not_a_failure(monkeypatch) -> None:
    """Stage 0 does not touch the game, so a missing Overwolf must not fail it."""
    from pubg_training_bot.diagnostics import probes

    monkeypatch.setattr(probes, "overwolf_info", lambda: probes.OverwolfInfo(installed=False))
    report = run_doctor()
    install = next(c for c in report.checks if c.name == "overwolf install")
    assert install.status is CheckStatus.WARN
    assert install.value == "not found"
    assert not report.blocking_failures


def test_doctor_survives_a_broken_repo_layout(tmp_path) -> None:
    paths = ProjectPaths(root=tmp_path)
    report = run_doctor(paths)
    layout = next(c for c in report.checks if c.name == "repo layout")
    assert layout.status is CheckStatus.FAIL
    assert layout.remedy
