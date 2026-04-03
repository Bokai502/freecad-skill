# FreeCAD: Move Object

Apply an already computed safe move to an object. This is a document-only fallback step for cases where
no YAML source exists and the YAML-first workflow cannot be used.

## Important

Do not use this as the default first step when the user asks to move a part. Prefer
`safe-move-workflow.md` first so the move is analyzed from YAML before any final mutation whenever
the layout file exists.

## When to Use

- When the safe move has already been computed.
- When the safe move distance or safe position has already been analyzed.
- When you need to apply the final safe translation to a document object and no YAML-driven sync
  path is available.

## Workflow

### Step 1: Prepare the move script

Write a Python script to `/tmp/move_object.py` and fill in `DOC_NAME`, `OBJ_NAME`, and either
delta or absolute mode:

```python
import FreeCAD
import json

DOC_NAME = "MyDoc"
OBJ_NAME = "P001"
MODE = "delta"  # "delta" or "absolute"
DX, DY, DZ = 50, 30, 0

doc = FreeCAD.getDocument(DOC_NAME)
obj = doc.getObject(OBJ_NAME)
if obj is None:
    raise RuntimeError(f"Object '{OBJ_NAME}' not found")

old = obj.Placement.Base
old_pos = [old.x, old.y, old.z]

if MODE == "delta":
    new = old + FreeCAD.Vector(DX, DY, DZ)
else:
    new = FreeCAD.Vector(DX, DY, DZ)

obj.Placement.Base = new
doc.recompute()
new_pos = [new.x, new.y, new.z]

print(json.dumps({"old_position": old_pos, "new_position": new_pos, "mode": MODE}))
```

### Step 2: Execute

```bash
freecad-exec-code --file /tmp/move_object.py
```

### Step 3: Verify after execution

Immediately re-run the collision workflow from `check-collision.md` against the moved object using
global transformed descendant shapes. Only report success if the post-move verification is clean or
matches the computed safe collision outcome.

## Rules

- Use this only after the safe movement plan has been computed.
- Prefer `freecad-yaml-safe-move --sync-cad` over this step when a YAML source is available.
- Collision analysis belongs before this step, not after it.
- Prefer `safe-move-workflow.md` as the top-level path and `check-collision.md` for the analysis stage.
- `delta` means relative offset from the current position; `absolute` means set the final position directly.
- Always call `doc.recompute()` after changing `Placement.Base`.
- If the target is a container such as `App::Part`, do not assume moving the container updates child `Shape` coordinates for analysis; rely on `getGlobalPlacement()` during verification.
