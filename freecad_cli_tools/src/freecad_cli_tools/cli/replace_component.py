#!/usr/bin/env python3
"""Replace a named component in a FreeCAD assembly STEP with an external STEP file."""

import argparse
import json
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
from freecad_cli_tools.rpc_script_loader import render_rpc_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replace a named component in a FreeCAD assembly with an external "
            "STEP file. The replacement is centered on the original component's "
            "bounding-box center (taken from the YAML position + dims) and the "
            "assembly STEP is overwritten in place, with a sibling GLB exported."
        )
    )
    parser.add_argument("--yaml", required=True, help="Source YAML layout file.")
    parser.add_argument(
        "--assembly",
        required=True,
        help="Existing assembly STEP file (overwritten in place, plus sibling .glb).",
    )
    parser.add_argument(
        "--replacement",
        required=True,
        help="Replacement component STEP file.",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Component id to replace (e.g. P022).",
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


def registry_inputs(
    args: argparse.Namespace,
    yaml_path: Path,
    assembly_path: Path,
    replacement_path: Path,
    doc_name: str,
) -> dict[str, object]:
    """Build the registry input payload for component replacement."""
    return {
        "yaml_path": str(yaml_path),
        "assembly_path": str(assembly_path),
        "replacement_path": str(replacement_path),
        "component_name": args.name,
        "doc_name": doc_name,
        "rpc_host": args.host,
        "rpc_port": args.port,
        "fit_view": not args.no_fit_view,
    }


def main() -> None:
    args = parse_args()
    assembly_path = Path(args.assembly)
    yaml_path = Path(args.yaml)
    replacement_path = Path(args.replacement)
    doc_name = args.doc_name or assembly_path.stem
    registry_run = start_registry_run(
        args,
        tool="freecad-replace-component",
        operation_type="replace_component",
        inputs=registry_inputs(
            args,
            yaml_path,
            assembly_path,
            replacement_path,
            doc_name,
        ),
    )

    try:
        code = render_rpc_script(
            "replace_component.py",
            {
                "__YAML_PATH__": json.dumps(normalize_runtime_path(yaml_path)),
                "__ASSEMBLY_PATH__": json.dumps(normalize_runtime_path(assembly_path)),
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
                "Assembly overwrite succeeded but the expected GLB artifact was not found.",
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
                "yaml_path": str(yaml_path),
                "step_path": str(step_path) if step_path else None,
                "glb_path": str(glb_path) if glb_path else None,
            },
            result=payload,
            error=registry_error,
            artifacts=[
                artifact_entry("yaml", yaml_path),
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
                "yaml_path": str(yaml_path),
            },
            result={"success": False},
            error=build_error_payload("REPLACE_COMPONENT_EXCEPTION", str(exc)),
            artifacts=[
                artifact_entry("yaml", yaml_path),
                artifact_entry("step", assembly_path),
                artifact_entry("glb", assembly_path.with_suffix(".glb")),
                artifact_entry("replacement_step", replacement_path),
            ],
        )
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print_json(payload)
    exit_on_failure(payload)


if __name__ == "__main__":
    main()
