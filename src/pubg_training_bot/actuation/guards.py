"""Concrete guards.

Each guard is constructed with a callable rather than reaching for the OS
itself, so the full guard chain is unit-testable without a running game.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..domain.actuation import ActuationCommand
from ..domain.enums import CommandOutcome, CommandType
from ..domain.sensors import ExpectedContext, FreshnessPolicy, SensorSnapshot
from .base import GuardResult

#: RELEASE_ALL must never be blocked - refusing to let go of a key is the one
#: failure mode with no safe fallback.
_ALWAYS_ALLOWED = (CommandType.RELEASE_ALL,)


@dataclass
class ForegroundGuard:
    """Blocks input unless PUBG is the foreground window."""

    is_foreground: Callable[[], bool]
    name: str = "foreground"

    def check(self, command: ActuationCommand, now: float) -> GuardResult:
        if command.type in _ALWAYS_ALLOWED:
            return GuardResult(allowed=True)
        if self.is_foreground():
            return GuardResult(allowed=True)
        return GuardResult(
            allowed=False,
            outcome=CommandOutcome.REJECTED_PRECONDITION,
            reason="game window is not foreground",
        )


@dataclass
class SensorFreshnessGuard:
    """Blocks input when the controller's picture of the world is not current
    or does not match what the route expects."""

    get_snapshot: Callable[[], SensorSnapshot | None]
    policy: FreshnessPolicy
    expected: ExpectedContext
    name: str = "sensor_freshness"

    def check(self, command: ActuationCommand, now: float) -> GuardResult:
        if command.type in _ALWAYS_ALLOWED:
            return GuardResult(allowed=True)
        snapshot = self.get_snapshot()
        if snapshot is None:
            return GuardResult(
                allowed=False,
                outcome=CommandOutcome.REJECTED_PRECONDITION,
                reason="no sensor snapshot available",
            )
        evaluated = snapshot.evaluate(self.policy, self.expected)
        if evaluated.is_valid:
            return GuardResult(allowed=True)
        reasons = ",".join(str(r) for r in evaluated.invalid_reasons)
        return GuardResult(
            allowed=False,
            outcome=CommandOutcome.REJECTED_PRECONDITION,
            reason=f"sensor snapshot invalid: {reasons}",
        )


@dataclass
class CallableGuard:
    """Adapts any predicate into a guard (used for map/phase overrides)."""

    name: str
    predicate: Callable[[], bool]
    failure_reason: str

    def check(self, command: ActuationCommand, now: float) -> GuardResult:
        if command.type in _ALWAYS_ALLOWED:
            return GuardResult(allowed=True)
        if self.predicate():
            return GuardResult(allowed=True)
        return GuardResult(
            allowed=False,
            outcome=CommandOutcome.REJECTED_PRECONDITION,
            reason=self.failure_reason,
        )


__all__ = ["CallableGuard", "ForegroundGuard", "SensorFreshnessGuard"]
