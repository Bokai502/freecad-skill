# FreeCAD: Load YAML Data

Batch-create objects in FreeCAD from a YAML specification file via `freecad-exec-code --file`.
This is an optional post-move rebuild step; prefer `freecad-create-assembly` for full assembly generation.

## YAML Format

```yaml
components:
  COMPONENT_ID:
    shape: box          # or "cylinder"
    dims: [L, W, H]    # box: [Length, Width, Height]; cylinder: [Radius, Height]
    category: avionics
    color: [R, G, B, A]
    placement:
      position: [x, y, z]
```

Fields like `mass`, `power`, `mount_face`, and `mount_point` may be present in the YAML
but are not all used directly for geometry generation. Boxes are axis-aligned (no stored rotation);
cylinder axis orientation is derived from `mount_face`.

## Workflow

### Step 1: Stage YAML into Snap-accessible path

```bash
freecad-exec-code "import os; print(os.path.join(os.path.expanduser('~'), 'freecad_data'))"
```

Copy the YAML from the normal shell into that directory.

### Step 2: Write and execute a loader script

Write a Python script to `/tmp/load_yaml.py`, then run:

```bash
freecad-exec-code --file /tmp/load_yaml.py
```

Key patterns:
- Read YAML from `Path.home() / 'freecad_data' / ...`
- Parse with `yaml.safe_load`
- Loop `components.items()`
- Create shapes based on `shape` field: `Part::Box` for `box`, `Part::Cylinder` for `cylinder`
- For box: set `Length`, `Width`, `Height` from `dims`
- For cylinder: set `Radius`, `Height` from `dims`
- Apply `placement.position` to `Placement.Base` (boxes remain axis-aligned)
- For cylinders, apply rotation derived from `placement.mount_face` (canonical `CYLINDER_AXIS_ROTATIONS`)
- Create envelope shell when YAML `envelope` data exists
- Set `ShapeColor` from `color`
- Fit GUI view after generation
- Export the assembly to a `STEP` file via `Import.export([assembly], path)`
