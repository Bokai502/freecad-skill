from __future__ import annotations

import math
from copy import deepcopy

from freecad_cli_tools.cli.yaml_component_safe_move import (
    IDENTITY_ROTATION,
    apply_in_plane_spin,
    box_bounds,
    broad_phase_obstacles,
    build_analysis_context,
    component_local_extents,
    component_solid_placement,
    compute_mount_point,
    find_best_safe_scale,
    mount_point_from_component,
    normalize_spin_quarter_turns,
    position_for_mount_point,
    translate_bounds,
    update_component_placement,
)


def make_layout() -> dict:
    return {
        "envelope": {
            "inner_size": [100.0, 100.0, 100.0],
        },
        "components": {
            "P001": {
                "dims": [10.0, 10.0, 10.0],
                "placement": {
                    "position": [0.0, 0.0, 0.0],
                    "mount_face": 1,
                    "mount_point": [10.0, 5.0, 5.0],
                },
            },
        },
    }


def make_cylinder_layout() -> dict:
    return {
        "envelope": {
            "inner_size": [100.0, 100.0, 100.0],
        },
        "components": {
            "C001": {
                "shape": "cylinder",
                "dims": [8.0, 20.0],
                "placement": {
                    "position": [0.0, 0.0, 0.0],
                    "mount_face": 1,
                    "mount_point": [999.0, 999.0, 999.0],
                },
            },
        },
    }


def test_find_best_safe_scale_returns_full_move_when_unobstructed() -> None:
    data = make_layout()
    context = build_analysis_context(data, "P001", IDENTITY_ROTATION)

    scale = find_best_safe_scale(
        context=context,
        start=[0.0, 0.0, 0.0],
        move=[20.0, 0.0, 0.0],
        rotation_matrix=IDENTITY_ROTATION,
    )

    assert scale == 1.0


def test_find_best_safe_scale_stops_at_first_collision_even_if_end_is_clear() -> None:
    data = make_layout()
    data["components"]["P999"] = {
        "dims": [10.0, 10.0, 10.0],
        "placement": {
            "position": [15.0, 0.0, 0.0],
            "mount_face": 1,
            "mount_point": [25.0, 5.0, 5.0],
        },
    }
    context = build_analysis_context(data, "P001", IDENTITY_ROTATION)

    scale = find_best_safe_scale(
        context=context,
        start=[0.0, 0.0, 0.0],
        move=[30.0, 0.0, 0.0],
        rotation_matrix=IDENTITY_ROTATION,
    )

    assert scale is not None
    assert math.isclose(scale, 1.0 / 6.0, rel_tol=0.0, abs_tol=1e-6)


def test_find_best_safe_scale_stops_at_envelope_boundary() -> None:
    data = make_layout()
    context = build_analysis_context(data, "P001", IDENTITY_ROTATION)

    scale = find_best_safe_scale(
        context=context,
        start=[0.0, 0.0, 0.0],
        move=[60.0, 0.0, 0.0],
        rotation_matrix=IDENTITY_ROTATION,
    )

    assert scale is not None
    assert math.isclose(scale, 2.0 / 3.0, rel_tol=0.0, abs_tol=1e-6)


def test_broad_phase_obstacles_filters_bounds_outside_swept_path() -> None:
    data = make_layout()
    data["components"]["NEAR"] = {
        "dims": [10.0, 10.0, 10.0],
        "placement": {
            "position": [18.0, 0.0, 0.0],
            "mount_face": 1,
            "mount_point": [28.0, 5.0, 5.0],
        },
    }
    data["components"]["FAR"] = {
        "dims": [10.0, 10.0, 10.0],
        "placement": {
            "position": [18.0, 80.0, 0.0],
            "mount_face": 1,
            "mount_point": [28.0, 85.0, 5.0],
        },
    }
    context = build_analysis_context(data, "P001", IDENTITY_ROTATION)
    start_bounds = box_bounds([0.0, 0.0, 0.0], [10.0, 10.0, 10.0], IDENTITY_ROTATION)

    candidates = broad_phase_obstacles(
        context=context,
        start_bounds=start_bounds,
        move=[30.0, 0.0, 0.0],
        max_scale=1.0,
    )

    assert [candidate_id for candidate_id, _ in candidates] == ["NEAR"]


def test_translate_bounds_keeps_collision_cutoff_exact() -> None:
    bounds = box_bounds([0.0, 0.0, 0.0], [10.0, 10.0, 10.0], IDENTITY_ROTATION)

    translated = translate_bounds(bounds, [5.0, -2.0, 3.0])

    assert translated == [(5.0, 15.0), (-2.0, 8.0), (3.0, 13.0)]


def test_component_local_extents_support_two_value_cylinder_dims() -> None:
    data = make_cylinder_layout()

    extents = component_local_extents("C001", data["components"]["C001"])

    assert extents == [20.0, 8.0, 8.0]


def test_find_best_safe_scale_supports_cylinder_targets() -> None:
    data = make_cylinder_layout()
    data["components"]["B001"] = {
        "dims": [10.0, 10.0, 10.0],
        "placement": {
            "position": [25.0, 0.0, 0.0],
            "mount_face": 1,
        },
    }
    context = build_analysis_context(data, "C001", IDENTITY_ROTATION)

    scale = find_best_safe_scale(
        context=context,
        start=[0.0, 0.0, 0.0],
        move=[20.0, 0.0, 0.0],
        rotation_matrix=IDENTITY_ROTATION,
    )

    assert scale is not None
    assert math.isclose(scale, 0.25, rel_tol=0.0, abs_tol=1e-6)


def test_mount_point_from_component_recomputes_stale_cylinder_value() -> None:
    data = make_cylinder_layout()

    mount_point = mount_point_from_component("C001", data["components"]["C001"])

    assert mount_point == [20.0, 4.0, 4.0]


def test_update_component_placement_updates_yaml_fields() -> None:
    data = make_layout()
    original = deepcopy(data)

    updated = update_component_placement(
        data=data,
        component_id="P001",
        position=[12.0, 8.0, 4.0],
        component_mount_face=1,
        envelope_face_id=5,
        rotation_matrix=IDENTITY_ROTATION,
    )

    assert data == original
    placement = updated["components"]["P001"]["placement"]
    assert placement["position"] == [12.0, 8.0, 4.0]
    assert placement["mount_face"] == 1
    assert placement["envelope_face"] == 5
    assert placement["rotation_matrix"] == IDENTITY_ROTATION
    assert placement["mount_point"] == [22.0, 13.0, 9.0]


def test_update_component_placement_updates_cylinder_mount_point() -> None:
    data = make_cylinder_layout()
    original = deepcopy(data)

    updated = update_component_placement(
        data=data,
        component_id="C001",
        position=[2.0, 4.0, 6.0],
        component_mount_face=1,
        envelope_face_id=5,
        rotation_matrix=IDENTITY_ROTATION,
    )

    assert data == original
    placement = updated["components"]["C001"]["placement"]
    assert placement["position"] == [2.0, 4.0, 6.0]
    assert placement["mount_point"] == [22.0, 8.0, 10.0]


def test_component_solid_placement_offsets_cylinder_for_cad_sync() -> None:
    data = make_cylinder_layout()

    position, rotation = component_solid_placement(
        "C001",
        data["components"]["C001"],
        [1.0, 2.0, 3.0],
        IDENTITY_ROTATION,
    )

    assert position == [1.0, 6.0, 7.0]
    assert rotation == [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]


def test_in_plane_spin_keeps_mount_point_fixed_on_same_face() -> None:
    dims = [10.0, 20.0, 30.0]
    mount_point = [10.0, 10.0, 15.0]

    rotated = apply_in_plane_spin(
        base_rotation=IDENTITY_ROTATION,
        target_envelope_face=1,
        spin_quarter_turns=normalize_spin_quarter_turns(90),
    )
    position = position_for_mount_point(
        mount_point=mount_point,
        dims=dims,
        mount_face=1,
        rotation_matrix=rotated,
    )

    assert rotated == [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
    assert position == [0.0, 25.0, 5.0]
    assert compute_mount_point(position, dims, 1, rotated) == mount_point


def test_normalize_spin_quarter_turns_rejects_non_right_angle_input() -> None:
    try:
        normalize_spin_quarter_turns(45)
    except ValueError as exc:
        assert "--spin must be a multiple of 90 degrees." in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-right-angle spin input.")
