"""Actuator registry.

The registry is the single place that answers "can this build send real input
to the game?". At Stage 0 the answer is no, because no live implementation is
registered - not because a flag happens to be off.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..clock import Clock
from .base import Actuator, Guard
from .recording import DryRunActuator, FakeActuator


@dataclass(frozen=True)
class ActuatorDescriptor:
    key: str
    description: str
    live: bool
    #: Stage that introduces this implementation.
    since_stage: str
    factory: Callable[[Clock, Sequence[Guard]], Actuator] | None


_REGISTRY: dict[str, ActuatorDescriptor] = {
    "dry-run": ActuatorDescriptor(
        key="dry-run",
        description="Evaluates guards and logs commands; never sends input.",
        live=False,
        since_stage="00",
        factory=lambda clock, guards: DryRunActuator(clock, guards),
    ),
    "fake": ActuatorDescriptor(
        key="fake",
        description="Simulates successful execution for tests; never sends input.",
        live=False,
        since_stage="00",
        factory=lambda clock, guards: FakeActuator(clock, guards),
    ),
    # The live OS-input actuator is registered here in Stage 3 and nowhere else.
    # (The scope scanner in safety.py flags the injection symbols themselves even
    # inside comments, so this note names none of them.)
}

DEFAULT_ACTUATOR = "dry-run"


def list_actuators() -> list[ActuatorDescriptor]:
    return sorted(_REGISTRY.values(), key=lambda d: d.key)


def live_actuator_available() -> bool:
    """True only when a registered actuator can actually send OS input."""
    return any(d.live and d.factory is not None for d in _REGISTRY.values())


def create_actuator(
    key: str = DEFAULT_ACTUATOR,
    *,
    clock: Clock,
    guards: Sequence[Guard] = (),
) -> Actuator:
    descriptor = _REGISTRY.get(key)
    if descriptor is None:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown actuator {key!r}; known actuators: {known}")
    if descriptor.factory is None:
        raise NotImplementedError(
            f"actuator {key!r} is declared but not implemented (arrives in Stage "
            f"{descriptor.since_stage})"
        )
    return descriptor.factory(clock, guards)


def require_live_actuator() -> None:
    """Called by any code path that intends to send real input.

    Raises until Stage 3 registers a live implementation, so ``--live`` cannot
    silently degrade into a no-op that looks like a successful run.
    """
    if not live_actuator_available():
        raise NotImplementedError(
            "No live actuator is registered in this build. Live input is introduced in "
            "Stage 3 (bounded live input feasibility). Current stage ships dry-run and "
            "fake actuators only."
        )


__all__ = [
    "DEFAULT_ACTUATOR",
    "ActuatorDescriptor",
    "create_actuator",
    "list_actuators",
    "live_actuator_available",
    "require_live_actuator",
]
