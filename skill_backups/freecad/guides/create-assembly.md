# FreeCAD: Create Placeholder Assembly From `layout_topology.json` + `geom.json`

Create a placeholder Assembly container with hierarchical sub-parts from the
layout dataset. Use this when the user explicitly requests a rebuilt assembly
from topology and geometry only.

`sample.yaml` is not part of the new workflow. It may exist as a backup fixture, but
`freecad-create-assembly` should use `layout_topology.json` and `geom.json` as the source.

## Preferred CLI

```bash
freecad-create-assembly \
  --doc-name LayoutAssembly
```

By default, the CLI resolves relative paths from `FREECAD_WORKSPACE_DIR` in
the runtime config or environment, reads `./01_layout/layout_topology.json` and
`./01_layout/geom.json`, then exports the placeholder assembly to
`./02_geometry_edit/geometry_after.step` and sibling `geometry_after.glb`.

FreeCAD consumes a normalized intermediate spec during RPC execution and exports
the placeholder model directly to `geometry_after.step` and
`geometry_after.glb`.

## CAD Modeling Inputs Derived From The Dataset

### Envelope

Use `geom.outer_shell` as the envelope source:

- `outer_bbox.min/max` -> `envelope.outer_size`
- `inner_bbox.min/max` -> `envelope.inner_size`
- `thickness` -> `envelope.shell_thickness`

### Component Identity And Metadata

Use `layout_topology.placements[]` as the placement list:

- `component_id` -> FreeCAD object / part id, e.g. `P000`
- `semantic_name`, `kind` -> preserved metadata

Resolve the backing `geom.components[...]` entry with this order:

- preferred: `geom.components[placement.component_id]`
- fallback: exactly one `geom.components[*].component_id == placement.component_id`

Use the resolved `geom.components[component_id]` entry for component geometry:

- `shape`
- `dims`
- `color`
- `mass`
- `power`
- optional `model`

### Placement And Orientation

Derive the modeling placement from both files:

- `placement.mount_face_id`:
  owner-qualified box/envelope install face id from `layout_topology.json`
- `placement.component_mount_face_id`:
  owner-qualified component-local install face id from `layout_topology.json`
- runtime orientation:
  derive from `component_mount_face_id -> mount_face_id` plus
  `placement.alignment.in_plane_rotation_deg`
- `placement.position`:
  treat `geom.components[*].position` as the world-space bbox minimum, then
  back-solve the component local origin from `dims + derived runtime orientation`

For the current dataset this is enough to reproduce the original box bounds exactly, including
external parts whose local mount face does not match the world-facing contact face without a
derived rotation.

## Target Hierarchy

```text
Assembly (Assembly::AssemblyObject or App::Part)
├── P000_part (App::Part)
│   └── P000 (Part::Box or Part::Cylinder)
├── P008_part (App::Part)
│   └── P008 (...)
└── Envelope_part (App::Part)
    └── EnvelopeShell (semi-transparent shell)
```

Use `layout_topology.placements[].component_id` as the stable FreeCAD object name.

## Workflow

### Step 1: Load And Normalize The Dataset

1. Read `layout_topology.json`.
2. Read `geom.json`.
3. Validate that every placement resolves to exactly one `geom.components[...]` entry.
   Prefer `placement.component_id -> geom.components[*].component_id`.
4. Build a normalized assembly spec containing:
   - `envelope.outer_size`
   - `envelope.inner_size`
   - `envelope.shell_thickness`
   - `components[component_id].shape`
   - `components[component_id].dims`
   - `components[component_id].placement.position`
   - `components[component_id].placement.mount_face_id`
   - `components[component_id].placement.component_mount_face_id`
   - `components[component_id].placement.alignment`

### Step 2: Create Or Reopen Document

Close an existing document with the same name first to avoid naming conflicts.

### Step 3: Create Assembly Container

```python
try:
    assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
except Exception:
    assembly = doc.addObject("App::Part", "Assembly")
```

### Step 4: Add Components

For each normalized component:

1. Create `App::Part` sub-container named `<component_id>_part`
2. Create the solid from `shape`
3. Set dimensions from `dims`
4. Apply `placement.position`
5. Derive runtime orientation from `mount_face_id + component_mount_face_id + alignment`
6. Set color when provided
7. Attach the solid under the component part

Boxes and cylinders both use the normalized placement. Cylinders still use the existing
axis helper logic derived from `component_mount_face_id`.

### Step 5: Create Envelope

Create the outer-minus-inner shell when the normalized spec contains:

- `envelope.outer_size`
- `envelope.inner_size`
- `envelope.shell_thickness`

Keep the envelope centered at the origin.

```python
envelope_shell.ViewObject.DisplayMode = "Wireframe"
envelope_shell.ViewObject.LineColor = (0.2, 0.5, 0.9, 0.0)
envelope_shell.ViewObject.LineWidth = 2.0
```

### Step 6: Recompute, Fit View, Export

Set component colors, call `doc.recompute()`, switch to an isometric fitted view, and export:

- `geometry_after.step`
- sibling `geometry_after.glb`

## Rules

- Prefer `--layout-topology` + `--geom` for the new dataset.
- If these flags are omitted, use `./01_layout/layout_topology.json` and `./01_layout/geom.json` from the configured workspace root.
- If `--output` is omitted, write `./02_geometry_edit/geometry_after.step` and sibling `.glb`.
- If `--output` is provided, use only its directory or parent path; the exported filenames must still be `geometry_after.step` and `geometry_after.glb`.
- Treat `sample.yaml` as backup only; do not use it as the primary build input.
- Preserve `component_id` from `layout_topology.json` as the user-facing CAD object id.
- Derive runtime orientation from topology instead of assuming identity for external parts.
- Support only orthogonal in-plane rotations; reject arbitrary non-90-degree `in_plane_rotation_deg`.
- Never attach raw shapes directly to the assembly; wrap them in `App::Part`.
- Use `assembly.addObject(part)` then `part.addObject(shape)` in that order.
