"""Actuator interface and the guard chain every command must survive.

Design rules encoded here:

* **Single writer.** Exactly one actuator instance owns the keyboard and mouse.
* **Bounded verbs only.** The public surface is tap / hold / move / click /
  release-all. There is no public indefinite key-down.
* **Dry-run by default.** ``live=False`` is the default everywhere; a live
  actuator must be explicitly constructed and explicitly armed.
* **Guards before every command**, not once at startup: foreground, freshness,
  arming, expiry and bounds are re-checked at execution time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..domain.actuation import ActuationCommand, CommandBounds
from ..domain.enums import CommandOutcome


class ActuatorStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    live: bool = False
    armed: bool = False
    emergency_stopped: bool = False
    commands_seen: int = 0
    commands_executed: int = 0
    commands_rejected: int = 0
    rejection_counts: dict[str, int] = Field(default_factory=dict)
    keys_currently_held: list[str] = Field(default_factory=list)
    last_command_id: str | None = None
    detail: str = ""

    @property
    def is_clean(self) -> bool:
        """True when nothing is held down - checked after every run and abort."""
        return not self.keys_currently_held


class GuardResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    outcome: CommandOutcome = CommandOutcome.PENDING
    reason: str = ""


@runtime_checkable
class Guard(Protocol):
    """A precondition evaluated immediately before execution."""

    name: str

    def check(self, command: ActuationCommand, now: float) -> GuardResult: ...


@runtime_checkable
class Actuator(Protocol):
    """Executes bounded commands, or explains why it refused."""

    name: str
    live: bool

    def arm(self, reason: str) -> bool:
        """Enable execution. Returns False if arming is not permitted."""
        ...

    def disarm(self, reason: str) -> None: ...

    def emergency_stop(self, reason: str) -> None:
        """Release everything and refuse all further commands until reset."""
        ...

    def submit(self, command: ActuationCommand) -> ActuationCommand:
        """Run the guard chain and (if live and allowed) execute.

        Always returns the command with its ``outcome`` resolved - a silently
        dropped command would be invisible in the run report.
        """
        ...

    def release_all(self, reason: str) -> None:
        """Release every held control. Must be safe to call at any time,
        including from an exception handler."""
        ...

    def status(self) -> ActuatorStatus: ...

    @property
    def bounds(self) -> CommandBounds: ...


__all__ = ["Actuator", "ActuatorStatus", "Guard", "GuardResult"]
