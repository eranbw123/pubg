"""Stage-gate mechanics.

The gate is the project's core operating rule, so it is enforced by code rather
than by discipline: a stage cannot be accepted while an earlier one is not.
"""

from __future__ import annotations

import pytest

from pubg_training_bot.config.paths import ProjectPaths
from pubg_training_bot.stages import (
    STAGE_BY_ID,
    STAGES,
    StageStatus,
    current_stage,
    gate_check,
    load_state,
    render_status_markdown,
    set_status,
    write_status_doc,
)


def test_stage_registry_is_complete_and_ordered() -> None:
    ids = [s.stage_id for s in STAGES]
    assert ids == [f"{i:02d}" for i in range(13)]
    assert len(STAGE_BY_ID) == len(STAGES)
    assert all(s.acceptance for s in STAGES), "every stage needs acceptance criteria"
    assert all(s.goal for s in STAGES)


def test_stage_zero_needs_no_live_game_but_stage_one_does() -> None:
    assert STAGE_BY_ID["00"].requires_live_game is False
    assert STAGE_BY_ID["01"].requires_live_game is True
    assert STAGE_BY_ID["06"].requires_live_game is False


def test_fresh_state_starts_at_stage_zero(tmp_paths: ProjectPaths) -> None:
    state = load_state(tmp_paths)
    assert state.stages == {}
    assert current_stage(state).stage_id == "00"
    assert not state.is_accepted("00")


def test_gate_blocks_a_later_stage_until_earlier_ones_are_accepted(
    tmp_paths: ProjectPaths,
) -> None:
    state = load_state(tmp_paths)
    allowed, why = gate_check("00", state)
    assert allowed and "accepted" in why

    allowed, why = gate_check("02", state)
    assert not allowed
    assert "stage 00" in why


def test_gate_opens_as_stages_are_accepted(tmp_paths: ProjectPaths) -> None:
    set_status("00", StageStatus.ACCEPTED, paths=tmp_paths)
    state = load_state(tmp_paths)
    assert state.is_accepted("00")
    assert current_stage(state).stage_id == "01"

    allowed, _ = gate_check("01", state)
    assert allowed
    allowed, why = gate_check("02", state)
    assert not allowed and "stage 01" in why


def test_status_round_trips_through_disk(tmp_paths: ProjectPaths) -> None:
    set_status(
        "00",
        StageStatus.READY_FOR_LIVE_TEST,
        notes="awaiting operator verification",
        evidence=["reports/stages/stage-00/stage-report.md"],
        paths=tmp_paths,
    )
    record = load_state(tmp_paths).record("00")
    assert record.status is StageStatus.READY_FOR_LIVE_TEST
    assert record.notes == "awaiting operator verification"
    assert record.evidence == ["reports/stages/stage-00/stage-report.md"]
    assert record.updated_at is not None
    assert record.accepted_at is None, "only acceptance stamps accepted_at"


def test_accepting_stamps_the_acceptance_time(tmp_paths: ProjectPaths) -> None:
    set_status("00", StageStatus.ACCEPTED, paths=tmp_paths)
    assert load_state(tmp_paths).record("00").accepted_at is not None


def test_blocked_status_keeps_its_blocker(tmp_paths: ProjectPaths) -> None:
    set_status("01", StageStatus.BLOCKED, blocker="Overwolf not installed", paths=tmp_paths)
    assert load_state(tmp_paths).record("01").blocker == "Overwolf not installed"


def test_unknown_stage_is_rejected(tmp_paths: ProjectPaths) -> None:
    with pytest.raises(KeyError):
        set_status("99", StageStatus.ACCEPTED, paths=tmp_paths)
    allowed, why = gate_check("99")
    assert not allowed and "unknown" in why


def test_generated_status_doc_reflects_state(tmp_paths: ProjectPaths) -> None:
    set_status("00", StageStatus.ACCEPTED, paths=tmp_paths)
    set_status("01", StageStatus.BLOCKED, blocker="Overwolf missing", paths=tmp_paths)
    target = write_status_doc(tmp_paths)
    text = target.read_text(encoding="utf-8")

    assert "GENERATED FILE" in text
    assert "`accepted`" in text
    assert "Overwolf missing" in text
    assert "Active stage: **01" in text
    for spec in STAGES:
        assert spec.title in text


def test_rendered_markdown_never_claims_unaccepted_criteria_are_met(
    tmp_paths: ProjectPaths,
) -> None:
    text = render_status_markdown(load_state(tmp_paths))
    assert "- [x]" not in text, "nothing is accepted in a fresh state"
    set_status("00", StageStatus.ACCEPTED, paths=tmp_paths)
    assert "- [x]" in render_status_markdown(load_state(tmp_paths))


def test_later_stages_are_not_implemented_yet() -> None:
    """Stage 0 must not have quietly built later stages."""
    import pubg_training_bot

    package_dir = __import__("pathlib").Path(pubg_training_bot.__file__).parent
    forbidden_modules = [
        "navigation",
        "behaviors",
        "recovery",
        "recording",
        "replay",
        "calibration",
        "routes",
        "protocol",
    ]
    present = [name for name in forbidden_modules if (package_dir / name).exists()]
    assert present == [], f"later-stage packages must not exist yet: {present}"
