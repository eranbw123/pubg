"""Actuation contract.

Two invariants encoded here rather than in prose:

* every command is **bounded** - a hold has a maximum duration, a mouse move has
  a maximum delta, and the model refuses to construct anything larger;
* every command **expires** - a command issued three seconds ago against a
  sensor reading that has since gone stale must not execute.
"""

from __future__ import annotations

import itertools
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import CommandOutcome, CommandType, ControlState

#: Hard ceilings. Route/profile config may lower these; nothing may raise them.
MAX_KEY_HOLD_MS = 1200
MAX_MOUSE_DELTA_UNITS = 600
MAX_COMMAND_LIFETIME_S = 2.0

_command_counter = itertools.count(1)


def next_command_id(prefix: str = "cmd") -> str:
    return f"{prefix}-{next(_command_counter):06d}"


class CommandBounds(BaseModel):
    """Per-run ceilings, always clamped to the module-level hard limits."""

    model_config = ConfigDict(frozen=True)

    max_key_hold_ms: int = Field(default=MAX_KEY_HOLD_MS, gt=0, le=MAX_KEY_HOLD_MS)
    max_mouse_delta_units: int = Field(
        default=MAX_MOUSE_DELTA_UNITS, gt=0, le=MAX_MOUSE_DELTA_UNITS
    )
    max_lifetime_s: float = Field(default=MAX_COMMAND_LIFETIME_S, gt=0, le=MAX_COMMAND_LIFETIME_S)


class ActuationCommand(BaseModel):
    """A single bounded input intent. Construction validates the bounds; the
    actuator re-validates before execution (defence in depth)."""

    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(default_factory=next_command_id)
    type: CommandType

    #: Logical key name resolved against GameProfile.key_bindings (KEY_* commands).
    key: str | None = None
    hold_ms: int | None = Field(default=None, ge=0, le=MAX_KEY_HOLD_MS)
    mouse_dx: int | None = Field(default=None, ge=-MAX_MOUSE_DELTA_UNITS, le=MAX_MOUSE_DELTA_UNITS)
    mouse_dy: int | None = Field(default=None, ge=-MAX_MOUSE_DELTA_UNITS, le=MAX_MOUSE_DELTA_UNITS)
    button: str | None = None

    #: Human-readable justification, surfaced in the run report.
    reason: str
    issuing_state: ControlState
    issued_at: float
    expires_at: float
    #: Conditions that must still hold at execution time.
    preconditions: tuple[str, ...] = ()

    outcome: CommandOutcome = CommandOutcome.PENDING
    outcome_detail: str = ""
    executed_at: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _shape_matches_type(self) -> ActuationCommand:
        if self.expires_at < self.issued_at:
            raise ValueError("expires_at must be >= issued_at")
        if self.expires_at - self.issued_at > MAX_COMMAND_LIFETIME_S + 1e-9:
            raise ValueError(f"command lifetime exceeds {MAX_COMMAND_LIFETIME_S}s")

        if self.type in (CommandType.KEY_TAP, CommandType.KEY_HOLD):
            if not self.key:
                raise ValueError(f"{self.type} requires a key")
            if self.type is CommandType.KEY_HOLD and not self.hold_ms:
                raise ValueError("key_hold requires a positive hold_ms")
        elif self.type is CommandType.MOUSE_MOVE:
            if self.mouse_dx is None and self.mouse_dy is None:
                raise ValueError("mouse_move requires mouse_dx and/or mouse_dy")
        elif self.type is CommandType.MOUSE_CLICK:
            if not self.button:
                raise ValueError("mouse_click requires a button")
        return self

    # ------------------------------------------------------------------ #
    def is_expired(self, now_monotonic: float) -> bool:
        return now_monotonic > self.expires_at

    def within(self, bounds: CommandBounds) -> bool:
        if self.hold_ms is not None and self.hold_ms > bounds.max_key_hold_ms:
            return False
        for delta in (self.mouse_dx, self.mouse_dy):
            if delta is not None and abs(delta) > bounds.max_mouse_delta_units:
                return False
        return (self.expires_at - self.issued_at) <= bounds.max_lifetime_s + 1e-9

    def resolved(
        self,
        outcome: CommandOutcome,
        *,
        at: float | None = None,
        detail: str = "",
    ) -> ActuationCommand:
        return self.model_copy(
            update={"outcome": outcome, "executed_at": at, "outcome_detail": detail}
        )


def release_all(
    *,
    reason: str,
    state: ControlState,
    now: float,
    lifetime_s: float = MAX_COMMAND_LIFETIME_S,
) -> ActuationCommand:
    """The one command that is always legal - including during abort."""
    return ActuationCommand(
        type=CommandType.RELEASE_ALL,
        reason=reason,
        issuing_state=state,
        issued_at=now,
        expires_at=now + min(lifetime_s, MAX_COMMAND_LIFETIME_S),
    )


__all__ = [
    "MAX_COMMAND_LIFETIME_S",
    "MAX_KEY_HOLD_MS",
    "MAX_MOUSE_DELTA_UNITS",
    "ActuationCommand",
    "CommandBounds",
    "next_command_id",
    "release_all",
]
