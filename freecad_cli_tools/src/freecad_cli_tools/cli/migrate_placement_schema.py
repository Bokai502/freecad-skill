#!/usr/bin/env python3
"""Migrate placement schema to the simplified single-face convention.

Per component:
  - Set mount_face := old envelope_face (if present) else old mount_face.
  - For boxes: absorb any old rotation_matrix into dims so the world AABB is
    preserved (new rotation is identity; dims are world extents; position is
    the world min corner).
  - For cylinders: leave dims alone (cylinder rotation is still derived from
    mount_face at runtime).
  - Recompute mount_point.
  - Remove envelope_face and rotation_matrix keys.
"""

from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path

import yaml

from freecad_cli_tools.geometry import (
    apply_rotation,
    component_contact_face,
    component_local_extents,
    compute_mount_point,
)


IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def _is_identity(matrix: list[list[float]]) -> bool:
    for r in range(3):
        for c in range(3):
            expected = 1.0 if r == c else 0.0
            if abs(float(matrix[r][c]) - expected) > 1e-9:
                return False
    return True


def _absorb_rotation_into_box(
    old_position: list[float],
    old_dims: list[float],
    old_rotation: list[list[float]],
) -> tuple[list[float], list[float]]:
    """Return (new_position, new_dims) preserving the world AABB."""
    dx, dy, dz = (float(v) for v in old_dims)
    corners = [
        [0.0, 0.0, 0.0],
        [dx, 0.0, 0.0],
        [0.0, dy, 0.0],
        [0.0, 0.0, dz],
        [dx, dy, 0.0],
        [dx, 0.0, dz],
        [0.0, dy, dz],
        [dx, dy, dz],
    ]
    world = [
        [float(old_position[i]) + apply_rotation(old_rotation, c)[i] for i in range(3)]
        for c in corners
    ]
    world_min = [min(c[i] for c in world) for i in range(3)]
    world_max = [max(c[i] for c in world) for i in range(3)]
    new_dims = [world_max[i] - world_min[i] for i in range(3)]
    return world_min, new_dims


def migrate_component(comp_id: str, comp: dict) -> dict:
    updated = deepcopy(comp)
    placement = updated.setdefault("placement", {})

    old_mount = placement.get("mount_face")
    old_envelope = placement.get("envelope_face")
    new_mount_face = old_envelope if old_envelope is not None else old_mount
    if new_mount_face is None:
        raise ValueError(f"component '{comp_id}' missing mount_face/envelope_face")
    placement["mount_face"] = int(new_mount_face)

    rotation = placement.get("rotation_matrix")
    shape = str(updated.get("shape", "box")).strip().lower()

    if shape == "box" and rotation is not None and not _is_identity(rotation):
        old_position = [float(v) for v in placement["position"]]
        old_dims = [float(v) for v in updated["dims"]]
        new_position, new_dims = _absorb_rotation_into_box(
            old_position, old_dims, rotation
        )
        placement["position"] = new_position
        updated["dims"] = new_dims

    placement.pop("envelope_face", None)
    placement.pop("rotation_matrix", None)

    extents = component_local_extents(comp_id, updated)
    contact_face = component_contact_face(placement["mount_face"])
    placement["mount_point"] = compute_mount_point(
        placement["position"], extents, contact_face, IDENTITY
    )
    return updated


def migrate_document(data: dict) -> dict:
    result = deepcopy(data)
    components = result.get("components", {})
    for comp_id, comp in list(components.items()):
        components[comp_id] = migrate_component(str(comp_id), comp)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input YAML file path.")
    parser.add_argument(
        "--output",
        help="Output YAML file (defaults to --input when --in-place).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file in place.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if args.in_place:
        output_path = input_path
    elif args.output:
        output_path = Path(args.output)
    else:
        raise SystemExit("Provide --output or --in-place.")

    with input_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    migrated = migrate_document(data)

    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(migrated, handle, sort_keys=False, allow_unicode=True)

    print(f"migrated: {input_path} -> {output_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
