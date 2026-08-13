"""Scope lock.

Section 3 of the brief forbids a set of techniques outright. This test makes
that boundary executable: if any of those techniques ever appears in the
shipped package, the stage check fails.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pubg_training_bot.actuation.registry import live_actuator_available
from pubg_training_bot.safety import (
    FORBIDDEN_TECHNIQUE_RULES,
    INPUT_INJECTION_RULES,
    LIVE_INPUT_ALLOWLIST,
    assert_scope_clean,
    package_root,
    scan_source,
)


def test_shipped_package_contains_no_forbidden_techniques() -> None:
    report = scan_source()
    assert report.files_scanned > 10, "scan must actually cover the package"
    assert report.forbidden_findings == [], "out-of-scope technique found: " + "; ".join(
        f"{f.file}:{f.line} {f.code}" for f in report.forbidden_findings
    )
    assert report.scope_clean
    assert report.ok


def test_stage_zero_build_cannot_send_input() -> None:
    report = scan_source()
    assert report.input_findings == [], (
        "input-injection symbol present before Stage 3: "
        + "; ".join(f"{f.file}:{f.line} {f.code}" for f in report.input_findings)
    )
    assert live_actuator_available() is False
    assert report.live_input_possible is False


def test_scanner_detects_a_planted_forbidden_technique(tmp_path: Path) -> None:
    """The scanner must be able to fail - a check that cannot fail proves nothing."""
    (tmp_path / "bad.py").write_text(
        textwrap.dedent(
            """
            import ctypes
            def cheat(handle, addr):
                return ctypes.windll.kernel32.ReadProcessMemory(handle, addr)
            """
        ),
        encoding="utf-8",
    )
    report = scan_source(tmp_path)
    assert [f.code for f in report.forbidden_findings] == ["mem-read"]
    assert not report.ok
    with pytest.raises(RuntimeError, match="scope violation"):
        assert_scope_clean(tmp_path)


def test_scanner_detects_planted_input_injection(tmp_path: Path) -> None:
    (tmp_path / "typer.py").write_text(
        "import ctypes\nctypes.windll.user32.SendInput(1, None, 0)\n", encoding="utf-8"
    )
    report = scan_source(tmp_path)
    codes = {f.code for f in report.input_findings}
    assert "sendinput" in codes
    assert not report.ok, "input symbols outside the allowlist must fail the scan"


def test_allowlisted_live_module_is_permitted(tmp_path: Path) -> None:
    """Stage 3 will add actuation/live_sendinput.py; the allowlist anticipates it."""
    module = tmp_path / "actuation" / "live_sendinput.py"
    module.parent.mkdir(parents=True)
    module.write_text("SendInput = None  # placeholder\n", encoding="utf-8")
    report = scan_source(tmp_path)
    assert [f.code for f in report.input_findings] == ["sendinput"]
    assert report.ok, "the allowlisted module must not fail the scan"
    assert report.live_input_possible is False, "still no live actuator registered"


def test_read_only_user32_calls_are_not_flagged(tmp_path: Path) -> None:
    """doctor reads display metrics from user32; only input entry points are banned."""
    (tmp_path / "probe.py").write_text(
        "import ctypes\nw = ctypes.windll.user32.GetSystemMetrics(0)\n", encoding="utf-8"
    )
    report = scan_source(tmp_path)
    assert report.input_findings == []
    assert report.ok


def test_rules_and_allowlist_are_non_empty() -> None:
    assert len(FORBIDDEN_TECHNIQUE_RULES) >= 6
    assert len(INPUT_INJECTION_RULES) >= 4
    assert LIVE_INPUT_ALLOWLIST
    codes = [r.code for r in (*FORBIDDEN_TECHNIQUE_RULES, *INPUT_INJECTION_RULES)]
    assert len(codes) == len(set(codes)), "rule codes must be unique"


def test_scan_skips_the_rules_module_itself() -> None:
    report = scan_source()
    assert all(not f.file.endswith("safety.py") for f in report.forbidden_findings)
    assert (package_root() / "safety.py").exists()


def test_no_networking_to_non_loopback_hosts_in_config() -> None:
    from pubg_training_bot.config.settings import BridgeSettings

    assert BridgeSettings().host == "127.0.0.1"
