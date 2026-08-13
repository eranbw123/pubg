"""Vision layer.

Deliberately narrow: heading from the HUD compass, interaction-prompt presence,
and route-specific visual anchors at choke points. No scene understanding, no
object detection, no learned models.
"""

from .fake_heading import FakeHeadingProvider, ScriptedHeading
from .heading import HeadingProvider, HeadingProviderStatus

__all__ = [
    "FakeHeadingProvider",
    "HeadingProvider",
    "HeadingProviderStatus",
    "ScriptedHeading",
]
