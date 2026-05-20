#!/usr/bin/env python3
"""Validate CAD-stage artifacts and write results into cad_agent_output.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from freecad_cli_tools.cad_validation import validate_cad_build
from freecad_cli_tools.cli_support import execute_script_payload, normalize_runtime_path
from freecad_cli_tools.progress import (
    ProgressLogWriter,
    attach_progress_log_path,
    infer_validation_workflow,
)
from freecad_cli_tools.rpc_client import print_result as print_json
from freecad_cli_tools.rpc_script_loader import render_rpc_script
from freecad_cli_tools.runtime_config import resolve_workspace_path
from freecad_cli_tools.workspace import add_workspace_arg, validate_workspace_root


SIX_FACE_VIEWS = ("top", "bottom", "front", "back", "left", "right")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate 01_cad outputs against 00_inputs and merge the report into "
            "01_cad/cad_agent_output.json."
        )
    )
    add_workspace_arg(parser)
    parser.add_argument("--input-dir", default="00_inputs", help="Input directory.")
    parser.add_argument("--cad-dir", default="01_cad", help="CAD output directory.")
    parser.add_argument("--real-bom", help="Optional explicit real_bom.json path.")
    parser.add_argument("--layout-topology", help="Optional explicit layout_topology.json path.")
    parser.add_argument("--geom", help="Optional explicit geom.json path.")
    parser.add_argument(
        "--tolerance-mm",
        type=float,
        default=1e-3,
        help="Geometry tolerance in mm. Default: 1e-3.",
    )
    parser.add_argument(
        "--max-occupancy-ratio",
        type=float,
        default=1.0,
        help="Maximum allowed summed face occupancy ratio. Default: 1.0.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when validation fails.",
    )
    parser.add_argument("--doc-name", default="LayoutAssembly", help="FreeCAD document name.")
    parser.add_argument(
        "--screenshot",
        default="freecad_screenshot.png",
        help=(
            "Screenshot filename, directory, or path prefix. Six face screenshots are "
            "written by appending _top/_bottom/_front/_back/_left/_right before the suffix."
        ),
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="Skip FreeCAD screenshot capture.",
    )
    parser.add_argument("--screenshot-width", type=int, default=1600)
    parser.add_argument("--screenshot-height", type=int, default=1000)
    parser.add_argument("--host", default=None, help="FreeCAD RPC host.")
    parser.add_argument("--port", type=int, default=None, help="FreeCAD RPC port.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_workspace_root(args.workspace)
    input_dir = resolve_workspace_path(args.input_dir)
    cad_dir = resolve_workspace_path(args.cad_dir)
    real_bom_path = resolve_workspace_path(args.real_bom) if args.real_bom else input_dir / "real_bom.json"
    layout_topology_path = (
        resolve_workspace_path(args.layout_topology)
        if args.layout_topology
        else input_dir / "layout_topology.json"
    )
    geom_path = resolve_workspace_path(args.geom) if args.geom else input_dir / "geom.json"
    screenshot_paths = (
        _resolve_six_face_screenshot_paths(args.screenshot, cad_dir)
        if not args.no_screenshot
        else {}
    )
    output_paths = _validation_output_paths(cad_dir, screenshot_paths)
    step_path = output_paths["step"]
    glb_path = output_paths["glb"]
    workflow = infer_validation_workflow()
    progress_writer = ProgressLogWriter(
        tool="freecad-tools cad validate",
        workflow=workflow,
        command="cad validate",
        stage="cad_validate",
        progress={
            "layout_completion_percent": 0.0,
            "modeling_percent": 0.0,
            "export_file_percent": 0.0,
            "validation_percent": 0.0,
        },
        output_paths=output_paths,
    ).start()
    screenshot_result = None
    try:
        if not args.no_screenshot:
            screenshot_result = capture_six_face_screenshots(
                doc_name=args.doc_name,
                output_paths=screenshot_paths,
                width=args.screenshot_width,
                height=args.screenshot_height,
                host=args.host,
                port=args.port,
            )
            progress_writer.update(
                progress={
                    "layout_completion_percent": 100.0,
                    "modeling_percent": 100.0 if step_path.exists() else 0.0,
                    "export_file_percent": _existing_export_percent(step_path, glb_path),
                    "validation_percent": 50.0,
                }
            )
        report = validate_cad_build(
            real_bom_path=real_bom_path,
            layout_topology_path=layout_topology_path,
            geom_path=geom_path,
            cad_dir=cad_dir,
            tolerance_mm=args.tolerance_mm,
            max_occupancy_ratio=args.max_occupancy_ratio,
            screenshot_result=screenshot_result,
            write_back=True,
        )
        progress_log_path = progress_writer.update(
            progress={
                "layout_completion_percent": 100.0,
                "modeling_percent": 100.0 if step_path.exists() else 0.0,
                "export_file_percent": _existing_export_percent(step_path, glb_path),
                "validation_percent": 100.0,
            },
            success=bool(report["success"]),
            status="success" if report["success"] else "validation_failed",
            error=None
            if report["success"]
            else {
                "code": "CAD_VALIDATION_FAILED",
                "message": "CAD validation completed with blocking errors.",
                "details": {
                    "error_count": len(report.get("failures") or report.get("errors") or []),
                    "warning_count": len(report.get("warnings") or []),
                },
            },
        )
        attach_progress_log_path(report, progress_log_path)
    except Exception:
        progress_writer.update(
            progress={
                "layout_completion_percent": 0.0,
                "modeling_percent": 0.0,
                "export_file_percent": 0.0,
                "validation_percent": 0.0,
            },
            success=False,
            status="failed",
        )
        raise
    print_json(report)
    return 1 if args.strict and not report["success"] else 0


def _existing_export_percent(step_path: Path, glb_path: Path) -> float:
    exported_count = int(step_path.exists()) + int(glb_path.exists())
    return (exported_count / 2.0) * 100.0


def _resolve_screenshot_path(raw_path: str, cad_dir: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    if len(candidate.parts) == 1:
        return cad_dir / candidate
    return resolve_workspace_path(candidate)


def _resolve_six_face_screenshot_paths(raw_path: str, cad_dir: Path) -> dict[str, Path]:
    base = _resolve_screenshot_path(raw_path, cad_dir)
    if base.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}:
        parent = base.parent
        stem = base.stem
        suffix = base.suffix
    else:
        parent = base
        stem = "freecad_screenshot"
        suffix = ".png"
    return {view: parent / f"{stem}_{view}{suffix}" for view in SIX_FACE_VIEWS}


def _validation_output_paths(
    cad_dir: Path,
    screenshot_paths: dict[str, Path],
) -> dict[str, Path]:
    paths = {
        "step": cad_dir / "geometry_after.step",
        "glb": cad_dir / "geometry_after.glb",
        "simulation_input": cad_dir / "simulation_input.json",
        "cad_agent_output": cad_dir / "cad_agent_output.json",
        "geometry_after_layout_topology": cad_dir / "geometry_after.layout_topology.json",
        "geometry_after_geom": cad_dir / "geometry_after.geom.json",
        "geometry_after_registry": cad_dir / "geometry_after_registry.json",
        "comsol_coord": cad_dir / "comsol_inputs" / "coord.txt",
        "comsol_channels_input": cad_dir / "comsol_inputs" / "channels_input.npz",
    }
    for view_name, path in screenshot_paths.items():
        paths[f"screenshot_{view_name}"] = path
    return paths


def capture_six_face_screenshots(
    *,
    doc_name: str,
    output_paths: dict[str, Path],
    width: int,
    height: int,
    host: str | None,
    port: int | None,
) -> dict[str, object]:
    captures = []
    for view_name in SIX_FACE_VIEWS:
        output_path = output_paths[view_name]
        captures.append(
            capture_screenshot(
                doc_name=doc_name,
                output_path=output_path,
                view_name=view_name,
                width=width,
                height=height,
                host=host,
                port=port,
            )
        )
    return {
        "success": all(bool(item.get("success")) for item in captures),
        "document": doc_name,
        "count": len(captures),
        "views": captures,
        "screenshot_paths": {
            view_name: str(output_paths[view_name]) for view_name in SIX_FACE_VIEWS
        },
        "width": int(width),
        "height": int(height),
    }


def capture_screenshot(
    *,
    doc_name: str,
    output_path: Path,
    view_name: str,
    width: int,
    height: int,
    host: str | None,
    port: int | None,
) -> dict[str, object]:
    code = render_rpc_script(
        "capture_document_screenshot.py",
        {
            "__DOC_NAME__": json.dumps(doc_name),
            "__OUTPUT_PATH__": json.dumps(normalize_runtime_path(output_path)),
            "__WIDTH__": str(int(width)),
            "__HEIGHT__": str(int(height)),
            "__VIEW_NAME__": json.dumps(view_name),
        },
    )
    try:
        return execute_script_payload(host, port, code)
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "screenshot_path": str(output_path),
            "document": doc_name,
        }


if __name__ == "__main__":
    raise SystemExit(main())
