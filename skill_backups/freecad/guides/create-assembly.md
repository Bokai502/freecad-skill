# FreeCAD: Create Assembly

Create an Assembly container with hierarchical sub-parts from YAML. Use only when the user
explicitly requests a rebuilt assembly.

## Preferred CLI

```bash
freecad-create-assembly --input data/sample.yaml --doc-name SampleYamlAssembly
```

If unavailable, fall back to `freecad-exec-code --file`.

## Target Hierarchy

```
Assembly (Assembly::AssemblyObject or App::Part)
├── Motor_part (App::Part)
│   └── Motor (Part::Box or Part::Cylinder)
├── Sensor_part (App::Part)
│   └── Sensor (Part::Box)
└── Envelope_part (App::Part)
    └── EnvelopeShell (semi-transparent shell)
```

## Workflow

### Step 1: Create or reopen document

Close an existing document with the same name first to avoid naming conflicts.

### Step 2: Create assembly container

```python
try:
    assembly = doc.addObject("Assembly::AssemblyObject", "MyAssembly")
except Exception:
    assembly = doc.addObject("App::Part", "MyAssembly")
```

### Step 3: Add components

For each component:
1. Create `App::Part` sub-container, attach to assembly
2. Create shape based on YAML `shape` field (`Part::Box` for box, `Part::Cylinder` for cylinder)
3. Set dimensions from `dims` and position from `placement.position`. Boxes are axis-aligned; `dims[0..2]` map directly to world X/Y/Z extents.
4. For cylinders, derive the axis rotation from `placement.mount_face` via the canonical `CYLINDER_AXIS_ROTATIONS` table.
5. Attach shape to sub-part

### Step 4: Create envelope (when YAML provides one)

If YAML contains `envelope.outer_size` / `envelope.inner_size`: create a wireframe shell under
an `Envelope_part` container, centered at origin.

```python
envelope_shell.ViewObject.DisplayMode = "Wireframe"
envelope_shell.ViewObject.LineColor = (0.2, 0.5, 0.9, 0.0)  # steel blue
envelope_shell.ViewObject.LineWidth = 2.0
```

### Step 5: Colors, recompute, fit view, export

Set `ShapeColor` from RGBA and `Transparency = 40` on each component solid. Call
`doc.recompute()`, switch to isometric, execute `fitAll()`, export the assembly to the
target `STEP` path via `Import.export([assembly], path)`.

```python
obj.ViewObject.ShapeColor = (r, g, b, a)
obj.ViewObject.Transparency = 40
```

## Rules

- Use `try/except` for `Assembly::AssemblyObject` (version-dependent).
- Never attach raw shapes directly to the assembly; wrap in `App::Part`.
- Use `assembly.addObject(part)` then `part.addObject(shape)` in correct order.
