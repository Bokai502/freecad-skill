# FreeCAD: Create Assembly

Create an Assembly container with hierarchical sub-parts from YAML. Prefer the packaged
`freecad-create-assembly` CLI and only fall back to `freecad-exec-code --file` when needed.

## Important

For move requests, this is an optional post-move regeneration step. The recommended top-level path is
`safe-move-workflow.md`.

## When to Use

- When building a multi-component model that needs an assembly container.
- When grouping parts hierarchically.
- When the user explicitly wants a rebuilt assembly from an updated YAML after a safe move has been written.

## Target Hierarchy

```text
Assembly (Assembly::AssemblyObject or App::Part)
|- Motor_part (App::Part)
|  |- Motor (Part::Box)
|- Sensor_part (App::Part)
|  |- Sensor (Part::Box)
|- ...
```

## Workflow

### Step 1: Create or reopen the document

Use `create-document` or `FreeCAD.newDocument()` in code. To re-run safely, close an existing
document with the same name first.

Preferred CLI:

```bash
freecad-create-assembly --input data/sample.updated.yaml --doc-name SampleYamlAssembly
```

### Step 2: Create the assembly container

Prefer `Assembly::AssemblyObject` when available, otherwise fall back to `App::Part`.

```python
try:
    assembly = doc.addObject("Assembly::AssemblyObject", "MyAssembly")
except Exception:
    assembly = doc.addObject("App::Part", "MyAssembly")
```

### Step 3: Add components

For each component:

1. create a sub-part container with `App::Part`
2. attach that part to the assembly
3. create the shape such as `Part::Box`
4. set dimensions and placement
5. attach the shape to the sub-part

If YAML placement includes `rotation_matrix`, apply it to the generated object placement instead of
assuming identity orientation.

### Step 4: Create the envelope when YAML provides one

If the YAML contains `envelope.outer_size` and `envelope.inner_size`, create an envelope shell and
attach it under an `Envelope_part` container.

- prefer a single visible shell object such as `EnvelopeShell`
- keep it semi-transparent for visual review
- center it around the document origin so the component coordinates match the YAML layout
### Step 5: Optional colors

Set `ShapeColor` from category mappings or RGBA values if needed.

### Step 6: Recompute, fit the GUI view, and save

Call `doc.recompute()`, switch the active GUI view to a suitable overview such as isometric,
execute `fitAll()`, and save the result to the target output path.

## Rules

- Use `try/except` for `Assembly::AssemblyObject` because it is version-dependent.
- Prefer `freecad-create-assembly` over ad hoc scripts when generating from YAML.
- Never attach raw shapes directly to the assembly; wrap them in `App::Part`.
- Use `assembly.addObject(part)` and `part.addObject(shape)` in the correct order.
- `Placement.Base` on the shape sets the world position.
- When YAML provides `placement.rotation_matrix`, apply that rotation together with
  `Placement.Base` so reoriented components match the YAML assembly intent.
- If YAML provides envelope data, include the envelope in the generated CAD so the assembly context is complete.
- Call `doc.recompute()` after all objects are added.
- After generation, set a readable GUI view automatically instead of leaving the camera in an arbitrary state.
- Close before re-run to avoid naming conflicts.
- In move workflows, use this only when the user explicitly asks for a rebuilt assembly after the safe move has been written to YAML.
- For Snap-based FreeCAD, use `Path.home() / 'freecad_data'` for file I/O.
