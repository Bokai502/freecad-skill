---
name: freecad
description: "FreeCAD workflow for layout_topology.json plus geom.json assembly generation, safe component moves, and component replacement. Use when Codex needs to operate the FreeCAD CLI or RPC workflow in this repo to build an assembly from ./01_layout, move a component safely and optionally sync CAD, or replace one placeholder part with a real STEP model."
---

# FreeCAD

## Prerequisites

- Use the packaged CLI entry points under `/data/lbk/freecad_skills/freecad-skill/freecad_cli_tools` instead of ad hoc Python when a command already exists.
- Resolve relative paths from `FREECAD_WORKSPACE_DIR` in `/data/lbk/freecad_skills/freecad-skill/config/freecad_runtime.conf`.
- Expect FreeCAD RPC at the host and port configured in that file. If RPC is unavailable, report the connection problem clearly instead of guessing.

## Route The Request

- Read exactly one guide first unless the user request truly spans multiple workflows.
- Use `guides/safe-move-workflow.md` for generic move, rotate, re-seat, collision-check, or "adjust this part" requests. Treat this as the default entry point.
- Use `guides/create-assembly.md` only when the user explicitly asks to build or rebuild an assembly from the dataset.
- Use `guides/replace-component.md` only when the user wants to swap one generated placeholder with a real STEP component in an existing assembly.

## Hard Rules

- Treat `layout_topology.json` plus `geom.json` as the only source of truth. Do not use `sample.yaml`; it is backup-only.
- Default dataset input paths are `./01_layout/layout_topology.json` and `./01_layout/geom.json` under `FREECAD_WORKSPACE_DIR`.
- Default output paths live under `./02_geometry_edit` under `FREECAD_WORKSPACE_DIR`.
- Generated CAD artifacts must be named `geometry_after.step` and `geometry_after.glb`. If a CLI accepts an output path, use it only to choose the directory or parent path unless the guide says otherwise.
- `freecad-layout-safe-move` writes non-destructive dataset outputs such as `geometry_after.layout_topology.json` and `geometry_after.geom.json`. Do not overwrite the source dataset unless the workflow explicitly says to.
- Preserve the component-local contact face when changing the installation face. Use `placement.rotation_matrix` to keep that same component face seated on the new envelope face.
- Prefer first-class commands:
  - `freecad-create-assembly`
  - `freecad-layout-safe-move`
  - `freecad-replace-component`
- After CAD geometry changes, recompute and fit the view unless the active command exposes and uses an explicit opt-out such as `--no-fit-view`.
- Verify outputs after execution. If the dataset update succeeds but STEP or GLB export is missing, report partial success rather than full success.

## Workflow Notes

- Build workflow: normalize the dataset into the internal spec, create the assembly hierarchy, include the envelope when available, then export `geometry_after.step` and `geometry_after.glb`.
- Safe-move workflow: solve in normalized coordinates, project the move into the active face plane, preserve the component contact face, write updated dataset files, and only then sync CAD when requested.
- Replace-component workflow: use the normalized dataset for placement truth, import the source assembly STEP as input only, replace `<NAME>_part`, and export new CAD artifacts to `geometry_after.step` and `geometry_after.glb`.

## Error Handling

- If RPC connection fails, tell the user to check the running FreeCAD instance and MCP/RPC setup.
- If the CLI returns `"success": false`, surface the returned error details.
- If a move or replace operation yields STEP without GLB, report partial success and include the artifact paths that do exist.
