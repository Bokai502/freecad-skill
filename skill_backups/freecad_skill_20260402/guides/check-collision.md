# FreeCAD: Check Collision

Analyze interference between objects and optionally compute the maximum safe move distance. This is
a document-only fallback path. Prefer the YAML-first `freecad-yaml-safe-move` workflow whenever a
layout file exists, and use the packaged `freecad-check-collision` CLI only when no YAML source of
truth is available.

## Important

This script is the analysis stage for a document-only move request. Use it before any final move is
executed when no YAML source is available. The recommended top-level entry for move requests is
`safe-move-workflow.md`.

## When to Use

- When the user wants to verify whether a requested move would cause overlap.
- When planning a move and needing the maximum safe distance or safe position.
- When the request starts from an already opened FreeCAD document object.

## Workflow

### Step 1: Prefer the packaged CLI

Run the CLI first:

```bash
freecad-check-collision --help
```

If the command is available for the target workflow, use it instead of handwritten analysis code.
The command should be treated as the default document collision checker for this skill.

### Step 2: Fallback to `freecad-exec-code` only when needed

If `freecad-check-collision` cannot be used because the environment is missing its implementation,
write a Python script to `/tmp/check_collision.py` and run:

```bash
freecad-exec-code --file /tmp/check_collision.py
```

Key patterns in the fallback script:

- filter `doc.Objects` to the target set
- if the moving target is an `App::Part`, `PartDesign::Body`, `Link`, or other container-like object, analyze its solid descendants instead of only the container object
- compute collision shapes in global coordinates, not local object coordinates
- exclude the moving object itself, its descendants, its ancestors, assembly containers, origin axes/planes, and known envelope helpers
- use transformed global shapes with `distToShape` as a pre-filter
- confirm overlap with `common()` on the transformed global shapes
- return a JSON summary of collisions

### Step 3: Optional safe-move computation

If a move direction is known, let `freecad-check-collision` compute the safe move when supported.
If you are in fallback mode, binary search for the maximum safe move distance in the script.

Key patterns:

- normalize the requested move direction
- use `lo` and `hi` bounds over the move length
- temporarily set `target.Placement.Base` during each probe, recompute, then rebuild global transformed shapes for every probe
- restore the original placement after analysis
- return `safe_distance`, `ratio`, and `safe_position`

### Step 4: Mandatory global-shape helper

The analysis script must use a helper equivalent to the following pattern so parent container
placement is included in collision checks:

```python
def global_shape(obj):
    shape = obj.Shape.copy()
    placement = obj.getGlobalPlacement()
    shape.transformShape(placement.toMatrix(), True)
    return shape
```

For container objects, gather all solid descendants and run collision tests on each descendant's
global shape.

## Detection API

| Method | Purpose |
|--------|---------|
| `shape.distToShape(other)` | Fast distance pre-check |
| `shape.common(other)` | Boolean intersection confirmation |

## Rules

- `freecad-check-collision` is the preferred path for document collision analysis in this skill.
- If `freecad-check-collision` fails with an import or entry-point error, report that the CLI is not installed correctly and only then use the fallback scripted workflow.
- Always use `distToShape` before `common` to avoid unnecessary expensive boolean operations.
- Do not trust `obj.Shape`, `Shape.BoundBox`, or child local `Placement` alone for collision checks when a parent container can move.
- Treat `getGlobalPlacement()` as the source of truth for document-space collision analysis.
- Exclude envelope or helper objects by name pattern when appropriate, but never exclude real solids only because they are descendants of an assembly.
- Binary search must not permanently move the object; always restore the original position during analysis.
- The returned JSON must list which concrete solid descendants collide, not only the top-level container name.
- Typical workflow: `safe-move-workflow` -> `check-collision` -> present the proposal to the user -> after confirmation `move-object`.
- Prefer `--file` over inline code for complex scripts.
