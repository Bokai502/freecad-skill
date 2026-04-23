#!/usr/bin/env python3
"""Safely update a component placement inside a YAML assembly."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.artifact_registry import (
    add_registry_args,
    artifact_entry,
    build_error_payload,
    finalize_registry_run,
    start_registry_run,
)
from freecad_cli_tools.freecad_sync import execute_batch_sync
from freecad_cli_tools.geometry import (
    FACE_DEFINITIONS,
    analyze_position,
    build_analysis_context,
    centered_face_position,
    component_local_extents,
    component_mount_face,
    component_solid_placement,
    constrain_position_to_envelope_face,
    envelope_face,
    find_best_safe_scale,
    get_face_data,
    is_external_face,
    project_move_to_mount_plane,
    rotation_matrix_from_component,
    update_component_placement,
    vector_add,
    vector_scale,
)
from freecad_cli_tools.yaml_schema import validate_assembly


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Move a component inside a YAML assembly, detect collisions, "
            "write an updated YAML file, and optionally sync the result to FreeCAD."
        )
    )
    parser.add_argument(
        "--input", default="data/sample.yaml", help="Path to the source YAML file."
    )
    parser.add_argument(
        "--output",
        default="data/sample.updated.yaml",
        help="Path to the output YAML file.",
    )
    parser.add_argument(
        "--component", default="P001", help="Target component id to move."
    )
    parser.add_argument(
        "--move",
        nargs=3,
        type=float,
        metavar=("DX", "DY", "DZ"),
        default=(50.0, 50.0, 0.0),
        help="Requested movement vector.",
    )
    parser.add_argument(
        "--install-face",
        type=int,
        choices=sorted(FACE_DEFINITIONS.keys()),
        help=(
            "Optional target envelope face for reorientation. When supplied, the component is "
            "rotated so its own mount_face is installed onto the specified envelope face and "
            "placed at the center of that face."
        ),
    )
    parser.add_argument(
        "--sync-cad",
        action="store_true",
        help="After writing the updated YAML, sync the component position into a FreeCAD document.",
    )
    parser.add_argument(
        "--doc-name",
        help="FreeCAD document name to update when --sync-cad is used.",
    )
    parser.add_argument(
        "--component-object",
        help="Exact FreeCAD solid object name for the component. Defaults to the component id.",
    )
    parser.add_argument(
        "--part-object",
        help=(
            "Exact FreeCAD container object name for the component. "
            "Defaults to '<component>_part'."
        ),
    )
    add_connection_args(parser)
    add_registry_args(parser)
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def save_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def sync_yaml_result_to_cad(
    args: argparse.Namespace,
    output_path: Path,
    component_id: str,
    component: dict,
) -> dict:
    if not args.sync_cad:
        return {"enabled": False, "success": False}
    if not args.doc_name:
        raise ValueError("--doc-name is required when --sync-cad is used.")

    position = [float(value) for value in component["placement"]["position"]]
    rotation_matrix = rotation_matrix_from_component(component)
    solid_position, solid_rotation_matrix = component_solid_placement(
        component_id,
        component,
        position,
        rotation_matrix,
    )
    solid_name = args.component_object or args.component
    part_name = args.part_object or f"{args.component}_part"
    try:
        payload = execute_batch_sync(
            args.host,
            args.port,
            args.doc_name,
            [
                {
                    "component": component_id,
                    "solid_name": solid_name,
                    "part_name": part_name,
                    "position": position,
                    "rotation_matrix": rotation_matrix,
                    "solid_position": solid_position,
                    "solid_rotation_matrix": solid_rotation_matrix,
                }
            ],
            recompute=False,
        )
    except SystemExit as exc:
        raise RuntimeError(
            f"cannot connect to FreeCAD RPC server at {args.host}:{args.port}"
        ) from exc
    payload["enabled"] = True
    payload["yaml_path"] = str(output_path)
    return payload


def registry_inputs(args: argparse.Namespace, input_path: Path, output_path: Path) -> dict[str, object]:
    """Build the registry input payload for YAML-safe-move."""
    return {
        "input_yaml_path": str(input_path),
        "output_yaml_path": str(output_path),
        "component": args.component,
        "move": [float(value) for value in args.move],
        "install_face": args.install_face,
        "sync_cad": args.sync_cad,
        "doc_name": args.doc_name,
        "rpc_host": args.host,
        "rpc_port": args.port,
    }


def build_result_payload(
    *,
    input_path: Path,
    output_path: Path,
    args: argparse.Namespace,
    component_face: int,
    original_envelope_face: int,
    target_envelope_face: int,
    target_face_label: str,
    target_rotation_matrix: list[list[float]],
    normal_component_ignored: list[float],
    original_position: list[float],
    start_position: list[float],
    move: list[float],
    effective_move: list[float],
    requested_position: list[float],
    requested_ok: bool,
    requested_blockers: list[str],
    solution_found: bool,
    applied_scale: float,
    applied_move: list[float],
    final_position: list[float],
    final_mount_point: list[float],
    final_blockers: list[str],
    cad_sync: dict,
) -> dict[str, object]:
    """Build a structured result payload for YAML-safe-move."""
    return {
        "success": not (args.sync_cad and not cad_sync.get("success")),
        "input_file": str(input_path.resolve()),
        "output_file": str(output_path.resolve()),
        "target_component": args.component,
        "component_mount_face": component_face,
        "component_mount_face_label": FACE_DEFINITIONS[component_face][0],
        "original_envelope_face": original_envelope_face,
        "original_envelope_face_label": FACE_DEFINITIONS[original_envelope_face][0],
        "target_envelope_face": target_envelope_face,
        "target_envelope_face_label": target_face_label,
        "orientation_change_supported": True,
        "orientation_change_applied": args.install_face is not None,
        "rotation_matrix": target_rotation_matrix,
        "normal_move_component_ignored": normal_component_ignored,
        "original_position": original_position,
        "constrained_start_position": start_position,
        "requested_move": move,
        "effective_move": effective_move,
        "requested_position": requested_position,
        "requested_move_is_safe": requested_ok,
        "requested_blockers": requested_blockers,
        "solution_found_on_requested_segment": solution_found,
        "applied_scale": applied_scale,
        "applied_move": applied_move,
        "final_position": final_position,
        "final_mount_point": final_mount_point,
        "final_blockers": final_blockers,
        "cad_sync_enabled": args.sync_cad,
        "cad_sync_result": cad_sync,
    }


def emit_result_lines(payload: dict[str, object]) -> None:
    """Print the legacy human-readable output for YAML-safe-move."""
    print(f"input_file: {payload['input_file']}")
    print(f"output_file: {payload['output_file']}")
    print(f"target_component: {payload['target_component']}")
    print(f"component_mount_face: {payload['component_mount_face']}")
    print(f"component_mount_face_label: {payload['component_mount_face_label']}")
    print(f"original_envelope_face: {payload['original_envelope_face']}")
    print(
        "original_envelope_face_label: "
        f"{payload['original_envelope_face_label']}"
    )
    print(f"target_envelope_face: {payload['target_envelope_face']}")
    print(f"target_envelope_face_label: {payload['target_envelope_face_label']}")
    print(
        "orientation_change_supported: "
        f"{payload['orientation_change_supported']}"
    )
    print(
        "orientation_change_applied: "
        f"{payload['orientation_change_applied']}"
    )
    print(f"rotation_matrix: {payload['rotation_matrix']}")
    print(
        "normal_move_component_ignored: "
        f"{payload['normal_move_component_ignored']}"
    )
    print(f"original_position: {payload['original_position']}")
    print(
        "constrained_start_position: "
        f"{payload['constrained_start_position']}"
    )
    print(f"requested_move: {payload['requested_move']}")
    print(f"effective_move: {payload['effective_move']}")
    print(f"requested_position: {payload['requested_position']}")
    print(f"requested_move_is_safe: {payload['requested_move_is_safe']}")
    print(f"requested_blockers: {payload['requested_blockers']}")
    print(
        "solution_found_on_requested_segment: "
        f"{payload['solution_found_on_requested_segment']}"
    )
    print(f"applied_scale: {float(payload['applied_scale']):.12f}")
    print(f"applied_move: {payload['applied_move']}")
    print(f"final_position: {payload['final_position']}")
    print(f"final_mount_point: {payload['final_mount_point']}")
    print(f"final_blockers: {payload['final_blockers']}")
    print(f"cad_sync_enabled: {payload['cad_sync_enabled']}")
    print(
        "cad_sync_result: "
        f"{json.dumps(payload['cad_sync_result'], ensure_ascii=False)}"
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    move = [float(value) for value in args.move]
    registry_run = start_registry_run(
        args,
        tool="freecad-yaml-safe-move",
        operation_type="yaml_safe_move",
        inputs=registry_inputs(args, input_path, output_path),
    )

    try:
        data = load_yaml(input_path)
        validate_assembly(data)
        components = data.get("components", {})
        if args.component not in components:
            available = ", ".join(sorted(components))
            raise KeyError(
                f"Component {args.component} not found. Available components: {available}"
            )

        target = components[args.component]
        component_face = component_mount_face(target)
        target_extents = component_local_extents(args.component, target)
        original_envelope_face = envelope_face(target)
        target_envelope_face = (
            args.install_face if args.install_face is not None else original_envelope_face
        )
        _, target_face_label, target_axis, _ = get_face_data(target_envelope_face)

        # Choose the reference wall size: outer surface for external faces, inner for internal.
        if is_external_face(target_envelope_face):
            outer_size = data["envelope"].get("outer_size")
            if outer_size is None:
                raise ValueError(
                    f"envelope.outer_size is required to install a component on external face "
                    f"{target_envelope_face}."
                )
            wall_size = list(outer_size)
        else:
            wall_size = list(data["envelope"]["inner_size"])

        target_rotation_matrix = rotation_matrix_from_component(target)
        if args.install_face is not None:
            base_position, _, _ = centered_face_position(
                target_extents,
                wall_size,
                component_face,
                target_envelope_face,
            )
            start_position = constrain_position_to_envelope_face(
                base_position,
                target_extents,
                wall_size,
                target_envelope_face,
                target_rotation_matrix,
            )
        else:
            start_position = constrain_position_to_envelope_face(
                target["placement"]["position"],
                target_extents,
                wall_size,
                target_envelope_face,
                target_rotation_matrix,
            )

        effective_move, normal_component_ignored = project_move_to_mount_plane(
            move, target_axis
        )
        analysis_context = build_analysis_context(
            data,
            args.component,
            target_rotation_matrix,
            check_envelope=not is_external_face(target_envelope_face),
            envelope_face_id=target_envelope_face,
            wall_size=wall_size,
        )
        requested_position = vector_add(start_position, effective_move)
        requested_ok, requested_blockers = analyze_position(
            analysis_context, requested_position, target_rotation_matrix
        )

        solution_found = True
        if requested_ok:
            applied_scale = 1.0
            applied_move = effective_move
            final_position = requested_position
        else:
            best_scale = find_best_safe_scale(
                analysis_context,
                start_position,
                effective_move,
                target_rotation_matrix,
            )
            if best_scale is None:
                solution_found = False
                applied_scale = 0.0
                applied_move = [0.0, 0.0, 0.0]
                final_position = start_position
            else:
                applied_scale = best_scale
                applied_move = vector_scale(effective_move, applied_scale)
                final_position = vector_add(start_position, applied_move)

        final_ok, final_blockers = analyze_position(
            analysis_context, final_position, target_rotation_matrix
        )
        if solution_found and not final_ok:
            raise RuntimeError(
                f"Failed to find a collision-free position for {args.component}. "
                f"Blockers: {final_blockers}"
            )

        updated = update_component_placement(
            data,
            args.component,
            final_position,
            target_envelope_face,
        )
        save_yaml(output_path, updated)

        try:
            cad_sync = sync_yaml_result_to_cad(
                args,
                output_path,
                args.component,
                updated["components"][args.component],
            )
        except Exception as exc:
            cad_sync = {
                "enabled": True,
                "success": False,
                "error": str(exc),
                "document": args.doc_name,
                "component": args.component,
            }

        payload = build_result_payload(
            input_path=input_path,
            output_path=output_path,
            args=args,
            component_face=component_face,
            original_envelope_face=original_envelope_face,
            target_envelope_face=target_envelope_face,
            target_face_label=target_face_label,
            target_rotation_matrix=target_rotation_matrix,
            normal_component_ignored=normal_component_ignored,
            original_position=list(target["placement"]["position"]),
            start_position=start_position,
            move=move,
            effective_move=effective_move,
            requested_position=requested_position,
            requested_ok=requested_ok,
            requested_blockers=requested_blockers,
            solution_found=solution_found,
            applied_scale=applied_scale,
            applied_move=applied_move,
            final_position=final_position,
            final_mount_point=updated["components"][args.component]["placement"][
                "mount_point"
            ],
            final_blockers=final_blockers,
            cad_sync=cad_sync,
        )
        registry_status = (
            "partial_success"
            if args.sync_cad and not cad_sync.get("success")
            else "success"
        )
        registry_error = (
            build_error_payload(
                "CAD_SYNC_FAILED",
                str(cad_sync.get("error") or "CAD sync did not complete successfully."),
                details=cad_sync,
            )
            if registry_status == "partial_success"
            else None
        )
        finalize_registry_run(
            registry_run,
            status=registry_status,
            outputs={
                "yaml_path": str(output_path),
            },
            result=payload,
            error=registry_error,
            artifacts=[
                artifact_entry("input_yaml", input_path),
                artifact_entry("output_yaml", output_path),
            ],
        )
        emit_result_lines(payload)
        return 2 if registry_status == "partial_success" else 0
    except Exception as exc:
        finalize_registry_run(
            registry_run,
            status="failed",
            outputs={},
            result={"success": False},
            error=build_error_payload("YAML_SAFE_MOVE_EXCEPTION", str(exc)),
            artifacts=[
                artifact_entry("input_yaml", input_path),
                artifact_entry("output_yaml", output_path),
            ],
        )
        raise


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


# Backward-compatible re-exports.  These names moved to
# freecad_cli_tools.geometry in v0.8.0.  Import from there directly
# in new code.
from freecad_cli_tools.geometry import (  # noqa: E402, F401
    IDENTITY_ROTATION,
    box_bounds,
    broad_phase_obstacles,
    compute_mount_point,
    translate_bounds,
)
