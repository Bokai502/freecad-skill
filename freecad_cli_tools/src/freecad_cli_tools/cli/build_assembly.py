#!/usr/bin/env python3
"""Build a FreeCAD assembly document from layout_topology.json + geom.json."""

import argparse
import json
import os
import shutil
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
from freecad_cli_tools.rpc_script_fragments import (
    COMPONENT_SHAPE_HELPERS,
    PLACEMENT_HELPERS,
)
from freecad_cli_tools.rpc_script_loader import render_rpc_script
from freecad_cli_tools.runtime_config import (
    get_default_geom_path,
    get_default_layout_topology_path,
    get_default_workspace_dir,
    resolve_geometry_after_step_path,
    resolve_workspace_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a FreeCAD assembly document from "
            "layout_topology.json + geom.json."
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
        "--doc-name", required=True, help="Name of the FreeCAD document to create."
    )
    parser.add_argument(
        "--output",
        help=(
            "Optional output STEP path or directory. The exported STEP/GLB "
            "filenames are always 'geometry_after.step' and "
            "'geometry_after.glb'. Defaults to './02_geometry_edit' under the "
            "configured workspace root."
        ),
    )
    parser.add_argument(
        "--view",
        default="Isometric",
        help="Preferred GUI view after creation. Currently uses an isometric fit workflow.",
    )
    parser.add_argument(
        "--no-fit-view",
        action="store_true",
        help="Skip automatic GUI view adjustment after generation.",
    )
    add_connection_args(parser)
    add_registry_args(parser)
    return parser.parse_args()


def stage_runtime_paths(
    input_path: Path, output_path: Path, doc_name: str
) -> tuple[Path, Path]:
    """Create stable per-document staging paths under the configured workspace."""
    safe_doc_name = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in doc_name
    ).strip("_") or "assembly"
    root = get_default_workspace_dir() / "assembly_builds" / safe_doc_name
    return root / "inputs" / input_path.name, root / "outputs" / output_path.name


def stage_input_data(data: dict[str, object], target: Path) -> None:
    """Write normalized input data into the workspace staging directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in (target.parent, target.parent.parent, target.parent.parent.parent):
        if directory.exists():
            os.chmod(directory, 0o777)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")


def stage_output_dir(target: Path) -> None:
    """Prepare the FreeCAD-side export directory before RPC execution."""
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in (target.parent, target.parent.parent, target.parent.parent.parent):
        if directory.exists():
            os.chmod(directory, 0o777)


def collect_runtime_exports(staged_output: Path, final_output: Path) -> None:
    """Copy FreeCAD-generated export artifacts back to the requested destination."""
    final_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged_output, final_output)

    staged_glb = staged_output.with_suffix(".glb")
    if staged_glb.exists():
        final_glb = final_output.with_suffix(".glb")
        final_glb.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_glb, final_glb)


def registry_inputs(
    layout_topology_path: Path,
    geom_path: Path,
    output_path: Path,
    args: argparse.Namespace,
) -> dict[str, object]:
    """Build the registry input payload for assembly creation."""
    return {
        "doc_name": args.doc_name,
        "output_path": str(output_path),
        "rpc_host": args.host,
        "rpc_port": args.port,
        "view": args.view,
        "fit_view": not args.no_fit_view,
        "layout_topology_path": str(layout_topology_path),
        "geom_path": str(geom_path),
        "input_format": "layout_dataset",
    }


def registry_output_paths(
    layout_topology_path: Path,
    geom_path: Path,
    step_path: str | None,
    glb_path: str | None,
) -> dict[str, object]:
    """Build registry output paths for the selected source mode."""
    return {
        "step_path": str(step_path) if step_path else None,
        "glb_path": str(glb_path) if glb_path else None,
        "layout_topology_path": str(layout_topology_path),
        "geom_path": str(geom_path),
    }


def source_artifacts(layout_topology_path: Path, geom_path: Path) -> list[dict[str, object]]:
    """Return artifact registry entries for the layout dataset."""
    return [
        artifact_entry("layout_topology", layout_topology_path),
        artifact_entry("geom", geom_path),
    ]


def main() -> None:
    args = parse_args()
    layout_topology_path = resolve_workspace_path(
        args.layout_topology or get_default_layout_topology_path()
    )
    geom_path = resolve_workspace_path(args.geom or get_default_geom_path())
    output_path = resolve_geometry_after_step_path(args.output)
    staged_input_name = Path("normalized_layout_dataset.json")
    staged_input_path, staged_output_path = stage_runtime_paths(
        staged_input_name, output_path, args.doc_name
    )
    registry_run = start_registry_run(
        args,
        tool="freecad-create-assembly",
        operation_type="create_assembly",
        inputs=registry_inputs(layout_topology_path, geom_path, output_path, args),
    )

    try:
        normalized_data = load_and_normalize_layout_dataset(
            layout_topology_path,
            geom_path,
        )
        stage_input_data(normalized_data, staged_input_path)
        stage_output_dir(staged_output_path)

        code = render_rpc_script(
            "assembly_from_layout.py",
            {
                "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
                "__COMPONENT_SHAPE_HELPERS__": COMPONENT_SHAPE_HELPERS,
                "__INPUT_PATH__": json.dumps(normalize_runtime_path(staged_input_path)),
                "__DOC_NAME__": json.dumps(args.doc_name),
                "__SAVE_PATH__": json.dumps(normalize_runtime_path(staged_output_path)),
                "__FIT_VIEW__": "False" if args.no_fit_view else "True",
                "__VIEW_NAME__": json.dumps(args.view),
            },
        )
        payload = execute_script_payload(args.host, args.port, code)
        if payload.get("success"):
            collect_runtime_exports(staged_output_path, output_path)
            payload["save_path"] = str(output_path)
            payload["glb_path"] = str(output_path.with_suffix(".glb"))

        step_path = payload.get("save_path")
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
                "STEP export succeeded but the expected GLB artifact was not found.",
                details=payload,
            )
        else:
            registry_status = "failed"
            registry_error = build_error_payload(
                "ASSEMBLY_BUILD_FAILED",
                str(payload.get("error") or "FreeCAD assembly build failed."),
                details=payload,
            )

        finalize_registry_run(
            registry_run,
            status=registry_status,
            outputs=registry_output_paths(layout_topology_path, geom_path, step_path, glb_path),
            result=payload,
            error=registry_error,
            artifacts=source_artifacts(layout_topology_path, geom_path)
            + [
                artifact_entry("step", step_path),
                artifact_entry("glb", glb_path),
            ],
        )
        print_json(payload)
        exit_on_failure(payload)
    except Exception as exc:
        finalize_registry_run(
            registry_run,
            status="failed",
            outputs=registry_output_paths(
                layout_topology_path,
                geom_path,
                output_path,
                output_path.with_suffix(".glb"),
            ),
            result={"success": False},
            error=build_error_payload("ASSEMBLY_BUILD_EXCEPTION", str(exc)),
            artifacts=source_artifacts(layout_topology_path, geom_path)
            + [
                artifact_entry("step", output_path),
                artifact_entry("glb", output_path.with_suffix(".glb")),
            ],
        )
        raise


if __name__ == "__main__":
    main()
