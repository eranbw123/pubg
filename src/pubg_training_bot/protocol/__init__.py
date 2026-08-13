"""Bridge transport: wire contract, session health, loopback server, normalisation."""

from .envelope import (
    PROTOCOL_VERSION,
    AuthRequest,
    AuthResponse,
    BridgeFrame,
    FeatureRegistration,
    generate_session_token,
)
from .normalize import (
    DECLINED_FEATURES,
    REQUIRED_FEATURES,
    NormalizedUpdate,
    normalize_location,
    normalize_update,
)
from .server import BridgeServer, ServerConfig
from .session import SessionTracker

__all__ = [
    "DECLINED_FEATURES",
    "PROTOCOL_VERSION",
    "REQUIRED_FEATURES",
    "AuthRequest",
    "AuthResponse",
    "BridgeFrame",
    "BridgeServer",
    "FeatureRegistration",
    "NormalizedUpdate",
    "ServerConfig",
    "SessionTracker",
    "generate_session_token",
    "normalize_location",
    "normalize_update",
]
