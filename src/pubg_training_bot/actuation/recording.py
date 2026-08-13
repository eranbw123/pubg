"""Non-live actuators: the dry-run actuator used by default, and the fake used
by tests.

Neither imports any OS input API. That is asserted by
``tests/unit/test_safety_no_live_input.py``, which greps the whole source tree
for input-injection symbols.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ..clock import Clock
from ..domain.actuation import ActuationCommand, CommandBounds
from ..domain.enums import CommandOutcome, CommandType
from .base import ActuatorStatus, Guard


@dataclass
class RecordingActuator:
    """Runs the full guard chain and records the result without touching the OS.

    ``simulate_execution`` selects the two non-live behaviours:

    * ``False`` (:class:`DryRunActuator`) - a permitted command is still marked
      ``REJECTED_DRY_RUN`` so no report can ever imply input was sent;
    * ``True``  (:class:`FakeActuator`) - a permitted command is marked
      ``EXECUTED`` and held keys are tracked, so controller tests can exercise
      the success path and assert that everything is released afterwards.
    """

    clock: Clock
    guards: Sequence[Guard] = ()
    simulate_execution: bool = False
    name: str = "dry-run"
    command_bounds: CommandBounds = field(default_factory=CommandBounds)

    #: Non-live actuators can never be live. Enforced in :meth:`__post_init__`.
    live: bool = False

    _armed: bool = field(default=False, init=False)
    _emergency: bool = field(default=False, init=False)
    _held: list[str] = field(default_factory=list, init=False)
    _log: list[ActuationCommand] = field(default_factory=list, init=False)
    _seen: int = field(default=0, init=False)
    _executed: int = field(default=0, init=False)
    _rejected: int = field(default=0, init=False)
    _rejections: dict[str, int] = field(default_factory=dict, init=False)
    _release_all_calls: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.live:
            raise ValueError("RecordingActuator can never be live")

    # ------------------------------------------------------------------ #
    @property
    def bounds(self) -> CommandBounds:
        return self.command_bounds

    @property
    def log(self) -> list[ActuationCommand]:
        """Every command seen, with its resolved outcome."""
        return list(self._log)

    @property
    def executed_commands(self) -> list[ActuationCommand]:
        return [c for c in self._log if c.outcome is CommandOutcome.EXECUTED]

    @property
    def release_all_calls(self) -> int:
        return self._release_all_calls

    # ------------------------------------------------------------------ #
    def arm(self, reason: str) -> bool:
        if self._emergency:
            return False
        self._armed = True
        return True

    def disarm(self, reason: str) -> None:
        self._armed = False
        self.release_all(f"disarm: {reason}")

    def emergency_stop(self, reason: str) -> None:
        self._emergency = True
        self._armed = False
        self.release_all(f"emergency stop: {reason}")

    def reset_emergency_stop(self, reason: str) -> None:
        """Explicit, separate action: an e-stop never clears itself."""
        self._emergency = False

    def release_all(self, reason: str) -> None:
        self._held.clear()
        self._release_all_calls += 1

    # ------------------------------------------------------------------ #
    def submit(self, command: ActuationCommand) -> ActuationCommand:
        self._seen += 1
        now = self.clock.monotonic()

        resolved = self._evaluate(command, now)
        if resolved.outcome is CommandOutcome.EXECUTED:
            self._executed += 1
            self._apply(resolved)
        elif resolved.outcome is not CommandOutcome.PENDING:
            self._rejected += 1
            key = str(resolved.outcome)
            self._rejections[key] = self._rejections.get(key, 0) + 1

        self._log.append(resolved)
        return resolved

    def _evaluate(self, command: ActuationCommand, now: float) -> ActuationCommand:
        if self._emergency and command.type is not CommandType.RELEASE_ALL:
            return command.resolved(
                CommandOutcome.REJECTED_PRECONDITION, at=now, detail="emergency stop engaged"
            )
        if command.is_expired(now):
            return command.resolved(
                CommandOutcome.REJECTED_EXPIRED,
                at=now,
                detail=f"expired at {command.expires_at:.3f}, now {now:.3f}",
            )
        if not command.within(self.command_bounds):
            return command.resolved(
                CommandOutcome.REJECTED_BOUNDS, at=now, detail="command exceeds configured bounds"
            )
        if not self._armed and command.type is not CommandType.RELEASE_ALL:
            return command.resolved(
                CommandOutcome.REJECTED_NOT_ARMED, at=now, detail="actuator is not armed"
            )
        for guard in self.guards:
            result = guard.check(command, now)
            if not result.allowed:
                return command.resolved(
                    result.outcome, at=now, detail=f"{guard.name}: {result.reason}"
                )

        if not self.simulate_execution:
            return command.resolved(
                CommandOutcome.REJECTED_DRY_RUN,
                at=now,
                detail="dry-run actuator: no input was sent",
            )
        return command.resolved(CommandOutcome.EXECUTED, at=now, detail="simulated")

    def _apply(self, command: ActuationCommand) -> None:
        """Track simulated held state so release semantics are testable."""
        if command.type is CommandType.RELEASE_ALL:
            self._held.clear()
            self._release_all_calls += 1
        elif command.type is CommandType.KEY_HOLD and command.key:
            # A hold is bounded and self-releasing; it is only "held" for the
            # duration of the pulse, which the fake collapses to instantaneous.
            if command.key not in self._held:
                self._held.append(command.key)
            self._held.remove(command.key)

    # ------------------------------------------------------------------ #
    def status(self) -> ActuatorStatus:
        return ActuatorStatus(
            name=self.name,
            live=False,
            armed=self._armed,
            emergency_stopped=self._emergency,
            commands_seen=self._seen,
            commands_executed=self._executed,
            commands_rejected=self._rejected,
            rejection_counts=dict(self._rejections),
            keys_currently_held=list(self._held),
            last_command_id=self._log[-1].command_id if self._log else None,
            detail=(
                "simulated execution; no OS input"
                if self.simulate_execution
                else "dry-run; every command rejected before execution"
            ),
        )


def DryRunActuator(clock: Clock, guards: Sequence[Guard] = ()) -> RecordingActuator:  # noqa: N802
    """Default actuator: evaluates everything, sends nothing."""
    return RecordingActuator(clock=clock, guards=guards, simulate_execution=False, name="dry-run")


def FakeActuator(clock: Clock, guards: Sequence[Guard] = ()) -> RecordingActuator:  # noqa: N802
    """Test actuator: simulates success so controller logic can be exercised."""
    return RecordingActuator(clock=clock, guards=guards, simulate_execution=True, name="fake")


__all__ = ["DryRunActuator", "FakeActuator", "RecordingActuator"]
