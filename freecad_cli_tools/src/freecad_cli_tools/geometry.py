"""Pure geometry, collision detection, and component-shape helpers.

These functions are stateless and depend only on the standard library.
They may be imported by CLI entry points, test suites, and future
modules without pulling in PyYAML or RPC dependencies.
"""

from __future__ import annotations

import itertools
import math
from copy import deepcopy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EPSILON = 1e-9

FACE_DEFINITIONS = {
    # Internal faces (0–5): component is mounted inside the envelope.
    0: ("-x", 0, -1),
    1: ("x", 0, 1),
    2: ("-y", 1, -1),
    3: ("y", 1, 1),
    4: ("-z", 2, -1),
    5: ("z", 2, 1),
    # External faces (6–11): component is mounted on the outside of the envelope.
    # Each external face mirrors its internal counterpart (face N mirrors face N-6).
    6: ("ext-x", 0, -1),
    7: ("ext+x", 0, 1),
    8: ("ext-y", 1, -1),
    9: ("ext+y", 1, 1),
    10: ("ext-z", 2, -1),
    11: ("ext+z", 2, 1),
}

def is_external_face(face_id: int) -> bool:
    """Return True if face_id refers to an external envelope face (6–11)."""
    return face_id >= 6


def component_contact_face(install_face: int) -> int:
    """Return the component's own face (0–5) that physically contacts the wall.

    For internal faces (0–5) the install face and contact face are the same.
    For external faces (6–11) the component wraps around the outer wall, so the
    contact face is the *opposite* of the corresponding internal face:
    e.g. external +Y (9) → contact face is internal -Y (2).
    """
    if is_external_face(install_face):
        return (install_face - 6) ^ 1
    return install_face


IDENTITY_ROTATION = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
]

CYLINDER_AXIS_ROTATIONS = {
    0: [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
    1: [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
    2: IDENTITY_ROTATION,
}

POSITIVE_AXIS_QUARTER_TURNS = {
    0: [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
    1: [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
    2: [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
}

FALLBACK_SAMPLE_COUNT = 256
FALLBACK_BISECTION_STEPS = 24

# ---------------------------------------------------------------------------
# Vector operations
# ---------------------------------------------------------------------------


def vector_add(a: list[float], b: list[float]) -> list[float]:
    return [a[i] + b[i] for i in range(3)]


def vector_scale(vector: list[float], factor: float) -> list[float]:
    return [factor * vector[i] for i in range(3)]


# ---------------------------------------------------------------------------
# Matrix operations
# ---------------------------------------------------------------------------


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
    return [sum(matrix[row][col] * point[col] for col in range(3)) for row in range(3)]


def multiply_rotation_matrices(left: list[list[int]], right: list[list[int]]) -> list[list[int]]:
    return [
        [sum(left[row][k] * right[k][col] for k in range(3)) for col in range(3)]
        for row in range(3)
    ]


def rotation_power(matrix: list[list[int]], turns: int) -> list[list[int]]:
    result = [row[:] for row in IDENTITY_ROTATION]
    for _ in range(turns % 4):
        result = multiply_rotation_matrices(matrix, result)
    return result


# ---------------------------------------------------------------------------
# Component data accessors
# ---------------------------------------------------------------------------


def component_shape(component: dict) -> str:
    return str(component.get("shape", "box")).strip().lower()


def component_mount_face(component: dict) -> int:
    """Return the component's own contact face (always 0–5).

    The YAML ``mount_face`` field stores the *installation face* (0–11).
    For external faces (6–11) this derives the component's physical contact
    face via ``component_contact_face``.
    """
    mount_face = component.get("placement", {}).get("mount_face")
    if mount_face not in FACE_DEFINITIONS:
        raise ValueError(
            f"Invalid or missing mount_face {mount_face!r}. Expected an integer in 0..11."
        )
    return component_contact_face(mount_face)


def envelope_face(component: dict) -> int:
    """Return the envelope installation face (0–11) for a component."""
    placement = component.get("placement", {})
    face = placement.get("envelope_face", placement.get("mount_face"))
    if face not in FACE_DEFINITIONS:
        raise ValueError(f"Invalid or missing envelope_face {face!r}. Expected an integer in 0..11.")
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


# ---------------------------------------------------------------------------
# Cylinder helpers
# ---------------------------------------------------------------------------


def cylinder_axis_index(mount_face: int) -> int:
    if mount_face not in FACE_DEFINITIONS:
        raise ValueError(
            f"Invalid or missing mount_face {mount_face!r}. Expected an integer in 0..11."
        )
    return FACE_DEFINITIONS[mount_face][1]


def infer_cylinder_radius_and_height(
    component_id: str,
    component: dict,
    axis_index: int,
) -> tuple[float, float]:
    dims = component.get("dims")
    dims_values = None if dims is None else [float(value) for value in dims]

    if dims_values is not None and len(dims_values) not in (2, 3):
        raise RuntimeError(
            "Cylinder component "
            f"{component_id} requires two or three dims values when dims are used."
        )

    radius = component.get("radius")
    height = component.get("height")

    if radius is None:
        if dims_values is None:
            raise RuntimeError(f"Cylinder component {component_id} requires radius or dims values.")
        if len(dims_values) == 2:
            radius = dims_values[0] / 2.0
        else:
            cross_section = [dims_values[index] for index in range(3) if index != axis_index]
            radius = min(cross_section) / 2.0
    else:
        radius = float(radius)

    if height is None:
        if dims_values is None:
            raise RuntimeError(f"Cylinder component {component_id} requires height or dims values.")
        if len(dims_values) == 2:
            height = dims_values[1]
        else:
            height = dims_values[axis_index]
    else:
        height = float(height)

    if radius <= 0.0 or height <= 0.0:
        raise RuntimeError(
            f"Cylinder component {component_id} requires positive radius and height."
        )

    return radius, height


def cylinder_base_center_offset(axis_index: int, radius: float) -> list[float]:
    offsets = {
        0: [0.0, radius, radius],
        1: [radius, 0.0, radius],
        2: [radius, radius, 0.0],
    }
    return offsets[axis_index]


# ---------------------------------------------------------------------------
# Component geometry (extents and solid placement)
# ---------------------------------------------------------------------------


def component_local_extents(component_id: str, component: dict) -> list[float]:
    shape = component_shape(component)
    dims = component.get("dims")

    if shape == "box":
        if dims is None or len(dims) != 3:
            raise RuntimeError(f"Box component {component_id} requires three dims values.")
        return [float(value) for value in dims]

    if shape == "cylinder":
        axis_index = cylinder_axis_index(component_mount_face(component))
        radius, height = infer_cylinder_radius_and_height(component_id, component, axis_index)
        diameter = radius * 2.0
        extents = [diameter, diameter, diameter]
        extents[axis_index] = height
        return extents

    raise RuntimeError(f"Unsupported shape for {component_id}: {shape}")


def component_solid_placement(
    component_id: str,
    component: dict,
    position: list[float],
    rotation_matrix: list[list[int]],
) -> tuple[list[float], list[list[int]]]:
    shape = component_shape(component)
    if shape == "box":
        return [float(value) for value in position], [
            [int(value) for value in row] for row in rotation_matrix
        ]

    if shape == "cylinder":
        axis_index = cylinder_axis_index(component_mount_face(component))
        radius, _ = infer_cylinder_radius_and_height(component_id, component, axis_index)
        offset = cylinder_base_center_offset(axis_index, radius)
        solid_position = vector_add(position, apply_rotation(rotation_matrix, offset))
        solid_rotation = multiply_rotation_matrices(
            rotation_matrix,
            CYLINDER_AXIS_ROTATIONS[axis_index],
        )
        return solid_position, solid_rotation

    raise RuntimeError(f"Unsupported shape for {component_id}: {shape}")


def local_face_centroid(dims: list[float], face_id: int) -> list[float]:
    _, axis, direction = FACE_DEFINITIONS[face_id]
    centroid = [dims[i] / 2.0 for i in range(3)]
    centroid[axis] = 0.0 if direction < 0 else dims[axis]
    return centroid


# ---------------------------------------------------------------------------
# Bounding box operations
# ---------------------------------------------------------------------------


def box_bounds(
    position: list[float],
    dims: list[float],
    rotation_matrix: list[list[int]],
) -> list[tuple[float, float]]:
    corners = []
    for x in (0.0, dims[0]):
        for y in (0.0, dims[1]):
            for z in (0.0, dims[2]):
                rotated = apply_rotation(rotation_matrix, [x, y, z])
                corners.append([position[i] + rotated[i] for i in range(3)])
    return [
        (min(point[i] for point in corners), max(point[i] for point in corners)) for i in range(3)
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


def bounds_overlap(
    a_bounds: list[tuple[float, float]],
    b_bounds: list[tuple[float, float]],
) -> bool:
    return all(
        a_bounds[i][0] < b_bounds[i][1] - EPSILON and b_bounds[i][0] < a_bounds[i][1] - EPSILON
        for i in range(3)
    )


def translate_bounds(
    bounds: list[tuple[float, float]],
    offset: list[float],
) -> list[tuple[float, float]]:
    return [(bounds[i][0] + offset[i], bounds[i][1] + offset[i]) for i in range(3)]


def swept_bounds(
    start_bounds: list[tuple[float, float]],
    move: list[float],
    scale_low: float = 0.0,
    scale_high: float = 1.0,
) -> list[tuple[float, float]]:
    swept = []
    for axis in range(3):
        low_start = start_bounds[axis][0] + move[axis] * scale_low
        low_end = start_bounds[axis][0] + move[axis] * scale_high
        high_start = start_bounds[axis][1] + move[axis] * scale_low
        high_end = start_bounds[axis][1] + move[axis] * scale_high
        swept.append((min(low_start, low_end), max(high_start, high_end)))
    return swept


# ---------------------------------------------------------------------------
# Envelope containment
# ---------------------------------------------------------------------------


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


def inside_envelope_bounds(
    bounds: list[tuple[float, float]],
    inner_size: list[float],
) -> bool:
    half_inner = [length / 2.0 for length in inner_size]
    for axis in range(3):
        low, high = bounds[axis]
        if low < -half_inner[axis] - EPSILON or high > half_inner[axis] + EPSILON:
            return False
    return True


# ---------------------------------------------------------------------------
# Placement geometry
# ---------------------------------------------------------------------------


def get_face_data(face_id: int) -> tuple[int, str, int, int]:
    label, axis, direction = FACE_DEFINITIONS[face_id]
    return face_id, label, axis, direction


def constrain_position_to_envelope_face(
    position: list[float],
    dims: list[float],
    wall_size: list[float],
    face_id: int,
    rotation_matrix: list[list[int]],
) -> list[float]:
    _, axis, direction = FACE_DEFINITIONS[face_id]
    target_contact = -wall_size[axis] / 2.0 if direction < 0 else wall_size[axis] / 2.0
    bounds = box_bounds(position, dims, rotation_matrix)
    # For external faces the component sits *outside* the wall, so the near edge
    # (opposite sign) is the one that must touch the outer surface.
    effective_direction = -direction if is_external_face(face_id) else direction
    current_contact = bounds[axis][0] if effective_direction < 0 else bounds[axis][1]
    constrained = list(position)
    constrained[axis] += target_contact - current_contact
    return constrained


def choose_rotation(component_face: int, target_envelope_face: int) -> list[list[int]]:
    source = face_normal(component_face)
    target = face_normal(target_envelope_face)
    candidates = [matrix for matrix in ROTATIONS if apply_rotation(matrix, source) == target]
    if not candidates:
        raise RuntimeError("No valid orthogonal rotation found for requested face change.")
    candidates.sort(key=lambda matrix: sum(matrix[i][i] for i in range(3)), reverse=True)
    return candidates[0]


def normalize_spin_quarter_turns(spin_degrees: int) -> int:
    if spin_degrees % 90 != 0:
        raise ValueError("--spin must be a multiple of 90 degrees.")
    return (spin_degrees // 90) % 4


def spin_rotation_for_envelope_face(
    target_envelope_face: int, spin_quarter_turns: int
) -> list[list[int]]:
    _, axis, direction = FACE_DEFINITIONS[target_envelope_face]
    effective_turns = (spin_quarter_turns * direction) % 4
    return rotation_power(POSITIVE_AXIS_QUARTER_TURNS[axis], effective_turns)


def apply_in_plane_spin(
    base_rotation: list[list[int]],
    target_envelope_face: int,
    spin_quarter_turns: int,
) -> list[list[int]]:
    if spin_quarter_turns % 4 == 0:
        return [row[:] for row in base_rotation]
    spin_matrix = spin_rotation_for_envelope_face(target_envelope_face, spin_quarter_turns)
    return multiply_rotation_matrices(spin_matrix, base_rotation)


def position_for_mount_point(
    mount_point: list[float],
    dims: list[float],
    mount_face: int,
    rotation_matrix: list[list[int]],
) -> list[float]:
    centroid_local = local_face_centroid(dims, mount_face)
    centroid_world = apply_rotation(rotation_matrix, centroid_local)
    return [mount_point[i] - centroid_world[i] for i in range(3)]


def mount_point_from_component(component_id: str, component: dict) -> list[float]:
    placement = component.get("placement", {})
    extents = component_local_extents(component_id, component)
    computed_mount_point = compute_mount_point(
        [float(value) for value in placement["position"]],
        extents,
        component_mount_face(component),
        rotation_matrix_from_component(component),
    )
    mount_point = placement.get("mount_point")
    if mount_point is None:
        return computed_mount_point
    stored_mount_point = [float(value) for value in mount_point]
    if any(
        abs(stored_mount_point[index] - computed_mount_point[index]) > EPSILON for index in range(3)
    ):
        return computed_mount_point
    return stored_mount_point


def centered_face_position(
    dims: list[float],
    wall_size: list[float],
    component_face: int,
    target_envelope_face: int,
) -> tuple[list[float], list[float], list[list[int]]]:
    if is_external_face(target_envelope_face):
        # For external installation the component's contact face has its normal
        # pointing *inward* (opposite to the outward wall normal), so we rotate
        # toward the mirrored internal face.
        rotation_target = (target_envelope_face - 6) ^ 1
    else:
        rotation_target = target_envelope_face
    rotation = choose_rotation(component_face, rotation_target)
    _, axis, direction = FACE_DEFINITIONS[target_envelope_face]
    mount_point = [0.0, 0.0, 0.0]
    mount_point[axis] = (-wall_size[axis] / 2.0) if direction < 0 else (wall_size[axis] / 2.0)
    position = position_for_mount_point(mount_point, dims, component_face, rotation)
    return position, mount_point, rotation


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


# ---------------------------------------------------------------------------
# Analysis context
# ---------------------------------------------------------------------------


def build_analysis_context(
    data: dict,
    component_id: str,
    rotation_matrix: list[list[int]],
    check_envelope: bool = True,
) -> dict:
    components = data["components"]
    target = components[component_id]
    target_extents = component_local_extents(component_id, target)
    other_bounds = []
    for other_id, other in components.items():
        if other_id == component_id:
            continue
        other_bounds.append(
            (
                other_id,
                box_bounds(
                    other["placement"]["position"],
                    component_local_extents(other_id, other),
                    rotation_matrix_from_component(other),
                ),
            )
        )
    return {
        "target_extents": target_extents,
        "inner_size": data["envelope"]["inner_size"],
        "other_bounds": other_bounds,
        "check_envelope": check_envelope,
    }


def analyze_bounds(
    context: dict,
    bounds: list[tuple[float, float]],
    obstacle_bounds: list[tuple[str, list[tuple[float, float]]]] | None = None,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if context.get("check_envelope", True):
        if not inside_envelope_bounds(bounds, context["inner_size"]):
            blockers.append("ENVELOPE_BOUNDARY")
    for other_id, other_bounds in obstacle_bounds or context["other_bounds"]:
        if bounds_overlap(bounds, other_bounds):
            blockers.append(other_id)
    return len(blockers) == 0, blockers


def analyze_position(
    context: dict,
    position: list[float],
    rotation_matrix: list[list[int]],
) -> tuple[bool, list[str]]:
    bounds = box_bounds(position, context["target_extents"], rotation_matrix)
    return analyze_bounds(context, bounds)


def analyze_translated_bounds(
    context: dict,
    start_bounds: list[tuple[float, float]],
    move: list[float],
    scale: float,
    obstacle_bounds: list[tuple[str, list[tuple[float, float]]]] | None = None,
) -> tuple[bool, list[str]]:
    candidate_bounds = translate_bounds(start_bounds, vector_scale(move, scale))
    return analyze_bounds(context, candidate_bounds, obstacle_bounds=obstacle_bounds)


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------


def axis_overlap_interval(
    moving_low: float,
    moving_high: float,
    delta: float,
    static_low: float,
    static_high: float,
) -> tuple[float, float] | None:
    overlap_low = static_low + EPSILON
    overlap_high = static_high - EPSILON

    if delta == 0.0:
        if moving_low < overlap_high and moving_high > overlap_low:
            return (-math.inf, math.inf)
        return None

    first = (overlap_low - moving_high) / delta
    second = (overlap_high - moving_low) / delta
    low = min(first, second)
    high = max(first, second)
    return (low, high)


def interval_intersection(
    intervals: list[tuple[float, float]],
) -> tuple[float, float] | None:
    if not intervals:
        return None
    low = max(interval[0] for interval in intervals)
    high = min(interval[1] for interval in intervals)
    if low >= high:
        return None
    return (low, high)


def collision_interval_for_obstacle(
    start_bounds: list[tuple[float, float]],
    move: list[float],
    obstacle_bounds: list[tuple[float, float]],
) -> tuple[float, float] | None:
    intervals = []
    for axis in range(3):
        axis_interval = axis_overlap_interval(
            moving_low=start_bounds[axis][0],
            moving_high=start_bounds[axis][1],
            delta=move[axis],
            static_low=obstacle_bounds[axis][0],
            static_high=obstacle_bounds[axis][1],
        )
        if axis_interval is None:
            return None
        intervals.append(axis_interval)
    return interval_intersection(intervals)


def envelope_safe_interval(
    start_bounds: list[tuple[float, float]],
    move: list[float],
    inner_size: list[float],
) -> tuple[float, float] | None:
    low = 0.0
    high = 1.0
    half_inner = [length / 2.0 for length in inner_size]

    for axis in range(3):
        min_allowed = -half_inner[axis]
        max_allowed = half_inner[axis]
        bound_low = start_bounds[axis][0]
        bound_high = start_bounds[axis][1]
        delta = move[axis]

        if delta == 0.0:
            if bound_low < min_allowed - EPSILON or bound_high > max_allowed + EPSILON:
                return None
            continue

        limit_one = (min_allowed - bound_low) / delta
        limit_two = (max_allowed - bound_high) / delta
        axis_low = min(limit_one, limit_two)
        axis_high = max(limit_one, limit_two)
        low = max(low, axis_low)
        high = min(high, axis_high)
        if low > high:
            return None

    return (low, high)


def broad_phase_obstacles(
    context: dict,
    start_bounds: list[tuple[float, float]],
    move: list[float],
    max_scale: float,
) -> list[tuple[str, list[tuple[float, float]]]]:
    path_bounds = swept_bounds(start_bounds, move, scale_high=max_scale)
    return [
        (other_id, other_bounds)
        for other_id, other_bounds in context["other_bounds"]
        if bounds_overlap(path_bounds, other_bounds)
    ]


def refine_safe_interval_end(
    context: dict,
    start_bounds: list[tuple[float, float]],
    move: list[float],
    safe_low: float,
    unsafe_high: float,
    obstacle_bounds: list[tuple[str, list[tuple[float, float]]]] | None = None,
    steps: int = FALLBACK_BISECTION_STEPS,
) -> float:
    low = safe_low
    high = unsafe_high
    for _ in range(steps):
        mid = (low + high) / 2.0
        ok, _ = analyze_translated_bounds(
            context,
            start_bounds,
            move,
            mid,
            obstacle_bounds=obstacle_bounds,
        )
        if ok:
            low = mid
        else:
            high = mid
    return low


def legacy_best_safe_scale(
    context: dict,
    start_bounds: list[tuple[float, float]],
    move: list[float],
    obstacle_bounds: list[tuple[str, list[tuple[float, float]]]] | None = None,
) -> float | None:
    safe_samples: list[float] = []
    for index in range(FALLBACK_SAMPLE_COUNT + 1):
        scale = index / FALLBACK_SAMPLE_COUNT
        ok, _ = analyze_translated_bounds(
            context,
            start_bounds,
            move,
            scale,
            obstacle_bounds=obstacle_bounds,
        )
        if ok:
            safe_samples.append(scale)

    if not safe_samples:
        return None

    best_sample = safe_samples[-1]
    if best_sample >= 1.0:
        return 1.0

    step = 1.0 / FALLBACK_SAMPLE_COUNT
    unsafe_high = min(1.0, best_sample + step)
    return refine_safe_interval_end(
        context=context,
        start_bounds=start_bounds,
        move=move,
        safe_low=best_sample,
        unsafe_high=unsafe_high,
        obstacle_bounds=obstacle_bounds,
    )


def find_best_safe_scale(
    context: dict,
    start: list[float],
    move: list[float],
    rotation_matrix: list[list[int]],
) -> float | None:
    start_bounds = box_bounds(start, context["target_extents"], rotation_matrix)
    start_ok, _ = analyze_bounds(context, start_bounds)
    if not start_ok:
        return legacy_best_safe_scale(context, start_bounds, move)

    if context.get("check_envelope", True):
        allowed_interval = envelope_safe_interval(start_bounds, move, context["inner_size"])
        if allowed_interval is None or allowed_interval[1] < 0.0:
            return None
        safe_low = max(0.0, allowed_interval[0])
        safe_high = min(1.0, allowed_interval[1])
        if not safe_low <= 0.0 <= safe_high:
            return legacy_best_safe_scale(context, start_bounds, move)
    else:
        safe_high = 1.0

    candidate_obstacles = broad_phase_obstacles(context, start_bounds, move, safe_high)
    earliest_blocking_scale = safe_high
    for _, obstacle_bounds in candidate_obstacles:
        collision_interval = collision_interval_for_obstacle(start_bounds, move, obstacle_bounds)
        if collision_interval is None:
            continue
        block_low = collision_interval[0]
        block_high = collision_interval[1]
        if block_high <= 0.0 or block_low >= earliest_blocking_scale:
            continue
        earliest_blocking_scale = max(0.0, block_low)
        if earliest_blocking_scale <= 0.0:
            return 0.0

    candidate_scale = earliest_blocking_scale
    if candidate_scale >= 1.0:
        return 1.0

    candidate_ok, _ = analyze_translated_bounds(
        context,
        start_bounds,
        move,
        candidate_scale,
        obstacle_bounds=candidate_obstacles,
    )
    if candidate_ok:
        return candidate_scale

    return refine_safe_interval_end(
        context=context,
        start_bounds=start_bounds,
        move=move,
        safe_low=0.0,
        unsafe_high=candidate_scale,
        obstacle_bounds=candidate_obstacles,
    )


# ---------------------------------------------------------------------------
# Data transform
# ---------------------------------------------------------------------------


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
    extents = component_local_extents(component_id, component)
    component["placement"]["position"] = position
    component["placement"]["mount_face"] = component_mount_face
    component["placement"]["envelope_face"] = envelope_face_id
    component["placement"]["rotation_matrix"] = rotation_matrix
    component["placement"]["mount_point"] = compute_mount_point(
        position, extents, component_mount_face, rotation_matrix
    )
    return updated
