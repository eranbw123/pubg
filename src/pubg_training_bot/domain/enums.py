"""Closed vocabularies shared across the controller.

Every enum has an ``UNKNOWN`` member where the value originates from the game.
Unknown is a first-class state: the controller must be able to say "I do not
know" instead of guessing a plausible default.
"""

from __future__ import annotations

from enum import StrEnum


# --------------------------------------------------------------------------- #
# Bridge / transport
# --------------------------------------------------------------------------- #
class MessageType(StrEnum):
    """Bridge -> controller message kinds."""

    HELLO = "hello"
    HEARTBEAT = "heartbeat"
    FEATURE_STATUS = "feature_status"
    INFO_UPDATE = "info_update"
    GAME_EVENT = "game_event"
    GAME_INFO = "game_info"
    SCREENSHOT = "screenshot"
    BRIDGE_ERROR = "bridge_error"
    UNKNOWN = "unknown"


class BridgeHealth(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STALE = "stale"


# --------------------------------------------------------------------------- #
# Game state (values are normalised by the bridge; raw values are preserved)
# --------------------------------------------------------------------------- #
class ViewMode(StrEnum):
    FPP = "fpp"
    TPP = "tpp"
    UNKNOWN = "unknown"


class Stance(StrEnum):
    STANDING = "standing"
    CROUCHING = "crouching"
    PRONE = "prone"
    UNKNOWN = "unknown"


class MovementState(StrEnum):
    IDLE = "idle"
    WALKING = "walking"
    RUNNING = "running"
    IN_VEHICLE = "in_vehicle"
    PARACHUTING = "parachuting"
    SWIMMING = "swimming"
    UNKNOWN = "unknown"


class MatchPhase(StrEnum):
    """PUBG's own documented phase vocabulary.

    Deliberately the game's values rather than a generic loading/playing/finished
    mapping: a lossy translation would hide which phase Training Mode actually
    reports, and that is one of the things Stage 1 exists to observe.
    """

    LOBBY = "lobby"
    LOADING_SCREEN = "loading_screen"
    AIRFIELD = "airfield"
    AIRCRAFT = "aircraft"
    FREEFLY = "freefly"
    #: On the ground and in control of the character - the only phase in which
    #: navigation may run.
    LANDED = "landed"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Sensor confidence
# --------------------------------------------------------------------------- #
class InvalidReason(StrEnum):
    """Why a :class:`SensorSnapshot` is not trustworthy enough to act on."""

    BRIDGE_DISCONNECTED = "bridge_disconnected"
    LOCATION_MISSING = "location_missing"
    LOCATION_STALE = "location_stale"
    HEADING_MISSING = "heading_missing"
    HEADING_STALE = "heading_stale"
    HEADING_LOW_CONFIDENCE = "heading_low_confidence"
    FRAME_MISSING = "frame_missing"
    FRAME_STALE = "frame_stale"
    MAP_MISSING = "map_missing"
    MAP_MISMATCH = "map_mismatch"
    PHASE_MISMATCH = "phase_mismatch"
    VIEW_MISMATCH = "view_mismatch"
    STANCE_MISMATCH = "stance_mismatch"
    FREE_VIEW_ACTIVE = "free_view_active"
    NOT_FOREGROUND = "not_foreground"
    NOT_ARMED = "not_armed"
    OUTSIDE_START_REGION = "outside_start_region"
    PROFILE_MISMATCH = "profile_mismatch"


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
class NodeKind(StrEnum):
    START = "start"
    TRANSIT = "transit"
    CHECKPOINT = "checkpoint"
    DOOR = "door"
    LOOT_SCAN = "loot_scan"
    STAIR_START = "stair_start"
    STAIR_END = "stair_end"
    ROOM_ENTRY = "room_entry"
    ROOM_EXIT = "room_exit"
    FINISH = "finish"


#: Nodes that carry meaning beyond "a point on the path". Route simplification
#: must never remove or move these.
SEMANTIC_NODE_KINDS: frozenset[NodeKind] = frozenset(
    {
        NodeKind.START,
        NodeKind.CHECKPOINT,
        NodeKind.DOOR,
        NodeKind.LOOT_SCAN,
        NodeKind.STAIR_START,
        NodeKind.STAIR_END,
        NodeKind.ROOM_ENTRY,
        NodeKind.ROOM_EXIT,
        NodeKind.FINISH,
    }
)


class MovementMode(StrEnum):
    WALK = "walk"
    RUN = "run"
    CROUCH_WALK = "crouch_walk"
    #: Deliberate slow, very short pulses (stairs, doorways).
    CAREFUL = "careful"


class SemanticAction(StrEnum):
    NONE = "none"
    OPEN_DOOR = "open_door"
    CROSS_DOOR = "cross_door"
    CLIMB_STAIRS = "climb_stairs"
    DESCEND_STAIRS = "descend_stairs"
    SCAN_AND_LOOT = "scan_and_loot"
    VERIFY_ANCHOR = "verify_anchor"


# --------------------------------------------------------------------------- #
# Actuation
# --------------------------------------------------------------------------- #
class CommandType(StrEnum):
    """Only bounded operations exist. There is no indefinite key-down command."""

    KEY_TAP = "key_tap"
    KEY_HOLD = "key_hold"
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    RELEASE_ALL = "release_all"


class CommandOutcome(StrEnum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED_DRY_RUN = "rejected_dry_run"
    REJECTED_NOT_ARMED = "rejected_not_armed"
    REJECTED_PRECONDITION = "rejected_precondition"
    REJECTED_EXPIRED = "rejected_expired"
    REJECTED_BOUNDS = "rejected_bounds"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# Controller state machine (full set declared now; implemented in Stage 6)
# --------------------------------------------------------------------------- #
class ControlState(StrEnum):
    IDLE = "idle"
    PRECHECK = "precheck"
    ACQUIRE_SENSORS = "acquire_sensors"
    ACQUIRE_HEADING = "acquire_heading"
    ALIGN_TO_EDGE = "align_to_edge"
    ADVANCE_EDGE = "advance_edge"
    VERIFY_NODE = "verify_node"
    EXECUTE_DOOR = "execute_door"
    EXECUTE_STAIRS = "execute_stairs"
    EXECUTE_LOOT = "execute_loot"
    RECOVER = "recover"
    COMPLETE = "complete"
    ABORT = "abort"


class RecoveryLevel(StrEnum):
    """Bounded recovery ladder (Section 18)."""

    L0_RELEASE_AND_SETTLE = "l0_release_and_settle"
    L1_REALIGN_RETRY = "l1_realign_retry"
    L2_BACK_OFF = "l2_back_off"
    L3_SIDESTEP = "l3_sidestep"
    L4_INTERACT_OR_VAULT = "l4_interact_or_vault"
    L5_RETURN_TO_CHECKPOINT = "l5_return_to_checkpoint"
    L6_VISUAL_REACQUIRE = "l6_visual_reacquire"
    L7_ABORT = "l7_abort"


#: Ordered ladder used by the recovery engine (Stage 11).
RECOVERY_LADDER: tuple[RecoveryLevel, ...] = (
    RecoveryLevel.L0_RELEASE_AND_SETTLE,
    RecoveryLevel.L1_REALIGN_RETRY,
    RecoveryLevel.L2_BACK_OFF,
    RecoveryLevel.L3_SIDESTEP,
    RecoveryLevel.L4_INTERACT_OR_VAULT,
    RecoveryLevel.L5_RETURN_TO_CHECKPOINT,
    RecoveryLevel.L6_VISUAL_REACQUIRE,
    RecoveryLevel.L7_ABORT,
)


class RunOutcome(StrEnum):
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"
    EMERGENCY_STOPPED = "emergency_stopped"
    DRY_RUN = "dry_run"


__all__ = [
    "RECOVERY_LADDER",
    "SEMANTIC_NODE_KINDS",
    "BridgeHealth",
    "CommandOutcome",
    "CommandType",
    "ControlState",
    "InvalidReason",
    "MatchPhase",
    "MessageType",
    "MovementMode",
    "MovementState",
    "NodeKind",
    "RecoveryLevel",
    "RunOutcome",
    "SemanticAction",
    "Stance",
    "StrEnum",
    "ViewMode",
]
