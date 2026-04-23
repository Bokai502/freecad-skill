import json

import FreeCAD

DOC_NAME = __DOC_NAME__
OBJ_NAME = __OBJ_NAME__


def safe_getattr(obj, attr, default=None):
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def safe_property(obj, name):
    try:
        return obj.getPropertyByName(name)
    except Exception:
        return safe_getattr(obj, name)


def to_float_list(values):
    return [float(value) for value in values]


def serialize_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]

    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}

    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return {
            "x": float(value.x),
            "y": float(value.y),
            "z": float(value.z),
        }

    if hasattr(value, "Axis") and hasattr(value, "Angle"):
        axis = safe_getattr(value, "Axis")
        return {
            "axis": serialize_value(axis),
            "angle": float(value.Angle),
        }

    if hasattr(value, "Base") and hasattr(value, "Rotation"):
        rotation = safe_getattr(value, "Rotation")
        return {
            "Base": serialize_value(value.Base),
            "Rotation": serialize_value(rotation),
            "Matrix": [
                to_float_list(value.toMatrix().A[index : index + 4])
                for index in range(0, 16, 4)
            ],
        }

    if all(hasattr(value, attr) for attr in ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax")):
        return {
            "xmin": float(value.XMin),
            "ymin": float(value.YMin),
            "zmin": float(value.ZMin),
            "xmax": float(value.XMax),
            "ymax": float(value.YMax),
            "zmax": float(value.ZMax),
            "xlen": float(value.XLength),
            "ylen": float(value.YLength),
            "zlen": float(value.ZLength),
        }

    if hasattr(value, "Value"):
        try:
            return value.Value
        except Exception:
            pass

    return str(value)


def serialize_view(view):
    if view is None:
        return None

    payload = {
        "TypeId": safe_getattr(view, "TypeId", ""),
    }
    for name in safe_getattr(view, "PropertiesList", []) or []:
        payload[name] = serialize_value(safe_property(view, name))
    return payload


def serialize_object(obj):
    payload = {
        "Name": obj.Name,
        "Label": safe_getattr(obj, "Label", obj.Name),
        "TypeId": safe_getattr(obj, "TypeId", ""),
    }

    for name in safe_getattr(obj, "PropertiesList", []) or []:
        payload[name] = serialize_value(safe_property(obj, name))

    shape = safe_getattr(obj, "Shape")
    if shape is not None:
        bound_box = safe_getattr(shape, "BoundBox")
        if bound_box is not None:
            payload["BoundBox"] = serialize_value(bound_box)

    view = safe_getattr(obj, "ViewObject")
    if view is not None:
        payload["ViewObject"] = serialize_view(view)

    return payload


doc = FreeCAD.getDocument(DOC_NAME)
obj = doc.getObject(OBJ_NAME)
if obj is None:
    raise RuntimeError(f"Object not found: {OBJ_NAME}")

print(json.dumps(serialize_object(obj), ensure_ascii=False))
