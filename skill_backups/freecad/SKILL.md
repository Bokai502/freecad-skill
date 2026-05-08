---
name: freecad
description: "FreeCAD workflow for layout_topology.json, geom.json, and geom_component_info.json assembly generation plus safe component moves. Use when Codex needs to operate the FreeCAD CLI or RPC workflow in this repo to build a placeholder assembly, build a direct STEP-or-box assembly from component info, or move a component safely and optionally sync CAD."
---

# FreeCAD

## Prerequisites

- Use the packaged CLI entry points under `/data/lbk/freecad_skills/freecad-skill/freecad_cli_tools` instead of ad hoc Python when a command already exists.
- Before running a workflow command, call `freecad-runtime-config` to read the resolved workspace, RPC settings, default input paths, default output paths, and component-info STEP size limit.
- Resolve relative paths only from the configured workspace root reported by `freecad-runtime-config`; that command applies this priority order:
  1. CLI/workflow `--workspace /abs/path/to/workspace`
  2. `FREECAD_WORKSPACE_DIR=/abs/path/to/workspace`
  3. `/data/lbk/codex_web/config.json` field `freecad.workspaceDir`
- If no workspace source is present, or the workspace path is not absolute, stop immediately instead of guessing from the current directory, repo root, or skill directory.
- Expect FreeCAD RPC at the `rpc_host` and `rpc_port` reported by `freecad-runtime-config`, unless the active workflow command is given explicit `--host` or `--port` overrides. If RPC is unavailable, report the connection problem clearly instead of guessing.

## Route The Request

- Read exactly one guide first unless the user request truly spans multiple workflows.
- Use `guides/safe-move-workflow.md` for generic move, rotate, re-seat, collision-check, or "adjust this part" requests. Treat this as the default entry point.
- Use `guides/create-assembly.md` only when the user explicitly asks to build or rebuild a placeholder assembly from `layout_topology.json + geom.json`.
- Use `guides/create-assembly-from-component-info.md` only when the user explicitly asks to build a brand-new assembly from real CAD assets, STEP/STP files, or `geom_component_info.json` `display_info.assets.cad_rotated_path` entries.
- If the user does not explicitly mention real CAD/STEP/STP assets, `cad_rotated_path`, or a component-info CAD-asset build, do not read or use `guides/create-assembly-from-component-info.md`; use the placeholder assembly or safe-move workflow instead.

## Hard Rules

- Treat `layout_topology.json` plus `geom.json` as the only source of truth. Do not use `sample.yaml`; it is backup-only.
- Default dataset input paths are `./01_layout/layout_topology.json` and `./01_layout/geom.json` under the configured workspace root.
- The component-info CAD-asset build also uses `./01_layout/geom_component_info.json` by default, but only after the route rules select `guides/create-assembly-from-component-info.md`.
- Default output paths live under `./02_geometry_edit` under the configured workspace root.
- Never infer dataset input paths from the repository root, the skill backup directory, or the process `cwd` once a workspace root has been resolved. Expand defaults to absolute paths before reasoning about missing files or running commands.
- If default input files are not present under the resolved workspace, do not search broadly for similarly named files. Ask for or require an explicit `--workspace`, `FREECAD_WORKSPACE_DIR`, `freecad.workspaceDir`, `--layout-topology`, and `--geom` path.
- Placeholder and safe-move CAD artifacts must be named `geometry_after.step` and `geometry_after.glb`. Component-info CAD-asset builds must be named `component_info_assembly.step` and `component_info_assembly.glb`. If a CLI accepts an output path, use it only to choose the directory or parent path unless the guide says otherwise.
- `freecad-layout-safe-move` writes non-destructive dataset outputs such as `geometry_after.layout_topology.json` and `geometry_after.geom.json`. Do not overwrite the source dataset unless the workflow explicitly says to.
- Preserve the component-local contact face when changing the installation face. Derive runtime orientation from `placement.mount_face_id`, `placement.component_mount_face_id`, and `placement.alignment.in_plane_rotation_deg` instead of storing `placement.rotation_matrix`.
- Prefer first-class commands:
  - `freecad-create-assembly`
  - `freecad-create-assembly-from-component-info`
  - `freecad-layout-safe-move`
- After CAD geometry changes, recompute and fit the view unless the active command exposes and uses an explicit opt-out such as `--no-fit-view`.
- Verify outputs after execution. If the dataset update succeeds but STEP or GLB export is missing, report partial success rather than full success.
- Check and report CLI progress fields: `layout_completion_percent`, `modeling_percent`, and `export_file_percent`. STEP and GLB exports each contribute 50% to `export_file_percent`. The latest values are written to `<configured workspace>/logs/progress_percentages.json` by the CLI and FreeCAD-side scripts as layout, modeling, and export stages advance; `output_files` records produced file paths and existence checks.

## Workflow Notes

- Placeholder-build workflow: normalize `layout_topology.json + geom.json` into the internal spec, create the assembly hierarchy, include the envelope when available, then export `geometry_after.step` and `geometry_after.glb`. Use this workflow for assembly creation unless the user clearly asks for real CAD/STEP/STP asset import.
- Component-info CAD-asset workflow: normalize `layout_topology.json + geom.json + geom_component_info.json` into the internal component-info assembly spec, create a new assembly, include the envelope from `geom.outer_shell`, import real STEP components from `cad_rotated_path` when available, fall back to box placeholders when they are not, then export `component_info_assembly.step` and `component_info_assembly.glb`.
- Safe-move workflow: solve in normalized coordinates, project the move into the active face plane, preserve the component contact face, write updated dataset files, and only then sync CAD when requested.

## Error Handling

- If RPC connection fails, tell the user to check the running FreeCAD instance and MCP/RPC setup.
- If the CLI returns `"success": false`, surface the returned error details.
- If a move or build operation yields STEP without GLB, report partial success and include the artifact paths that do exist.
