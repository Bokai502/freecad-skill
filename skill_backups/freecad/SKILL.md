---
name: freecad
description: "Unified FreeCAD skill for 3D modeling via RPC. Covers document management, object CRUD, Python code execution, view capture, parts library operations, YAML layout pre-processing, replace-component workflows, and safe move workflows."
argument-hint: "[action] [args...]"
allowed-tools: "Bash(*), Read, Write, Edit"
---

# FreeCAD Unified Skill

## Context: $ARGUMENTS

## Prerequisites

- FreeCAD must be running with the **FreeCADMCP addon** active (RPC server on `localhost:9875`).
- Python environment: `base` (where `freecad-cli-tools` is installed).
- Prefer packaged CLI entry points over ad hoc Python. If a CLI fails with a missing-module error, treat it as an environment problem and fall back to `freecad-exec-code` only as a temporary workaround.

## Action Routing

Read the matching guide with the `Read` tool. Always prefer the highest-level workflow; use lower-level commands only as sub-steps.

| Intent | Guide |
|--------|-------|
| Document / object CRUD, parts library | `guides/crud-reference.md` |
| Run arbitrary Python in FreeCAD | `guides/execute-code.md` |
| Capture screenshots / visual review | `guides/get-view.md` |
| Batch-create objects from YAML | `guides/load-yaml-data.md` |
| Create assembly from YAML | `guides/create-assembly.md` |
| Replace a placeholder component with a real STEP part | `guides/replace-component.md` |
| **Move a part** (default entry point) | `guides/safe-move-workflow.md` |
| Document-only collision analysis (no YAML) | `guides/check-collision.md` |

## Common Patterns

- **New project**: `create-doc` -> `create-obj` -> `get-view`
- **Move with safety**: `safe-move-workflow.md` (handles YAML and document branches)
- **Build / rebuild from YAML**: `create-assembly.md` (only when user explicitly requests)
- **Swap in a real CAD part**: `replace-component.md` (replaces one `<NAME>_part` in an existing assembly STEP)

## Common CLI Flags

All RPC commands accept `--host <host>` (default `localhost`) and `--port <port>` (default `9875`). When FreeCAD runs inside WSL, pass these explicitly if Windows `localhost` forwarding is unstable.

## Global Rules

### YAML as Source of Truth
- When a YAML layout file exists, treat it as the source of truth for move planning and execution.
- `freecad-yaml-safe-move` is the preferred YAML-first move command; use it to overwrite the source YAML and sync/save the current CAD document instead of creating sibling output files.
- `placement.mount_face` identifies the envelope face the component is installed onto (`0..5` internal, `6..11` external). The component's physical contact face is derived from this automatically; no separate `envelope_face` or `rotation_matrix` is stored.

### Move Safety
- For any move request, prefer `safe-move-workflow.md` as the default entry point.
- Analyze first, then execute the fully safe move or closest safe result. Report any adjustment clearly.
- After any executed move, run a post-move collision verification before reporting success.
- `freecad-check-collision` and `freecad-move-obj` are document-only fallbacks; use only when no YAML source exists.

### Orientation & Rotation
- `--install-face <0..11>` places a component on a target envelope face. Faces `0..5` are internal (inside the envelope); faces `6..11` are external (outside the envelope, requires `envelope.outer_size` in YAML).
- Boxes are always axis-aligned; `dims[0]`, `dims[1]`, `dims[2]` are world X/Y/Z extents. To reorient a box, reorder its `dims`.
- Migrate legacy YAMLs carrying `envelope_face` or `rotation_matrix` with `freecad-migrate-placement --input <yaml> --in-place`.

### CAD Generation
- `freecad-create-assembly` is for explicit rebuild only; do not use it as the default after a move.
- `freecad-replace-component` is for swapping one generated placeholder with a detailed STEP part in an existing assembly.
- When only moving/rotating, update YAML in place and re-export the existing `STEP` file in place.
- Generated assemblies should include the envelope when YAML provides one.
- Always call `doc.recompute()` after geometry changes.
- After generation, switch the GUI to a fitted view automatically.

### Document Collision Checks
- Treat `getGlobalPlacement()` as the source of truth. Local `Shape` and `BoundBox` can be stale when a parent container moves.
- For container targets (`App::Part`, etc.), analyze descendant solids in global coordinates.

### File I/O
- **Snap sandbox**: FreeCAD via Snap cannot access arbitrary paths. Use `Path.home() / 'freecad_data'` for file I/O inside FreeCAD.
- Prefer first-class CLI commands over handwritten Python whenever the packaged command covers the task.
- Prefer `--file` over inline code for complex scripts.

### Safety
- Never auto-execute destructive actions (delete, unrelated overwrite) without user confirmation. Safe move execution is allowed after analysis.
- When verifying a YAML-to-CAD sync result, perform verification after the write completes, not in parallel.

## Error Handling

- **RPC connection failed**: Prompt user to check FreeCAD is running with the MCP addon active.
- **CLI not found / import error**: Report environment problem; fall back to `freecad-exec-code` workflow.
- **`"success": false`**: Display the returned error details to the user.
- **Post-move collision detected**: Surface the failure clearly; do not describe the move as successful.
