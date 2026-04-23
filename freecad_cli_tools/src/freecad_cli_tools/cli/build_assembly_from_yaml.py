#!/usr/bin/env python3
"""Build a FreeCAD assembly document from a YAML layout."""

import argparse
import json
import os
import shutil
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
from freecad_cli_tools.rpc_client import print_result as print_json
from freecad_cli_tools.rpc_script_fragments import (
    COMPONENT_SHAPE_HELPERS,
    PLACEMENT_HELPERS,
)
from freecad_cli_tools.rpc_script_loader import render_rpc_script
from freecad_cli_tools.runtime_config import get_default_runtime_data_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a FreeCAD assembly document from a YAML layout."
    )
    parser.add_argument("--input", required=True, help="Path to the source YAML file.")
    parser.add_argument(
        "--doc-name", required=True, help="Name of the FreeCAD document to create."
    )
    parser.add_argument(
        "--output",
        help=(
            "Optional output STEP path. Defaults to '<doc-name>.step' beside the "
            "YAML file, and also writes a sibling '<doc-name>.glb'."
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


def runtime_data_dir() -> Path:
    """Return a shell/FreeCAD shared directory for temporary file exchange."""
    return get_default_runtime_data_dir()


def stage_runtime_paths(input_path: Path, output_path: Path, doc_name: str) -> tuple[Path, Path]:
    """Create stable per-document runtime paths visible to the FreeCAD process."""
    safe_doc_name = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in doc_name
    ).strip("_") or "assembly"
    root = runtime_data_dir() / "assembly_builds" / safe_doc_name
    return root / "inputs" / input_path.name, root / "outputs" / output_path.name


def stage_input_file(source: Path, target: Path) -> None:
    """Copy an input file into the shared runtime directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    # FreeCAD may run under a different local user than the CLI. Make the
    # staged exchange directories writable by both sides before RPC execution.
    for directory in (target.parent, target.parent.parent, target.parent.parent.parent):
        if directory.exists():
            os.chmod(directory, 0o777)
    shutil.copy2(source, target)


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
    input_path: Path,
    output_path: Path,
    args: argparse.Namespace,
) -> dict[str, object]:
    """Build the registry input payload for assembly creation."""
    return {
        "yaml_path": str(input_path),
        "doc_name": args.doc_name,
        "output_path": str(output_path),
        "rpc_host": args.host,
        "rpc_port": args.port,
        "view": args.view,
        "fit_view": not args.no_fit_view,
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{args.doc_name}.step")
    )
    staged_input_path, staged_output_path = stage_runtime_paths(
        input_path, output_path, args.doc_name
    )
    registry_run = start_registry_run(
        args,
        tool="freecad-create-assembly",
        operation_type="create_assembly",
        inputs=registry_inputs(input_path, output_path, args),
    )

    try:
        stage_input_file(input_path, staged_input_path)
        stage_output_dir(staged_output_path)

        code = render_rpc_script(
            "assembly_from_yaml.py",
            {
                "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
                "__COMPONENT_SHAPE_HELPERS__": COMPONENT_SHAPE_HELPERS,
                "__YAML_PATH__": json.dumps(normalize_runtime_path(staged_input_path)),
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
            outputs={
                "yaml_path": str(input_path),
                "step_path": str(step_path) if step_path else None,
                "glb_path": str(glb_path) if glb_path else None,
            },
            result=payload,
            error=registry_error,
            artifacts=[
                artifact_entry("yaml", input_path),
                artifact_entry("step", step_path),
                artifact_entry("glb", glb_path),
            ],
        )
    except Exception as exc:
        finalize_registry_run(
            registry_run,
            status="failed",
            outputs={
                "yaml_path": str(input_path),
            },
            result={"success": False},
            error=build_error_payload("ASSEMBLY_BUILD_EXCEPTION", str(exc)),
            artifacts=[
                artifact_entry("yaml", input_path),
                artifact_entry("step", output_path),
                artifact_entry("glb", output_path.with_suffix(".glb")),
            ],
        )
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print_json(payload)
    exit_on_failure(payload)


if __name__ == "__main__":
    main()
