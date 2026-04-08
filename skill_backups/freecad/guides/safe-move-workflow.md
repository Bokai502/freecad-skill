# FreeCAD: Safe Move Workflow

Default high-safety workflow for moving a part. Analyze first, then execute, then verify.

## Inputs

Collect before execution:
- Target part / component ID
- Requested move vector
- Source YAML path (required for YAML branch)
- Document name and object name (if starting from FreeCAD)

## Step 1: Detect Source of Truth

- If a source YAML file exists → **YAML branch** (preferred).
- If starting from a FreeCAD document → locate the source YAML first. Use **document-only branch** only when no YAML can be found.
- Without source YAML, stop after analysis and explain that YAML output cannot be completed.

## Step 2: Analyze (never move yet)

### YAML Branch — `freecad-yaml-safe-move`

```bash
# Translation only
freecad-yaml-safe-move \
  --input data/sample.yaml --output data/sample.yaml \
  --component P001 --move 50 50 0

# Move to another envelope face
freecad-yaml-safe-move \
  --input data/sample.yaml --output data/sample.yaml \
  --component P002 --install-face 4 --move 0 0 0

# In-place rotation on same face
freecad-yaml-safe-move \
  --input data/sample.yaml --output data/sample.yaml \
  --component P002 --spin 90 --move 0 0 0

# Combine face change + spin
freecad-yaml-safe-move \
  --input data/sample.yaml --output data/sample.yaml \
  --component P002 --install-face 4 --spin 90 --move 0 0 0

# With CAD sync
freecad-yaml-safe-move \
  --input data/sample.yaml --output data/sample.yaml \
  --component P001 --move 50 50 0 \
  --sync-cad --doc-name SampleYamlAssembly
```

**Behavior:**
- Treats each component as an axis-aligned box (`placement.position` + `dims`).
- Without `--install-face`: preserves orientation, in-plane safe move on current face.
- With `--install-face <0..5>`: rotates component onto the target envelope face, centers it, then applies `--move` as in-plane offset.
- With `--spin <degrees>`: rotates in-place around envelope-face normal (multiples of 90), keeps mount point fixed.
- If full move is safe → applies directly. If collision → searches for closest safe prefix.
- If no safe point exists → writes the constrained result back to YAML (does not revert).
- Without `--sync-cad`: pure offline YAML operation, no RPC needed.
- With `--sync-cad`: pushes result into the live FreeCAD document after YAML write.

**Output fields:** input/output paths, target component, requested move, safe status, blockers, `rotation_matrix`, `mount_point`, spin details, final position, CAD sync result.

Read the output and convert it into a user-facing move summary.

### Document-Only Branch (fallback)

Use only if no YAML source exists.

1. Inspect the target object and current placement.
2. Run `freecad-check-collision` (see `check-collision.md` for details and fallback script).
3. Compute the maximum safe move distance or safe position before mutation.
4. Convert result into a user-facing move summary.

## Step 3: Execute

Before mutation, record: the requested move, whether it can be applied exactly, the closest safe move if adjusted, and what constraints caused the adjustment.

### YAML Branch Execution

1. Run `freecad-yaml-safe-move` so the safe result overwrites the source YAML in place (same path for `--input` and `--output`).
2. Run again with `--sync-cad --doc-name <doc>` to update the live CAD document.
3. Save the FreeCAD document to its existing `FCStd` path.
4. Do **not** create a new assembly by default.

Return: updated YAML path, updated FCStd path, document result, summary of move and any adjustment.

### Document-Only Branch Execution

1. Apply the safe move using a Python script via `freecad-exec-code --file`:

```python
import FreeCAD, json

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
print(json.dumps({"old_position": old_pos, "new_position": [new.x, new.y, new.z], "mode": MODE}))
```

2. Re-run collision verification immediately after move (same global-shape method as pre-check).
3. If post-move collision detected → surface failure, do not report success.
4. Reflect final position back into source YAML if one exists.
5. Save existing document to its current FCStd path.

Return: updated YAML path, updated FCStd path, document result, summary of move and any adjustment.

## Step 4: Post-Move Verification

Mandatory for both branches. Run collision check after execution. Only report success if verification is clean.
