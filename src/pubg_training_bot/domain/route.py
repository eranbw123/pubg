"""Route contract: the output of a teach (recording) pass and the input to a repeat pass.

The MVP replays a single path, but the schema is a node/edge graph so branching
and A* can be added later without a migration. No path search is implemented.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .. import SCHEMA_VERSION
from .enums import MovementMode, NodeKind, SemanticAction
from .sensors import Vec3


class CircleRegion(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["circle"] = "circle"
    center: Vec3
    radius_units: float = Field(gt=0)
    z_tolerance_units: float = Field(default=5.0, gt=0)

    def contains(self, point: Vec3) -> bool:
        return (
            point.distance_2d(self.center) <= self.radius_units
            and abs(point.z - self.center.z) <= self.z_tolerance_units
        )


class BoxRegion(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["box"] = "box"
    min_corner: Vec3
    max_corner: Vec3

    @model_validator(mode="after")
    def _ordered(self) -> BoxRegion:
        if (
            self.min_corner.x > self.max_corner.x
            or self.min_corner.y > self.max_corner.y
            or self.min_corner.z > self.max_corner.z
        ):
            raise ValueError("min_corner must be component-wise <= max_corner")
        return self

    def contains(self, point: Vec3) -> bool:
        return (
            self.min_corner.x <= point.x <= self.max_corner.x
            and self.min_corner.y <= point.y <= self.max_corner.y
            and self.min_corner.z <= point.z <= self.max_corner.z
        )


Region = CircleRegion | BoxRegion


class VisualAnchor(BaseModel):
    """A route-specific reference image used only at choke points.

    Deterministic matching only (no learned models). Must abstain below
    ``min_score`` rather than report a weak match.
    """

    model_config = ConfigDict(frozen=True)

    anchor_id: str
    image_path: str
    expected_heading_deg: float | None = None
    min_score: float = Field(default=0.7, ge=0.0, le=1.0)
    note: str = ""


class RecoveryPolicy(BaseModel):
    """Bounded recovery budget. Unbounded retrying is a defect, not a fallback."""

    model_config = ConfigDict(frozen=True)

    policy_id: str = "default"
    max_attempts_per_node: int = Field(default=4, ge=0)
    max_attempts_per_run: int = Field(default=12, ge=0)
    max_level: int = Field(default=7, ge=0, le=7)
    settle_seconds: float = Field(default=1.5, gt=0)
    back_off_pulse_ms: int = Field(default=250, gt=0)
    sidestep_pulse_ms: int = Field(default=250, gt=0)


class RouteNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    kind: NodeKind
    position: Vec3
    xy_tolerance_units: float = Field(gt=0)
    z_tolerance_units: float = Field(default=5.0, gt=0)

    desired_heading_deg: float | None = Field(default=None, ge=0.0, lt=360.0)
    heading_tolerance_deg: float = Field(default=15.0, gt=0.0, le=180.0)

    max_duration_s: float = Field(default=30.0, gt=0)
    movement_mode: MovementMode = MovementMode.WALK
    action: SemanticAction = SemanticAction.NONE
    visual_anchor_id: str | None = None
    recovery_policy_id: str | None = None

    #: Expected Z delta across a stair edge; sign carries direction.
    expected_z_delta_units: float | None = None
    label: str = ""

    @property
    def is_semantic(self) -> bool:
        from .enums import SEMANTIC_NODE_KINDS

        return self.kind in SEMANTIC_NODE_KINDS


class RouteEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source_id: str
    target_id: str
    movement_mode: MovementMode = MovementMode.WALK

    #: Pure-pursuit look-ahead, adapted per edge: large outdoors, tiny at doors.
    lookahead_min_units: float = Field(default=2.0, gt=0)
    lookahead_max_units: float = Field(default=12.0, gt=0)
    #: Narrow geometry: stricter heading gate and shorter movement pulses.
    critical: bool = False
    max_cross_track_units: float = Field(default=6.0, gt=0)
    max_duration_s: float = Field(default=60.0, gt=0)

    @model_validator(mode="after")
    def _lookahead_ordered(self) -> RouteEdge:
        if self.lookahead_min_units > self.lookahead_max_units:
            raise ValueError("lookahead_min_units must be <= lookahead_max_units")
        return self


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    route_id: str
    name: str = ""
    map_id: str
    #: Fingerprint of the GameProfile this route was recorded under.
    profile_fingerprint: str
    #: Route-local coordinates are ``raw - world_origin``.
    world_origin: Vec3

    start_region: Region = Field(discriminator="kind")
    end_region: Region = Field(discriminator="kind")

    expected_view: str = "fpp"
    expected_stance: str = "standing"

    nodes: list[RouteNode] = Field(min_length=2)
    edges: list[RouteEdge] = Field(min_length=1)
    visual_anchors: list[VisualAnchor] = Field(default_factory=list)
    recovery_policy: RecoveryPolicy = Field(default_factory=RecoveryPolicy)
    loot_policy_id: str | None = None

    recorded_at: str | None = None
    source_recording_id: str | None = None
    notes: str = ""

    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def _structurally_valid(self) -> Route:
        ids = [n.node_id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate node_id in route")
        known = set(ids)
        for edge in self.edges:
            if edge.source_id not in known:
                raise ValueError(f"edge {edge.edge_id} references unknown source {edge.source_id}")
            if edge.target_id not in known:
                raise ValueError(f"edge {edge.edge_id} references unknown target {edge.target_id}")
            if edge.source_id == edge.target_id:
                raise ValueError(f"edge {edge.edge_id} is a self-loop")
        edge_ids = [e.edge_id for e in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate edge_id in route")

        kinds = [n.kind for n in self.nodes]
        if kinds[0] is not NodeKind.START:
            raise ValueError("first node must be of kind 'start'")
        if kinds[-1] is not NodeKind.FINISH:
            raise ValueError("last node must be of kind 'finish'")
        if sum(1 for k in kinds if k is NodeKind.START) != 1:
            raise ValueError("route must contain exactly one start node")
        if sum(1 for k in kinds if k is NodeKind.FINISH) != 1:
            raise ValueError("route must contain exactly one finish node")

        anchor_ids = {a.anchor_id for a in self.visual_anchors}
        for node in self.nodes:
            if node.visual_anchor_id and node.visual_anchor_id not in anchor_ids:
                raise ValueError(
                    f"node {node.node_id} references unknown visual anchor {node.visual_anchor_id}"
                )
        return self

    # ------------------------------------------------------------------ #
    def node(self, node_id: str) -> RouteNode:
        for candidate in self.nodes:
            if candidate.node_id == node_id:
                return candidate
        raise KeyError(node_id)

    def outgoing_edges(self, node_id: str) -> list[RouteEdge]:
        return [e for e in self.edges if e.source_id == node_id]

    def principal_path(self) -> list[str]:
        """Node ids along the single MVP path, start -> finish.

        Raises when the graph branches: the MVP controller must not silently
        pick one of several successors.
        """
        path = [self.nodes[0].node_id]
        seen = {path[0]}
        while True:
            out = self.outgoing_edges(path[-1])
            if not out:
                break
            if len(out) > 1:
                raise ValueError(
                    f"node {path[-1]} has {len(out)} outgoing edges; "
                    "MVP supports a single principal path only"
                )
            nxt = out[0].target_id
            if nxt in seen:
                raise ValueError(f"route contains a cycle at {nxt}")
            seen.add(nxt)
            path.append(nxt)
        return path

    def to_local(self, raw: Vec3) -> Vec3:
        return raw - self.world_origin

    def to_raw(self, local: Vec3) -> Vec3:
        return local + self.world_origin


__all__ = [
    "BoxRegion",
    "CircleRegion",
    "RecoveryPolicy",
    "Region",
    "Route",
    "RouteEdge",
    "RouteNode",
    "VisualAnchor",
]
