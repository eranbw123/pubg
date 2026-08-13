"""Frame capture providers.

Stage 0 defines the interface and a synthetic provider. Real providers
(Windows Graphics Capture, Overwolf screenshot fallback) are implemented and
*benchmarked against the running game* in Stage 2 - provider choice is decided
by measurement, not by theoretical speed.
"""

from .base import CaptureProvider, CaptureStatus, Frame
from .fake import FakeCaptureProvider

__all__ = ["CaptureProvider", "CaptureStatus", "FakeCaptureProvider", "Frame"]
