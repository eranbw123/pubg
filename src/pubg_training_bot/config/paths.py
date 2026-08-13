"""Filesystem layout.

Resolved from the installed package location upward, so the CLI works from any
working directory and an editable install still finds the repo's ``config/``
and ``data/`` trees.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_MARKERS = ("pyproject.toml", ".git")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` looking for a repo marker.

    Falls back to the package's grandparent (``src/..``) so a non-editable
    install still produces a usable, if less interesting, root.
    """
    override = os.environ.get("PUBG_BOT_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if candidate.is_dir() and any((candidate / m).exists() for m in _MARKERS):
            return candidate
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def game_profiles_dir(self) -> Path:
        return self.config_dir / "game_profiles"

    @property
    def routes_config_dir(self) -> Path:
        return self.config_dir / "routes"

    @property
    def loot_policies_dir(self) -> Path:
        return self.config_dir / "loot_policies"

    @property
    def schemas_dir(self) -> Path:
        return self.root / "schemas"

    @property
    def docs_dir(self) -> Path:
        return self.root / "docs"

    @property
    def data_dir(self) -> Path:
        return self.root / "data" / "local"

    @property
    def captures_dir(self) -> Path:
        return self.data_dir / "captures"

    @property
    def recordings_dir(self) -> Path:
        return self.data_dir / "recordings"

    @property
    def routes_dir(self) -> Path:
        return self.data_dir / "routes"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def stage_reports_dir(self) -> Path:
        return self.reports_dir / "stages"

    @property
    def run_reports_dir(self) -> Path:
        return self.reports_dir / "runs"

    def stage_report_dir(self, stage_id: str) -> Path:
        return self.stage_reports_dir / f"stage-{stage_id}"

    def ensure_runtime_dirs(self) -> list[Path]:
        """Create the local data/report directories (all git-ignored)."""
        created: list[Path] = []
        for path in (
            self.captures_dir,
            self.recordings_dir,
            self.routes_dir,
            self.runs_dir,
            self.data_dir / "fixtures",
            self.stage_reports_dir,
            self.run_reports_dir,
        ):
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created.append(path)
        return created


def default_paths() -> ProjectPaths:
    return ProjectPaths(root=find_repo_root())


__all__ = ["ProjectPaths", "default_paths", "find_repo_root"]
