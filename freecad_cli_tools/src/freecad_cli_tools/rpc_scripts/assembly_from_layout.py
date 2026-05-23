import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD
import FreeCADGui
import Import
import ImportGui
import Part

INPUT_PATH = __INPUT_PATH__
DOC_NAME = __DOC_NAME__
SAVE_PATH = __SAVE_PATH__
EXPORT_GLB = __EXPORT_GLB__
FIT_VIEW = __FIT_VIEW__
VIEW_NAME = __VIEW_NAME__
PROGRESS_PATH = __PROGRESS_PATH__
PROGRESS_TOOL = __PROGRESS_TOOL__
PROGRESS_OUTPUT_FILES = __PROGRESS_OUTPUT_FILES__
LAST_PROGRESS = {
    "layout_completion_percent": 100.0,
    "modeling_percent": 0.0,
    "export_file_percent": 0.0,
    "validation_percent": 0.0,
}
PROGRESS_SCHEMA_VERSION = "freecad_progress/1.0"
PROGRESS_KEYS = (
    "modeling_percent",
    "export_file_percent",
    "validation_percent",
)
CAD_BUILD_COMMANDS = {"cad build", "freecad-tools cad build"}
CAD_VALIDATE_COMMANDS = {"cad validate", "freecad-tools cad validate"}
CAD_MODIFY_COMMANDS = {"layout safe-move", "freecad-layout-safe-move", "freecad-tools layout safe-move"}


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def output_file_records():
    records = {}
    for name, path in (PROGRESS_OUTPUT_FILES or {}).items():
        records[name] = {
            "path": path,
            "exists": bool(path) and Path(path).exists(),
        }
    return records


def read_existing_progress(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def overall_percent(progress):
    return round(sum(float(progress.get(key, 0.0)) for key in PROGRESS_KEYS) / len(PROGRESS_KEYS), 2)


def normalize_progress(progress):
    normalized = {key: 0.0 for key in PROGRESS_KEYS}
    for key, value in progress.items():
        normalized[key] = float(value)
    return normalized


def progress_for_tool_payload(tool, payload):
    progress = payload.get("progress_percentages")
    if not isinstance(progress, dict):
        return {}

    command = str(payload.get("command") or tool).strip().lower()
    tool_name = str(payload.get("tool") or tool).strip().lower()
    names = {command, tool_name}
    normalized = normalize_progress(progress)

    if names & CAD_VALIDATE_COMMANDS:
        return {"validation_percent": normalized["validation_percent"]}
    if names & CAD_BUILD_COMMANDS:
        return {
            "modeling_percent": normalized["modeling_percent"],
            "export_file_percent": normalized["export_file_percent"],
        }
    return {key: float(value) for key, value in normalized.items() if key in PROGRESS_KEYS}


def aggregate_progress_from_tools(tools, fallback):
    aggregated = {key: 0.0 for key in PROGRESS_KEYS}
    for tool_name, tool_payload in tools.items():
        if not isinstance(tool_payload, dict):
            continue
        for key, value in progress_for_tool_payload(str(tool_name), tool_payload).items():
            aggregated[key] = max(aggregated[key], float(value))

    fallback_progress = fallback.get("progress_percentages")
    if isinstance(fallback_progress, dict):
        for key in PROGRESS_KEYS:
            value = fallback_progress.get(key)
            if isinstance(value, (int, float)):
                aggregated[key] = max(aggregated[key], float(value))
    for key in PROGRESS_KEYS:
        value = fallback.get(key)
        if isinstance(value, (int, float)):
            aggregated[key] = max(aggregated[key], float(value))
    return aggregated


def starts_cad_workflow(payload):
    command = str(payload.get("command") or "").strip().lower()
    tool = str(payload.get("tool") or "").strip().lower()
    return bool({command, tool} & (CAD_BUILD_COMMANDS | CAD_MODIFY_COMMANDS))


def merge_progress_payload(path, tool, payload):
    existing = read_existing_progress(path)
    merged = dict(existing)
    merged.update(payload)

    tools = existing.get("tools")
    if not isinstance(tools, dict):
        tools = {}
    merged_tools = dict(tools)
    if starts_cad_workflow(payload):
        for stale_tool in list(merged_tools):
            stale_payload = merged_tools.get(stale_tool)
            if not isinstance(stale_payload, dict):
                continue
            stale_command = str(stale_payload.get("command") or stale_tool).strip().lower()
            stale_tool_name = str(stale_payload.get("tool") or stale_tool).strip().lower()
            if {stale_command, stale_tool_name} & CAD_VALIDATE_COMMANDS:
                merged_tools.pop(stale_tool, None)
    merged_tools[tool] = payload
    for tool_payload in merged_tools.values():
        if isinstance(tool_payload, dict):
            tool_payload.pop("output_files", None)
    merged["tools"] = merged_tools
    merged["progress_percentages"] = aggregate_progress_from_tools(merged_tools, existing)

    merged.pop("history", None)
    return merged


def write_progress(layout_percent, modeling_percent, export_percent, success=False):
    global LAST_PROGRESS
    if not PROGRESS_PATH:
        return
    progress = {
        "layout_completion_percent": float(layout_percent),
        "modeling_percent": float(modeling_percent),
        "export_file_percent": float(export_percent),
        "validation_percent": 0.0,
    }
    LAST_PROGRESS = dict(progress)
    write_progress_payload(progress, success=success)


def write_progress_payload(progress, success=False):
    if not PROGRESS_PATH:
        return
    path = Path(PROGRESS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "workflow": "create_cad",
        "command": "cad build",
        "stage": "cad_build",
        "status": "success" if success else "running",
        "tool": PROGRESS_TOOL,
        "updated_at": utc_now_iso(),
        "success": bool(success),
        "overall_percent": overall_percent(progress),
        "progress_percentages": normalize_progress(progress),
        "error": None,
        **{key: value for key, value in progress.items() if key != "layout_completion_percent"},
    }
    if PROGRESS_OUTPUT_FILES:
        payload["output_files"] = output_file_records()
    payload = merge_progress_payload(path, PROGRESS_TOOL, payload)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(str(temp_path), str(path))


def mark_progress_failed():
    write_progress_payload(dict(LAST_PROGRESS), success=False)


def build_envelope(doc, assembly, data):
    envelope = data.get("envelope")
    if not envelope:
        return None

    outer_size = envelope.get("outer_size")
    inner_size = envelope.get("inner_size")
    shell_thickness = envelope.get("shell_thickness")
    if not outer_size or not inner_size or shell_thickness is None:
        return None

    outer_bbox = envelope.get("outer_bbox") or {}
    inner_bbox = envelope.get("inner_bbox") or {}
    outer_min = outer_bbox.get("min") or [-(float(v) / 2.0) for v in outer_size]
    inner_min = inner_bbox.get("min") or [-(float(v) / 2.0) for v in inner_size]

    outer_shape = Part.makeBox(
        float(outer_size[0]),
        float(outer_size[1]),
        float(outer_size[2]),
        FreeCAD.Vector(*outer_min),
    )
    inner_shape = Part.makeBox(
        float(inner_size[0]),
        float(inner_size[1]),
        float(inner_size[2]),
        FreeCAD.Vector(*inner_min),
    )
    shell_shape = outer_shape.cut(inner_shape)

    envelope_part = doc.addObject("App::Part", "Envelope_part")
    assembly.addObject(envelope_part)
    envelope_shell = doc.addObject("Part::Feature", "EnvelopeShell")
    envelope_shell.Shape = shell_shape
    envelope_shell.ViewObject.DisplayMode = "Wireframe"
    envelope_shell.ViewObject.LineColor = (0.2, 0.5, 0.9, 0.0)
    envelope_shell.ViewObject.LineWidth = 2.0
    envelope_part.addObject(envelope_shell)
    return envelope_shell.Name


__PLACEMENT_HELPERS__
__COMPONENT_SHAPE_HELPERS__


def set_view(doc_name):
    gui_doc = FreeCADGui.getDocument(doc_name)
    if gui_doc is None:
        return False
    FreeCADGui.ActiveDocument = gui_doc
    try:
        gui_doc.activeView().setAnimationEnabled(False)
    except Exception:
        pass
    try:
        gui_doc.activeView().viewIsometric()
    except Exception:
        try:
            FreeCADGui.SendMsgToActiveView("ViewIsometric")
        except Exception:
            pass
    try:
        gui_doc.activeView().fitAll()
    except Exception:
        try:
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
    return True


def apply_color(obj, color):
    if not color or len(color) < 3:
        return
    rgba = [float(c) / 255.0 for c in color[:4]]
    while len(rgba) < 4:
        rgba.append(1.0)
    obj.ViewObject.ShapeColor = (rgba[0], rgba[1], rgba[2], rgba[3])
    obj.ViewObject.Transparency = 40


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
            shape = obj.Shape
        except Exception:
            continue
        if shape is None or shape.isNull():
            continue
        yield obj


def collect_glb_export_objects(objects):
    glb_objects = []
    for obj in objects:
        descendants = list(iter_descendant_shapes(obj))
        if descendants:
            glb_objects.extend(descendants)
            continue
        try:
            shape = obj.Shape
        except Exception:
            shape = None
        if shape is not None and not shape.isNull():
            glb_objects.append(obj)
    return glb_objects or list(objects)


def export_step_and_glb(objects, step_path):
    step_path = str(Path(step_path))
    glb_path = str(Path(step_path).with_suffix(".glb"))

    write_progress(100.0, 100.0, 0.0)
    Import.export(objects, step_path)
    write_progress(100.0, 100.0, 50.0)
    glb_objects = collect_glb_export_objects(objects)

    export_options = None
    if hasattr(ImportGui, "exportOptions"):
        try:
            export_options = ImportGui.exportOptions("glTF")
        except Exception:
            export_options = None

    if export_options is None:
        ImportGui.export(glb_objects, glb_path)
    else:
        try:
            ImportGui.export(glb_objects, glb_path, export_options)
        except TypeError:
            ImportGui.export(glb_objects, glb_path)

    write_progress(100.0, 100.0, 100.0, success=True)
    return step_path, glb_path


def export_step(objects, step_path):
    step_path = str(Path(step_path))
    write_progress(100.0, 100.0, 0.0)
    Import.export(objects, step_path)
    write_progress(100.0, 100.0, 50.0)
    return step_path


try:
    write_progress(100.0, 0.0, 0.0)
    path = Path(INPUT_PATH)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

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

    try:
        assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
    except Exception:
        assembly = doc.addObject("App::Part", "Assembly")

    envelope_name = build_envelope(doc, assembly, data)
    created = []
    components = list(data.get("components", {}).items())
    total_components = max(len(components), 1)
    for index, (component_id, component) in enumerate(components, start=1):
        part = doc.addObject("App::Part", f"{component_id}_part")
        assembly.addObject(part)

        shape_spec = build_component_shape_spec(component_id, component)
        solid = doc.addObject(shape_spec["object_type"], component_id)

        if shape_spec["shape"] == "box":
            solid.Length = shape_spec["length"]
            solid.Width = shape_spec["width"]
            solid.Height = shape_spec["height"]
        elif shape_spec["shape"] == "cylinder":
            solid.Radius = shape_spec["radius"]
            solid.Height = shape_spec["height"]
            solid.Angle = shape_spec["angle"]
        else:
            raise RuntimeError(f"Unsupported shape for {component_id}: {shape_spec['shape']}")

        solid.Placement = make_placement(
            shape_spec["placement_position"],
            shape_spec["rotation_rows"],
        )
        apply_color(solid, component.get("color"))
        part.addObject(solid)
        created.append(component_id)
        write_progress(100.0, (index / total_components) * 90.0, 0.0)

    write_progress(100.0, 95.0, 0.0)
    doc.recompute()
    write_progress(100.0, 100.0, 0.0)
    if EXPORT_GLB:
        save_path, glb_path = export_step_and_glb([assembly], SAVE_PATH)
    else:
        save_path = export_step([assembly], SAVE_PATH)
        glb_path = None

    view_updated = False
    if FIT_VIEW:
        view_updated = set_view(doc.Name)

    print(
        json.dumps(
            {
                "success": True,
                "document": doc.Name,
                "save_path": save_path,
                "glb_path": glb_path,
                "component_count": len(created),
                "envelope_object": envelope_name,
                "view_name": VIEW_NAME,
                "view_updated": view_updated,
            }
        )
    )
except Exception as exc:
    mark_progress_failed()
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
