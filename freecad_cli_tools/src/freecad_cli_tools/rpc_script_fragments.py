"""Reusable FreeCAD-side code fragments for embedded RPC scripts."""

PLACEMENT_HELPERS = r"""
def matrix_to_rotation(matrix_rows):
    matrix = FreeCAD.Matrix()
    matrix.A11 = float(matrix_rows[0][0])
    matrix.A12 = float(matrix_rows[0][1])
    matrix.A13 = float(matrix_rows[0][2])
    matrix.A14 = 0.0
    matrix.A21 = float(matrix_rows[1][0])
    matrix.A22 = float(matrix_rows[1][1])
    matrix.A23 = float(matrix_rows[1][2])
    matrix.A24 = 0.0
    matrix.A31 = float(matrix_rows[2][0])
    matrix.A32 = float(matrix_rows[2][1])
    matrix.A33 = float(matrix_rows[2][2])
    matrix.A34 = 0.0
    matrix.A41 = 0.0
    matrix.A42 = 0.0
    matrix.A43 = 0.0
    matrix.A44 = 1.0
    return FreeCAD.Placement(matrix).Rotation


def make_placement(position, rotation_rows):
    placement = FreeCAD.Placement()
    placement.Base = FreeCAD.Vector(float(position[0]), float(position[1]), float(position[2]))
    placement.Rotation = matrix_to_rotation(rotation_rows)
    return placement
"""


COMPONENT_SHAPE_HELPERS = r"""
# NOTE: Several functions in this fragment have canonical Python equivalents in
# freecad_cli_tools.geometry.  The string versions here are required because
# they execute inside FreeCAD's embedded Python, which cannot import CLI-side
# modules.  See tests/test_fragment_sync.py for a cross-validation test.
#
# Fragment function                      -> geometry.py equivalent
# -----------------------------------------------------------------------
# IDENTITY_ROTATION_ROWS                 -> IDENTITY_ROTATION
# CYLINDER_AXIS_ROTATION_ROWS            -> CYLINDER_AXIS_ROTATIONS
# apply_rotation_rows()                  -> apply_rotation()
# multiply_rotation_rows()               -> multiply_rotation_matrices()
# cylinder_axis_index()                  -> cylinder_axis_index()
# cylinder_base_center_offset()          -> cylinder_base_center_offset()
# infer_cylinder_radius_and_height()     -> infer_cylinder_radius_and_height()
# translate_position()                   -> vector_add + apply_rotation
IDENTITY_ROTATION_ROWS = [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
]
CYLINDER_AXIS_ROTATION_ROWS = {
    0: [
        [0.0, 0.0, 1.0],
        [0.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
    ],
    1: [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, -1.0, 0.0],
    ],
    2: IDENTITY_ROTATION_ROWS,
}


def normalize_rotation_rows(rotation_rows):
    rows = rotation_rows or IDENTITY_ROTATION_ROWS
    return [[float(value) for value in row] for row in rows]


def apply_rotation_rows(rotation_rows, point):
    return [
        sum(rotation_rows[row][col] * float(point[col]) for col in range(3))
        for row in range(3)
    ]


def translate_position(position, rotation_rows, local_offset):
    rotated_offset = apply_rotation_rows(rotation_rows, local_offset)
    return [float(position[i]) + rotated_offset[i] for i in range(3)]


def multiply_rotation_rows(left_rows, right_rows):
    return [
        [
            sum(float(left_rows[row][k]) * float(right_rows[k][col]) for k in range(3))
            for col in range(3)
        ]
        for row in range(3)
    ]


def cylinder_axis_index(mount_face):
    if mount_face is None:
        return 2
    mount_face = int(mount_face)
    if mount_face < 0 or mount_face > 11:
        raise RuntimeError(f"Invalid mount_face for cylinder: {mount_face}")
    return (mount_face % 6) // 2


def cylinder_base_center_offset(axis_index, radius):
    offsets = {
        0: [0.0, radius, radius],
        1: [radius, 0.0, radius],
        2: [radius, radius, 0.0],
    }
    return offsets[axis_index]


def infer_cylinder_radius_and_height(component_id, dims, radius, height, axis_index):
    dims_values = None if dims is None else [float(value) for value in dims]

    if dims_values is not None and len(dims_values) not in (2, 3):
        raise RuntimeError(
            "Cylinder component "
            f"{component_id} requires two or three dims values when dims are used."
        )

    if radius is None:
        if dims_values is None:
            raise RuntimeError(
                f"Cylinder component {component_id} requires radius or dims values."
            )
        if len(dims_values) == 2:
            radius = dims_values[0] / 2.0
        else:
            cross_section = [dims_values[index] for index in range(3) if index != axis_index]
            radius = min(cross_section) / 2.0
    else:
        radius = float(radius)

    if height is None:
        if dims_values is None:
            raise RuntimeError(
                f"Cylinder component {component_id} requires height or dims values."
            )
        if len(dims_values) == 2:
            height = dims_values[1]
        else:
            height = dims_values[axis_index]
    else:
        height = float(height)

    return radius, height


def build_component_shape_spec(component_id, component):
    shape = component.get("shape", "box")
    placement = component.get("placement", {})
    if "position" not in placement:
        raise RuntimeError(f"Missing placement.position for {component_id}")

    position = [float(value) for value in placement["position"]]
    rotation_rows = normalize_rotation_rows(None)
    dims = component.get("dims")

    if shape == "box":
        if dims is None or len(dims) != 3:
            raise RuntimeError(f"Box component {component_id} requires three dims values.")
        dims = [float(value) for value in dims]
        return {
            "shape": "box",
            "object_type": "Part::Box",
            "placement_position": position,
            "rotation_rows": rotation_rows,
            "length": dims[0],
            "width": dims[1],
            "height": dims[2],
        }

    if shape == "cylinder":
        axis_index = cylinder_axis_index(placement.get("mount_face"))
        radius, height = infer_cylinder_radius_and_height(
            component_id,
            dims,
            component.get("radius"),
            component.get("height"),
            axis_index,
        )

        if radius <= 0.0 or height <= 0.0:
            raise RuntimeError(
                f"Cylinder component {component_id} requires positive radius and height."
            )

        placement_position = translate_position(
            position,
            rotation_rows,
            cylinder_base_center_offset(axis_index, radius),
        )
        placement_rotation_rows = multiply_rotation_rows(
            rotation_rows,
            CYLINDER_AXIS_ROTATION_ROWS[axis_index],
        )
        return {
            "shape": "cylinder",
            "object_type": "Part::Cylinder",
            "placement_position": placement_position,
            "rotation_rows": placement_rotation_rows,
            "radius": radius,
            "height": height,
            "angle": 360.0,
        }

    raise RuntimeError(f"Unsupported shape for {component_id}: {shape}")
"""
