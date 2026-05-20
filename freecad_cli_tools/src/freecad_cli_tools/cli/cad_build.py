#!/usr/bin/env python3
"""Build 01_cad artifacts from 00_inputs real_bom + layout_topology + geom."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.artifact_registry import (
    add_registry_args,
    artifact_entry,
    build_error_payload,
    finalize_registry_run,
    start_registry_run,
)
from freecad_cli_tools.cad_inputs import build_cad_stage_inputs
from freecad_cli_tools.cli_support import execute_script_payload, exit_on_failure, normalize_runtime_path
from freecad_cli_tools.progress import (
    ProgressLogWriter,
    attach_progress_log_path,
    attach_progress_percentages,
    get_progress_log_path,
)
from freecad_cli_tools.rpc_client import print_result as print_json
from freecad_cli_tools.rpc_script_fragments import COMPONENT_SHAPE_HELPERS, PLACEMENT_HELPERS
from freecad_cli_tools.rpc_script_loader import render_rpc_script
from freecad_cli_tools.runtime_config import resolve_workspace_path
from freecad_cli_tools.workspace import add_workspace_arg, validate_workspace_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build CAD-stage artifacts from 00_inputs/real_bom.json, "
            "00_inputs/layout_topology.json, and 00_inputs/geom.json."
        )
    )
    add_workspace_arg(parser)
    parser.add_argument(
        "--input-dir",
        default="00_inputs",
        help="Input directory under the workspace. Default: 00_inputs.",
    )
    parser.add_argument(
        "--output-dir",
        default="01_cad",
        help="Output directory under the workspace. Default: 01_cad.",
    )
    parser.add_argument("--real-bom", help="Optional explicit real_bom.json path.")
    parser.add_argument("--layout-topology", help="Optional explicit layout_topology.json path.")
    parser.add_argument("--geom", help="Optional explicit geom.json path.")
    parser.add_argument("--doc-name", default="LayoutAssembly", help="FreeCAD document name.")
    parser.add_argument("--view", default="Isometric", help="Preferred GUI view after creation.")
    parser.add_argument("--no-fit-view", action="store_true", help="Skip GUI fit/view adjustment.")
    parser.add_argument(
        "--grid-shape",
        nargs=3,
        type=int,
        metavar=("NX", "NY", "NZ"),
        default=(32, 32, 32),
        help=(
            "Grid shape used for comsol_inputs/coord.txt and "
            "comsol_inputs/channels_input.npz. Default: 32 32 32."
        ),
    )
    add_connection_args(parser)
    add_registry_args(parser)
    return parser.parse_args()


def _input_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    input_dir = resolve_workspace_path(args.input_dir)
    real_bom = resolve_workspace_path(args.real_bom) if args.real_bom else input_dir / "real_bom.json"
    layout_topology = (
        resolve_workspace_path(args.layout_topology)
        if args.layout_topology
        else input_dir / "layout_topology.json"
    )
    geom = resolve_workspace_path(args.geom) if args.geom else input_dir / "geom.json"
    return real_bom, layout_topology, geom


def _registry_inputs(
    args: argparse.Namespace,
    *,
    real_bom_path: Path,
    layout_topology_path: Path,
    geom_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    return {
        "input_format": "real_bom_layout_topology_geom",
        "real_bom_path": str(real_bom_path),
        "layout_topology_path": str(layout_topology_path),
        "geom_path": str(geom_path),
        "output_dir": str(output_dir),
        "doc_name": args.doc_name,
        "rpc_host": args.host,
        "rpc_port": args.port,
        "view": args.view,
        "fit_view": not args.no_fit_view,
        "grid_shape": [int(value) for value in args.grid_shape],
    }


def main() -> None:
    args = parse_args()
    validate_workspace_root(args.workspace)
    real_bom_path, layout_topology_path, geom_path = _input_paths(args)
    for path in (real_bom_path, layout_topology_path, geom_path):
        if not path.exists():
            raise FileNotFoundError(f"required input file not found: {path}")

    output_dir = resolve_workspace_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    step_path = output_dir / "geometry_after.step"
    glb_path = output_dir / "geometry_after.glb"

    output_paths = {
        "step": step_path,
        "glb": glb_path,
        "geometry_after_layout_topology": output_dir / "geometry_after.layout_topology.json",
        "geometry_after_geom": output_dir / "geometry_after.geom.json",
        "geometry_after_registry": output_dir / "geometry_after_registry.json",
        "normalized_layout_dataset": output_dir / "normalized_layout_dataset.json",
        "simulation_input": output_dir / "simulation_input.json",
        "cad_agent_output": output_dir / "cad_agent_output.json",
        "comsol_coord": output_dir / "comsol_inputs" / "coord.txt",
        "comsol_channels_input": output_dir / "comsol_inputs" / "channels_input.npz",
    }
    progress_writer = ProgressLogWriter(
        tool="freecad-tools cad build",
        workflow="create_cad",
        command="cad build",
        stage="cad_build",
        progress={
            "layout_completion_percent": 0.0,
            "modeling_percent": 0.0,
            "export_file_percent": 0.0,
            "validation_percent": 0.0,
        },
        output_paths=output_paths,
    ).start()

    registry_run = start_registry_run(
        args,
        tool="freecad-tools cad build",
        operation_type="cad_build_from_inputs",
        inputs=_registry_inputs(
            args,
            real_bom_path=real_bom_path,
            layout_topology_path=layout_topology_path,
            geom_path=geom_path,
            output_dir=output_dir,
        ),
    )

    try:
        prepared = build_cad_stage_inputs(
            real_bom_path=real_bom_path,
            layout_topology_path=layout_topology_path,
            geom_path=geom_path,
            output_dir=output_dir,
            step_filename=step_path.name,
            grid_shape=tuple(int(value) for value in args.grid_shape),
        )
        progress_writer.update(
            progress={
                "layout_completion_percent": 100.0,
                "modeling_percent": 0.0,
                "export_file_percent": 0.0,
                "validation_percent": 0.0,
            }
        )

        normalized_input_path = output_dir / "normalized_layout_dataset.json"
        normalized_input_path.write_text(
            json.dumps(prepared["normalized"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        progress_log_path = get_progress_log_path()
        code = render_rpc_script(
            "assembly_from_layout.py",
            {
                "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
                "__COMPONENT_SHAPE_HELPERS__": COMPONENT_SHAPE_HELPERS,
                "__INPUT_PATH__": json.dumps(normalize_runtime_path(normalized_input_path)),
                "__DOC_NAME__": json.dumps(args.doc_name),
                "__SAVE_PATH__": json.dumps(normalize_runtime_path(step_path)),
                "__EXPORT_GLB__": "True",
                "__FIT_VIEW__": "False" if args.no_fit_view else "True",
                "__VIEW_NAME__": json.dumps(args.view),
                "__PROGRESS_PATH__": json.dumps(normalize_runtime_path(progress_log_path)),
                "__PROGRESS_TOOL__": json.dumps("freecad-tools cad build"),
                "__PROGRESS_OUTPUT_FILES__": json.dumps(
                    {name: str(path) for name, path in output_paths.items()}
                ),
            },
        )
        payload = execute_script_payload(args.host, args.port, code)
        if payload.get("success"):
            payload["save_path"] = str(step_path)
            payload["glb_path"] = str(glb_path) if glb_path.exists() else None

        step_exists = step_path.exists()
        glb_exists = glb_path.exists()
        progress = attach_progress_percentages(
            payload,
            layout_complete=True,
            modeling_requested=True,
            modeling_complete=bool(payload.get("success")),
            step_path=step_path,
            glb_path=glb_path,
            export_requested=True,
        )
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
                "CAD_BUILD_FAILED",
                str(payload.get("error") or "FreeCAD CAD build failed."),
                details=payload,
            )

        progress_log_path = progress_writer.update(
            progress=progress,
            success=bool(payload.get("success")) and step_exists and glb_exists,
            status=registry_status,
            error=registry_error,
        )
        attach_progress_log_path(payload, progress_log_path)
        payload.update(
            {
                "input_format": "real_bom_layout_topology_geom",
                "output_dir": str(output_dir),
                "simulation_input_path": str(output_paths["simulation_input"]),
                "cad_agent_output_path": str(output_paths["cad_agent_output"]),
                "comsol_coord_path": str(output_paths["comsol_coord"]),
                "comsol_channels_input_path": str(output_paths["comsol_channels_input"]),
                "geometry_after_registry_path": str(output_dir / "geometry_after_registry.json"),
                "geometry_after_geom_path": str(output_dir / "geometry_after.geom.json"),
                "geometry_after_layout_topology_path": str(
                    output_dir / "geometry_after.layout_topology.json"
                ),
                "cad_agent_output": prepared["cad_agent_output"],
            }
        )

        finalize_registry_run(
            registry_run,
            status=registry_status,
            outputs={name: str(path) for name, path in output_paths.items()},
            result=payload,
            error=registry_error,
            artifacts=[
                artifact_entry("real_bom", real_bom_path),
                artifact_entry("layout_topology", layout_topology_path),
                artifact_entry("geom", geom_path),
                artifact_entry("step", step_path),
                artifact_entry("glb", glb_path),
                artifact_entry("simulation_input", output_paths["simulation_input"]),
                artifact_entry("cad_agent_output", output_paths["cad_agent_output"]),
                artifact_entry("comsol_coord", output_paths["comsol_coord"]),
                artifact_entry("comsol_channels_input", output_paths["comsol_channels_input"]),
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
                "validation_percent": 0.0,
            },
            success=False,
            status="failed",
            error={
                "code": "CAD_BUILD_EXCEPTION",
                "message": str(exc),
            },
        )
        finalize_registry_run(
            registry_run,
            status="failed",
            outputs={name: str(path) for name, path in output_paths.items()},
            result={"success": False},
            error=build_error_payload("CAD_BUILD_EXCEPTION", str(exc)),
            artifacts=[artifact_entry(name, path) for name, path in output_paths.items()],
        )
        raise


if __name__ == "__main__":
    main()
