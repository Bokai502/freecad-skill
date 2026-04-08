# FreeCAD: Check Collision

Document-only fallback for interference analysis when no YAML source exists. Used as the analysis
stage within `safe-move-workflow.md`.

## Step 1: Prefer the Packaged CLI

```bash
freecad-check-collision --help
```

If available, use it as the default document collision checker.

## Step 2: Fallback to `freecad-exec-code`

If the CLI is unavailable, write a Python script to `/tmp/check_collision.py` and run:

```bash
freecad-exec-code --file /tmp/check_collision.py
```

Key patterns in the fallback script:

- Filter `doc.Objects` to the target set
- For container objects (`App::Part`, `PartDesign::Body`, `Link`), analyze solid descendants
- Compute collision shapes in **global coordinates** using the mandatory helper:

```python
def global_shape(obj):
    shape = obj.Shape.copy()
    placement = obj.getGlobalPlacement()
    shape.transformShape(placement.toMatrix(), True)
    return shape
```

- Exclude: the moving object itself, its descendants/ancestors, assembly containers, origin axes/planes, envelope helpers
- Use `distToShape` as pre-filter, confirm with `common()` on transformed global shapes
- Return JSON listing concrete colliding **descendants**, not just container names

## Step 3: Optional Safe-Move Computation

If a move direction is known, compute the maximum safe distance via binary search:

- Normalize the requested move direction
- Use `lo`/`hi` bounds over move length
- Temporarily set `target.Placement.Base` during each probe, recompute, rebuild global shapes
- Restore original placement after analysis
- Return `safe_distance`, `ratio`, `safe_position`

## Detection API

| Method | Purpose |
|--------|---------|
| `shape.distToShape(other)` | Fast distance pre-check |
| `shape.common(other)` | Boolean intersection confirmation |

Always use `distToShape` before `common` to avoid expensive boolean ops.
