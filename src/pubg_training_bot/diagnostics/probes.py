"""Read-only environment probes.

Everything here observes; nothing here changes machine or game state. No
process is started, no window is focused, no input is produced. Each probe
degrades to ``None``/``unknown`` rather than raising, so ``doctor`` always
produces a full report even on an unusual machine.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

#: Where Overwolf normally lives.
OVERWOLF_PATH_CANDIDATES: tuple[str, ...] = (
    r"%LOCALAPPDATA%\Overwolf",
    r"%ProgramFiles(x86)%\Overwolf",
    r"%ProgramFiles%\Overwolf",
)
OVERWOLF_PROCESS_NAMES: tuple[str, ...] = ("Overwolf.exe", "OverwolfLauncher.exe")

#: Steam default plus common secondary library roots.
PUBG_PATH_CANDIDATES: tuple[str, ...] = (
    r"%ProgramFiles(x86)%\Steam\steamapps\common\PUBG",
    r"%ProgramFiles%\Steam\steamapps\common\PUBG",
    r"C:\SteamLibrary\steamapps\common\PUBG",
    r"D:\SteamLibrary\steamapps\common\PUBG",
    r"E:\SteamLibrary\steamapps\common\PUBG",
)
PUBG_PROCESS_NAMES: tuple[str, ...] = ("TslGame.exe",)


@dataclass(frozen=True)
class CommandVersion:
    available: bool
    version: str | None
    path: str | None
    detail: str = ""


def command_version(command: str, args: str = "--version", timeout: float = 20.0) -> CommandVersion:
    """Resolve a CLI tool and read its version string.

    Windows shims (``npm.cmd``, ``pnpm.cmd``) are not directly executable via
    ``CreateProcess``, so they are invoked through ``cmd /c``.
    """
    path = shutil.which(command)
    if path is None:
        return CommandVersion(available=False, version=None, path=None, detail="not on PATH")
    argv: list[str]
    if IS_WINDOWS and Path(path).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        argv = ["cmd", "/c", command, args]
    else:
        argv = [path, args]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no user input
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CommandVersion(available=False, version=None, path=path, detail=str(exc))
    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    version = output[0].strip() if output else None
    return CommandVersion(
        available=completed.returncode == 0,
        version=version,
        path=path,
        detail="" if completed.returncode == 0 else f"exit code {completed.returncode}",
    )


def expand_existing(candidates: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for raw in candidates:
        expanded = os.path.expandvars(raw)
        if "%" in expanded:
            continue
        if Path(expanded).exists():
            found.append(expanded)
    return found


def running_processes(names: tuple[str, ...]) -> list[str]:
    """Which of ``names`` are currently running (read-only ``tasklist`` query)."""
    if not IS_WINDOWS:
        return []
    running: list[str] = []
    for name in names:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv
                ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if name.lower() in (completed.stdout or "").lower():
            running.append(name)
    return running


@dataclass(frozen=True)
class OverwolfInfo:
    """Overwolf client facts, read from the registry where available.

    The registry is authoritative: ``%LOCALAPPDATA%\\Overwolf`` holds user data
    while the client itself installs under Program Files, so a path scan alone
    reports "installed" without knowing the version or the release channel.

    ``channel`` matters because ``Development options`` is absent from the
    production client. The developer *whitelist* is not represented here - it
    lives in Overwolf's account state, not on this machine, so it stays an
    observation the Stage 1 load attempt has to make.
    """

    installed: bool
    install_folder: str | None = None
    version: str | None = None
    channel: str | None = None
    running: bool = False
    source: str = "none"

    @property
    def is_developer_channel(self) -> bool:
        return (self.channel or "").strip().lower() == "developers"


#: Registry locations of the Overwolf client, most specific first.
_OVERWOLF_REGISTRY_KEYS: tuple[tuple[str, str], ...] = (
    ("HKLM", r"SOFTWARE\WOW6432Node\Overwolf"),
    ("HKLM", r"SOFTWARE\Overwolf"),
    ("HKCU", r"Software\Overwolf"),
)


def overwolf_info() -> OverwolfInfo:
    running = bool(running_processes(OVERWOLF_PROCESS_NAMES))
    paths = expand_existing(OVERWOLF_PATH_CANDIDATES)

    if IS_WINDOWS:
        try:
            import winreg

            roots = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
            for root_name, sub_key in _OVERWOLF_REGISTRY_KEYS:
                try:
                    with winreg.OpenKey(roots[root_name], sub_key) as key:
                        values: dict[str, str] = {}
                        for name in ("InstallFolder", "CurrentVersion", "Channel"):
                            try:
                                values[name] = str(winreg.QueryValueEx(key, name)[0])
                            except OSError:
                                continue
                        if values:
                            folder = values.get("InstallFolder") or (paths[0] if paths else None)
                            return OverwolfInfo(
                                installed=True,
                                install_folder=folder,
                                version=values.get("CurrentVersion"),
                                channel=values.get("Channel"),
                                running=running,
                                source=f"registry {root_name}\\{sub_key}",
                            )
                except OSError:
                    continue
        except ImportError:  # pragma: no cover - non-Windows
            pass

    if paths:
        return OverwolfInfo(
            installed=True, install_folder=paths[0], running=running, source="path scan"
        )
    return OverwolfInfo(installed=False, running=running, source="not found")


@dataclass(frozen=True)
class DisplayInfo:
    width: int | None
    height: int | None
    dpi: int | None
    scale: float | None
    detail: str = ""


def display_info() -> DisplayInfo:
    """Primary display metrics, read-only.

    The process is not made DPI-aware here: changing awareness is a global,
    irreversible side effect, and Stage 2 handles DPI properly when it owns the
    capture window. Values are therefore reported as the OS presents them to a
    DPI-unaware process, which is flagged in ``detail``.
    """
    if not IS_WINDOWS:
        return DisplayInfo(None, None, None, None, detail="non-Windows host")
    try:
        import ctypes

        user32 = ctypes.windll.user32  # read-only metric queries only
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
        dpi: int | None = None
        try:
            dpi = int(user32.GetDpiForSystem())
        except (AttributeError, OSError):
            dpi = None
        scale = round(dpi / 96.0, 3) if dpi else None
        return DisplayInfo(
            width=width,
            height=height,
            dpi=dpi,
            scale=scale,
            detail="values as seen by a DPI-unaware process",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return DisplayInfo(None, None, None, None, detail=f"probe failed: {exc}")


@dataclass(frozen=True)
class GitState:
    is_repo: bool
    branch: str | None = None
    head: str | None = None
    dirty_files: int = 0
    untracked_files: int = 0
    detail: str = ""


def git_state(root: Path) -> GitState:
    if shutil.which("git") is None:
        return GitState(is_repo=False, detail="git not on PATH")

    def run(args: list[str]) -> str | None:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv
                ["git", "-C", str(root), *args],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip() if completed.returncode == 0 else None

    if run(["rev-parse", "--is-inside-work-tree"]) != "true":
        return GitState(is_repo=False, detail="not a git work tree")

    status = run(["status", "--porcelain"]) or ""
    lines = [ln for ln in status.splitlines() if ln.strip()]
    return GitState(
        is_repo=True,
        branch=run(["rev-parse", "--abbrev-ref", "HEAD"]),
        head=run(["log", "-1", "--format=%h %s"]),
        dirty_files=sum(1 for ln in lines if not ln.startswith("??")),
        untracked_files=sum(1 for ln in lines if ln.startswith("??")),
    )


def python_info() -> dict[str, str]:
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "in_virtualenv": str(sys.prefix != sys.base_prefix),
        "prefix": sys.prefix,
    }


def os_info() -> dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor_architecture": os.environ.get("PROCESSOR_ARCHITECTURE", "unknown"),
    }


__all__ = [
    "IS_WINDOWS",
    "OVERWOLF_PATH_CANDIDATES",
    "OVERWOLF_PROCESS_NAMES",
    "PUBG_PATH_CANDIDATES",
    "PUBG_PROCESS_NAMES",
    "CommandVersion",
    "DisplayInfo",
    "GitState",
    "OverwolfInfo",
    "command_version",
    "display_info",
    "expand_existing",
    "git_state",
    "os_info",
    "overwolf_info",
    "python_info",
    "running_processes",
]
