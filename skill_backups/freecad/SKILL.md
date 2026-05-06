---
name: freecad
description: "FreeCAD workflow for layout_topology.json, geom.json, and geom_component_info.json assembly generation plus safe component moves. Use when Codex needs to operate the FreeCAD CLI or RPC workflow in this repo to build a placeholder assembly, build a direct STEP-or-box assembly from component info, or move a component safely and optionally sync CAD."
---

# FreeCAD

## Prerequisites

- Use the packaged CLI entry points under `/data/lbk/freecad_skills/freecad-skill/freecad_cli_tools` instead of ad hoc Python when a command already exists.
- Resolve relative paths from `FREECAD_WORKSPACE_DIR` in the runtime config or environment. Runtime config lookup prefers `FREECAD_RUNTIME_CONFIG`, then project `.freecad/freecad_runtime.conf`, then user config, with `/data/lbk/freecad_skills/freecad-skill/config/freecad_runtime.conf` kept as a fallback.
- Before running any FreeCAD CLI, resolve and report the effective workspace root. Use this order exactly:
  1. `FREECAD_WORKSPACE_DIR` environment variable, if set.
  2. `FREECAD_WORKSPACE_DIR` from `FREECAD_RUNTIME_CONFIG`, if that environment variable points to a config file.
  3. `FREECAD_WORKSPACE_DIR` from the first project config found at `.freecad/freecad_runtime.conf` or `freecad_runtime.conf` under the current working directory.
  4. `FREECAD_WORKSPACE_DIR` from the user config at `$XDG_CONFIG_HOME/freecad-cli-tools/runtime.conf` or `~/.config/freecad-cli-tools/runtime.conf`.
  5. `FREECAD_WORKSPACE_DIR` from `/data/lbk/freecad_skills/freecad-skill/config/freecad_runtime.conf`.
- If the resolved workspace is missing or still relative, stop and report the ambiguity instead of guessing from the current directory or the skill directory.
- Expect FreeCAD RPC at the host and port configured in that file. If RPC is unavailable, report the connection problem clearly instead of guessing.

## Route The Request

- Read exactly one guide first unless the user request truly spans multiple workflows.
- Use `guides/safe-move-workflow.md` for generic move, rotate, re-seat, collision-check, or "adjust this part" requests. Treat this as the default entry point.
- Use `guides/create-assembly.md` only when the user explicitly asks to build or rebuild a placeholder assembly from `layout_topology.json + geom.json`.
- Use `guides/create-assembly-from-component-info.md` only when the user explicitly asks to build a brand-new assembly from real CAD assets, STEP/STP files, or `geom_component_info.json` `display_info.assets.cad_rotated_path` entries.
- If the user does not explicitly mention real CAD/STEP/STP assets, `cad_rotated_path`, or a component-info CAD-asset build, do not read or use `guides/create-assembly-from-component-info.md`; use the placeholder assembly or safe-move workflow instead.

## Hard Rules

- Treat `layout_topology.json` plus `geom.json` as the only source of truth. Do not use `sample.yaml`; it is backup-only.
- Default dataset input paths are `./01_layout/layout_topology.json` and `./01_layout/geom.json` under `FREECAD_WORKSPACE_DIR`.
- The component-info CAD-asset build also uses `./01_layout/geom_component_info.json` by default, but only after the route rules select `guides/create-assembly-from-component-info.md`.
- Default output paths live under `./02_geometry_edit` under `FREECAD_WORKSPACE_DIR`.
- Never infer dataset input paths from the repository root, the skill backup directory, or the process `cwd` once a workspace root has been resolved. Expand defaults to absolute paths before reasoning about missing files or running commands.
- If default input files are not present under the resolved workspace, do not search broadly for similarly named files. Ask for or require an explicit `FREECAD_WORKSPACE_DIR`, `FREECAD_RUNTIME_CONFIG`, `--layout-topology`, and `--geom` path.
- Placeholder and safe-move CAD artifacts must be named `geometry_after.step` and `geometry_after.glb`. Component-info CAD-asset builds must be named `component_info_assembly.step` and `component_info_assembly.glb`. If a CLI accepts an output path, use it only to choose the directory or parent path unless the guide says otherwise.
- `freecad-layout-safe-move` writes non-destructive dataset outputs such as `geometry_after.layout_topology.json` and `geometry_after.geom.json`. Do not overwrite the source dataset unless the workflow explicitly says to.
- Preserve the component-local contact face when changing the installation face. Derive runtime orientation from `placement.mount_face_id`, `placement.component_mount_face_id`, and `placement.alignment.in_plane_rotation_deg` instead of storing `placement.rotation_matrix`.
- Prefer first-class commands:
  - `freecad-create-assembly`
  - `freecad-create-assembly-from-component-info`
  - `freecad-layout-safe-move`
- After CAD geometry changes, recompute and fit the view unless the active command exposes and uses an explicit opt-out such as `--no-fit-view`.
- Verify outputs after execution. If the dataset update succeeds but STEP or GLB export is missing, report partial success rather than full success.
- Check and report CLI progress fields: `layout_completion_percent`, `modeling_percent`, and `export_file_percent`. STEP and GLB exports each contribute 50% to `export_file_percent`. The latest values are written to `$FREECAD_WORKSPACE_DIR/logs/progress_percentages.json` by the CLI and FreeCAD-side scripts as layout, modeling, and export stages advance; `output_files` records produced file paths and existence checks.

## Workflow Notes

- Placeholder-build workflow: normalize `layout_topology.json + geom.json` into the internal spec, create the assembly hierarchy, include the envelope when available, then export `geometry_after.step` and `geometry_after.glb`. Use this workflow for assembly creation unless the user clearly asks for real CAD/STEP/STP asset import.
- Component-info CAD-asset workflow: normalize `layout_topology.json + geom.json + geom_component_info.json` into the internal component-info assembly spec, create a new assembly, include the envelope from `geom.outer_shell`, import real STEP components from `cad_rotated_path` when available, fall back to box placeholders when they are not, then export `component_info_assembly.step` and `component_info_assembly.glb`.
- Safe-move workflow: solve in normalized coordinates, project the move into the active face plane, preserve the component contact face, write updated dataset files, and only then sync CAD when requested.

## Error Handling

- If RPC connection fails, tell the user to check the running FreeCAD instance and MCP/RPC setup.
- If the CLI returns `"success": false`, surface the returned error details.
- If a move or build operation yields STEP without GLB, report partial success and include the artifact paths that do exist.
