"""Actuation layer: the only place allowed to produce game input.

Stage 0 contains no live implementation at all. See
:mod:`pubg_training_bot.actuation.registry`.
"""

from .base import Actuator, ActuatorStatus, Guard, GuardResult
from .guards import CallableGuard, ForegroundGuard, SensorFreshnessGuard
from .recording import DryRunActuator, FakeActuator, RecordingActuator
from .registry import (
    DEFAULT_ACTUATOR,
    ActuatorDescriptor,
    create_actuator,
    list_actuators,
    live_actuator_available,
    require_live_actuator,
)

__all__ = [
    "DEFAULT_ACTUATOR",
    "Actuator",
    "ActuatorDescriptor",
    "ActuatorStatus",
    "CallableGuard",
    "DryRunActuator",
    "FakeActuator",
    "ForegroundGuard",
    "Guard",
    "GuardResult",
    "RecordingActuator",
    "SensorFreshnessGuard",
    "create_actuator",
    "list_actuators",
    "live_actuator_available",
    "require_live_actuator",
]
