import json
import sys

import FreeCAD

DOC_NAME = __DOC_NAME__
OBJ_NAME = __OBJ_NAME__
MOVE = FreeCAD.Vector(__DX__, __DY__, __DZ__)
VOLUME_EPS = __VOLUME_EPS__


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def global_shape(obj):
    shape = obj.Shape.copy()
    shape.transformShape(obj.getGlobalPlacement().toMatrix(), True)
    return shape


def is_helper(obj):
    name = obj.Name
    if name == "Assembly":
        return True
    if name.startswith("Origin") or name.startswith("X_Axis") or name.startswith("Y_Axis") or name.startswith("Z_Axis"):
        return True
    if "Plane" in name or "Envelope" in name:
        return True
    if getattr(obj, "TypeId", "") == "Assembly::AssemblyObject":
        return True
    return False


def solid_descendants(root):
    result = []
    seen = set()

    def walk(obj):
        if obj.Name in seen:
            return
        seen.add(obj.Name)
        children = [
            child
            for child in (getattr(obj, "OutList", []) or [])
            if getattr(child, "Document", None) is not None and not is_helper(child)
        ]
        child_has_solid = False
        for child in children:
            walk(child)
            cshape = getattr(child, "Shape", None)
            if cshape is not None and not cshape.isNull() and getattr(cshape, "Volume", 0) > 0:
                child_has_solid = True
        shape = getattr(obj, "Shape", None)
        if (
            shape is not None
            and not shape.isNull()
            and getattr(shape, "Volume", 0) > 0
            and not child_has_solid
            and not is_helper(obj)
        ):
            result.append(obj)

    walk(root)
    return result


def ancestors(obj):
    out = set()
    stack = list(getattr(obj, "InList", []) or [])
    while stack:
        cur = stack.pop()
        if cur.Name in out:
            continue
        out.add(cur.Name)
        stack.extend(list(getattr(cur, "InList", []) or []))
    return out


def collisions(doc, target):
    moving = solid_descendants(target)
    skip = {target.Name} | ancestors(target) | {obj.Name for obj in moving}
    others = []
    for obj in doc.Objects:
        if obj.Name in skip or is_helper(obj):
            continue
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull() or getattr(shape, "Volume", 0) <= 0:
            continue
        others.append(obj)

    found = []
    for moving_obj in moving:
        moving_shape = global_shape(moving_obj)
        for other in others:
            other_shape = global_shape(other)
            if moving_shape.distToShape(other_shape)[0] > 0:
                continue
            common = moving_shape.common(other_shape)
            volume = float(getattr(common, "Volume", 0.0)) if not common.isNull() else 0.0
            if volume > VOLUME_EPS:
                found.append(
                    {
                        "moving_leaf": moving_obj.Name,
                        "other": other.Name,
                        "intersection_volume": volume,
                    }
                )
    return found


try:
    doc = FreeCAD.getDocument(DOC_NAME)
    if doc is None:
        raise RuntimeError(f"document not found: {DOC_NAME}")
    target = doc.getObject(OBJ_NAME)
    if target is None:
        raise RuntimeError(f"object not found: {OBJ_NAME}")

    current = FreeCAD.Vector(target.Placement.Base.x, target.Placement.Base.y, target.Placement.Base.z)
    requested = float(MOVE.Length)
    direction = (
        FreeCAD.Vector(MOVE.x / requested, MOVE.y / requested, MOVE.z / requested)
        if requested
        else FreeCAD.Vector(0, 0, 0)
    )

    start_collisions = collisions(doc, target)

    requested_collisions = []
    safe_distance = requested
    safe_ratio = 1.0
    safe_position = vec(current)

    if requested:
        target.Placement.Base = current.add(MOVE)
        doc.recompute()
        requested_collisions = collisions(doc, target)

        if requested_collisions:
            lo, hi = 0.0, requested
            for _ in range(24):
                mid = (lo + hi) / 2.0
                probe = FreeCAD.Vector(direction.x * mid, direction.y * mid, direction.z * mid)
                target.Placement.Base = current.add(probe)
                doc.recompute()
                if collisions(doc, target):
                    hi = mid
                else:
                    lo = mid
            safe_distance = lo
        safe_ratio = safe_distance / requested
        safe_offset = FreeCAD.Vector(
            direction.x * safe_distance,
            direction.y * safe_distance,
            direction.z * safe_distance,
        )
        safe_position = vec(current.add(safe_offset))

    target.Placement.Base = current
    doc.recompute()

    print(
        json.dumps(
            {
                "success": True,
                "document": DOC_NAME,
                "object": OBJ_NAME,
                "current_position": vec(current),
                "requested_move": vec(MOVE),
                "start_collision_count": len(start_collisions),
                "start_collisions": start_collisions,
                "requested_collision_count": len(requested_collisions),
                "requested_collisions": requested_collisions,
                "safe_distance": safe_distance,
                "safe_ratio": safe_ratio,
                "safe_position": safe_position,
            }
        )
    )
except Exception as exc:
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
