---
name: freecad
description: "Unified FreeCAD skill for 3D modeling via RPC. Covers document management, object CRUD, Python code execution, view capture, parts library operations, YAML layout pre-processing, and safe move workflows."
argument-hint: "[action] [args...]"
allowed-tools: "Bash(*), Read, Write, Edit"
---

# FreeCAD Unified Skill

All-in-one skill for interacting with FreeCAD and related YAML layout files. This skill delegates to
action guides based on the requested task.

## Context: $ARGUMENTS

## Prerequisites

- FreeCAD must be running with the **FreeCADMCP addon** active (RPC server on `localhost:9875` by default) for RPC-based commands.
- Use the Python environment where `freecad-cli-tools` is installed. On this machine that is currently `base`.
- Prefer the packaged CLI entry points when they exist:
  - `freecad-yaml-safe-move` for YAML-first move analysis, YAML rewrite, and optional CAD sync
  - `freecad-create-assembly` for regenerating CAD from YAML with envelope and automatic view fitting
  - `freecad-check-collision` only when there is no YAML source of truth and a document-only analysis is needed
  - `freecad-move-obj` only when there is no YAML source of truth and a document-only execution step is needed
- If a CLI entry point exists but fails to start because its Python module is missing, treat that as an environment problem and fall back to the documented `freecad-exec-code` workflow only as a temporary workaround.

## Available Actions

Determine the user's intent and read the corresponding guide from the `guides/` folder for detailed instructions.

| Action | Script | When to Use |
|--------|--------|-------------|
| **Create Document** | `guides/create-document.md` | Start a new project, create a blank document |
| **List Documents** | `guides/list-documents.md` | Find open document names |
| **Create Object** | `guides/create-object.md` | Add 3D shapes, draft elements, FEM components |
| **Edit Object** | `guides/edit-object.md` | Change dimensions, placement, color of an existing object |
| **Delete Object** | `guides/delete-object.md` | Remove an object from a document |
| **Get Object** | `guides/get-object.md` | Inspect a single object's properties |
| **Get Objects** | `guides/get-objects.md` | List all objects in a document |
| **Execute Code** | `guides/execute-code.md` | Run arbitrary Python in FreeCAD (boolean ops, batch, advanced) |
| **Get View** | `guides/get-view.md` | Capture screenshots and visual review |
| **Get Parts List** | `guides/get-parts-list.md` | Browse available parts in the library |
| **Insert Part** | `guides/insert-part-from-library.md` | Insert a pre-made part from the library |
| **Load YAML Data** | `guides/load-yaml-data.md` | Batch-create objects from a YAML spec file |
| **YAML Safe Move** | `guides/yaml-safe-move.md` | Analyze and rewrite a YAML component move with collision and boundary checks |
| **Safe Move Workflow** | `guides/safe-move-workflow.md` | Default workflow for analyzing a move, executing the safe result, and updating YAML/CAD without creating a new assembly by default |
| **Create Assembly** | `guides/create-assembly.md` | Create an Assembly container with hierarchical sub-parts |
| **Move Object** | `guides/move-object.md` | Apply an already computed safe move to a document object |
| **Check Collision** | `guides/check-collision.md` | Analyze interference and compute safe move options before execution |

## Routing Logic

1. **Read the matching guide** based on the table above, use the `Read` tool to open the corresponding `guides/*.md` file.
2. **Prefer the highest-level safe workflow** when multiple scripts seem relevant.
3. **Use lower-level scripts only as substeps** of a larger workflow unless the user explicitly asks for that specific low-level operation.

## Common Patterns

### New project from scratch
1. `create-document` -> create a blank document
2. `create-object` -> add shapes
3. `get-view` -> capture screenshots and review

### Build assembly from YAML
1. `safe-move-workflow` -> analyze any requested part move first
2. `yaml-safe-move` -> update the YAML with the safe move result
3. keep the current CAD document synced instead of creating a new assembly by default
4. `create-assembly` only when the user explicitly wants a rebuilt assembly file
5. `get-view` -> verify visually

### Move YAML with collision safety
1. `safe-move-workflow` -> analyze the requested move
2. `yaml-safe-move` -> write the updated YAML using the safe move result
3. sync CAD from the written YAML when an open document should be updated
4. `create-assembly` only when the user explicitly asks for a rebuilt assembly file

### Move a document object with collision safety
1. `safe-move-workflow` -> locate the source YAML first
2. `yaml-safe-move` -> compute the safe move from YAML and write the updated YAML
3. `yaml-safe-move --sync-cad` or full YAML reload -> sync the updated result into FreeCAD
4. `create-assembly` only when the user explicitly asks for a full regenerated document
5. Use document-only commands only if no YAML source exists

## Global Rules

- For any request to move a part, prefer `safe-move-workflow` as the default entry point instead of directly calling `move-object`.
- Default safety rule: analyze first, then execute the fully safe move or the closest safe result on the requested path, and report any adjustment clearly.
- Prefer first-class CLI commands over handwritten ad hoc Python whenever the packaged command covers the task.
- When a YAML layout file exists, treat that YAML file as the source of truth for move planning and execution.
- For document-space collision checks, treat `getGlobalPlacement()` as the source of truth. Local `Shape` and local `BoundBox` can be stale or misleading when a parent container such as `App::Part` moves.
- `freecad-yaml-safe-move` is the preferred YAML-first move command; it can work offline on YAML only, or it can sync the written result into CAD when asked.
- In the intended data model, YAML `placement.mount_face` identifies the component's own mounting face, not the envelope face.
- `freecad-yaml-safe-move` supports two YAML-first workflows:
  - translation-only moves that preserve the current orientation
  - reorientation moves that keep `placement.mount_face` as the component's own face while changing `placement.envelope_face` and `placement.rotation_matrix`
- For reorientation, use `--install-face <0..5>` to rotate the component so its own `mount_face` is installed onto the requested envelope face. The command then applies the requested `--move` as an in-plane offset on that target face.
- When the target FreeCAD instance runs inside WSL, YAML-to-CAD sync may need a WSL-visible path and
  an explicit RPC host if Windows `localhost` forwarding is flaky.
- `freecad-create-assembly` is the preferred CLI only when a new CAD document from YAML is explicitly needed.
- Generated assemblies should include the envelope when YAML provides one.
- When only moving an existing layout, prefer syncing the current CAD document instead of creating a new assembly.
- After CAD generation, switch the GUI to a readable fitted view automatically.
- `freecad-check-collision` is a document-only fallback CLI for FreeCAD document objects when no YAML source is available.
- `freecad-move-obj` is a document-only fallback CLI for applying a computed safe move when no YAML source is available.
- When verifying a YAML-to-CAD sync or regeneration result, avoid reading back document state in parallel with the mutation step; perform verification after the write completes.
- `check-collision` is an analysis tool, not the final move step.
- `move-object` is an execution tool and should be used only after the safe final move has been computed.
- After any executed move, run a post-move collision verification before reporting success.
- **Snap sandbox**: FreeCAD installed via Snap cannot access paths outside its home. Use `Path.home() / 'freecad_data'` for file I/O inside FreeCAD. Copy files in/out from the normal shell.
- RPC-oriented commands usually return JSON output; check `"success": true`.
- Common optional flags for RPC commands: `--host <host>`, `--port <port>` (defaults: `localhost`, `9875`).
- Always call `doc.recompute()` after geometry changes in execute-code.
- Never auto-execute destructive actions such as delete or unrelated overwrite operations without user confirmation. Safe move execution is allowed after analysis.
