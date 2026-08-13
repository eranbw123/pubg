"""Typed, versioned data contracts shared by every layer.

This package is pure: no I/O, no OS calls, no game access. Everything here is
deterministically testable.
"""

from .actuation import ActuationCommand, CommandBounds, release_all
from .bridge import BridgeMessage, ParseWarning, parse_maybe_nested_json
from .enums import (
    BridgeHealth,
    CommandOutcome,
    CommandType,
    ControlState,
    InvalidReason,
    MatchPhase,
    MessageType,
    MovementMode,
    MovementState,
    NodeKind,
    RecoveryLevel,
    RunOutcome,
    SemanticAction,
    Stance,
    ViewMode,
)
from .profile import CropRegion, GameProfile, KeyBindings, Rect
from .route import BoxRegion, CircleRegion, RecoveryPolicy, Route, RouteEdge, RouteNode
from .run import RunManifest, RunSummary, SensorSummary, StateTransition
from .sensors import (
    ExpectedContext,
    FreshnessPolicy,
    HeadingReading,
    SensorSnapshot,
    Vec3,
    WeaponState,
)

__all__ = [
    "ActuationCommand",
    "BoxRegion",
    "BridgeHealth",
    "BridgeMessage",
    "CircleRegion",
    "CommandBounds",
    "CommandOutcome",
    "CommandType",
    "ControlState",
    "CropRegion",
    "ExpectedContext",
    "FreshnessPolicy",
    "GameProfile",
    "HeadingReading",
    "InvalidReason",
    "KeyBindings",
    "MatchPhase",
    "MessageType",
    "MovementMode",
    "MovementState",
    "NodeKind",
    "ParseWarning",
    "Rect",
    "RecoveryLevel",
    "RecoveryPolicy",
    "Route",
    "RouteEdge",
    "RouteNode",
    "RunManifest",
    "RunOutcome",
    "RunSummary",
    "SemanticAction",
    "SensorSnapshot",
    "SensorSummary",
    "Stance",
    "StateTransition",
    "Vec3",
    "ViewMode",
    "WeaponState",
    "parse_maybe_nested_json",
    "release_all",
]
