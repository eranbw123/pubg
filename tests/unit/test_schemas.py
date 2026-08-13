"""JSON Schema export.

The bridge (TypeScript) will validate against these files, so a schema that has
drifted from the pydantic model is worse than no schema at all.
"""

from __future__ import annotations

import json

import jsonschema
import pytest

from pubg_training_bot.config.paths import ProjectPaths
from pubg_training_bot.schema_export import SCHEMA_MODELS, export_schemas, render


def test_committed_schemas_match_the_models(repo_paths: ProjectPaths) -> None:
    _, drifted = export_schemas(repo_paths, check_only=True)
    assert drifted == [], (
        "committed schemas are stale: " + ", ".join(drifted) + "; run: pubg-bot schemas export"
    )


def test_every_contract_has_a_schema_file(repo_paths: ProjectPaths) -> None:
    for filename in SCHEMA_MODELS:
        assert (repo_paths.schemas_dir / filename).exists(), f"missing schema: {filename}"


@pytest.mark.parametrize("filename", sorted(SCHEMA_MODELS))
def test_schemas_are_valid_json_schema_documents(repo_paths: ProjectPaths, filename: str) -> None:
    document = json.loads((repo_paths.schemas_dir / filename).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(document)
    assert document["$schema"].startswith("https://json-schema.org/draft/2020-12")
    assert document["$id"].endswith(filename)


def test_export_is_deterministic() -> None:
    for filename, model in SCHEMA_MODELS.items():
        assert render(model, filename) == render(model, filename)


def test_bridge_message_schema_requires_raw_payload(repo_paths: ProjectPaths) -> None:
    document = json.loads(
        (repo_paths.schemas_dir / "bridge-message.schema.json").read_text(encoding="utf-8")
    )
    assert "raw" in document["properties"]
    assert "sequence" in document["required"]


def test_export_writes_files_into_an_empty_tree(tmp_paths: ProjectPaths) -> None:
    written, drifted = export_schemas(tmp_paths)
    assert sorted(drifted) == sorted(SCHEMA_MODELS)
    for path in written:
        assert path.exists()
    _, drifted_again = export_schemas(tmp_paths, check_only=True)
    assert drifted_again == []
