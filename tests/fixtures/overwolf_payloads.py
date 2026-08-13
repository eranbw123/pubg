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

__all__ = [
    "GET_INFO_SNAPSHOT",
    "LOCATION_UPDATE",
    "MALFORMED_LOCATION",
    "MAP_UPDATE",
    "ME_UPDATE",
    "PHASE_UPDATE",
    "UNDOCUMENTED_PHASE",
]
