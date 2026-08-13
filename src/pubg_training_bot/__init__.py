"""PUBG Training Mode teach-and-repeat bot (Windows-only MVP).

Scope is deliberately narrow and enforced by :mod:`pubg_training_bot.safety`:
documented Overwolf game events, visible game pixels, ordinary OS-level input,
locally recorded routes and deterministic local algorithms only.
"""

__version__ = "0.1.0"

# Bumped whenever a persisted contract (bridge message / profile / route / run summary)
# changes in a non-backward-compatible way.
SCHEMA_VERSION = 1

__all__ = ["__version__", "SCHEMA_VERSION"]
