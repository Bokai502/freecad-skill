# FreeCAD: Execute Code

Run arbitrary Python inside FreeCAD's interpreter via RPC. Full access to `FreeCAD`, `FreeCADGui`,
`Part`, `Draft`, `Fem`, etc.

## Invocation

**Inline:**
```bash
freecad-exec-code "import FreeCAD; print(FreeCAD.ActiveDocument.Name)"
```

**From file (preferred for multi-line):**
```bash
freecad-exec-code --file /path/to/script.py
```

**From stdin:**
```bash
cat <<'EOF' | freecad-exec-code
import FreeCAD, Part
doc = FreeCAD.ActiveDocument
box = doc.addObject('Part::Box', 'MyBox')
box.Length = 50; box.Width = 30; box.Height = 20
doc.recompute()
print('Box created successfully')
EOF
```

## Output

JSON with `"success": true/false` and `"message"` containing `print()` output.

```json
{"success": true, "message": "Box created successfully"}
```

## Rules

- Use `print()` to produce output returned in `"message"`.
- Prefer `--file` over inline for complex scripts.
