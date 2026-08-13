"""CLI surface.

Only read-only commands are exercised against the real repository; anything
that writes state runs against an isolated tree in test_stage00_acceptance.py.
"""

from __future__ import annotations

import json

import pytest

from pubg_training_bot.cli.main import main


def test_version_command(capsys) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip()


def test_doctor_text_output(capsys) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "pubg-training-bot doctor" in out
    assert "live actuation" in out


def test_doctor_json_output(capsys) -> None:
    assert main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]
    assert payload["counts"]


def test_doctor_writes_files(tmp_path, capsys) -> None:
    assert main(["doctor", "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    assert (tmp_path / "doctor.json").exists()
    assert (tmp_path / "doctor.txt").exists()


def test_stage_status_text(capsys) -> None:
    assert main(["stage", "status"]) == 0
    out = capsys.readouterr().out
    assert "Stage status" in out
    assert "Foundation, scope lock and doctor" in out


def test_stage_status_json(capsys) -> None:
    assert main(["stage", "status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["stages"]) == 13
    assert payload["stages"][0]["stage_id"] == "00"


def test_safety_scan_reports_no_live_input(capsys) -> None:
    assert main(["safety", "scan"]) == 0
    out = capsys.readouterr().out
    assert "live_input_possible=False" in out
    assert "live actuator available: False" in out


def test_safety_scan_json(capsys) -> None:
    assert main(["safety", "scan", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["live_input_possible"] is False
    assert payload["forbidden_findings"] == []


def test_schemas_check_passes_against_committed_files(capsys) -> None:
    assert main(["schemas", "export", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_unknown_command_exits_with_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["nope"])
    assert excinfo.value.code == 2


def test_only_stage_appropriate_commands_are_exposed(capsys) -> None:
    """Stage 1 adds a read-only probe; nothing that moves the character exists."""
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = capsys.readouterr().out
    assert "probe" in help_text
    for forbidden in ("run", "record", "calibrate", "arm", "navigate"):
        assert f" {forbidden} " not in help_text
