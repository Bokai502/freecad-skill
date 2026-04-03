import json
import sys
from pathlib import Path

import FreeCAD
import yaml

DOC_NAME = __DOC_NAME__
YAML_PATH = Path(__YAML_PATH__)
COMPONENT_ID = __COMPONENT_ID__
SOLID_NAME = __SOLID_NAME__
PART_NAME = __PART_NAME__


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


__PLACEMENT_HELPERS__


def placement_payload(placement):
    return {
        "base": vec(placement.Base),
        "rotation_quaternion": [
            float(placement.Rotation.Q[0]),
            float(placement.Rotation.Q[1]),
            float(placement.Rotation.Q[2]),
            float(placement.Rotation.Q[3]),
        ],
    }


try:
    doc = FreeCAD.getDocument(DOC_NAME)
    if doc is None:
        raise RuntimeError(f"document not found: {DOC_NAME}")

    with YAML_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    component = data.get("components", {}).get(COMPONENT_ID)
    if component is None:
        raise RuntimeError(f"component not found in yaml: {COMPONENT_ID}")

    target_position = component["placement"]["position"]
    rotation_rows = component["placement"].get("rotation_matrix") or [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
    ]
    target_placement = make_placement(target_position, rotation_rows)

    solid = doc.getObject(SOLID_NAME) if SOLID_NAME else None
    part = doc.getObject(PART_NAME) if PART_NAME else None

    updates = []
    if solid is not None:
        old = solid.Placement
        solid.Placement = target_placement
        updates.append(
            {
                "object": solid.Name,
                "old_placement": placement_payload(old),
                "new_placement": placement_payload(solid.Placement),
                "mode": "absolute",
            }
        )

    if part is not None:
        old = part.Placement
        if solid is not None:
            part.Placement = FreeCAD.Placement()
        else:
            part.Placement = target_placement
        updates.append(
            {
                "object": part.Name,
                "old_placement": placement_payload(old),
                "new_placement": placement_payload(part.Placement),
                "mode": "absolute",
            }
        )

    if not updates:
        raise RuntimeError(
            f"neither solid '{SOLID_NAME}' nor part '{PART_NAME}' exists in document '{DOC_NAME}'"
        )

    doc.recompute()
    print(
        json.dumps(
            {
                "success": True,
                "document": DOC_NAME,
                "component": COMPONENT_ID,
                "yaml_path": str(YAML_PATH),
                "updates": updates,
            }
        )
    )
except Exception as exc:
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
