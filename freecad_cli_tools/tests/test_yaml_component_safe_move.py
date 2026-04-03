from __future__ import annotations

import math
from copy import deepcopy

from freecad_cli_tools.cli.yaml_component_safe_move import (
    IDENTITY_ROTATION,
    build_analysis_context,
    find_best_safe_scale,
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
