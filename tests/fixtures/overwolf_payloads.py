"""Payload fixtures taken from Overwolf's published PUBG game-events docs.

These are the *documented* shapes, not shapes invented to make the parser pass.
Stage 1's live probe records what the game really sends; if it differs, these
fixtures get corrected and the difference goes into docs/decisions.md.
"""

from __future__ import annotations

from typing import Any

#: `location` arrives as a JSON string, not an object.
LOCATION_UPDATE: dict[str, Any] = {
    "info": {"location": {"location": '{"x":2300,"y":5740,"z":1520}'}},
    "feature": "location",
}

ME_UPDATE: dict[str, Any] = {
    "info": {
        "me": {
            "view": "FPP",
            "stance": "stand",
            "movement": "normal",
            "freeView": False,
            "inVehicle": False,
            "bodyPosition": "straight",
            "health": '{"health":100,"ko_health":100}',
        }
    },
    "feature": "me",
}

MAP_UPDATE: dict[str, Any] = {"info": {"map": {"map": "Erangel_Main"}}, "feature": "map"}

PHASE_UPDATE: dict[str, Any] = {"info": {"phase": {"phase": "landed"}}, "feature": "phase"}

#: `getInfo` uses `res` rather than `info`.
GET_INFO_SNAPSHOT: dict[str, Any] = {
    "res": {
        "map": {"map": "Erangel_Main"},
        "phase": {"phase": "landed"},
        "me": {"view": "TPP", "stance": "crouch", "movement": "fast", "freeView": True},
        "location": {"location": '{"x":1.5,"y":-2.5,"z":30}'},
    },
    "status": "success",
}

MALFORMED_LOCATION: dict[str, Any] = {
    "info": {"location": {"location": '{"x":1,"y":'}},
    "feature": "location",
}

UNDOCUMENTED_PHASE: dict[str, Any] = {
    "info": {"phase": {"phase": "training_ground"}},
    "feature": "phase",
}

#: Captured live from GEP 311.2.2 on 2026-08-16. The documented shape and the
#: real one differ in two ways that broke normalisation:
#:   * the map arrives as `match_info.map` (internal name), not a `map` section
#:   * the phase arrives as `game_info.phase`, not a `phase` section
#: `me` also has no `stance` key in this version, and its booleans are strings.
#: Roster entries are redacted by the bridge before they ever reach the
#: controller, so the placeholder key is what a real bundle contains.
LIVE_GETINFO_AIRCRAFT: dict[str, Any] = {
    "success": True,
    "status": "success",
    "res": {
        "game_info": {"phase": "aircraft", "safe_zone": None, "blue_zone": None},
        "gep_internal": {"version_info": '{"local_version":"311.2.2","is_updated":true}'},
        "me": {
            "movement": "normal",
            "bodyPosition": "straight",
            "inVehicle": "false",
            "view": "TPP",
            "health": '{"health":0,"ko_health":100}',
            "freeView": "false",
        },
        "match_info": {
            "map": "Baltic_Main",
            "mode": "solo",
            "total_teams": "100",
            "_roster_entries_redacted": 101,
        },
    },
}

__all__ = [
    "LIVE_GETINFO_AIRCRAFT",
    "GET_INFO_SNAPSHOT",
    "LOCATION_UPDATE",
    "MALFORMED_LOCATION",
    "MAP_UPDATE",
    "ME_UPDATE",
    "PHASE_UPDATE",
    "UNDOCUMENTED_PHASE",
]
