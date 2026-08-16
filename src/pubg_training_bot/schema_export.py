"""JSON Schema export for the persisted contracts.

The schemas in ``schemas/`` are generated from the pydantic models, never
hand-edited. ``export_schemas(check_only=True)`` fails the stage check when the
committed files drift from the code - a stale schema is worse than none,
because the bridge (TypeScript) validates against it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .config.paths import ProjectPaths, default_paths
from .domain.bridge import BridgeMessage
from .domain.profile import GameProfile
from .domain.route import Route
from .domain.run import RunSummary

#: Filename -> model. These four are the contracts that cross a process or
#: session boundary and therefore need an external, language-neutral schema.
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "bridge-message.schema.json": BridgeMessage,
    "game-profile.schema.json": GameProfile,
    "route.schema.json": Route,
    "run-summary.schema.json": RunSummary,
}


def build_schema(model: type[BaseModel], filename: str) -> dict[str, Any]:
    schema = model.model_json_schema(mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://pubg-training-bot.local/schemas/{filename}"
    return schema


def render(model: type[BaseModel], filename: str) -> str:
    return json.dumps(build_schema(model, filename), indent=2, sort_keys=True) + "\n"


def export_schemas(
    paths: ProjectPaths | None = None,
    *,
    check_only: bool = False,
) -> tuple[list[Path], list[str]]:
    """Write (or verify) every schema file.

    Returns ``(written_or_verified_paths, drifted_filenames)``.
    """
    paths = paths or default_paths()
    target_dir = paths.schemas_dir
    if not check_only:
        target_dir.mkdir(parents=True, exist_ok=True)

    touched: list[Path] = []
    drifted: list[str] = []
    for filename, model in SCHEMA_MODELS.items():
        expected = render(model, filename)
        path = target_dir / filename
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != expected:
            drifted.append(filename)
            if not check_only:
                path.write_text(expected, encoding="utf-8")
        touched.append(path)
    return touched, drifted


__all__ = ["SCHEMA_MODELS", "build_schema", "export_schemas", "render"]
