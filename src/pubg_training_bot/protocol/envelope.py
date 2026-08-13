"""Wire contract between the Overwolf bridge and the Python controller.

Loopback only, token-authenticated. The bridge is a sensor: this protocol has
no command direction that could reach the game. The only controller -> bridge
messages are the auth acknowledgement and heartbeats.

Two rules the rest of the stack depends on:

* the ``raw`` field is passed through untouched, so a run bundle can be
  re-parsed offline months later against a corrected normaliser;
* the bridge's own ``normalized`` view is advisory. The controller re-derives
  everything from ``raw`` itself, so a bug in the TypeScript normaliser cannot
  silently become the controller's belief.
"""

from __future__ import annotations

import secrets
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .. import SCHEMA_VERSION

#: Bumped only for breaking wire changes; both sides refuse a mismatch.
PROTOCOL_VERSION = 1

#: Controller -> bridge.
MSG_AUTH_OK = "auth_ok"
MSG_AUTH_FAILED = "auth_failed"
MSG_PONG = "pong"

#: Bridge -> controller.
MSG_AUTH = "auth"


def generate_session_token(nbytes: int = 24) -> str:
    """Fresh per-session shared secret. Never persisted to the repo."""
    return secrets.token_urlsafe(nbytes)


class AuthRequest(BaseModel):
    """First frame the bridge must send. Anything else is rejected."""

    model_config = ConfigDict(extra="allow")

    type: Literal["auth"] = "auth"
    protocol_version: int
    token: str
    bridge_version: str = ""
    session_id: str = ""
    #: Overwolf client version, for the run bundle's provenance record.
    overwolf_version: str = ""


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    protocol_version: int = PROTOCOL_VERSION
    schema_version: int = SCHEMA_VERSION
    accepted: bool
    detail: str = ""
    #: Interval the bridge should heartbeat at, in seconds.
    heartbeat_interval_s: float = 1.0


class FeatureRegistration(BaseModel):
    """Outcome of ``overwolf.games.events.setRequiredFeatures`` per feature.

    Recorded per feature rather than as one boolean: a partially registered
    provider is the realistic failure, and it must be visible rather than
    inferred later from missing data.
    """

    model_config = ConfigDict(extra="forbid")

    feature: str
    registered: bool
    detail: str = ""


class BridgeFrame(BaseModel):
    """Any bridge -> controller frame after successful auth."""

    model_config = ConfigDict(extra="allow")

    type: str
    sequence: int = Field(ge=0)
    #: Bridge monotonic milliseconds since bridge start.
    bridge_ts_ms: float = Field(ge=0)
    #: Wall-clock epoch milliseconds, when the bridge has one.
    source_ts_ms: float | None = None
    #: Untouched payload exactly as Overwolf delivered it.
    raw: dict[str, Any] = Field(default_factory=dict)
    #: Advisory. The controller re-derives its own view from ``raw``.
    normalized: dict[str, Any] | None = None
    #: Feature name for info updates, when known.
    feature: str | None = None


__all__ = [
    "MSG_AUTH",
    "MSG_AUTH_FAILED",
    "MSG_AUTH_OK",
    "MSG_PONG",
    "PROTOCOL_VERSION",
    "AuthRequest",
    "AuthResponse",
    "BridgeFrame",
    "FeatureRegistration",
    "generate_session_token",
]
