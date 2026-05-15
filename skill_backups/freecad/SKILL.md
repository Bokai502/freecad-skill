---
name: freecad
description: "FreeCAD CLI/RPC workflow for this repo's layout dataset. Use when Codex needs to inspect FreeCAD runtime/workspace config, build placeholder assemblies from layout_topology.json + geom.json, build CAD-asset assemblies from geom_component_info.json or STEP/STP component assets, safely move or re-seat components, export STEP/GLB artifacts, or debug FreeCAD workflow command arguments and progress logs."
---

# FreeCAD

## Prerequisites

- Use the packaged CLI entry points under `/data/lbk/freecad_skills/freecad-skill/freecad_cli_tools` instead of ad hoc Python when a command already exists.
- Before running a workflow command, call `freecad-runtime-config` to read the resolved workspace, RPC settings, default input paths, default output paths, and component-info STEP size limit.
- `freecad-runtime-config` does not accept `--workspace`. To inspect defaults for a specific workspace, set `FREECAD_WORKSPACE_DIR=/path/to/workspace` for that command, for example `FREECAD_WORKSPACE_DIR=/data/lbk/codex_web/FreeCAD_data/v4_data freecad-runtime-config`.
- Workflow commands such as `freecad-create-assembly`, `freecad-create-assembly-from-component-info`, and `freecad-layout-safe-move` do accept `--workspace`. When you plan to pass `--workspace` to a workflow command, call `freecad-runtime-config` first with `FREECAD_WORKSPACE_DIR` set to the same workspace so the inspected defaults match the workflow run.
- Resolve relative input and output paths only from the configured workspace root. Workflow commands apply this priority order:
  1. CLI/workflow `--workspace /path/to/workspace`; relative paths are resolved under that workspace.
  2. `FREECAD_WORKSPACE_DIR=/path/to/workspace`; relative paths are resolved under that workspace.
  3. `/data/lbk/codex_web/config.json` field `freecad.workspaceDir`; relative paths are resolved under that workspace.
- If no workspace source is present, stop immediately instead of guessing from the current directory, repo root, or skill directory. If a workspace source is relative, use the absolute path reported by `freecad-runtime-config` or by the workflow command's resolved outputs.
- Expect FreeCAD RPC at the `rpc_host` and `rpc_port` reported by `freecad-runtime-config`, unless the active workflow command is given explicit `--host` or `--port` overrides. If RPC is unavailable, report the connection problem clearly instead of guessing.

## Route The Request

- Read exactly one guide first unless the request truly spans multiple workflows.
- Use `guides/safe-move-workflow.md` for move, rotate, re-seat, install-face changes, collision checks, or requests to adjust an existing component. Treat this as the default entry point for component edits.
- Use `guides/create-assembly-from-component-info.md` when the request mentions or provides `geom_component_info.json`, `cad_rotated_path`, STEP/STP CAD assets, real component CAD, component-info assembly, or the command `freecad-create-assembly-from-component-info`.
- Use `guides/create-assembly.md` when the request is to build or rebuild an assembly from the layout dataset without component-info CAD assets, especially from `layout_topology.json + geom.json` or the command `freecad-create-assembly`.
- If the user asks only about workspace/config/CLI argument behavior, stay in this file unless a workflow guide is needed.

## Hard Rules

- Treat `layout_topology.json` plus `geom.json` as the only source of truth. Do not use `sample.yaml`; it is backup-only.
- Default dataset input paths are `./01_layout/layout_topology.json` and `./01_layout/geom.json` under the configured workspace root.
- The component-info CAD-asset build also uses `./component_info/geom_component_info.json` by default, but only after the route rules select `guides/create-assembly-from-component-info.md`. `./component_info/bom_component_info.json` is colocated there for BOM metadata, but the current CAD-asset build does not read it.
- Default output paths live under `./02_geometry_edit` under the configured workspace root.
- Never infer dataset input paths from the repository root, the skill backup directory, or the process `cwd` once a workspace root has been resolved. Expand defaults to absolute paths before reasoning about missing files or running commands.
- If default input files are not present under the resolved workspace, do not search broadly for similarly named files. Ask for or require an explicit workflow `--workspace`, `FREECAD_WORKSPACE_DIR`, `freecad.workspaceDir`, `--layout-topology`, and `--geom` path. Do not pass `--workspace` to `freecad-runtime-config`; use `FREECAD_WORKSPACE_DIR` for that command.
- Placeholder and safe-move CAD artifacts must be named `geometry_after.step` and `geometry_after.glb`. Component-info CAD-asset builds must be named `component_info_assembly.step` and `component_info_assembly.glb`. If a CLI accepts an output path, use it only to choose the directory or parent path unless the guide says otherwise.
- `freecad-layout-safe-move` writes non-destructive dataset outputs such as `geometry_after.layout_topology.json` and `geometry_after.geom.json`. Do not overwrite the source dataset unless the workflow explicitly says to.
- Preserve the component-local contact face when changing the installation face. Derive runtime orientation from `placement.mount_face_id`, `placement.component_mount_face_id`, and `placement.alignment.in_plane_rotation_deg` instead of storing `placement.rotation_matrix`.
- Prefer first-class commands:
  - `freecad-create-assembly`
  - `freecad-create-assembly-from-component-info`
  - `freecad-layout-safe-move`
- After CAD geometry changes, recompute and fit the view unless the active command exposes and uses an explicit opt-out such as `--no-fit-view`.
- Verify outputs after execution. If the dataset update succeeds but STEP or GLB export is missing, report partial success rather than full success.
- Check and report CLI progress fields: `layout_completion_percent`, `modeling_percent`, and `export_file_percent`. STEP and GLB exports each contribute 50% to `export_file_percent`. The latest values are written to `<configured workspace>/logs/progress_percentages.json` by the CLI and FreeCAD-side scripts as layout, modeling, and export stages advance.
- When that progress file already contains the BOM pipeline schema (`schema_version: "1.0"` with `steps`), FreeCAD must not replace the file with its standalone payload. Merge FreeCAD progress into the `geometry-edit` step: set `steps[].percent` for `geometry-edit` to the average of the three FreeCAD progress fields, keep it in the range `0-100`, attach the detailed values under `freecad_progress`, recompute `overall_percent`, and preserve top-level `output_files` for frontend display.
- When the progress file does not contain the BOM pipeline schema, the CLI may keep writing the standalone FreeCAD progress payload for direct FreeCAD use.

## Workflow Notes

- Placeholder-build workflow: normalize `layout_topology.json + geom.json` into the internal spec, create the assembly hierarchy, include the envelope when available, then export `geometry_after.step` and `geometry_after.glb`. Use this workflow for assembly creation unless the user clearly asks for real CAD/STEP/STP asset import.
- Component-info CAD-asset workflow: normalize `layout_topology.json + geom.json + geom_component_info.json` into the internal component-info assembly spec, create a new assembly, include the envelope from `geom.outer_shell`, import real STEP components from `cad_rotated_path` when available, fall back to box placeholders when they are not, then export `component_info_assembly.step` and `component_info_assembly.glb`.
- Safe-move workflow: solve in normalized coordinates, project the move into the active face plane, preserve the component contact face, write updated dataset files, and only then sync CAD when requested.

## Error Handling

- If RPC connection fails, tell the user to check the running FreeCAD instance and MCP/RPC setup.
- If the CLI returns `"success": false`, surface the returned error details.
- If a move or build operation yields STEP without GLB, report partial success and include the artifact paths that do exist.
