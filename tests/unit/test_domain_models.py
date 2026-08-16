"""Profile and route contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pubg_training_bot.domain.enums import NodeKind, SemanticAction
from pubg_training_bot.domain.profile import CropRegion, GameProfile, Rect
from pubg_training_bot.domain.route import (
    BoxRegion,
    CircleRegion,
    Route,
    RouteEdge,
    RouteNode,
)
from pubg_training_bot.domain.sensors import HeadingReading, Vec3


# --------------------------------------------------------------------------- #
# GameProfile
# --------------------------------------------------------------------------- #
def base_profile(**overrides) -> GameProfile:
    data = {"profile_id": "test", "screen_width": 1920, "screen_height": 1080}
    data.update(overrides)
    return GameProfile(**data)


def test_fingerprint_is_stable_across_identical_profiles() -> None:
    assert base_profile().fingerprint == base_profile().fingerprint
    assert base_profile().fingerprint.startswith("gp1:")


@pytest.mark.parametrize(
    "override",
    [
        {"screen_width": 2560},
        {"dpi_scale": 1.25},
        {"fov": 103.0},
        {"mouse_sensitivity": 40.0},
        {"language": "de"},
        {"map_id": "TRAINING"},
    ],
)
def test_fingerprint_changes_when_a_route_relevant_field_changes(override: dict) -> None:
    assert base_profile().fingerprint != base_profile(**override).fingerprint


def test_fingerprint_ignores_cosmetic_fields() -> None:
    assert base_profile().fingerprint == base_profile(description="notes", notes="x").fingerprint


def test_uncalibrated_profile_reports_what_is_missing() -> None:
    missing = base_profile().missing_for_navigation()
    assert "compass_crop_calibrated" in missing
    assert "coordinate_transform_fitted" in missing
    assert "map_observed" in missing


def test_crop_region_rejects_out_of_bounds_rectangles() -> None:
    with pytest.raises(ValidationError):
        CropRegion(x=0.9, y=0.0, width=0.2, height=0.1)
    with pytest.raises(ValidationError):
        CropRegion(x=0.0, y=0.95, width=0.1, height=0.2)
    with pytest.raises(ValidationError):
        CropRegion(x=-0.1, y=0.0, width=0.1, height=0.1)


def test_crop_region_scales_to_window_pixels() -> None:
    region = CropRegion(x=0.5, y=0.0, width=0.25, height=0.1, calibrated=True)
    rect = region.to_pixels(Rect(left=100, top=50, width=1920, height=1080))
    assert (rect.left, rect.top, rect.width, rect.height) == (1060, 50, 480, 108)


def test_shipped_dev_profile_is_honest_about_being_uncalibrated(repo_paths) -> None:
    from pubg_training_bot.config import load_game_profile

    profile = load_game_profile("dev-1080p-fpp", paths=repo_paths)
    assert profile.map_id is None, "map must be observed live, never guessed"
    assert profile.compass_crop is None
    assert profile.coordinate_transform.fitted is False
    assert profile.missing_for_navigation(), "profile must not claim navigation readiness"


# --------------------------------------------------------------------------- #
# Regions
# --------------------------------------------------------------------------- #
def test_circle_region_containment_uses_xy_plus_z_tolerance() -> None:
    region = CircleRegion(center=Vec3(x=0, y=0, z=100), radius_units=5.0, z_tolerance_units=2.0)
    assert region.contains(Vec3(x=3, y=3, z=100))
    assert not region.contains(Vec3(x=9, y=0, z=100))
    assert not region.contains(Vec3(x=0, y=0, z=110)), "wrong floor must not count as arrival"


def test_box_region_requires_ordered_corners() -> None:
    with pytest.raises(ValidationError):
        BoxRegion(min_corner=Vec3(x=5, y=0, z=0), max_corner=Vec3(x=0, y=1, z=1))
    box = BoxRegion(min_corner=Vec3(x=0, y=0, z=0), max_corner=Vec3(x=10, y=10, z=5))
    assert box.contains(Vec3(x=5, y=5, z=2))
    assert not box.contains(Vec3(x=5, y=5, z=9))


# --------------------------------------------------------------------------- #
# Route
# --------------------------------------------------------------------------- #
def build_route(**overrides) -> Route:
    nodes = [
        RouteNode(
            node_id="n0", kind=NodeKind.START, position=Vec3(x=0, y=0, z=0), xy_tolerance_units=3.0
        ),
        RouteNode(
            node_id="n1",
            kind=NodeKind.CHECKPOINT,
            position=Vec3(x=0, y=20, z=0),
            xy_tolerance_units=3.0,
        ),
        RouteNode(
            node_id="n2",
            kind=NodeKind.FINISH,
            position=Vec3(x=20, y=20, z=0),
            xy_tolerance_units=3.0,
        ),
    ]
    edges = [
        RouteEdge(edge_id="e0", source_id="n0", target_id="n1"),
        RouteEdge(edge_id="e1", source_id="n1", target_id="n2"),
    ]
    data = {
        "route_id": "test-route",
        "map_id": "TRAINING",
        "profile_fingerprint": "gp1:deadbeef",
        "world_origin": Vec3(x=1000, y=2000, z=50),
        "start_region": CircleRegion(center=Vec3(x=0, y=0, z=0), radius_units=5.0),
        "end_region": CircleRegion(center=Vec3(x=20, y=20, z=0), radius_units=5.0),
        "nodes": nodes,
        "edges": edges,
    }
    data.update(overrides)
    return Route(**data)


def test_valid_route_exposes_its_principal_path() -> None:
    assert build_route().principal_path() == ["n0", "n1", "n2"]


def test_route_must_start_with_start_and_end_with_finish() -> None:
    nodes = [
        RouteNode(
            node_id="a", kind=NodeKind.TRANSIT, position=Vec3(x=0, y=0, z=0), xy_tolerance_units=1.0
        ),
        RouteNode(
            node_id="b", kind=NodeKind.FINISH, position=Vec3(x=1, y=1, z=0), xy_tolerance_units=1.0
        ),
    ]
    with pytest.raises(ValidationError, match="start"):
        build_route(nodes=nodes, edges=[RouteEdge(edge_id="e", source_id="a", target_id="b")])


def test_edges_must_reference_known_nodes() -> None:
    with pytest.raises(ValidationError, match="unknown target"):
        build_route(
            edges=[
                RouteEdge(edge_id="e0", source_id="n0", target_id="n1"),
                RouteEdge(edge_id="e1", source_id="n1", target_id="ghost"),
            ]
        )


def test_duplicate_node_ids_rejected() -> None:
    route = build_route()
    duplicated = [*route.nodes, route.nodes[1].model_copy()]
    with pytest.raises(ValidationError, match="duplicate node_id"):
        build_route(nodes=duplicated)


def test_self_loop_edge_rejected() -> None:
    with pytest.raises(ValidationError, match="self-loop"):
        build_route(
            edges=[
                RouteEdge(edge_id="e0", source_id="n0", target_id="n0"),
                RouteEdge(edge_id="e1", source_id="n1", target_id="n2"),
            ]
        )


def test_branching_route_is_refused_by_the_mvp_path_walker() -> None:
    route = build_route(
        edges=[
            RouteEdge(edge_id="e0", source_id="n0", target_id="n1"),
            RouteEdge(edge_id="e1", source_id="n1", target_id="n2"),
            RouteEdge(edge_id="e2", source_id="n0", target_id="n2"),
        ]
    )
    with pytest.raises(ValueError, match="single principal path"):
        route.principal_path()


def test_unknown_visual_anchor_reference_rejected() -> None:
    route = build_route()
    nodes = list(route.nodes)
    nodes[1] = nodes[1].model_copy(update={"visual_anchor_id": "missing-anchor"})
    with pytest.raises(ValidationError, match="unknown visual anchor"):
        build_route(nodes=nodes)


def test_world_origin_round_trip() -> None:
    route = build_route()
    raw = Vec3(x=1010.0, y=2020.0, z=55.0)
    assert route.to_raw(route.to_local(raw)) == raw
    assert route.to_local(raw) == Vec3(x=10.0, y=20.0, z=5.0)


def test_semantic_nodes_are_marked_for_simplification_protection() -> None:
    route = build_route()
    assert route.node("n0").is_semantic
    assert route.node("n1").is_semantic
    transit = RouteNode(
        node_id="t", kind=NodeKind.TRANSIT, position=Vec3(x=0, y=0, z=0), xy_tolerance_units=1.0
    )
    assert not transit.is_semantic


def test_edge_lookahead_bounds_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="lookahead_min_units"):
        RouteEdge(
            edge_id="e",
            source_id="a",
            target_id="b",
            lookahead_min_units=10.0,
            lookahead_max_units=2.0,
        )


def test_door_node_carries_its_semantic_action() -> None:
    node = RouteNode(
        node_id="door-1",
        kind=NodeKind.DOOR,
        position=Vec3(x=1, y=2, z=3),
        xy_tolerance_units=1.0,
        desired_heading_deg=270.0,
        action=SemanticAction.OPEN_DOOR,
    )
    assert node.is_semantic
    assert node.action is SemanticAction.OPEN_DOOR


# --------------------------------------------------------------------------- #
# Misc value objects
# --------------------------------------------------------------------------- #
def test_heading_reading_rejects_out_of_range_bearing() -> None:
    with pytest.raises(ValidationError):
        HeadingReading(heading_deg=360.0, confidence=1.0, observed_at=0.0)
    with pytest.raises(ValidationError):
        HeadingReading(heading_deg=10.0, confidence=1.4, observed_at=0.0)


def test_vec3_arithmetic() -> None:
    a, b = Vec3(x=1, y=2, z=3), Vec3(x=10, y=20, z=30)
    assert (b - a) == Vec3(x=9, y=18, z=27)
    assert (a + b) == Vec3(x=11, y=22, z=33)
    assert a.distance_2d(Vec3(x=4, y=6, z=99)) == pytest.approx(5.0)
