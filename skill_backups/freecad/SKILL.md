---
name: freecad
description: "Unified FreeCAD skill for layout-dataset assembly generation, replace-component workflows, and safe move workflows."
argument-hint: "[action] [args...]"
allowed-tools: "Bash(*), Read, Write, Edit"
---

# FreeCAD Unified Skill

## Context: $ARGUMENTS

## Prerequisites

- FreeCAD must be running with the **FreeCADMCP addon** active, using the RPC host/port configured in `/data/lbk/freecad_skills/freecad-skill/config/freecad_runtime.conf` (currently `localhost:9876`).
- Python environment: `base` (where `freecad-cli-tools` is installed).
- Prefer packaged CLI entry points over ad hoc Python.

## Action Routing

Read the matching guide with the `Read` tool. Always prefer the highest-level workflow; use lower-level commands only as sub-steps.

| Intent | Guide |
|--------|-------|
| Create assembly from layout dataset | `guides/create-assembly.md` |
| Replace a placeholder component with a real STEP part | `guides/replace-component.md` |
| **Move a part** (default entry point) | `guides/safe-move-workflow.md` |

## Common Patterns

- **Move with safety**: `safe-move-workflow.md` (handles layout-dataset and document branches)
- **Build / rebuild from layout dataset**: `create-assembly.md` (only when user explicitly requests)
- **Swap in a real CAD part**: `replace-component.md` (replaces one `<NAME>_part` in an existing assembly STEP)

## Common CLI Flags

All RPC commands accept `--host <host>` and `--port <port>`. Their defaults come from `/data/lbk/freecad_skills/freecad-skill/config/freecad_runtime.conf` (currently `localhost:9876`). When FreeCAD runs inside WSL, pass these explicitly if Windows `localhost` forwarding is unstable.

## Global Rules

### Layout Dataset as Source of Truth
- Use `layout_topology.json + geom.json` as the source of truth for move planning and execution.
- Prefer `freecad-layout-safe-move`. It expects `--layout-topology` and `--geom` and should overwrite those dataset files in place unless explicit output paths are provided.
- Normalized `placement.mount_face` identifies the envelope face the component is installed onto (`0..5` internal, `6..11` external). When moving to a new install face, preserve the original component-local contact face and store `placement.rotation_matrix` if rotation is needed to seat that same component face on the new envelope face.

### Move Safety
- For any move request, prefer `safe-move-workflow.md` as the default entry point.
- Analyze first, then execute the fully safe move or closest safe result. Report any adjustment clearly.
- After any executed move, run a post-move collision verification before reporting success.

### Orientation & Rotation
- `--install-face <0..11>` places a component on a target envelope face. Faces `0..5` are internal (inside the envelope); faces `6..11` are external (outside the envelope, requires `geom.outer_shell.outer_bbox` / normalized `envelope.outer_size`).
- Boxes use `dims[0]`, `dims[1]`, `dims[2]` as local X/Y/Z extents. When `placement.rotation_matrix` is present, apply it to keep the intended component-local contact face seated on the selected envelope face.

### CAD Generation
- `freecad-create-assembly` is for explicit rebuild only; do not use it as the default after a move.
- `freecad-replace-component` is for swapping one generated placeholder with a detailed STEP part in an existing assembly.
- When only moving or rotating, update `layout_topology.json` and `geom.json` in place and re-export the existing `STEP` file and sibling `GLB` in place.
- Generated assemblies should include the envelope when the layout dataset provides one.
- Always call `doc.recompute()` after geometry changes.
- After generation, switch the GUI to a fitted view automatically.

### File I/O
- Use the shared runtime directory configured by `FREECAD_RUNTIME_DATA_DIR` in `/data/lbk/freecad_skills/freecad-skill/config/freecad_runtime.conf` for dataset inputs and generated artifacts (`STEP`, `GLB`, screenshots).
- `freecad-create-assembly` normalizes `layout_topology.json + geom.json` into the shared runtime directory before RPC execution, then copies generated exports back to the requested output path.
- Prefer first-class CLI commands over handwritten Python whenever the packaged command covers the task.

### Safety
- Never auto-execute destructive actions (delete, unrelated overwrite) without user confirmation. Safe move execution is allowed after analysis.
- When verifying a dataset-to-CAD sync result, perform verification after the write completes, not in parallel.

## Error Handling

- **RPC connection failed**: Prompt user to check FreeCAD is running with the MCP addon active.
- **CLI not found / import error**: Report environment problem.
- **`"success": false`**: Display the returned error details to the user.
- **Post-move collision detected**: Surface the failure clearly; do not describe the move as successful.
