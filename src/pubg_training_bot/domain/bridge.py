"""Bridge wire contract (Overwolf app -> Python controller).

Two rules drive this model:

1. The **raw** payload is preserved verbatim. Overwolf delivers nested JSON as
   strings; normalisation may be wrong, so the original must survive into the
   run bundle for offline re-parsing.
2. Malformed input is never quietly replaced by a plausible default. It becomes
   a :class:`ParseWarning` attached to the message.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import SCHEMA_VERSION
from .enums import MessageType


class ParseWarning(BaseModel):
    """A normalisation problem that must stay visible instead of being swallowed."""

    model_config = ConfigDict(frozen=True)

    field: str
    code: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.detail:
            return f"{self.field}: {self.code} ({self.detail})"
        return f"{self.field}: {self.code}"


class BridgeMessage(BaseModel):
    """One message received from the Overwolf bridge.

    Timestamps are kept separately on purpose: the bridge clock and the
    controller clock are different clocks, and only the controller's monotonic
    clock may drive control decisions.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    #: Monotonically increasing per bridge session; resets on reconnect.
    sequence: int = Field(ge=0)
    session_id: str = ""
    type: MessageType = MessageType.UNKNOWN

    #: Game/Overwolf supplied wall-clock epoch seconds, when the payload has one.
    source_timestamp: float | None = None
    #: Bridge-side monotonic seconds since bridge start.
    bridge_monotonic_ts: float = Field(ge=0.0)
    #: Controller-side monotonic seconds at receive time. Authoritative for freshness.
    controller_receive_ts: float | None = None

    #: Verbatim payload exactly as the bridge saw it (never mutated).
    raw: dict[str, Any] = Field(default_factory=dict)
    #: Best-effort normalised view. ``None`` means "not normalised", not "empty".
    normalized: dict[str, Any] | None = None
    parse_warnings: list[ParseWarning] = Field(default_factory=list)

    @field_validator("raw")
    @classmethod
    def _raw_must_be_mapping(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):  # pragma: no cover - pydantic enforces
            raise TypeError("raw payload must be a mapping")
        return value

    @property
    def has_warnings(self) -> bool:
        return bool(self.parse_warnings)

    def age_seconds(self, now_monotonic: float) -> float | None:
        """Age against the controller monotonic clock, or ``None`` if untimed."""
        if self.controller_receive_ts is None:
            return None
        return max(0.0, now_monotonic - self.controller_receive_ts)


def parse_maybe_nested_json(
    value: Any,
    *,
    field: str,
    warnings: list[ParseWarning] | None = None,
    max_depth: int = 3,
) -> Any:
    """Decode Overwolf values that are JSON documents wrapped in strings.

    Handles repeated wrapping (a JSON string containing a JSON string) up to
    ``max_depth`` levels. Returns the decoded object when the string is JSON,
    otherwise the original value. A string that *looks* like JSON but fails to
    decode produces a warning and is returned unchanged - never a fabricated
    substitute.
    """
    current = value
    for _ in range(max_depth):
        if not isinstance(current, str):
            break
        stripped = current.strip()
        # Object, array and quoted-string starts are the only candidates; a bare
        # HUD value such as "training" must survive untouched.
        if not stripped or stripped[0] not in '{["':
            break
        try:
            current = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if warnings is not None:
                warnings.append(
                    ParseWarning(field=field, code="nested_json_invalid", detail=str(exc))
                )
            return current
    return current


__all__ = ["BridgeMessage", "ParseWarning", "parse_maybe_nested_json"]
