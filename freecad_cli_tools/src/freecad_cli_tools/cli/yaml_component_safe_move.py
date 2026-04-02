#!/usr/bin/env python3
"""Safely update a component placement inside a YAML assembly."""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
import itertools

import yaml

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import execute_script_payload, to_wsl_path
from freecad_cli_tools.rpc_script_fragments import PLACEMENT_HELPERS
from freecad_cli_tools.rpc_script_loader import render_rpc_script


EPSILON = 1e-9
FACE_DEFINITIONS = {
    0: ("-x", 0, -1),
    1: ("x", 0, 1),
    2: ("-y", 1, -1),
    3: ("y", 1, 1),
    4: ("-z", 2, -1),
    5: ("z", 2, 1),
}

IDENTITY_ROTATION = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Move a box component inside a YAML assembly, detect collisions, "
            "write an updated YAML file, and optionally sync the result to FreeCAD."
        )
    )
    parser.add_argument("--input", default="data/sample.yaml", help="Path to the source YAML file.")
    parser.add_argument(
        "--output",
        default="data/sample.updated.yaml",
        help="Path to the output YAML file.",
    )
    parser.add_argument("--component", default="P001", help="Target component id to move.")
    parser.add_argument(
        "--move",
        nargs=3,
        type=float,
        metavar=("DX", "DY", "DZ"),
        default=(50.0, 50.0, 0.0),
        help="Requested movement vector.",
    )
    parser.add_argument(
        "--install-face",
        type=int,
        choices=sorted(FACE_DEFINITIONS.keys()),
        help=(
            "Optional target envelope face for reorientation. When supplied, the component is "
            "rotated so its own mount_face is installed onto the specified envelope face and "
            "placed at the center of that face."
        ),
    )
    parser.add_argument(
        "--sync-cad",
        action="store_true",
        help="After writing the updated YAML, sync the component position into a FreeCAD document.",
    )
    parser.add_argument(
        "--doc-name",
        help="FreeCAD document name to update when --sync-cad is used.",
    )
    parser.add_argument(
        "--component-object",
        help="Exact FreeCAD solid object name for the component. Defaults to the component id.",
    )
    parser.add_argument(
        "--part-object",
        help="Exact FreeCAD container object name for the component. Defaults to '<component>_part'.",
    )
    add_connection_args(parser)
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def save_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def vector_add(a: list[float], b: list[float]) -> list[float]:
    return [a[i] + b[i] for i in range(3)]


def vector_scale(vector: list[float], factor: float) -> list[float]:
    return [factor * vector[i] for i in range(3)]


def determinant3(matrix: list[list[int]]) -> int:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def signed_permutation_rotations() -> list[list[list[int]]]:
    rotations = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            matrix = [[0, 0, 0] for _ in range(3)]
            for row, col in enumerate(perm):
                matrix[row][col] = signs[row]
            if determinant3(matrix) == 1:
                rotations.append(matrix)
    return rotations


ROTATIONS = signed_permutation_rotations()


def apply_rotation(matrix: list[list[int]], point: list[float]) -> list[float]:
    return [
        sum(matrix[row][col] * point[col] for col in range(3))
        for row in range(3)
    ]


def component_mount_face(component: dict) -> int:
    mount_face = component.get("placement", {}).get("mount_face")
    if mount_face not in FACE_DEFINITIONS:
        raise ValueError(
            f"Invalid or missing mount_face {mount_face!r}. Expected an integer in 0..5."
        )
    return mount_face


def envelope_face(component: dict) -> int:
    placement = component.get("placement", {})
    face = placement.get("envelope_face", placement.get("mount_face"))
    if face not in FACE_DEFINITIONS:
        raise ValueError(
            f"Invalid or missing envelope_face {face!r}. Expected an integer in 0..5."
        )
    return face


def face_normal(face_id: int) -> list[int]:
    _, axis, direction = FACE_DEFINITIONS[face_id]
    vec = [0, 0, 0]
    vec[axis] = direction
    return vec


def rotation_matrix_from_component(component: dict) -> list[list[int]]:
    placement = component.get("placement", {})
    matrix = placement.get("rotation_matrix")
    if matrix is None:
        return [row[:] for row in IDENTITY_ROTATION]
    return [[int(value) for value in row] for row in matrix]


def local_face_centroid(dims: list[float], face_id: int) -> list[float]:
    _, axis, direction = FACE_DEFINITIONS[face_id]
    centroid = [dims[i] / 2.0 for i in range(3)]
    centroid[axis] = 0.0 if direction < 0 else dims[axis]
    return centroid


def box_bounds(position: list[float], dims: list[float], rotation_matrix: list[list[int]]) -> list[tuple[float, float]]:
    corners = []
    for x in (0.0, dims[0]):
        for y in (0.0, dims[1]):
            for z in (0.0, dims[2]):
                rotated = apply_rotation(rotation_matrix, [x, y, z])
                corners.append([position[i] + rotated[i] for i in range(3)])
    return [
        (min(point[i] for point in corners), max(point[i] for point in corners))
        for i in range(3)
    ]


def boxes_overlap(
    a_position: list[float],
    a_dims: list[float],
    a_rotation: list[list[int]],
    b_position: list[float],
    b_dims: list[float],
    b_rotation: list[list[int]],
) -> bool:
    a_box = box_bounds(a_position, a_dims, a_rotation)
    b_box = box_bounds(b_position, b_dims, b_rotation)
    return all(
        a_box[i][0] < b_box[i][1] - EPSILON and b_box[i][0] < a_box[i][1] - EPSILON
        for i in range(3)
    )


def inside_envelope(
    position: list[float],
    dims: list[float],
    inner_size: list[float],
    rotation_matrix: list[list[int]],
) -> bool:
    half_inner = [length / 2.0 for length in inner_size]
    bounds = box_bounds(position, dims, rotation_matrix)
    for axis in range(3):
        low, high = bounds[axis]
        if low < -half_inner[axis] - EPSILON or high > half_inner[axis] + EPSILON:
            return False
    return True


def get_face_data(face_id: int) -> tuple[int, str, int, int]:
    label, axis, direction = FACE_DEFINITIONS[face_id]
    return face_id, label, axis, direction


def constrain_position_to_envelope_face(
    position: list[float],
    dims: list[float],
    inner_size: list[float],
    face_id: int,
    rotation_matrix: list[list[int]],
) -> list[float]:
    _, axis, direction = FACE_DEFINITIONS[face_id]
    target_contact = -inner_size[axis] / 2.0 if direction < 0 else inner_size[axis] / 2.0
    bounds = box_bounds(position, dims, rotation_matrix)
    current_contact = bounds[axis][0] if direction < 0 else bounds[axis][1]
    constrained = list(position)
    constrained[axis] += target_contact - current_contact
    return constrained


def choose_rotation(component_face: int, target_envelope_face: int) -> list[list[int]]:
    source = face_normal(component_face)
    target = face_normal(target_envelope_face)
    candidates = [
        matrix for matrix in ROTATIONS
        if apply_rotation(matrix, source) == target
    ]
    if not candidates:
        raise RuntimeError("No valid orthogonal rotation found for requested face change.")
    candidates.sort(key=lambda matrix: sum(matrix[i][i] for i in range(3)), reverse=True)
    return candidates[0]


def centered_face_position(
    dims: list[float],
    inner_size: list[float],
    component_face: int,
    target_envelope_face: int,
) -> tuple[list[float], list[list[int]]]:
    rotation = choose_rotation(component_face, target_envelope_face)
    centroid_local = local_face_centroid(dims, component_face)
    centroid_world = apply_rotation(rotation, centroid_local)
    _, axis, direction = FACE_DEFINITIONS[target_envelope_face]
    target_contact = [0.0, 0.0, 0.0]
    target_contact[axis] = (-inner_size[axis] / 2.0) if direction < 0 else (inner_size[axis] / 2.0)
    position = [target_contact[i] - centroid_world[i] for i in range(3)]
    return position, rotation


def project_move_to_mount_plane(move: list[float], axis: int) -> tuple[list[float], bool]:
    projected = list(move)
    ignored = abs(projected[axis]) > EPSILON
    projected[axis] = 0.0
    return projected, ignored


def compute_mount_point(
    position: list[float],
    dims: list[float],
    mount_face: int,
    rotation_matrix: list[list[int]],
) -> list[float]:
    centroid = local_face_centroid(dims, mount_face)
    rotated = apply_rotation(rotation_matrix, centroid)
    return [position[i] + rotated[i] for i in range(3)]


def analyze_position(
    data: dict,
    component_id: str,
    position: list[float],
    rotation_matrix: list[list[int]],
) -> tuple[bool, list[str]]:
    components = data["components"]
    target = components[component_id]
    dims = target["dims"]
    inner_size = data["envelope"]["inner_size"]
    blockers: list[str] = []

    if not inside_envelope(position, dims, inner_size, rotation_matrix):
        blockers.append("ENVELOPE_BOUNDARY")

    for other_id, other in components.items():
        if other_id == component_id:
            continue
        if boxes_overlap(
            position,
            dims,
            rotation_matrix,
            other["placement"]["position"],
            other["dims"],
            rotation_matrix_from_component(other),
        ):
            blockers.append(other_id)

    return len(blockers) == 0, blockers


def refine_safe_interval_end(
    data: dict,
    component_id: str,
    start_position: list[float],
    move: list[float],
    safe_low: float,
    unsafe_high: float,
    rotation_matrix: list[list[int]],
) -> float:
    low = safe_low
    high = unsafe_high
    for _ in range(60):
        mid = (low + high) / 2.0
        candidate = vector_add(start_position, vector_scale(move, mid))
        ok, _ = analyze_position(data, component_id, candidate, rotation_matrix)
        if ok:
            low = mid
        else:
            high = mid
    return low


def find_best_safe_scale(
    data: dict,
    component_id: str,
    start: list[float],
    move: list[float],
    rotation_matrix: list[list[int]],
) -> float | None:
    full_position = vector_add(start, move)
    full_ok, _ = analyze_position(data, component_id, full_position, rotation_matrix)
    if full_ok:
        return 1.0

    sample_count = 2000
    safe_samples: list[float] = []
    for index in range(sample_count + 1):
        scale = index / sample_count
        candidate = vector_add(start, vector_scale(move, scale))
        ok, _ = analyze_position(data, component_id, candidate, rotation_matrix)
        if ok:
            safe_samples.append(scale)

    if not safe_samples:
        return None

    best_sample = safe_samples[-1]
    if best_sample >= 1.0:
        return 1.0

    step = 1.0 / sample_count
    unsafe_high = min(1.0, best_sample + step)
    return refine_safe_interval_end(
        data=data,
        component_id=component_id,
        start_position=start,
        move=move,
        safe_low=best_sample,
        unsafe_high=unsafe_high,
        rotation_matrix=rotation_matrix,
    )


def update_component_placement(
    data: dict,
    component_id: str,
    position: list[float],
    component_mount_face: int,
    envelope_face_id: int,
    rotation_matrix: list[list[int]],
) -> dict:
    updated = deepcopy(data)
    component = updated["components"][component_id]
    component["placement"]["position"] = position
    component["placement"]["mount_face"] = component_mount_face
    component["placement"]["envelope_face"] = envelope_face_id
    component["placement"]["rotation_matrix"] = rotation_matrix
    component["placement"]["mount_point"] = compute_mount_point(
        position, component["dims"], component_mount_face, rotation_matrix
    )
    return updated


def sync_yaml_result_to_cad(args: argparse.Namespace, output_path: Path) -> dict:
    if not args.sync_cad:
        return {"enabled": False, "success": False}
    if not args.doc_name:
        raise ValueError("--doc-name is required when --sync-cad is used.")

    solid_name = args.component_object or args.component
    part_name = args.part_object or f"{args.component}_part"
    code = render_rpc_script(
        "sync_component_from_yaml.py",
        {
            "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
            "__DOC_NAME__": json.dumps(args.doc_name),
            "__YAML_PATH__": json.dumps(to_wsl_path(output_path)),
            "__COMPONENT_ID__": json.dumps(args.component),
            "__SOLID_NAME__": json.dumps(solid_name),
            "__PART_NAME__": json.dumps(part_name),
        },
    )

    try:
        payload = execute_script_payload(args.host, args.port, code)
    except SystemExit as exc:
        raise RuntimeError(
            f"cannot connect to FreeCAD RPC server at {args.host}:{args.port}"
        ) from exc
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or "CAD sync failed")
    payload["enabled"] = True
    return payload


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    move = [float(value) for value in args.move]

    data = load_yaml(input_path)
    components = data.get("components", {})
    if args.component not in components:
        available = ", ".join(sorted(components))
        raise KeyError(f"Component {args.component} not found. Available components: {available}")

    target = components[args.component]
    component_face = component_mount_face(target)
    original_envelope_face = envelope_face(target)
    target_envelope_face = args.install_face if args.install_face is not None else original_envelope_face
    _, target_face_label, target_axis, _ = get_face_data(target_envelope_face)

    if args.install_face is not None:
        start_position, target_rotation_matrix = centered_face_position(
            target["dims"],
            data["envelope"]["inner_size"],
            component_face,
            target_envelope_face,
        )
    else:
        target_rotation_matrix = rotation_matrix_from_component(target)
        start_position = constrain_position_to_envelope_face(
            target["placement"]["position"],
            target["dims"],
            data["envelope"]["inner_size"],
            target_envelope_face,
            target_rotation_matrix,
        )

    effective_move, normal_component_ignored = project_move_to_mount_plane(move, target_axis)
    requested_position = vector_add(start_position, effective_move)
    requested_ok, requested_blockers = analyze_position(
        data, args.component, requested_position, target_rotation_matrix
    )

    solution_found = True
    if requested_ok:
        applied_scale = 1.0
        applied_move = effective_move
        final_position = requested_position
    else:
        best_scale = find_best_safe_scale(
            data,
            args.component,
            start_position,
            effective_move,
            target_rotation_matrix,
        )
        if best_scale is None:
            solution_found = False
            applied_scale = 0.0
            applied_move = [0.0, 0.0, 0.0]
            final_position = start_position
        else:
            applied_scale = best_scale
            applied_move = vector_scale(effective_move, applied_scale)
            final_position = vector_add(start_position, applied_move)

    final_ok, final_blockers = analyze_position(
        data, args.component, final_position, target_rotation_matrix
    )
    if solution_found and not final_ok:
        raise RuntimeError(
            f"Failed to find a collision-free position for {args.component}. "
            f"Blockers: {final_blockers}"
        )

    updated = update_component_placement(
        data,
        args.component,
        final_position,
        component_face,
        target_envelope_face,
        target_rotation_matrix,
    )
    save_yaml(output_path, updated)

    try:
        cad_sync = sync_yaml_result_to_cad(args, output_path)
    except Exception as exc:
        cad_sync = {
            "enabled": True,
            "success": False,
            "error": str(exc),
            "document": args.doc_name,
            "component": args.component,
        }

    print(f"input_file: {input_path.resolve()}")
    print(f"output_file: {output_path.resolve()}")
    print(f"target_component: {args.component}")
    print(f"component_mount_face: {component_face}")
    print(f"component_mount_face_label: {FACE_DEFINITIONS[component_face][0]}")
    print(f"original_envelope_face: {original_envelope_face}")
    print(f"original_envelope_face_label: {FACE_DEFINITIONS[original_envelope_face][0]}")
    print(f"target_envelope_face: {target_envelope_face}")
    print(f"target_envelope_face_label: {target_face_label}")
    print("orientation_change_supported: True")
    print(f"orientation_change_applied: {args.install_face is not None}")
    print(f"rotation_matrix: {target_rotation_matrix}")
    print(f"normal_move_component_ignored: {normal_component_ignored}")
    print(f"original_position: {target['placement']['position']}")
    print(f"constrained_start_position: {start_position}")
    print(f"requested_move: {move}")
    print(f"effective_move: {effective_move}")
    print(f"requested_position: {requested_position}")
    print(f"requested_move_is_safe: {requested_ok}")
    print(f"requested_blockers: {requested_blockers}")
    print(f"solution_found_on_requested_segment: {solution_found}")
    print(f"applied_scale: {applied_scale:.12f}")
    print(f"applied_move: {applied_move}")
    print(f"final_position: {final_position}")
    print(
        "final_mount_point: "
        f"{updated['components'][args.component]['placement']['mount_point']}"
    )
    print(f"final_blockers: {final_blockers}")
    print(f"cad_sync_enabled: {args.sync_cad}")
    print(f"cad_sync_result: {json.dumps(cad_sync, ensure_ascii=False)}")
    return 2 if args.sync_cad and not cad_sync.get("success") else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
