import json
import sys

import FreeCAD

DOC_NAME = __DOC_NAME__
OBJ_NAME = __OBJ_NAME__
MODE = __MODE__
VECTOR = FreeCAD.Vector(__X__, __Y__, __Z__)


try:
    doc = FreeCAD.getDocument(DOC_NAME)
    if doc is None:
        raise RuntimeError(f"document not found: {DOC_NAME}")
    obj = doc.getObject(OBJ_NAME)
    if obj is None:
        raise RuntimeError(f"object not found: {OBJ_NAME}")

    old = obj.Placement.Base
    old_pos = [float(old.x), float(old.y), float(old.z)]
    new = old.add(VECTOR) if MODE == "delta" else VECTOR
    obj.Placement.Base = new
    doc.recompute()

    print(
        json.dumps(
            {
                "success": True,
                "document": DOC_NAME,
                "object": OBJ_NAME,
                "mode": MODE,
                "old_position": old_pos,
                "new_position": [float(new.x), float(new.y), float(new.z)],
            }
        )
    )
except Exception as exc:
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
