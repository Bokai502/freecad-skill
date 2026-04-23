import json
import math
import sys
from pathlib import Path

import FreeCAD
import FreeCADGui
import Import
import ImportGui
import Part
import yaml

YAML_PATH = __YAML_PATH__
ASSEMBLY_PATH = __ASSEMBLY_PATH__
REPLACEMENT_PATH = __REPLACEMENT_PATH__
COMPONENT_NAME = __COMPONENT_NAME__
DOC_NAME = __DOC_NAME__
FIT_VIEW = __FIT_VIEW__


FACE_DEFINITIONS = {
    0: ("-x", 0, -1),
    1: ("x", 0, 1),
    2: ("-y", 1, -1),
    3: ("y", 1, 1),
    4: ("-z", 2, -1),
    5: ("z", 2, 1),
    6: ("ext-x", 0, -1),
    7: ("ext+x", 0, 1),
    8: ("ext-y", 1, -1),
    9: ("ext+y", 1, 1),
    10: ("ext-z", 2, -1),
    11: ("ext+z", 2, 1),
}


def is_external_face(face_id):
    return face_id >= 6


def yaml_bbox(component):
    placement = component.get("placement") or {}
    position = [float(v) for v in placement.get("position", [0.0, 0.0, 0.0])]
    shape = (component.get("shape") or "box").lower()
    dims = component.get("dims")
    if dims is None:
        return position, [0.0, 0.0, 0.0]
    dims = [float(v) for v in dims]
    if shape == "box" and len(dims) == 3:
        return position, dims
    if shape == "cylinder":
        mount_face = placement.get("mount_face", 5)
        axis_index = FACE_DEFINITIONS[int(mount_face)][1]
        if len(dims) == 2:
            radius = dims[0] / 2.0
            height = dims[1]
        elif len(dims) == 3:
            cross = [dims[i] for i in range(3) if i != axis_index]
            radius = min(cross) / 2.0
            height = dims[axis_index]
        else:
            return position, [0.0, 0.0, 0.0]
        diameter = radius * 2.0
        extents = [diameter, diameter, diameter]
        extents[axis_index] = height
        return position, extents
    return position, [0.0, 0.0, 0.0]


def shape_world_bbox(obj):
    try:
        shape = obj.Shape
    except Exception:
        return None
    if shape is None or shape.isNull():
        return None
    placed = shape.copy()
    placed.Placement = obj.getGlobalPlacement()
    bb = placed.BoundBox
    if not bb.isValid():
        return None
    return bb


def aggregate_world_bbox(objs):
    aggregate = None
    for obj in objs:
        bb = shape_world_bbox(obj)
        if bb is None:
            continue
        if aggregate is None:
            aggregate = FreeCAD.BoundBox(bb)
        else:
            aggregate.add(bb)
    return aggregate


def combined_shape(objs):
    shapes = []
    for obj in objs:
        if obj.TypeId == "App::Part":
            # Recurse into Part containers; sub-shapes already carry global placements.
            sub = combined_shape(list(getattr(obj, "Group", []) or []))
            if sub is not None:
                placed = sub.copy()
                placed.Placement = obj.getGlobalPlacement().multiply(sub.Placement)
                shapes.append(placed)
            continue
        try:
            sh = obj.Shape
        except Exception:
            continue
        if sh is None or sh.isNull():
            continue
        placed = sh.copy()
        placed.Placement = obj.getGlobalPlacement()
        shapes.append(placed)
    if not shapes:
        return None
    if len(shapes) == 1:
        return shapes[0]
    compound = Part.Compound(shapes)
    return compound


def rotation_to_align(src_dir, dst_dir):
    src = FreeCAD.Vector(*src_dir).normalize()
    dst = FreeCAD.Vector(*dst_dir).normalize()
    dot = src.dot(dst)
    if abs(dot - 1.0) < 1e-9:
        return FreeCAD.Rotation()
    if abs(dot + 1.0) < 1e-9:
        if abs(src.x) < 0.9:
            perp = FreeCAD.Vector(1, 0, 0).cross(src)
        else:
            perp = FreeCAD.Vector(0, 1, 0).cross(src)
        perp.normalize()
        return FreeCAD.Rotation(perp, 180.0)
    axis = src.cross(dst)
    axis.normalize()
    angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
    return FreeCAD.Rotation(axis, angle)


def find_assembly(doc):
    candidates = [
        o for o in doc.Objects
        if o.TypeId in ("Assembly::AssemblyObject", "App::Part")
        and (o.Label == "Assembly" or o.Name == "Assembly")
    ]
    if candidates:
        return candidates[0]
    parts = [o for o in doc.Objects if o.TypeId == "App::Part"]
    roots = [o for o in parts if not any(
        parent.TypeId in ("Assembly::AssemblyObject", "App::Part")
        for parent in getattr(o, "InList", []) or []
    )]
    return roots[0] if roots else None


def list_assembly_components(assembly):
    ids = []
    for child in getattr(assembly, "Group", []) or []:
        label = getattr(child, "Label", "")
        if label.endswith("_part"):
            ids.append(label[: -len("_part")])
        elif label and label != "Envelope_part":
            ids.append(label)
    return ids


def find_component_part(assembly, name):
    if assembly is None:
        return None
    part_label = f"{name}_part"
    for child in getattr(assembly, "Group", []) or []:
        if child.Label == part_label or child.Label == name or child.Name == name:
            return child
    return None


def remove_object_with_children(doc, obj):
    removed = []
    children = list(getattr(obj, "OutList", []) or [])
    for child in children:
        if child is None or child is obj:
            continue
        try:
            removed.extend(remove_object_with_children(doc, child))
        except Exception:
            pass
    # Clear OriginFeatures *after* children are already removed so FreeCAD
    # never sees the Origin in a broken "has list, missing features" state.
    if obj.TypeId == "App::Origin":
        try:
            obj.OriginFeatures = []
        except Exception:
            pass
    name = obj.Name
    try:
        doc.removeObject(name)
        removed.append(name)
    except Exception:
        pass
    return removed


def create_component_part(doc, label):
    """Create a plain App::Part container matching the YAML builder's convention."""
    part = doc.addObject("App::Part", label)
    part.Label = label
    return part


def serialize_placement(placement):
    base = placement.Base
    rotation = placement.Rotation.Q
    return {
        "base": [float(base.x), float(base.y), float(base.z)],
        "rotation_q": [
            float(rotation[0]),
            float(rotation[1]),
            float(rotation[2]),
            float(rotation[3]),
        ],
    }


def deserialize_placement(payload):
    placement = FreeCAD.Placement()
    base = payload.get("base", [0.0, 0.0, 0.0])
    rotation_q = payload.get("rotation_q", [0.0, 0.0, 0.0, 1.0])
    placement.Base = FreeCAD.Vector(
        float(base[0]),
        float(base[1]),
        float(base[2]),
    )
    placement.Rotation = FreeCAD.Rotation(
        float(rotation_q[0]),
        float(rotation_q[1]),
        float(rotation_q[2]),
        float(rotation_q[3]),
    )
    return placement


def capture_assembly_placements(container, skip_names=None):
    skip_names = set(skip_names or ())
    placements = {}
    stack = [container]
    while stack:
        obj = stack.pop()
        if obj is None:
            continue
        name = getattr(obj, "Name", "")
        if name in skip_names:
            continue
        try:
            placements[name] = serialize_placement(obj.Placement)
        except Exception:
            pass
        children = list(getattr(obj, "Group", []) or [])
        stack.extend(reversed(children))
    return placements


def restore_captured_placements(doc, placements):
    restored = []
    for name, payload in placements.items():
        obj = doc.getObject(name)
        if obj is None:
            continue
        try:
            obj.Placement = deserialize_placement(payload)
            restored.append(name)
        except Exception:
            pass
    return restored


def normalize_rgba(color):
    if not color or len(color) < 3:
        return None
    rgba = []
    for channel in color[:4]:
        value = float(channel)
        if value < 0.0 or value > 1.0:
            value = value / 255.0
        rgba.append(max(0.0, min(1.0, value)))
    while len(rgba) < 4:
        rgba.append(1.0)
    return (rgba[0], rgba[1], rgba[2], rgba[3])


def set_component_display_mode(view):
    for mode in ("Flat Lines", "Shaded", "As Is"):
        try:
            view.DisplayMode = mode
            return
        except Exception:
            pass


def apply_color(obj, color, transparency=None):
    rgba = normalize_rgba(color)
    if rgba is None:
        return
    view = getattr(obj, "ViewObject", None)
    if view is None:
        return
    try:
        set_component_display_mode(view)
    except Exception:
        pass
    try:
        view.ShapeColor = rgba
    except Exception:
        pass
    if transparency is not None:
        try:
            view.Transparency = int(transparency)
        except Exception:
            pass
    try:
        face_count = len(getattr(obj.Shape, "Faces", []) or [])
        if face_count > 0:
            view.DiffuseColor = [rgba] * face_count
    except Exception:
        pass


def capture_object_view_style(obj):
    view = getattr(obj, "ViewObject", None)
    if view is None:
        return None
    style = {}
    for attr in ("ShapeColor", "DiffuseColor", "LineColor", "LineWidth"):
        try:
            style[attr] = getattr(view, attr)
        except Exception:
            pass
    return style or None


def capture_view_styles(objs):
    styles = {}
    for obj in objs:
        style = capture_object_view_style(obj)
        if style:
            styles[obj.Name] = style
    return styles


def capture_view_style(container):
    for obj in iter_descendant_shapes(container):
        view = getattr(obj, "ViewObject", None)
        if view is None:
            continue
        style = {}
        for attr in ("ShapeColor", "Transparency", "DisplayMode", "LineColor", "LineWidth"):
            try:
                style[attr] = getattr(view, attr)
            except Exception:
                pass
        if style:
            return style
    return None


def restore_replacement_style(obj, imported_style, fallback_color):
    view = getattr(obj, "ViewObject", None)
    if view is None:
        return
    set_component_display_mode(view)
    try:
        view.Transparency = 0
    except Exception:
        pass

    restored = False
    if imported_style:
        shape_color = imported_style.get("ShapeColor")
        diffuse_color = imported_style.get("DiffuseColor")
        if shape_color is not None:
            try:
                view.ShapeColor = shape_color
                restored = True
            except Exception:
                pass
        if diffuse_color is not None:
            try:
                view.DiffuseColor = diffuse_color
                restored = True
            except Exception:
                pass
    if not restored and fallback_color is not None:
        apply_color(obj, fallback_color, transparency=0)


def apply_scene_view_style(
    assembly,
    components,
    replaced_part_label,
    replacement_styles,
    replacement_fallback_color,
):
    """Restore review colors after STEP import/replacement.

    Import.insert resets display properties for all objects in the document,
    so every component must be re-styled — not just the replaced one.
    """
    for child in getattr(assembly, "Group", []) or []:
        label = getattr(child, "Label", "")
        is_envelope = label == "Envelope_part"
        is_replaced = label == replaced_part_label
        component_id = label[: -len("_part")] if label.endswith("_part") else label
        component_meta = (components or {}).get(component_id) or {}
        component_color = component_meta.get("color")
        for obj in iter_descendant_shapes(child):
            view = getattr(obj, "ViewObject", None)
            if view is None:
                continue
            try:
                if is_envelope:
                    view.DisplayMode = "Wireframe"
                    view.LineColor = (0.2, 0.5, 0.9, 0.0)
                    view.LineWidth = 2.0
                    view.Transparency = 100
                elif is_replaced:
                    restore_replacement_style(
                        obj,
                        replacement_styles.get(obj.Name),
                        replacement_fallback_color,
                    )
                else:
                    apply_color(obj, component_color, transparency=40)
            except Exception:
                pass


def iter_descendant_shapes(container):
    stack = list(getattr(container, "Group", []) or [])
    while stack:
        obj = stack.pop()
        if obj is None:
            continue
        if obj.TypeId == "App::Part":
            stack.extend(getattr(obj, "Group", []) or [])
            continue
        try:
            sh = obj.Shape
        except Exception:
            continue
        if sh is None or sh.isNull():
            continue
        yield obj


_ORIGIN_TYPES = ("App::Origin", "App::Line", "App::Plane")


def hide_origin_features(doc):
    """Hide App::Origin + axis/plane children that STEP import auto-creates."""
    for obj in doc.Objects:
        if obj.TypeId in _ORIGIN_TYPES:
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


def fit_view(doc_name):
    try:
        gui_doc = FreeCADGui.getDocument(doc_name)
        if gui_doc is None:
            return False
        FreeCADGui.ActiveDocument = gui_doc
        try:
            gui_doc.activeView().viewIsometric()
        except Exception:
            FreeCADGui.SendMsgToActiveView("ViewIsometric")
        try:
            gui_doc.activeView().fitAll()
        except Exception:
            FreeCADGui.SendMsgToActiveView("ViewFit")
        return True
    except Exception:
        return False


def export_step_and_glb(objects, step_path):
    step_path = str(Path(step_path))
    glb_path = str(Path(step_path).with_suffix(".glb"))

    Import.export(objects, step_path)

    export_options = None
    if hasattr(ImportGui, "exportOptions"):
        try:
            export_options = ImportGui.exportOptions("glTF")
        except Exception:
            export_options = None

    if export_options is None:
        ImportGui.export(objects, glb_path)
    else:
        try:
            ImportGui.export(objects, glb_path, export_options)
        except TypeError:
            ImportGui.export(objects, glb_path)

    return step_path, glb_path


try:
    for _name, _d in list(FreeCAD.listDocuments().items()):
        if _name == DOC_NAME or getattr(_d, "Label", "") == DOC_NAME:
            try:
                FreeCAD.closeDocument(_name)
            except Exception:
                pass
    doc = FreeCAD.newDocument(DOC_NAME)
    if doc.Label != DOC_NAME:
        doc.Label = DOC_NAME
    FreeCAD.setActiveDocument(doc.Name)

    Import.insert(ASSEMBLY_PATH, doc.Name)
    doc.recompute()

    with Path(YAML_PATH).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    component = (data.get("components") or {}).get(COMPONENT_NAME)
    if component is None:
        raise RuntimeError(
            f"Component '{COMPONENT_NAME}' not found in YAML {YAML_PATH}"
        )

    placement = component.get("placement") or {}
    mount_face = placement.get("mount_face")
    if mount_face is None or int(mount_face) not in FACE_DEFINITIONS:
        raise RuntimeError(
            f"Component '{COMPONENT_NAME}' has invalid or missing mount_face={mount_face!r}"
        )
    mount_face = int(mount_face)
    _, mount_axis, mount_direction = FACE_DEFINITIONS[mount_face]
    external = is_external_face(mount_face)

    envelope = data.get("envelope") or {}
    outer_size = envelope.get("outer_size")
    inner_size = envelope.get("inner_size")
    if external:
        if not outer_size:
            raise RuntimeError("External mount face requires envelope.outer_size in YAML.")
        wall_position = mount_direction * float(outer_size[mount_axis]) / 2.0
    else:
        if not inner_size:
            raise RuntimeError("Internal mount face requires envelope.inner_size in YAML.")
        wall_position = mount_direction * float(inner_size[mount_axis]) / 2.0

    flange_dir = [0.0, 0.0, 0.0]
    flange_dir[mount_axis] = (-mount_direction) if external else mount_direction

    yaml_position, yaml_dims = yaml_bbox(component)
    yaml_bbox_center = [yaml_position[i] + yaml_dims[i] / 2.0 for i in range(3)]

    assembly = find_assembly(doc)
    if assembly is None:
        raise RuntimeError(
            f"Assembly container not found in {ASSEMBLY_PATH}. "
            "Expected an 'Assembly' App::Part at the document root."
        )

    existing_component_ids = list_assembly_components(assembly)
    target_part = find_component_part(assembly, COMPONENT_NAME)
    if target_part is None:
        available = ", ".join(sorted(existing_component_ids)) or "(none)"
        raise RuntimeError(
            f"Component '{COMPONENT_NAME}' not found in Assembly. "
            f"Available components: {available}"
        )
    preserved_placements = capture_assembly_placements(
        assembly,
        skip_names={target_part.Name},
    )

    # Import replacement STEP into the main document BEFORE removing the old
    # component. Validation, rotation, and translation are all computed while
    # the old component is still present. The irreversible removal only happens
    # after every computation has succeeded, so any failure leaves the
    # assembly intact.
    before = {o.Name for o in doc.Objects}
    Import.insert(REPLACEMENT_PATH, doc.Name)
    doc.recompute()
    new_objs = [o for o in doc.Objects if o.Name not in before]
    if not new_objs:
        raise RuntimeError(
            f"Replacement STEP {REPLACEMENT_PATH!r} did not produce any objects."
        )
    replacement_styles = capture_view_styles(new_objs)

    top_level_new = [o for o in new_objs if not getattr(o, "InList", [])]
    bbox_objs = top_level_new or new_objs

    combined = combined_shape(bbox_objs)
    if combined is None:
        for o in reversed(new_objs):
            try:
                doc.removeObject(o.Name)
            except Exception:
                pass
        raise RuntimeError(
            f"Replacement STEP {REPLACEMENT_PATH!r} produced no valid shape. "
            "The file may be empty or corrupt."
        )

    native_bb = combined.BoundBox
    native_dims = [native_bb.XLength, native_bb.YLength, native_bb.ZLength]

    # Auto-detect thrust axis by matching STEP bbox extents to YAML placeholder
    # dims. The STEP axis whose extent is closest to yaml_dims[mount_axis] is
    # the one that should align with the world mount axis after rotation.
    replacement_meta = component.get("replacement") or {}
    axis_override = replacement_meta.get("thrust_axis")
    sign_override = replacement_meta.get("flange_sign")

    if axis_override is not None:
        thrust_axis = {"x": 0, "y": 1, "z": 2}[str(axis_override).lower()]
        thrust_axis_source = "yaml"
    else:
        mount_extent = float(yaml_dims[mount_axis])
        if mount_extent > 0.0:
            diffs = sorted(
                (abs(native_dims[i] - mount_extent), i) for i in range(3)
            )
            thrust_axis = diffs[0][1]
            thrust_axis_source = "step_bbox_match"
            ambiguity_margin = abs(diffs[0][0] - diffs[1][0])
            if ambiguity_margin < 5.0:
                import sys as _sys
                _sys.stderr.write(
                    f"[WARN] thrust_axis auto-detection ambiguous for '{COMPONENT_NAME}' "
                    f"(margin={ambiguity_margin:.1f} mm). "
                    "If orientation looks wrong, add replacement.thrust_axis to the YAML.\n"
                )
        else:
            thrust_axis = mount_axis
            thrust_axis_source = "mount_face_fallback"

    if sign_override is not None:
        flange_sign = int(sign_override)
        flange_sign_source = "yaml"
    else:
        flange_sign = 1
        flange_sign_source = "default_positive"
    src_flange_dir = [0.0, 0.0, 0.0]
    src_flange_dir[thrust_axis] = float(flange_sign)

    rotation = rotation_to_align(src_flange_dir, flange_dir)

    for obj in top_level_new:
        current = obj.Placement
        new_placement = FreeCAD.Placement()
        new_placement.Rotation = rotation.multiply(current.Rotation)
        new_placement.Base = rotation.multVec(current.Base)
        obj.Placement = new_placement
    doc.recompute()

    rotated = combined_shape(bbox_objs)
    rb = rotated.BoundBox
    rb_center = [
        (rb.XMin + rb.XMax) / 2.0,
        (rb.YMin + rb.YMax) / 2.0,
        (rb.ZMin + rb.ZMax) / 2.0,
    ]
    rb_min = [rb.XMin, rb.YMin, rb.ZMin]
    rb_max = [rb.XMax, rb.YMax, rb.ZMax]

    delta = [0.0, 0.0, 0.0]
    for axis in range(3):
        if axis == mount_axis:
            if flange_dir[axis] > 0.0:
                delta[axis] = wall_position - rb_max[axis]
            else:
                delta[axis] = wall_position - rb_min[axis]
        else:
            delta[axis] = yaml_bbox_center[axis] - rb_center[axis]

    # All computation succeeded — safe to remove the old component now.
    preserved_style = capture_view_style(target_part)
    removed_objects = remove_object_with_children(doc, target_part)
    doc.recompute()

    container = create_component_part(doc, f"{COMPONENT_NAME}_part")
    color = component.get("color")
    replacement_color = color
    if replacement_color is None and preserved_style is not None:
        replacement_color = preserved_style.get("ShapeColor")
    for obj in top_level_new:
        base = obj.Placement.Base
        obj.Placement.Base = FreeCAD.Vector(
            base.x + delta[0],
            base.y + delta[1],
            base.z + delta[2],
        )
        container.addObject(obj)
    # Add container to assembly only after it is fully populated so FreeCAD's
    # cross-document Origin resolver finds a consistent Part on first lookup.
    assembly.addObject(container)

    doc.recompute()
    restored_placements = restore_captured_placements(doc, preserved_placements)
    if restored_placements:
        doc.recompute()

    apply_scene_view_style(
        assembly,
        data.get("components") or {},
        f"{COMPONENT_NAME}_part",
        replacement_styles,
        replacement_color,
    )
    hide_origin_features(doc)

    assembly_path, glb_path = export_step_and_glb([assembly], ASSEMBLY_PATH)

    fcstd_path = str(Path(assembly_path).with_suffix(".FCStd"))
    try:
        doc.saveAs(fcstd_path)
    except Exception:
        fcstd_path = None

    view_updated = fit_view(doc.Name) if FIT_VIEW else False

    print(
        json.dumps(
            {
                "success": True,
                "document": doc.Name,
                "assembly_path": assembly_path,
                "glb_path": glb_path,
                "fcstd_path": fcstd_path,
                "replacement_path": REPLACEMENT_PATH,
                "component": COMPONENT_NAME,
                "assembly_container": assembly.Name,
                "assembly_component_count": len(list_assembly_components(assembly)),
                "removed_objects": removed_objects,
                "new_objects": [o.Name for o in new_objs],
                "container": container.Name,
                "preserved_placements_count": len(preserved_placements),
                "restored_placements_count": len(restored_placements),
                "mount_face": mount_face,
                "mount_axis": mount_axis,
                "external": external,
                "wall_position": wall_position,
                "thrust_axis": thrust_axis,
                "thrust_axis_source": thrust_axis_source,
                "flange_sign": flange_sign,
                "flange_sign_source": flange_sign_source,
                "flange_dir": flange_dir,
                "yaml_dims": yaml_dims,
                "native_dims": native_dims,
                "yaml_bbox_center": yaml_bbox_center,
                "translation_applied": delta,
                "rotation_axis": list(rotation.Axis),
                "rotation_angle_deg": rotation.Angle * 180.0 / math.pi,
                "view_updated": view_updated,
            }
        )
    )
except Exception as exc:
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
