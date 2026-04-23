# FreeCAD: CRUD & Library Reference

Quick reference for document management, object CRUD, and parts library operations.

## Command Summary

| Command | Usage | Description |
|---------|-------|-------------|
| `freecad-create-doc` | `freecad-create-doc "<name>"` | Create a new empty document |
| `freecad-list-docs` | `freecad-list-docs` | List open documents as `[{name, label}, ...]` |
| `freecad-get-objs` | `freecad-get-objs "<doc>"` | List all objects in a document (JSON array) |
| `freecad-get-obj` | `freecad-get-obj "<doc>" "<obj>"` | Get detailed properties of one object (JSON) |
| `freecad-create-obj` | `freecad-create-obj "<doc>" "<type>" "<name>" -p '<json>'` | Create a new object |
| `freecad-edit-obj` | `freecad-edit-obj "<doc>" "<obj>" '<json>'` | Update properties of an existing object |
| `freecad-del-obj` | `freecad-del-obj "<doc>" "<obj>"` | Delete an object (requires user confirmation) |
| `freecad-get-parts` | `freecad-get-parts` | List parts library paths (JSON array) |
| `freecad-insert-part` | `freecad-insert-part "<relative_path>"` | Insert a library part into active document |

All commands return JSON with `"success": true/false`. All accept optional `--host`/`--port` flags.

## Typical Workflows

- **Before any modification**: run `freecad-get-objs` to confirm current state.
- **Before editing**: run `freecad-get-obj` to discover property names. After editing: verify with `freecad-get-obj`.
- **Before inserting a library part**: browse with `freecad-get-parts`, then adjust placement with `freecad-edit-obj`.
- **Deletion is irreversible**: always confirm with the user first. Dependent objects (e.g., FEM constraints) may break.

## Create Object Details

`freecad-create-obj` supports `Part::`, `Draft::`, `PartDesign::`, and `Fem::` object types.

**Optional flags:**
- `-p '<json>'` or `--properties '<json>'` — inline JSON properties
- `--properties-file <path>` — JSON file with properties
- `--analysis <name>` — associate FEM objects with an analysis

**Property patterns:**
- Position: `"Placement": {"Base": {"x": 5, "y": 5, "z": 0}}`
- Color: `"ViewObject": {"ShapeColor": [0.5, 0.5, 0.5, 1.0]}` (RGBA 0.0–1.0)
- FEM mesh requires `"Part": "ObjectName"`

### Examples

```bash
# Box with placement and color
freecad-create-obj "MyDoc" "Part::Box" "Box001" -p '{"Length": 20, "Width": 15, "Height": 10, "Placement": {"Base": {"x": 5, "y": 5, "z": 0}}, "ViewObject": {"ShapeColor": [0.5, 0.5, 0.5, 1.0]}}'

# Cylinder
freecad-create-obj "MyDoc" "Part::Cylinder" "Cylinder001" -p '{"Height": 30, "Radius": 10}'

# FEM analysis + constraint + mesh
freecad-create-obj "MyDoc" "Fem::AnalysisPython" "FemAnalysis"
freecad-create-obj "MyDoc" "Fem::ConstraintFixed" "FixedConstraint" --analysis "FemAnalysis" -p '{"References": [{"object_name": "Box001", "face": "Face1"}]}'
freecad-create-obj "MyDoc" "Fem::FemMeshGmsh" "FemMesh" --analysis "FemAnalysis" -p '{"Part": "Box001", "ElementSizeMax": 10}'

# Edit dimensions
freecad-edit-obj "MyDoc" "Box001" '{"Length": 20, "Width": 15, "Height": 10}'

# Using properties file
freecad-create-obj "MyDoc" "Part::Box" "Box001" --properties-file /tmp/box_props.json
```
