import json
import sys

import FreeCAD

DOC_NAME = __DOC_NAME__
YAML_PATH = __YAML_PATH__
COMPONENT_ID = __COMPONENT_ID__
SOLID_NAME = __SOLID_NAME__
PART_NAME = __PART_NAME__
TARGET_POSITION = __TARGET_POSITION__
ROTATION_ROWS = __ROTATION_ROWS__
RECOMPUTE = __RECOMPUTE__


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

    target_placement = make_placement(TARGET_POSITION, ROTATION_ROWS)
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

    if RECOMPUTE:
        doc.recompute()

    print(
        json.dumps(
            {
                "success": True,
                "document": DOC_NAME,
                "component": COMPONENT_ID,
                "yaml_path": YAML_PATH,
                "updates": updates,
                "recomputed": bool(RECOMPUTE),
            }
        )
    )
except Exception as exc:
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
