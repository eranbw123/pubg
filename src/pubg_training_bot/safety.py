"""Scope lock and live-input interlock.

Section 3 of the project brief forbids a specific set of techniques. Prose in a
document does not enforce anything, so this module turns the boundary into a
machine check: it scans the shipped source tree for the symbols those
techniques require and fails the stage check if any appear outside an explicit
allowlist.

It answers two questions the doctor and every stage report must print:

* is any forbidden technique present in this build?
* can this build send real input to the game at all?
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .actuation.registry import live_actuator_available

# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Rule:
    code: str
    pattern: str
    description: str


#: Techniques that are out of scope for this project under any circumstances.
FORBIDDEN_TECHNIQUE_RULES: tuple[Rule, ...] = (
    Rule(
        "mem-read",
        r"ReadProcessMemory|WriteProcessMemory|\bpymem\b|OpenProcess",
        "process memory access",
    ),
    Rule(
        "injection",
        r"CreateRemoteThread|LoadLibraryA|VirtualAllocEx|SetWindowsHookEx",
        "code/DLL injection",
    ),
    Rule("packets", r"\bscapy\b|\bpydivert\b|WinDivert|\bpcap\b|npcap", "packet interception"),
    Rule(
        "driver",
        r"interception\.dll|\bCreateFile\(\s*['\"]\\\\\\\\\.\\\\|kernel driver",
        "kernel-level input or driver access",
    ),
    Rule(
        "engine-hook",
        r"UnrealEngine|UE4Dumper|\bGObjects\b|\bGNames\b",
        "game engine internal hooks",
    ),
    Rule("anticheat", r"BattlEye|anti-?cheat bypass|\bobfuscat", "anti-cheat interference"),
)

#: OS input-injection symbols. Legal only inside the allowlisted live actuator
#: module, which does not exist before Stage 3.
INPUT_INJECTION_RULES: tuple[Rule, ...] = (
    Rule("sendinput", r"\bSendInput\b", "Win32 SendInput"),
    Rule("legacy-input", r"\bkeybd_event\b|\bmouse_event\b", "legacy Win32 input"),
    Rule("cursor", r"\bSetCursorPos\b|\bmouse_event\b", "cursor manipulation"),
    Rule(
        "input-libs",
        r"\bpyautogui\b|\bpydirectinput\b|\bpynput\b\.\w*[Cc]ontroller|\bkeyboard\.press\b",
        "third-party input libraries",
    ),
    # Read-only user32 calls (GetSystemMetrics, GetForegroundWindow) are permitted:
    # only the input-producing entry points are flagged.
    Rule(
        "user32-input",
        r"user32\.\s*(SendInput|keybd_event|mouse_event|SetCursorPos|BlockInput)",
        "user32 input injection entry points",
    ),
)

#: Modules permitted to contain input-injection symbols once implemented.
LIVE_INPUT_ALLOWLIST: tuple[str, ...] = (
    "actuation/live_sendinput.py",
    "actuation/scancodes.py",
)


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    description: str
    file: str
    line: int
    excerpt: str


class SafetyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_root: str
    files_scanned: int = 0
    forbidden_findings: list[Finding] = Field(default_factory=list)
    input_findings: list[Finding] = Field(default_factory=list)
    live_actuator_registered: bool = False
    allowlist: list[str] = Field(default_factory=list)

    @property
    def live_input_possible(self) -> bool:
        """Real input requires both a registered live actuator and code that
        can actually inject it. Stage 0 has neither."""
        return self.live_actuator_registered and bool(self.input_findings)

    @property
    def scope_clean(self) -> bool:
        return not self.forbidden_findings

    @property
    def ok(self) -> bool:
        """Scope is respected and every input symbol sits in an allowlisted module."""
        return self.scope_clean and all(_is_allowlisted(f.file) for f in self.input_findings)

    def summary(self) -> str:
        parts = [
            f"files_scanned={self.files_scanned}",
            f"forbidden={len(self.forbidden_findings)}",
            f"input_symbols={len(self.input_findings)}",
            f"live_actuator_registered={self.live_actuator_registered}",
            f"live_input_possible={self.live_input_possible}",
        ]
        return " ".join(parts)


def _is_allowlisted(relative_path: str) -> bool:
    normalised = relative_path.replace("\\", "/")
    return any(normalised.endswith(entry) for entry in LIVE_INPUT_ALLOWLIST)


def package_root() -> Path:
    return Path(__file__).resolve().parent


def scan_source(root: Path | None = None) -> SafetyReport:
    """Scan the shipped package for forbidden techniques and input symbols.

    This module is skipped: it necessarily contains the patterns it looks for.
    """
    root = (root or package_root()).resolve()
    self_path = Path(__file__).resolve()

    forbidden: list[Finding] = []
    inputs: list[Finding] = []
    files = 0

    compiled_forbidden = [(r, re.compile(r.pattern)) for r in FORBIDDEN_TECHNIQUE_RULES]
    compiled_inputs = [(r, re.compile(r.pattern)) for r in INPUT_INJECTION_RULES]

    for path in sorted(root.rglob("*.py")):
        if path.resolve() == self_path:
            continue
        files += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - defensive
            continue
        relative = path.relative_to(root).as_posix()
        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule, regex in compiled_forbidden:
                if regex.search(line):
                    forbidden.append(
                        Finding(
                            code=rule.code,
                            description=rule.description,
                            file=relative,
                            line=line_no,
                            excerpt=line.strip()[:160],
                        )
                    )
            for rule, regex in compiled_inputs:
                if regex.search(line):
                    inputs.append(
                        Finding(
                            code=rule.code,
                            description=rule.description,
                            file=relative,
                            line=line_no,
                            excerpt=line.strip()[:160],
                        )
                    )

    return SafetyReport(
        scanned_root=str(root),
        files_scanned=files,
        forbidden_findings=forbidden,
        input_findings=inputs,
        live_actuator_registered=live_actuator_available(),
        allowlist=list(LIVE_INPUT_ALLOWLIST),
    )


def assert_scope_clean(root: Path | None = None) -> SafetyReport:
    """Raise if the build has drifted outside the permitted technique set."""
    report = scan_source(root)
    if not report.ok:
        problems = [
            f"{f.file}:{f.line} {f.code} ({f.description})" for f in report.forbidden_findings
        ]
        problems += [
            f"{f.file}:{f.line} input symbol {f.code} outside allowlist"
            for f in report.input_findings
            if not _is_allowlisted(f.file)
        ]
        raise RuntimeError("scope violation:\n  " + "\n  ".join(problems))
    return report


__all__ = [
    "FORBIDDEN_TECHNIQUE_RULES",
    "INPUT_INJECTION_RULES",
    "LIVE_INPUT_ALLOWLIST",
    "Finding",
    "Rule",
    "SafetyReport",
    "assert_scope_clean",
    "package_root",
    "scan_source",
]
