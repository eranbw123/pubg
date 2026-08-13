"""Bridge message contract: raw preservation and honest failure.

Overwolf delivers nested JSON as strings and occasionally malformed values.
Both must survive into the run bundle instead of being replaced by a plausible
default.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pubg_training_bot.domain.bridge import (
    BridgeMessage,
    ParseWarning,
    parse_maybe_nested_json,
)
from pubg_training_bot.domain.enums import MessageType


def test_nested_json_string_is_decoded() -> None:
    warnings: list[ParseWarning] = []
    value = parse_maybe_nested_json('{"x": 1.5, "y": -2.0}', field="location", warnings=warnings)
    assert value == {"x": 1.5, "y": -2.0}
    assert warnings == []


def test_double_encoded_json_is_decoded_to_the_object() -> None:
    inner = json.dumps({"x": 1, "y": 2})
    doubly = json.dumps(inner)
    assert parse_maybe_nested_json(doubly, field="location") == {"x": 1, "y": 2}


def test_malformed_nested_json_warns_and_returns_original() -> None:
    warnings: list[ParseWarning] = []
    raw = '{"x": 1.5, "y":'
    value = parse_maybe_nested_json(raw, field="location", warnings=warnings)
    assert value == raw, "malformed payload must be returned unchanged, not replaced"
    assert len(warnings) == 1
    assert warnings[0].code == "nested_json_invalid"
    assert warnings[0].field == "location"


def test_plain_string_is_not_treated_as_json() -> None:
    warnings: list[ParseWarning] = []
    assert parse_maybe_nested_json("training", field="map", warnings=warnings) == "training"
    assert warnings == []


def test_depth_limit_stops_runaway_unwrapping() -> None:
    payload = json.dumps(json.dumps(json.dumps(json.dumps({"deep": True}))))
    shallow = parse_maybe_nested_json(payload, field="x", max_depth=1)
    assert isinstance(shallow, str)
    deep = parse_maybe_nested_json(payload, field="x", max_depth=4)
    assert deep == {"deep": True}


def test_message_preserves_raw_payload_verbatim() -> None:
    raw = {"info": {"location": '{"x": 1, "y": 2}'}, "feature": "location"}
    message = BridgeMessage(
        sequence=7,
        type=MessageType.INFO_UPDATE,
        bridge_monotonic_ts=12.5,
        controller_receive_ts=1000.0,
        raw=raw,
        normalized={"x": 1.0, "y": 2.0},
    )
    assert message.raw == raw
    assert message.raw["info"]["location"] == '{"x": 1, "y": 2}'
    assert message.normalized == {"x": 1.0, "y": 2.0}
    assert not message.has_warnings


def test_normalized_none_means_not_normalised_not_empty() -> None:
    message = BridgeMessage(sequence=0, bridge_monotonic_ts=0.0, raw={"a": 1})
    assert message.normalized is None
    assert message.type is MessageType.UNKNOWN


def test_message_age_uses_controller_clock() -> None:
    message = BridgeMessage(
        sequence=1, bridge_monotonic_ts=5.0, controller_receive_ts=1000.0, raw={}
    )
    assert message.age_seconds(1002.5) == pytest.approx(2.5)
    assert message.age_seconds(999.0) == pytest.approx(0.0), "age must never go negative"
    untimed = BridgeMessage(sequence=2, bridge_monotonic_ts=6.0, raw={})
    assert untimed.age_seconds(1000.0) is None


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        BridgeMessage(sequence=1, bridge_monotonic_ts=0.0, raw={}, surprise="nope")


def test_negative_sequence_rejected() -> None:
    with pytest.raises(ValidationError):
        BridgeMessage(sequence=-1, bridge_monotonic_ts=0.0, raw={})


def test_warnings_round_trip_through_json() -> None:
    message = BridgeMessage(
        sequence=3,
        bridge_monotonic_ts=1.0,
        raw={"bad": "{"},
        parse_warnings=[ParseWarning(field="bad", code="nested_json_invalid", detail="eof")],
    )
    restored = BridgeMessage.model_validate_json(message.model_dump_json())
    assert restored.has_warnings
    assert restored.parse_warnings[0].code == "nested_json_invalid"
    assert restored.raw == {"bad": "{"}
