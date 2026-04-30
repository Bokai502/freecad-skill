"""Normalize layout_topology.json + geom.json + component info into a build spec."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from freecad_cli_tools.geometry import FACE_DEFINITIONS, is_external_face
from freecad_cli_tools.layout_dataset_common import (
    LayoutDatasetError,
    bbox_size,
    require_string,
    vector3,
)
from freecad_cli_tools.layout_dataset_faces import (
    component_local_face_to_face_id,
    layout_mount_face_to_face_id,
)
from freecad_cli_tools.layout_dataset_io import load_json_file
from freecad_cli_tools.runtime_config import resolve_workspace_path


def load_and_normalize_component_info_assembly(
    layout_topology_path: str | Path,
    geom_path: str | Path,
    geom_component_info_path: str | Path,
    max_step_size_mb: float = 100.0,
) -> dict[str, Any]:
    layout_topology = load_json_file(layout_topology_path)
    geom = load_json_file(geom_path)
    geom_component_info = load_json_file(geom_component_info_path)
    return normalize_component_info_assembly(
        layout_topology=layout_topology,
        geom=geom,
        geom_component_info=geom_component_info,
        geom_component_info_path=geom_component_info_path,
        max_step_size_mb=max_step_size_mb,
    )


def normalize_component_info_assembly(
    *,
    layout_topology: dict[str, Any],
    geom: dict[str, Any],
    geom_component_info: dict[str, Any],
    geom_component_info_path: str | Path,
    max_step_size_mb: float = 100.0,
) -> dict[str, Any]:
    if not isinstance(layout_topology, dict):
        raise LayoutDatasetError("layout_topology data must be a JSON object.")
    if not isinstance(geom, dict):
        raise LayoutDatasetError("geom data must be a JSON object.")
    if not isinstance(geom_component_info, dict):
        raise LayoutDatasetError("geom_component_info data must be a JSON object.")

    outer_shell = geom.get("outer_shell")
    if not isinstance(outer_shell, dict):
        raise LayoutDatasetError("geom.outer_shell must be a JSON object.")

    placement_by_component = _placements_by_component_id(layout_topology)
    geom_components = geom.get("components")
    if geom_components is not None and not isinstance(geom_components, dict):
        raise LayoutDatasetError("geom.components must be a JSON object when present.")

    max_step_size_bytes = _step_size_limit_bytes(max_step_size_mb)
    normalized_components: dict[str, Any] = {}
    for entry in _component_info_entries(geom_component_info):
        component_id = require_string(entry.get("component_id"), "component.component_id")
        placement = placement_by_component.get(component_id)
        if not isinstance(placement, dict):
            raise LayoutDatasetError(
                f"layout_topology.placements is missing component_id={component_id!r}."
            )
        geom_component = _resolve_geom_component(geom_components, component_id)
        target_bbox = _resolve_target_bbox(entry, geom_component, component_id)
        mount_face_id = require_string(
            placement.get("mount_face_id"),
            f"placement[{component_id!r}].mount_face_id",
        )
        component_mount_face_id = require_string(
            placement.get("component_mount_face_id"),
            f"placement[{component_id!r}].component_mount_face_id",
        )
        install_face = layout_mount_face_to_face_id(mount_face_id)
        component_local_face = component_local_face_to_face_id(component_mount_face_id)
        _, mount_axis, mount_direction = FACE_DEFINITIONS[install_face]
        requested_step_path = _requested_step_path(entry)
        step_path, step_size_bytes, step_fallback_reason = _resolve_step_path(
            requested_step_path,
            max_step_size_bytes=max_step_size_bytes,
        )
        color = _resolve_color(entry, geom_component)
        normalized_components[component_id] = {
            "id": component_id,
            "component_id": component_id,
            "category": _resolve_category(entry, geom_component),
            "color": color,
            "target_bbox": target_bbox,
            "target_size": bbox_size(target_bbox, f"components[{component_id!r}].target_bbox"),
            "placement": {
                "mount_face_id": mount_face_id,
                "component_mount_face_id": component_mount_face_id,
                "alignment": deepcopy(placement.get("alignment") or {}),
                "install_face": install_face,
                "component_local_face": component_local_face,
                "mount_axis": mount_axis,
                "mount_direction": mount_direction,
                "external": bool(is_external_face(install_face)),
            },
            "source": {
                "kind": "step" if step_path is not None else "box",
                "step_path": str(step_path) if step_path is not None else None,
                "requested_step_path": requested_step_path,
                "step_size_bytes": step_size_bytes,
                "fallback_reason": step_fallback_reason,
                "geom_component_info_path": str(Path(geom_component_info_path).resolve()),
            },
        }

    if not normalized_components:
        raise LayoutDatasetError(
            "geom_component_info.components must contain at least one component."
        )

    return {
        "schema_version": "geom_component_assembly/1.0",
        "source": {
            "layout_id": layout_topology.get("layout_id"),
            "source_design_id": layout_topology.get("source_design_id"),
            "topology_schema_version": layout_topology.get("schema_version"),
            "geom_schema_version": geom.get("schema_version"),
            "geom_component_info_schema_version": geom_component_info.get("schema_version"),
        },
        "envelope": {
            "outer_size": bbox_size(outer_shell.get("outer_bbox"), "geom.outer_shell.outer_bbox"),
            "inner_size": bbox_size(outer_shell.get("inner_bbox"), "geom.outer_shell.inner_bbox"),
            "shell_thickness": float(outer_shell.get("thickness") or 0.0),
        },
        "components": normalized_components,
    }


def _placements_by_component_id(layout_topology: dict[str, Any]) -> dict[str, dict[str, Any]]:
    placements = layout_topology.get("placements")
    if not isinstance(placements, list) or not placements:
        raise LayoutDatasetError("layout_topology.placements must be a non-empty array.")
    result: dict[str, dict[str, Any]] = {}
    for placement in placements:
        if not isinstance(placement, dict):
            raise LayoutDatasetError("Each placement must be a JSON object.")
        component_id = require_string(placement.get("component_id"), "placement.component_id")
        result[component_id] = placement
    return result


def _component_info_entries(geom_component_info: dict[str, Any]) -> list[dict[str, Any]]:
    components = geom_component_info.get("components")
    if isinstance(components, list):
        return [entry for entry in components if isinstance(entry, dict)]
    if isinstance(components, dict):
        return [
            {"component_id": key, **value}
            for key, value in components.items()
            if isinstance(key, str) and isinstance(value, dict)
        ]
    raise LayoutDatasetError("geom_component_info.components must be an array or object.")


def _resolve_geom_component(
    geom_components: dict[str, Any] | None,
    component_id: str,
) -> dict[str, Any] | None:
    if not isinstance(geom_components, dict):
        return None
    direct = geom_components.get(component_id)
    if isinstance(direct, dict):
        return direct
    matches = [
        value
        for value in geom_components.values()
        if isinstance(value, dict)
        and (value.get("component_id") == component_id or value.get("id") == component_id)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _resolve_target_bbox(
    entry: dict[str, Any],
    geom_component: dict[str, Any] | None,
    component_id: str,
) -> dict[str, list[float]]:
    bbox = entry.get("bbox")
    if isinstance(bbox, dict):
        return {
            "min": vector3(bbox.get("min"), f"geom_component_info[{component_id!r}].bbox.min"),
            "max": vector3(bbox.get("max"), f"geom_component_info[{component_id!r}].bbox.max"),
        }

    position = entry.get("position")
    dims = entry.get("dims", entry.get("size"))
    if position is not None and dims is not None:
        bbox_min = vector3(position, f"geom_component_info[{component_id!r}].position")
        bbox_dims = vector3(dims, f"geom_component_info[{component_id!r}].dims")
        return {
            "min": bbox_min,
            "max": [bbox_min[index] + bbox_dims[index] for index in range(3)],
        }

    if isinstance(geom_component, dict):
        bbox_min = geom_component.get("position")
        bbox_dims = geom_component.get("dims")
        if bbox_min is not None and bbox_dims is not None:
            parsed_min = vector3(bbox_min, f"geom.components[{component_id!r}].position")
            parsed_dims = vector3(bbox_dims, f"geom.components[{component_id!r}].dims")
            return {
                "min": parsed_min,
                "max": [parsed_min[index] + parsed_dims[index] for index in range(3)],
            }

    raise LayoutDatasetError(
        f"Component {component_id!r} requires bbox or position+dims in geom_component_info.json."
    )


def _resolve_category(entry: dict[str, Any], geom_component: dict[str, Any] | None) -> str | None:
    value = entry.get("category")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(geom_component, dict):
        fallback = geom_component.get("category")
        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip()
    return None


def _resolve_color(
    entry: dict[str, Any],
    geom_component: dict[str, Any] | None,
) -> list[int] | None:
    for candidate in (
        entry.get("color"),
        geom_component.get("color") if isinstance(geom_component, dict) else None,
    ):
        if isinstance(candidate, list) and 3 <= len(candidate) <= 4:
            return [int(value) for value in candidate]
    return None


def _requested_step_path(entry: dict[str, Any]) -> str | None:
    display_info = entry.get("display_info")
    assets = display_info.get("assets") if isinstance(display_info, dict) else None
    step_path = assets.get("cad_rotated_path") if isinstance(assets, dict) else None
    if not isinstance(step_path, str) or not step_path.strip():
        return None
    return step_path


def _step_size_limit_bytes(max_step_size_mb: float) -> int | None:
    if max_step_size_mb < 0:
        return None
    return int(max_step_size_mb * 1024 * 1024)


def _resolve_step_path(
    requested: str | None,
    *,
    max_step_size_bytes: int | None,
) -> tuple[Path | None, int | None, str | None]:
    if requested is None:
        return None, None, "missing_step_path"
    resolved = resolve_workspace_path(requested)
    if not resolved.exists():
        return None, None, "missing_file"
    if resolved.suffix.lower() not in {".step", ".stp"}:
        return None, None, "unsupported_extension"
    size_bytes = resolved.stat().st_size
    if max_step_size_bytes is not None and size_bytes > max_step_size_bytes:
        return None, size_bytes, "file_too_large"
    return resolved, size_bytes, None


__all__ = [
    "LayoutDatasetError",
    "load_and_normalize_component_info_assembly",
    "normalize_component_info_assembly",
]
