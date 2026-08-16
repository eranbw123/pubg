"""Sensor sources: whatever can tell the controller where the player is.

Stage 0 ships the interface plus a scripted fake. The live Overwolf-backed
implementation arrives in Stage 1 and must satisfy the same contract.
"""

from .base import SensorSource, SensorSourceStatus
from .fake import FakeSensorSource, ScriptedSample

__all__ = [
    "FakeSensorSource",
    "ScriptedSample",
    "SensorSource",
    "SensorSourceStatus",
]
