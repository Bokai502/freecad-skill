# FreeCAD: Execute Code

Run arbitrary Python code inside FreeCAD's Python environment via the RPC server. This gives full access to FreeCAD's API (`FreeCAD`, `FreeCADGui`, `Part`, `Draft`, `Fem`, etc.).

## When to Use

- When detailed customization or specialized operations are needed beyond basic object creation/editing.
- For complex shape generation, boolean operations, parametric modeling, or batch processing.
- When directly accessing FreeCAD's Python API is required.
- When the user provides a Python snippet to run in FreeCAD.

## Workflow

### Step 1: Prepare the Code

Write the Python code that uses FreeCAD's API. Use `print()` for output messages. Always call `doc.recompute()` after making changes.

### Step 2: Execute via CLI

**Option A — Inline code:**
```bash
freecad-exec-code "import FreeCAD; print(FreeCAD.ActiveDocument.Name)"
```

**Option B — From a file:**
```bash
freecad-exec-code --file /path/to/script.py
```

**Option C — From stdin (for multi-line code):**
```bash
cat <<'EOF' | freecad-exec-code
import FreeCAD
import Part

doc = FreeCAD.ActiveDocument
box = doc.addObject('Part::Box', 'MyBox')
box.Length = 50
box.Width = 30
box.Height = 20
doc.recompute()
print('Box created successfully')
EOF
```

**Optional flags:**
- `--host <host>` — FreeCAD RPC host (default: `localhost`)
- `--port <port>` — FreeCAD RPC port (default: `9875`)

### Step 3: Verify Result

The script outputs JSON. Check `"success": true` and `"message"` for `print()` output.

Example success output:
```json
{
  "success": true,
  "message": "Box created successfully"
}
```

## Examples

### Create a box with custom dimensions
```bash
freecad-exec-code "import FreeCAD; doc = FreeCAD.ActiveDocument; box = doc.addObject('Part::Box','MyBox'); box.Length=50; box.Width=30; box.Height=20; doc.recompute(); print('Done')"
```

### Boolean cut operation from file
Write the script to a temp file first, then execute:
```bash
freecad-exec-code --file /tmp/freecad_boolean.py
```

## Rules

- The code runs in FreeCAD's Python interpreter with full access to all FreeCAD modules.
- Use `print()` to produce output messages returned in the `"message"` field.
- Always call `doc.recompute()` after making geometry changes.
- Errors in the code will be returned as `"success": false` with error details.
- For multi-line code, prefer the `--file` or stdin approach over inline.
