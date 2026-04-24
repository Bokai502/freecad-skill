#!/usr/bin/env python3
"""Replace a named component in a FreeCAD assembly STEP with an external STEP file."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.artifact_registry import (
    add_registry_args,
    artifact_entry,
    build_error_payload,
    finalize_registry_run,
    start_registry_run,
)
from freecad_cli_tools.cli_support import (
    execute_script_payload,
    exit_on_failure,
    normalize_runtime_path,
)
from freecad_cli_tools.layout_dataset import load_and_normalize_layout_dataset
from freecad_cli_tools.rpc_client import print_result as print_json
from freecad_cli_tools.rpc_script_loader import render_rpc_script
from freecad_cli_tools.runtime_config import (
    get_default_geom_path,
    get_default_geometry_after_step_path,
    get_default_layout_topology_path,
    get_default_workspace_dir,
    resolve_workspace_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replace a named component in a FreeCAD assembly with an external "
            "STEP file. The replacement is positioned from "
            "layout_topology.json + geom.json and the assembly STEP is "
            "exported to geometry_after.step, with a sibling GLB exported."
        )
    )
    parser.add_argument(
        "--layout-topology",
        help=(
            "Path to layout_topology.json for the layout dataset. "
            "Defaults to './01_layout/layout_topology.json' under the configured "
            "workspace root."
        ),
    )
    parser.add_argument(
        "--geom",
        help=(
            "Path to geom.json for the layout dataset. Defaults to "
            "'./01_layout/geom.json' under the configured workspace root."
        ),
    )
    parser.add_argument(
        "--assembly",
        required=True,
        help=(
            "Existing assembly STEP file to import before replacement. "
            "Relative paths resolve from the configured workspace root."
        ),
    )
    parser.add_argument(
        "--replacement",
        required=True,
        help=(
            "Replacement component STEP file. Relative paths resolve from the "
            "configured workspace root."
        ),
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Component id to replace (e.g. P022).",
    )
    parser.add_argument(
        "--thrust-axis",
        choices=("x", "y", "z"),
        help=(
            "Optional override for the replacement STEP native thrust axis when "
            "bbox-based auto-detection is ambiguous."
        ),
    )
    parser.add_argument(
        "--flange-sign",
        type=int,
        choices=(-1, 1),
        help=(
            "Optional override for which end of the replacement STEP native "
            "thrust axis is treated as the flange."
        ),
    )
    parser.add_argument(
        "--doc-name",
        default=None,
        help="FreeCAD document name. Defaults to the assembly file stem.",
    )
    parser.add_argument(
        "--no-fit-view",
        action="store_true",
        help="Skip GUI view fit after the replacement.",
    )
    add_connection_args(parser)
    add_registry_args(parser)
    return parser.parse_args()


def stage_runtime_input_path(doc_name: str) -> Path:
    """Return a stable workspace staging path for the normalized input payload."""
    safe_doc_name = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in doc_name
    ).strip("_") or "assembly"
    return (
        get_default_workspace_dir()
        / "assembly_builds"
        / safe_doc_name
        / "inputs"
        / "replace_component_layout_dataset.json"
    )


def stage_input_data(data: dict[str, object], target: Path) -> None:
    """Write normalized input data into the workspace staging directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in (target.parent, target.parent.parent, target.parent.parent.parent):
        if directory.exists():
            os.chmod(directory, 0o777)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")


def apply_component_overrides(
    normalized_data: dict[str, object],
    component_name: str,
    thrust_axis: str | None,
    flange_sign: int | None,
) -> None:
    """Attach replacement-orientation overrides to the selected component."""
    components = normalized_data.get("components")
    if not isinstance(components, dict):
        raise RuntimeError("Normalized layout dataset is missing components.")
    component = components.get(component_name)
    if not isinstance(component, dict):
        raise RuntimeError(
            f"Component '{component_name}' not found in normalized layout dataset."
        )
    if thrust_axis is None and flange_sign is None:
        return
    replacement = dict(component.get("replacement") or {})
    if thrust_axis is not None:
        replacement["thrust_axis"] = thrust_axis
    if flange_sign is not None:
        replacement["flange_sign"] = int(flange_sign)
    component["replacement"] = replacement


def registry_inputs(
    args: argparse.Namespace,
    layout_topology_path: Path,
    geom_path: Path,
    assembly_input_path: Path,
    step_output_path: Path,
    replacement_path: Path,
    doc_name: str,
) -> dict[str, object]:
    """Build the registry input payload for component replacement."""
    return {
        "layout_topology_path": str(layout_topology_path),
        "geom_path": str(geom_path),
        "assembly_input_path": str(assembly_input_path),
        "step_output_path": str(step_output_path),
        "glb_output_path": str(step_output_path.with_suffix(".glb")),
        "replacement_path": str(replacement_path),
        "component_name": args.name,
        "thrust_axis": args.thrust_axis,
        "flange_sign": args.flange_sign,
        "doc_name": doc_name,
        "rpc_host": args.host,
        "rpc_port": args.port,
        "fit_view": not args.no_fit_view,
        "input_format": "layout_dataset",
    }


def main() -> None:
    args = parse_args()
    layout_topology_path = resolve_workspace_path(
        args.layout_topology or get_default_layout_topology_path()
    )
    geom_path = resolve_workspace_path(args.geom or get_default_geom_path())
    assembly_input_path = resolve_workspace_path(args.assembly)
    step_output_path = get_default_geometry_after_step_path()
    replacement_path = resolve_workspace_path(args.replacement)
    doc_name = args.doc_name or assembly_input_path.stem
    staged_input_path = stage_runtime_input_path(doc_name)
    registry_run = start_registry_run(
        args,
        tool="freecad-replace-component",
        operation_type="replace_component",
        inputs=registry_inputs(
            args,
            layout_topology_path,
            geom_path,
            assembly_input_path,
            step_output_path,
            replacement_path,
            doc_name,
        ),
    )

    try:
        normalized_data = load_and_normalize_layout_dataset(
            layout_topology_path,
            geom_path,
        )
        apply_component_overrides(
            normalized_data,
            args.name,
            args.thrust_axis,
            args.flange_sign,
        )
        stage_input_data(normalized_data, staged_input_path)

        code = render_rpc_script(
            "replace_component.py",
            {
                "__INPUT_PATH__": json.dumps(normalize_runtime_path(staged_input_path)),
                "__ASSEMBLY_INPUT_PATH__": json.dumps(
                    normalize_runtime_path(assembly_input_path)
                ),
                "__EXPORT_PATH__": json.dumps(normalize_runtime_path(step_output_path)),
                "__REPLACEMENT_PATH__": json.dumps(
                    normalize_runtime_path(replacement_path)
                ),
                "__COMPONENT_NAME__": json.dumps(args.name),
                "__DOC_NAME__": json.dumps(doc_name),
                "__FIT_VIEW__": "False" if args.no_fit_view else "True",
            },
        )
        payload = execute_script_payload(args.host, args.port, code)
        step_path = payload.get("assembly_path")
        glb_path = payload.get("glb_path")
        step_exists = bool(step_path) and Path(step_path).exists()
        glb_exists = bool(glb_path) and Path(glb_path).exists()
        if payload.get("success") and step_exists and glb_exists:
            registry_status = "success"
            registry_error = None
        elif payload.get("success") and step_exists:
            registry_status = "partial_success"
            registry_error = build_error_payload(
                "GLB_EXPORT_INCOMPLETE",
                "Assembly STEP export succeeded but the expected GLB artifact was not found.",
                details=payload,
            )
        else:
            registry_status = "failed"
            registry_error = build_error_payload(
                "REPLACE_COMPONENT_FAILED",
                str(payload.get("error") or "FreeCAD replace-component command failed."),
                details=payload,
            )

        finalize_registry_run(
            registry_run,
            status=registry_status,
            outputs={
                "layout_topology_path": str(layout_topology_path),
                "geom_path": str(geom_path),
                "step_path": str(step_path) if step_path else None,
                "glb_path": str(glb_path) if glb_path else None,
            },
            result=payload,
            error=registry_error,
            artifacts=[
                artifact_entry("layout_topology", layout_topology_path),
                artifact_entry("geom", geom_path),
                artifact_entry("step", step_path),
                artifact_entry("glb", glb_path),
                artifact_entry("replacement_step", replacement_path),
            ],
        )
    except Exception as exc:
        finalize_registry_run(
            registry_run,
            status="failed",
            outputs={
                "layout_topology_path": str(layout_topology_path),
                "geom_path": str(geom_path),
            },
            result={"success": False},
            error=build_error_payload("REPLACE_COMPONENT_EXCEPTION", str(exc)),
            artifacts=[
                artifact_entry("layout_topology", layout_topology_path),
                artifact_entry("geom", geom_path),
                artifact_entry("step", step_output_path),
                artifact_entry("glb", step_output_path.with_suffix(".glb")),
                artifact_entry("replacement_step", replacement_path),
            ],
        )
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print_json(payload)
    exit_on_failure(payload)


if __name__ == "__main__":
    main()
