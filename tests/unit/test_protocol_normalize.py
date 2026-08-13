"""Normalisation of documented Overwolf PUBG payloads."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures import overwolf_payloads as payloads  # noqa: E402
from pubg_training_bot.domain.enums import (  # noqa: E402
    MatchPhase,
    MovementState,
    Stance,
    ViewMode,
)
from pubg_training_bot.protocol.normalize import (  # noqa: E402
    DECLINED_FEATURES,
    REQUIRED_FEATURES,
    extract_info_sections,
    normalize_update,
)


def test_location_nested_json_string_is_decoded() -> None:
    result = normalize_update(payloads.LOCATION_UPDATE)
    assert result.position is not None
    assert result.position.as_tuple() == (2300.0, 5740.0, 1520.0)
    assert result.warnings == []


def test_me_fields_map_to_the_control_vocabulary() -> None:
    result = normalize_update(payloads.ME_UPDATE)
    assert result.view is ViewMode.FPP
    assert result.stance is Stance.STANDING
    assert result.movement is MovementState.WALKING
    assert result.free_view is False
    assert result.warnings == []


def test_fast_movement_maps_to_running() -> None:
    result = normalize_update({"info": {"me": {"movement": "fast"}}})
    assert result.movement is MovementState.RUNNING


def test_in_vehicle_overrides_movement_mode() -> None:
    result = normalize_update({"info": {"me": {"movement": "normal", "inVehicle": True}}})
    assert result.movement is MovementState.IN_VEHICLE


def test_map_and_phase() -> None:
    assert normalize_update(payloads.MAP_UPDATE).map_id == "Erangel_Main"
    assert normalize_update(payloads.PHASE_UPDATE).phase is MatchPhase.LANDED


def test_get_info_res_shape_is_handled_too() -> None:
    result = normalize_update(payloads.GET_INFO_SNAPSHOT)
    assert result.map_id == "Erangel_Main"
    assert result.phase is MatchPhase.LANDED
    assert result.view is ViewMode.TPP
    assert result.stance is Stance.CROUCHING
    assert result.movement is MovementState.RUNNING
    assert result.free_view is True
    assert result.position is not None
    assert result.position.as_tuple() == (1.5, -2.5, 30.0)


def test_malformed_location_warns_and_yields_no_position() -> None:
    result = normalize_update(payloads.MALFORMED_LOCATION)
    assert result.position is None
    assert any(w.code in {"nested_json_invalid", "location_not_object"} for w in result.warnings)


def test_undocumented_phase_becomes_unknown_with_a_warning() -> None:
    """Training Mode may report a phase the docs do not list. It must surface as
    unknown-plus-warning, never be coerced into a documented value."""
    result = normalize_update(payloads.UNDOCUMENTED_PHASE)
    assert result.phase is MatchPhase.UNKNOWN
    assert any(w.code == "unknown_phase_value" for w in result.warnings)
    assert "training_ground" in result.warnings[0].detail


def test_unknown_view_and_stance_warn() -> None:
    result = normalize_update({"info": {"me": {"view": "VR", "stance": "hovering"}}})
    assert result.view is ViewMode.UNKNOWN
    assert result.stance is Stance.UNKNOWN
    codes = {w.code for w in result.warnings}
    assert {"unknown_view_value", "unknown_stance_value"} <= codes


def test_absent_fields_stay_none_so_callers_can_tell_unchanged_from_empty() -> None:
    result = normalize_update({"info": {"map": {"map": "Erangel_Main"}}})
    assert result.map_id == "Erangel_Main"
    assert result.position is None
    assert result.view is None
    assert result.phase is None


def test_empty_payload_produces_nothing_and_no_warnings() -> None:
    result = normalize_update({})
    assert result.position is None
    assert result.warnings == []


def test_location_with_missing_component_warns() -> None:
    result = normalize_update({"info": {"location": {"location": '{"x":1,"y":2}'}}})
    assert result.position is None
    assert any(w.code == "location_incomplete" for w in result.warnings)


def test_location_already_an_object_is_accepted() -> None:
    result = normalize_update({"info": {"location": {"location": {"x": 1, "y": 2, "z": 3}}}})
    assert result.position is not None
    assert result.position.as_tuple() == (1.0, 2.0, 3.0)


def test_string_booleans_are_coerced() -> None:
    assert normalize_update({"info": {"me": {"freeView": "true"}}}).free_view is True
    assert normalize_update({"info": {"me": {"freeView": "false"}}}).free_view is False


def test_non_boolean_free_view_warns_rather_than_defaulting() -> None:
    result = normalize_update({"info": {"me": {"freeView": "maybe"}}})
    assert result.free_view is None
    assert any(w.code == "not_a_boolean" for w in result.warnings)


def test_extract_info_sections_handles_both_envelopes() -> None:
    assert "location" in extract_info_sections(payloads.LOCATION_UPDATE)
    assert "map" in extract_info_sections(payloads.GET_INFO_SNAPSHOT)


@pytest.mark.parametrize("feature", REQUIRED_FEATURES)
def test_required_features_are_documented_ones(feature: str) -> None:
    documented = {
        "gep_internal",
        "kill",
        "revived",
        "death",
        "killer",
        "match",
        "match_info",
        "rank",
        "counters",
        "location",
        "me",
        "team",
        "phase",
        "map",
        "roster",
    }
    assert feature in documented


def test_combat_and_roster_features_are_explicitly_declined() -> None:
    """Out-of-scope data is not merely unused - it is never requested."""
    for feature in ("kill", "death", "killer", "roster", "team"):
        assert feature in DECLINED_FEATURES
        assert feature not in REQUIRED_FEATURES
