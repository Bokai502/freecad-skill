import json
import sys

import FreeCAD

DOC_NAME = __DOC_NAME__
UPDATES = __UPDATES__
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

    applied = []
    for update in UPDATES:
        component_id = update["component"]
        part_placement = make_placement(update["position"], update["rotation_matrix"])
        solid_placement = make_placement(
            update.get("solid_position", update["position"]),
            update.get("solid_rotation_matrix", update["rotation_matrix"]),
        )
        solid_name = update.get("solid_name")
        part_name = update.get("part_name")
        solid = doc.getObject(solid_name) if solid_name else None
        part = doc.getObject(part_name) if part_name else None

        if solid is None and part is None:
            raise RuntimeError(
                f"component '{component_id}' missing from document '{DOC_NAME}' "
                f"(solid='{solid_name}', part='{part_name}')"
            )

        placements = []
        if solid is not None:
            old = solid.Placement
            solid.Placement = solid_placement
            placements.append(
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
                part.Placement = part_placement
            placements.append(
                {
                    "object": part.Name,
                    "old_placement": placement_payload(old),
                    "new_placement": placement_payload(part.Placement),
                    "mode": "absolute",
                }
            )

        applied.append({"component": component_id, "updates": placements})

    if RECOMPUTE:
        doc.recompute()

    print(
        json.dumps(
            {
                "success": True,
                "document": DOC_NAME,
                "component_count": len(applied),
                "components": applied,
                "recomputed": bool(RECOMPUTE),
            }
        )
    )
except Exception as exc:
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
