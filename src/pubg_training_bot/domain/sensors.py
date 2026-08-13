"""The controller's single view of "what is true right now".

A snapshot is *not* a bag of best guesses: every derived value carries its own
age, and :meth:`SensorSnapshot.evaluate` returns the explicit list of reasons
the snapshot is unusable. Actuation is gated on that list being empty.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    BridgeHealth,
    InvalidReason,
    MatchPhase,
    MovementState,
    Stance,
    ViewMode,
)


class Vec3(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    z: float

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(x=self.x - other.x, y=self.y - other.y, z=self.z - other.z)

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)

    def distance_2d(self, other: Vec3) -> float:
        from .geometry import distance_2d

        return distance_2d(self.x, self.y, other.x, other.y)

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


class HeadingReading(BaseModel):
    """A heading observation with provenance. Confidence below the configured
    threshold must cause abstention, never a fabricated bearing."""

    model_config = ConfigDict(frozen=True)

    heading_deg: float = Field(ge=0.0, lt=360.0)
    confidence: float = Field(ge=0.0, le=1.0)
    #: Controller monotonic timestamp of the observation.
    observed_at: float
    source: str = "unknown"
    #: Path to the diagnostic crop that produced this reading, when saved.
    diagnostic_crop: str | None = None

    def age_seconds(self, now_monotonic: float) -> float:
        return max(0.0, now_monotonic - self.observed_at)


class WeaponState(BaseModel):
    """Weapon slot state, used as independent evidence for loot verification."""

    model_config = ConfigDict(frozen=True)

    primary: str | None = None
    secondary: str | None = None
    selected_slot: int | None = None
    raw: dict = Field(default_factory=dict)

    def occupied_slots(self) -> tuple[str, ...]:
        return tuple(w for w in (self.primary, self.secondary) if w)


class FreshnessPolicy(BaseModel):
    """Staleness budgets. Values are configuration, justified by measurements
    taken in Stages 1-2; the Stage 0 values are conservative placeholders and
    are flagged as such in ``config/default.yaml``."""

    model_config = ConfigDict(frozen=True)

    max_location_age_s: float = Field(default=2.5, gt=0)
    max_heading_age_s: float = Field(default=0.6, gt=0)
    max_frame_age_s: float = Field(default=0.5, gt=0)
    min_heading_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    #: True until Stage 1/2 measurements replace these numbers.
    provisional: bool = True


class ExpectedContext(BaseModel):
    """What the active route/profile requires the world to look like."""

    model_config = ConfigDict(frozen=True)

    map_id: str | None = None
    view: ViewMode | None = None
    stance: Stance | None = None
    phases: tuple[MatchPhase, ...] = (MatchPhase.LANDED,)
    require_foreground: bool = True
    require_free_view_inactive: bool = True
    require_frame: bool = False
    require_heading: bool = True


class SensorSnapshot(BaseModel):
    """Immutable view of sensor state at one controller tick."""

    model_config = ConfigDict(frozen=True)

    #: Controller monotonic seconds when this snapshot was assembled.
    monotonic_ts: float

    bridge_health: BridgeHealth = BridgeHealth.DISCONNECTED
    map_id: str | None = None
    phase: MatchPhase = MatchPhase.UNKNOWN
    view: ViewMode = ViewMode.UNKNOWN
    stance: Stance = Stance.UNKNOWN
    movement: MovementState = MovementState.UNKNOWN
    free_view_active: bool | None = None
    foreground: bool = False

    #: Position as reported by the game, in game units.
    raw_position: Vec3 | None = None
    #: Position expressed in the active route's local frame (origin-shifted).
    route_position: Vec3 | None = None
    #: Age of the newest location update, in seconds.
    location_age_s: float | None = None

    heading: HeadingReading | None = None

    frame_id: str | None = None
    frame_age_s: float | None = None

    weapon: WeaponState | None = None

    #: Filled by :meth:`evaluate`; empty means "safe to act on".
    invalid_reasons: tuple[InvalidReason, ...] = ()
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # ------------------------------------------------------------------ #
    @property
    def heading_deg(self) -> float | None:
        return self.heading.heading_deg if self.heading else None

    @property
    def is_valid(self) -> bool:
        return not self.invalid_reasons

    def evaluate(
        self,
        policy: FreshnessPolicy,
        expected: ExpectedContext,
        *,
        armed: bool = True,
    ) -> SensorSnapshot:
        """Return a copy with ``invalid_reasons`` and ``confidence`` filled in.

        Pure and side-effect free so it can be unit-tested against fixtures.
        """
        reasons: list[InvalidReason] = []

        if self.bridge_health in (BridgeHealth.DISCONNECTED, BridgeHealth.CONNECTING):
            reasons.append(InvalidReason.BRIDGE_DISCONNECTED)

        if self.raw_position is None or self.location_age_s is None:
            reasons.append(InvalidReason.LOCATION_MISSING)
        elif self.location_age_s > policy.max_location_age_s:
            reasons.append(InvalidReason.LOCATION_STALE)

        if expected.require_heading:
            if self.heading is None:
                reasons.append(InvalidReason.HEADING_MISSING)
            else:
                if self.heading.age_seconds(self.monotonic_ts) > policy.max_heading_age_s:
                    reasons.append(InvalidReason.HEADING_STALE)
                if self.heading.confidence < policy.min_heading_confidence:
                    reasons.append(InvalidReason.HEADING_LOW_CONFIDENCE)

        if expected.require_frame:
            if self.frame_id is None or self.frame_age_s is None:
                reasons.append(InvalidReason.FRAME_MISSING)
            elif self.frame_age_s > policy.max_frame_age_s:
                reasons.append(InvalidReason.FRAME_STALE)

        if expected.map_id is not None:
            if self.map_id is None:
                reasons.append(InvalidReason.MAP_MISSING)
            elif self.map_id != expected.map_id:
                reasons.append(InvalidReason.MAP_MISMATCH)

        if expected.phases and self.phase not in expected.phases:
            reasons.append(InvalidReason.PHASE_MISMATCH)

        if expected.view is not None and self.view != expected.view:
            reasons.append(InvalidReason.VIEW_MISMATCH)

        if expected.stance is not None and self.stance != expected.stance:
            reasons.append(InvalidReason.STANCE_MISMATCH)

        if expected.require_free_view_inactive and self.free_view_active:
            reasons.append(InvalidReason.FREE_VIEW_ACTIVE)

        if expected.require_foreground and not self.foreground:
            reasons.append(InvalidReason.NOT_FOREGROUND)

        if not armed:
            reasons.append(InvalidReason.NOT_ARMED)

        return self.model_copy(
            update={
                "invalid_reasons": tuple(reasons),
                "confidence": _confidence_from(self, policy, reasons),
            }
        )


def _confidence_from(
    snapshot: SensorSnapshot,
    policy: FreshnessPolicy,
    reasons: list[InvalidReason],
) -> float:
    """Blend freshness into a single 0..1 score. Any hard invalidity is 0.0 -
    confidence must never soften a disqualifying condition."""
    if reasons:
        return 0.0
    scores: list[float] = []
    if snapshot.location_age_s is not None:
        scores.append(_freshness_score(snapshot.location_age_s, policy.max_location_age_s))
    if snapshot.heading is not None:
        age = snapshot.heading.age_seconds(snapshot.monotonic_ts)
        scores.append(_freshness_score(age, policy.max_heading_age_s))
        scores.append(snapshot.heading.confidence)
    if snapshot.frame_age_s is not None:
        scores.append(_freshness_score(snapshot.frame_age_s, policy.max_frame_age_s))
    if not scores:
        return 0.0
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def _freshness_score(age_s: float, budget_s: float) -> float:
    if budget_s <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (age_s / budget_s)))


__all__ = [
    "ExpectedContext",
    "FreshnessPolicy",
    "HeadingReading",
    "SensorSnapshot",
    "Vec3",
    "WeaponState",
]
