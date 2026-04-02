# FreeCAD: Load YAML Data

Batch-create objects in FreeCAD from a YAML specification file via `freecad-exec-code --file`.

## Important

In a move request, this is a post-confirmation step. The recommended top-level path is
`safe-move-workflow.md`.

## When to Use

- When the user provides a YAML file describing components, dimensions, positions, and metadata.
- When rebuilding geometry in FreeCAD from an updated layout file.
- When the task needs a regenerated assembly after a confirmed move.

## YAML Format

```yaml
components:
  COMPONENT_ID:
    shape: box
    dims: [L, W, H]
    category: avionics
    color: [R, G, B, A]
    placement:
      position: [x, y, z]
```

Fields such as `mass`, `power`, `mount_face`, and `mount_point` may pass through the YAML even if
only some of them are used directly for geometry generation.

## Workflow

### Step 1: Copy YAML into a Snap-accessible path

FreeCAD installed through Snap cannot access arbitrary host paths. Copy the YAML into the writable
FreeCAD data directory:

```bash
freecad-exec-code "import os; print(os.path.join(os.path.expanduser('~'), 'freecad_data'))"
```

Then copy the YAML from the normal shell into that directory.

### Step 2: Write and execute a loader script

Write a Python script to `/tmp/load_yaml.py`, then run:

```bash
freecad-exec-code --file /tmp/load_yaml.py
```

Key patterns in the loader script:

- read YAML from `Path.home() / 'freecad_data' / ...`
- parse with `yaml.safe_load`
- loop through `components.items()`
- create the envelope shell as well when YAML `envelope` data exists
- use `dims` for `Length`, `Width`, and `Height`
- use `placement.position` for `Placement.Base`
- set `ShapeColor` from `color` when present
- fit the GUI view after generation when the document is intended for visual inspection
- save the resulting document or assembly file

## Rules

- Always use `Path.home()` for paths inside FreeCAD.
- Use `yaml.safe_load()` rather than unsafe loaders.
- Call `doc.recompute()` after all objects are created.
- If the task is to build a new assembly from YAML, prefer `create-assembly.md` or the packaged
  `freecad-create-assembly` CLI.
- Use this after the user has confirmed the approved move and the YAML has been updated.
- Prefer `--file` over inline code for complex scripts.
