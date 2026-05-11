#!/usr/bin/env python3
"""Build a FreeCAD placeholder assembly document from layout_topology.json + geom.json."""

from __future__ import annotations

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
from freecad_cli_tools.progress import (
    ProgressLogWriter,
    attach_progress_log_path,
    attach_progress_percentages,
    get_progress_log_path,
)
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
from freecad_cli_tools.workspace import add_workspace_arg, validate_workspace_inputs, validate_workspace_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Create a FreeCAD placeholder assembly from layout_topology.json + geom.json.")
    )
    parser.add_argument("--layout-topology", help="Path to layout_topology.json.")
    parser.add_argument("--geom", help="Path to geom.json.")
    add_workspace_arg(parser)
    parser.add_argument("--doc-name", required=True, help="Name of the FreeCAD document to create.")
    parser.add_argument(
        "--output",
        help=(
            "Optional output STEP path or directory. Exported filenames are always "
            "'geometry_after.step' and 'geometry_after.glb'."
        ),
    )
    parser.add_argument("--view", default="Isometric", help="Preferred GUI view after creation.")
    parser.add_argument("--no-fit-view", action="store_true", help="Skip GUI fit/view adjustment.")
    add_connection_args(parser)
    add_registry_args(parser)
    return parser.parse_args()


def stage_runtime_paths(input_path: Path, output_path: Path, doc_name: str) -> tuple[Path, Path]:
    safe_doc_name = (
        "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in doc_name).strip("_")
        or "assembly"
    )
    root = get_default_workspace_dir() / "assembly_builds" / safe_doc_name
    return root / "inputs" / input_path.name, root / "outputs" / output_path.name


def stage_input_data(data: dict[str, object], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in (target.parent, target.parent.parent, target.parent.parent.parent):
        if directory.exists():
            try:
                os.chmod(directory, 0o777)
            except PermissionError:
                pass
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")


def stage_output_dir(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in (target.parent, target.parent.parent, target.parent.parent.parent):
        if directory.exists():
            try:
                os.chmod(directory, 0o777)
            except PermissionError:
                pass


def copy_runtime_export(staged_output: Path, final_output: Path) -> None:
    if staged_output.resolve() == final_output.resolve():
        return
    final_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(staged_output, final_output)


def collect_runtime_exports(staged_output: Path, final_output: Path) -> None:
    copy_runtime_export(staged_output, final_output)
    staged_glb = staged_output.with_suffix(".glb")
    if staged_glb.exists():
        final_glb = final_output.with_suffix(".glb")
        copy_runtime_export(staged_glb, final_glb)


def registry_inputs(
    *,
    args: argparse.Namespace,
    layout_topology_path: Path,
    geom_path: Path,
    output_path: Path,
) -> dict[str, object]:
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


def main() -> None:
    args = parse_args()
    validate_workspace_root(args.workspace)
    validate_workspace_inputs(
        args.workspace,
        require_layout_topology=args.layout_topology is None,
        require_geom=args.geom is None,
    )
    layout_topology_path = resolve_workspace_path(
        args.layout_topology or get_default_layout_topology_path()
    )
    geom_path = resolve_workspace_path(args.geom or get_default_geom_path())
    output_path = resolve_geometry_after_step_path(args.output)
    staged_input_name = Path("normalized_layout_dataset.json")
    staged_input_path, staged_output_path = stage_runtime_paths(
        staged_input_name,
        output_path,
        args.doc_name,
    )
    output_paths = {
        "step": output_path,
        "glb": output_path.with_suffix(".glb"),
    }
    progress_log_path = get_progress_log_path()
    progress_writer = ProgressLogWriter(
        tool="freecad-create-assembly",
        progress={
            "layout_completion_percent": 0.0,
            "modeling_percent": 0.0,
            "export_file_percent": 0.0,
        },
        output_paths=output_paths,
    ).start()

    registry_run = start_registry_run(
        args,
        tool="freecad-create-assembly",
        operation_type="create_assembly",
        inputs=registry_inputs(
            args=args,
            layout_topology_path=layout_topology_path,
            geom_path=geom_path,
            output_path=output_path,
        ),
    )

    try:
        normalized_data = load_and_normalize_layout_dataset(
            layout_topology_path,
            geom_path,
        )
        stage_input_data(normalized_data, staged_input_path)
        stage_output_dir(staged_output_path)
        progress_writer.update(
            progress={
                "layout_completion_percent": 100.0,
                "modeling_percent": 0.0,
                "export_file_percent": 0.0,
            }
        )

        code = render_rpc_script(
            "assembly_from_layout.py",
            {
                "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
                "__COMPONENT_SHAPE_HELPERS__": COMPONENT_SHAPE_HELPERS,
                "__INPUT_PATH__": json.dumps(normalize_runtime_path(staged_input_path)),
                "__DOC_NAME__": json.dumps(args.doc_name),
                "__SAVE_PATH__": json.dumps(normalize_runtime_path(staged_output_path)),
                "__EXPORT_GLB__": "True",
                "__FIT_VIEW__": "False" if args.no_fit_view else "True",
                "__VIEW_NAME__": json.dumps(args.view),
                "__PROGRESS_PATH__": json.dumps(normalize_runtime_path(progress_log_path)),
                "__PROGRESS_TOOL__": json.dumps("freecad-create-assembly"),
                "__PROGRESS_OUTPUT_FILES__": json.dumps(
                    {
                        name: str(path) if path is not None else None
                        for name, path in output_paths.items()
                    }
                ),
            },
        )
        payload = execute_script_payload(args.host, args.port, code)
        if payload.get("success"):
            collect_runtime_exports(staged_output_path, output_path)
            payload["save_path"] = str(output_path)
            final_glb = output_path.with_suffix(".glb")
            payload["glb_path"] = str(final_glb) if final_glb.exists() else None

        step_path = payload.get("save_path")
        glb_path = payload.get("glb_path")
        step_exists = bool(step_path) and Path(step_path).exists()
        glb_exists = bool(glb_path) and Path(glb_path).exists()
        progress = attach_progress_percentages(
            payload,
            layout_complete=True,
            modeling_requested=True,
            modeling_complete=bool(payload.get("success")),
            step_path=step_path,
            glb_path=glb_path,
            export_requested=True,
        )
        progress_log_path = progress_writer.update(
            progress=progress,
            success=bool(payload.get("success")),
        )
        attach_progress_log_path(payload, progress_log_path)
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
            ],
        )
        print_json(payload)
        exit_on_failure(payload)
    except Exception as exc:
        progress_writer.update(
            progress={
                "layout_completion_percent": 0.0,
                "modeling_percent": 0.0,
                "export_file_percent": 0.0,
            },
            success=False,
        )
        finalize_registry_run(
            registry_run,
            status="failed",
            outputs={
                "layout_topology_path": str(layout_topology_path),
                "geom_path": str(geom_path),
                "step_path": str(output_path),
                "glb_path": str(output_path.with_suffix(".glb")),
            },
            result={"success": False},
            error=build_error_payload("ASSEMBLY_BUILD_EXCEPTION", str(exc)),
            artifacts=[
                artifact_entry("layout_topology", layout_topology_path),
                artifact_entry("geom", geom_path),
                artifact_entry("step", output_path),
                artifact_entry("glb", output_path.with_suffix(".glb")),
            ],
        )
        raise


if __name__ == "__main__":
    main()
