import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD
import Import
import ImportGui

DOC_NAME = __DOC_NAME__
UPDATES = __UPDATES__
RECOMPUTE = __RECOMPUTE__
EXPORT_STEP_PATH = __EXPORT_STEP_PATH__
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
        "workflow": "modify_cad",
        "command": "layout safe-move",
        "stage": "layout_safe_move",
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


def apply_delta_placement(target_placement, source_placement, current_placement):
    delta = target_placement.multiply(source_placement.inverse())
    return delta.multiply(current_placement)


def export_step_and_glb(objects, step_path):
    step_path = str(Path(step_path))
    Path(step_path).parent.mkdir(parents=True, exist_ok=True)
    glb_path = str(Path(step_path).with_suffix(".glb"))

    write_progress(100.0, 100.0, 0.0)
    Import.export(objects, step_path)
    write_progress(100.0, 100.0, 50.0)

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

    write_progress(100.0, 100.0, 100.0, success=True)
    return step_path, glb_path


def top_level_export_objects(doc):
    ignored_names = {"Origin", "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane"}
    roots = []
    for obj in getattr(doc, "Objects", []):
        if getattr(obj, "InList", []):
            continue
        if getattr(obj, "TypeId", "") == "App::Origin":
            continue
        if getattr(obj, "Name", "") in ignored_names:
            continue
        roots.append(obj)
    return roots


def find_export_objects(doc):
    for obj in getattr(doc, "Objects", []):
        type_id = getattr(obj, "TypeId", "")
        if type_id not in ("Assembly::AssemblyObject", "App::Part"):
            continue
        if getattr(obj, "InList", []):
            continue
        if getattr(obj, "Name", "") == "Assembly" or getattr(obj, "Label", "") == "Assembly":
            return [obj], "assembly_root"

    roots = top_level_export_objects(doc)
    if roots:
        return roots, "top_level"
    return [], "none"


try:
    write_progress(100.0, 0.0, 0.0)
    doc = FreeCAD.getDocument(DOC_NAME)
    if doc is None:
        raise RuntimeError(f"document not found: {DOC_NAME}")

    applied = []
    total_updates = max(len(UPDATES), 1)
    for index, update in enumerate(UPDATES, start=1):
        component_id = update["component"]
        part_placement = make_placement(update["position"], update["orientation_rows"])
        has_source_placement = "source_position" in update and "source_orientation_rows" in update
        source_placement = (
            make_placement(update["source_position"], update["source_orientation_rows"])
            if has_source_placement
            else None
        )
        solid_placement = make_placement(
            update.get("solid_position", update["position"]),
            update.get("solid_orientation_rows", update["orientation_rows"]),
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
        if part is not None and has_source_placement:
            old = part.Placement
            part.Placement = apply_delta_placement(
                part_placement,
                source_placement,
                old,
            )
            placements.append(
                {
                    "object": part.Name,
                    "old_placement": placement_payload(old),
                    "new_placement": placement_payload(part.Placement),
                    "mode": "delta",
                }
            )
        elif solid is not None:
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

        if part is not None and not has_source_placement:
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
        write_progress(100.0, (index / total_updates) * 90.0, 0.0)

    exported_step_path = None
    exported_glb_path = None
    export_mode = None
    exported_object_names = []

    performed_recompute = bool(RECOMPUTE or EXPORT_STEP_PATH)
    if performed_recompute:
        write_progress(100.0, 95.0, 0.0)
        doc.recompute()
        write_progress(100.0, 100.0, 0.0)

    if EXPORT_STEP_PATH:
        export_objects, export_mode = find_export_objects(doc)
        if not export_objects:
            raise RuntimeError(
                f"document '{DOC_NAME}' does not contain any exportable top-level objects"
            )
        exported_object_names = [obj.Name for obj in export_objects]
        exported_step_path, exported_glb_path = export_step_and_glb(
            export_objects,
            EXPORT_STEP_PATH,
        )

    print(
        json.dumps(
            {
                "success": True,
                "document": DOC_NAME,
                "component_count": len(applied),
                "components": applied,
                "recomputed": performed_recompute,
                "step_path": exported_step_path,
                "glb_path": exported_glb_path,
                "export_mode": export_mode,
                "exported_objects": exported_object_names,
            }
        )
    )
except Exception as exc:
    mark_progress_failed()
    print(json.dumps({"success": False, "error": str(exc)}))
    sys.exit(1)
