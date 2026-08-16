"""Authoritative normalisation of Overwolf PUBG payloads.

The bridge also normalises, but its output is advisory only. The controller
re-derives everything here from the raw payload, so a bug in the TypeScript
normaliser cannot become the controller's belief, and a recorded run can be
re-parsed offline after this file is corrected.

Payload shapes are from Overwolf's PUBG game-events documentation:

* ``location`` -> ``{"location": "{\\"x\\":2300,\\"y\\":5740,\\"z\\":1520}"}``
  (a JSON **string**, not an object - the single most likely place to lose data)
* ``me`` -> ``view`` (``TPP``/``FPP``), ``stance`` (``stand``/``crouch``/
  ``prone``), ``movement`` (``normal``/``fast``/``stealth``), ``freeView``
  (bool), ``inVehicle`` (bool), ``bodyPosition``, ``aiming``, ``health``
* ``phase`` -> ``lobby``/``loading_screen``/``airfield``/``aircraft``/
  ``freefly``/``landed``
* ``map`` -> ``{"map": "Erangel_Main"}``

Unrecognised values never become a plausible default: they produce a
:class:`ParseWarning` and leave the field ``None``/``UNKNOWN``.
"""

from __future__ import annotations

from typing import Any

from ..domain.bridge import ParseWarning, parse_maybe_nested_json
from ..domain.enums import MatchPhase, MovementState, Stance, ViewMode
from ..domain.sensors import Vec3

#: Documented features this project registers. Nothing else is requested:
#: kill/death/killer/roster/team are combat and social data we have no use for,
#: and requesting them would widen the data surface for no benefit.
REQUIRED_FEATURES: tuple[str, ...] = (
    "location",
    "me",
    "phase",
    "map",
    "match_info",
)

#: Documented but deliberately not requested, with the reason.
DECLINED_FEATURES: dict[str, str] = {
    "kill": "combat data; out of scope",
    "death": "combat data; out of scope",
    "killer": "combat data; out of scope",
    "revived": "combat data; out of scope",
    "roster": "other players; out of scope",
    "team": "other players; out of scope",
    "rank": "not needed for navigation",
    "counters": "not needed for navigation",
    "match": "superseded by match_info for our purposes",
    "gep_internal": "provider diagnostics only",
}

_VIEW_MAP = {"fpp": ViewMode.FPP, "tpp": ViewMode.TPP}
_STANCE_MAP = {
    "stand": Stance.STANDING,
    "standing": Stance.STANDING,
    "crouch": Stance.CROUCHING,
    "crouching": Stance.CROUCHING,
    "prone": Stance.PRONE,
}
#: PUBG reports a movement *mode*, not whether the character is moving, so IDLE
#: is not derivable from this feature. Actual motion is measured from position
#: deltas instead.
_MOVEMENT_MAP = {
    "normal": MovementState.WALKING,
    "stealth": MovementState.WALKING,
    "fast": MovementState.RUNNING,
}


class NormalizedUpdate:
    """Fields extracted from one info update. Absent keys stay ``None`` so the
    caller can distinguish "unchanged" from "reported as empty"."""

    __slots__ = (
        "free_view",
        "map_id",
        "movement",
        "phase",
        "position",
        "stance",
        "view",
        "warnings",
    )

    def __init__(self) -> None:
        self.position: Vec3 | None = None
        self.map_id: str | None = None
        self.phase: MatchPhase | None = None
        self.view: ViewMode | None = None
        self.stance: Stance | None = None
        self.movement: MovementState | None = None
        self.free_view: bool | None = None
        self.warnings: list[ParseWarning] = []

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"NormalizedUpdate(position={self.position}, map_id={self.map_id}, "
            f"phase={self.phase}, view={self.view}, stance={self.stance}, "
            f"movement={self.movement}, free_view={self.free_view}, "
            f"warnings={len(self.warnings)})"
        )


def extract_info_sections(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Pull the per-feature sections out of either payload shape.

    ``onInfoUpdates2`` delivers ``{"info": {"me": {...}}, "feature": "me"}``
    while ``getInfo`` delivers ``{"res": {"me": {...}}}``. Both appear in a real
    session, so both are handled rather than assuming one.
    """
    for key in ("info", "res"):
        section = raw.get(key)
        if isinstance(section, dict):
            return {k: v for k, v in section.items() if isinstance(v, dict)}
    # Some payloads arrive already unwrapped.
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def normalize_location(value: Any, warnings: list[ParseWarning]) -> Vec3 | None:
    """Decode the nested-JSON location payload into a :class:`Vec3`."""
    decoded = parse_maybe_nested_json(value, field="location", warnings=warnings)
    if not isinstance(decoded, dict):
        warnings.append(
            ParseWarning(
                field="location",
                code="location_not_object",
                detail=f"expected an object, got {type(decoded).__name__}",
            )
        )
        return None
    try:
        return Vec3(
            x=float(decoded["x"]),
            y=float(decoded["y"]),
            z=float(decoded["z"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        warnings.append(
            ParseWarning(
                field="location",
                code="location_incomplete",
                detail=f"{exc!r} in {decoded!r}"[:200],
            )
        )
        return None


def normalize_update(raw: dict[str, Any]) -> NormalizedUpdate:
    """Normalise one bridge frame's raw payload."""
    result = NormalizedUpdate()
    sections = extract_info_sections(raw)

    location_section = sections.get("location", {})
    if "location" in location_section:
        result.position = normalize_location(location_section["location"], result.warnings)

    # Observed live (GEP 311.2.2): the map arrives as `match_info.map`, not as a
    # standalone `map` section, and the value is an internal name
    # ("Baltic_Main" for Erangel). The documented `map` feature is still checked
    # first in case it returns in a later provider version.
    map_section = sections.get("map", {})
    if "map" not in map_section:
        match_info = sections.get("match_info", {})
        if isinstance(match_info.get("map"), str):
            map_section = {"map": match_info["map"]}
    if "map" in map_section:
        raw_map = map_section["map"]
        if isinstance(raw_map, str) and raw_map.strip():
            result.map_id = raw_map.strip()
        else:
            result.warnings.append(
                ParseWarning(field="map", code="map_not_a_string", detail=repr(raw_map)[:160])
            )

    # Observed live: phase arrives as `game_info.phase`, not a standalone
    # `phase` section. Documented location checked first, as above.
    phase_section = sections.get("phase", {})
    if "phase" not in phase_section:
        game_info = sections.get("game_info", {})
        if game_info.get("phase") is not None:
            phase_section = {"phase": game_info["phase"]}
    if "phase" in phase_section:
        raw_phase = str(phase_section["phase"]).strip().lower()
        try:
            result.phase = MatchPhase(raw_phase)
        except ValueError:
            result.phase = MatchPhase.UNKNOWN
            result.warnings.append(
                ParseWarning(
                    field="phase",
                    code="unknown_phase_value",
                    detail=(
                        f"{raw_phase!r} is not a documented phase; "
                        "recorded as unknown rather than guessed"
                    ),
                )
            )

    me = sections.get("me", {})
    if "view" in me:
        raw_view = str(me["view"]).strip().lower()
        result.view = _VIEW_MAP.get(raw_view, ViewMode.UNKNOWN)
        if raw_view not in _VIEW_MAP:
            result.warnings.append(
                ParseWarning(field="me.view", code="unknown_view_value", detail=repr(me["view"]))
            )
    if "stance" in me:
        raw_stance = str(me["stance"]).strip().lower()
        result.stance = _STANCE_MAP.get(raw_stance, Stance.UNKNOWN)
        if raw_stance not in _STANCE_MAP:
            result.warnings.append(
                ParseWarning(
                    field="me.stance", code="unknown_stance_value", detail=repr(me["stance"])
                )
            )
    if "inVehicle" in me and _coerce_bool(me["inVehicle"]):
        result.movement = MovementState.IN_VEHICLE
    elif "movement" in me:
        raw_movement = str(me["movement"]).strip().lower()
        result.movement = _MOVEMENT_MAP.get(raw_movement, MovementState.UNKNOWN)
        if raw_movement not in _MOVEMENT_MAP:
            result.warnings.append(
                ParseWarning(
                    field="me.movement",
                    code="unknown_movement_value",
                    detail=repr(me["movement"]),
                )
            )
    if "freeView" in me:
        coerced = _coerce_bool(me["freeView"])
        if coerced is None:
            result.warnings.append(
                ParseWarning(field="me.freeView", code="not_a_boolean", detail=repr(me["freeView"]))
            )
        else:
            result.free_view = coerced

    return result


__all__ = [
    "DECLINED_FEATURES",
    "REQUIRED_FEATURES",
    "NormalizedUpdate",
    "extract_info_sections",
    "normalize_location",
    "normalize_update",
]
