"""GameProfile: every environmental assumption, in one versioned, fingerprinted file.

Nothing in this project may hardcode a resolution, a crop rectangle, a key
binding or a calibration constant. If it varies with the machine, the display
or the game settings, it lives here.

The *fingerprint* is a hash over the fields that would invalidate a recorded
route if they changed. A route records the fingerprint it was recorded under;
replaying against a different fingerprint is refused.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .. import SCHEMA_VERSION
from .enums import ViewMode


class Rect(BaseModel):
    """Pixel rectangle (screen or window space)."""

    model_config = ConfigDict(frozen=True)

    left: int
    top: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


class CropRegion(BaseModel):
    """A HUD region in **normalised** window coordinates (0..1).

    Normalised so a profile survives a resolution change with only a
    re-verification step rather than a rewrite. ``calibrated=False`` marks a
    placeholder that has never been checked against a real frame - vision code
    must refuse to trust it.
    """

    model_config = ConfigDict(frozen=True)

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)
    calibrated: bool = False
    note: str = ""

    @model_validator(mode="after")
    def _within_bounds(self) -> CropRegion:
        if self.x + self.width > 1.0 + 1e-9:
            raise ValueError("crop exceeds right edge of window")
        if self.y + self.height > 1.0 + 1e-9:
            raise ValueError("crop exceeds bottom edge of window")
        return self

    def to_pixels(self, window: Rect) -> Rect:
        return Rect(
            left=window.left + round(self.x * window.width),
            top=window.top + round(self.y * window.height),
            width=max(1, round(self.width * window.width)),
            height=max(1, round(self.height * window.height)),
        )


class KeyBindings(BaseModel):
    """Key names are resolved to scan codes by the actuation layer (Stage 3),
    so these stay layout-independent."""

    model_config = ConfigDict(frozen=True)

    forward: str = "w"
    backward: str = "s"
    strafe_left: str = "a"
    strafe_right: str = "d"
    interact: str = "f"
    jump: str = "space"
    crouch: str = "left_ctrl"
    sprint: str = "left_shift"
    walk_toggle: str = "left_alt"
    free_look: str = "left_alt"
    inventory: str = "tab"
    map_key: str = "m"


class CoordinateTransform(BaseModel):
    """Maps compass heading to a unit displacement in game XY.

    Deliberately a general 2x2 matrix rather than "X is east, Y is north": the
    axis assignment, handedness and sign are *unknown* until Stage 4 fits them
    from real walk data. ``fitted=False`` means the identity placeholder below
    has never been validated and must not be used for navigation.
    """

    model_config = ConfigDict(frozen=True)

    #: unit_xy = (m00*sin(h) + m01*cos(h), m10*sin(h) + m11*cos(h))
    m00: float = 1.0
    m01: float = 0.0
    m10: float = 0.0
    m11: float = 1.0
    #: Game units per metre of real travel (unknown until measured).
    units_per_metre: float = Field(default=1.0, gt=0)
    #: Sign of Z when moving up (+1 or -1); unknown until measured on stairs.
    z_up_sign: int = Field(default=1)
    fitted: bool = False
    fit_rmse_deg: float | None = None
    fit_sample_count: int = 0


class MovementCalibration(BaseModel):
    model_config = ConfigDict(frozen=True)

    walk_units_per_second: float | None = None
    run_units_per_second: float | None = None
    #: Observed position noise while standing perfectly still (game units).
    stationary_noise_p95_units: float | None = None
    #: Delay between issuing a key and seeing position change.
    actuation_latency_s: float | None = None
    measured: bool = False


class MouseTurnCalibration(BaseModel):
    model_config = ConfigDict(frozen=True)

    #: Degrees of yaw per unit of relative mouse dx. Sign included.
    degrees_per_unit: float | None = None
    #: Largest single pulse the controller may issue.
    max_pulse_units: int = Field(default=400, gt=0)
    #: Below this, the game may swallow the input entirely.
    min_effective_units: int = Field(default=2, gt=0)
    repeatability_std_deg: float | None = None
    measured: bool = False


class CaptureSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "none"
    target_fps: float = Field(default=8.0, gt=0)
    window_title_hint: str = "PLAYERUNKNOWN'S BATTLEGROUNDS"
    process_name_hint: str = "TslGame.exe"
    benchmarked: bool = False


class GameProfile(BaseModel):
    """Versioned bundle of display, game-settings and calibration state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    profile_id: str
    description: str = ""

    map_id: str | None = None
    screen_width: int = Field(gt=0)
    screen_height: int = Field(gt=0)
    window_rect: Rect | None = None
    dpi_scale: float = Field(default=1.0, gt=0)
    ui_scale: float | None = None

    view: ViewMode = ViewMode.FPP
    fov: float | None = None
    mouse_sensitivity: float | None = None
    ads_sensitivity: float | None = None
    language: str = "en"
    key_bindings: KeyBindings = Field(default_factory=KeyBindings)

    capture: CaptureSettings = Field(default_factory=CaptureSettings)
    compass_crop: CropRegion | None = None
    interaction_crop: CropRegion | None = None
    inventory_crop: CropRegion | None = None

    coordinate_transform: CoordinateTransform = Field(default_factory=CoordinateTransform)
    movement: MovementCalibration = Field(default_factory=MovementCalibration)
    mouse_turn: MouseTurnCalibration = Field(default_factory=MouseTurnCalibration)

    #: Free-text notes about how this profile was produced.
    notes: str = ""

    # ------------------------------------------------------------------ #
    @property
    def fingerprint(self) -> str:
        """Stable hash of the fields a recorded route depends on."""
        material = {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "map_id": self.map_id,
            "screen": [self.screen_width, self.screen_height],
            "dpi_scale": round(self.dpi_scale, 4),
            "view": str(self.view),
            "fov": self.fov,
            "mouse_sensitivity": self.mouse_sensitivity,
            "language": self.language,
            "key_bindings": self.key_bindings.model_dump(mode="json"),
            "coordinate_transform": self.coordinate_transform.model_dump(mode="json"),
        }
        blob = json.dumps(material, sort_keys=True, separators=(",", ":"))
        return "gp1:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def readiness(self) -> dict[str, bool]:
        """Which parts of this profile have real measurements behind them."""
        return {
            "capture_benchmarked": self.capture.benchmarked,
            "compass_crop_calibrated": bool(self.compass_crop and self.compass_crop.calibrated),
            "interaction_crop_calibrated": bool(
                self.interaction_crop and self.interaction_crop.calibrated
            ),
            "coordinate_transform_fitted": self.coordinate_transform.fitted,
            "movement_measured": self.movement.measured,
            "mouse_turn_measured": self.mouse_turn.measured,
            "map_observed": self.map_id is not None,
        }

    def missing_for_navigation(self) -> tuple[str, ...]:
        """Everything that must be measured before autonomous navigation is legal."""
        return tuple(name for name, ok in self.readiness().items() if not ok)


__all__ = [
    "CaptureSettings",
    "CoordinateTransform",
    "CropRegion",
    "GameProfile",
    "KeyBindings",
    "MouseTurnCalibration",
    "MovementCalibration",
    "Rect",
]
