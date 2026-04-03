# FreeCAD: Create Object

Create a new object in a FreeCAD document via the RPC server. Supports Part::, Draft::, PartDesign::, and Fem:: object types.

## When to Use

- When the user wants to add a 3D shape (box, cylinder, sphere, cone, etc.)
- When adding draft elements (circle, line, wire, etc.)
- When creating FEM analysis components (analysis, constraints, materials, meshes)
- When the user says "create", "add", "make a box/cylinder/sphere", etc.

## Workflow

### Step 1: Ensure Document Exists

Use `list-documents` to verify the target document is open, or `create-document` to create one.

### Step 2: Create the Object

```bash
freecad-create-obj "<doc_name>" "<obj_type>" "<obj_name>" --properties '<json>'
```

**Positional arguments:**
| Argument | Description |
|----------|-------------|
| `doc_name` | Name of the target document |
| `obj_type` | Object type (e.g. `Part::Box`, `Part::Cylinder`, `Draft::Circle`, `Fem::AnalysisPython`) |
| `obj_name` | Name for the new object |

**Optional flags:**
- `--properties '<json>'` or `-p '<json>'` — JSON string of object properties
- `--properties-file <path>` — Path to a JSON file with properties
- `--analysis <name>` — FEM analysis name to associate with (for Fem:: objects)
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 3: Verify Result

Check `"success": true` and `"object_name"` in the JSON output.

## Examples

### Basic cylinder
```bash
freecad-create-obj "MyDoc" "Part::Cylinder" "Cylinder001" -p '{"Height": 30, "Radius": 10}'
```

### Box with placement and color
```bash
freecad-create-obj "MyDoc" "Part::Box" "Box001" -p '{"Length": 20, "Width": 15, "Height": 10, "Placement": {"Base": {"x": 5, "y": 5, "z": 0}}, "ViewObject": {"ShapeColor": [0.5, 0.5, 0.5, 1.0]}}'
```

### FEM analysis
```bash
freecad-create-obj "MyDoc" "Fem::AnalysisPython" "FemAnalysis"
```

### FEM constraint (associated with analysis)
```bash
freecad-create-obj "MyDoc" "Fem::ConstraintFixed" "FixedConstraint" --analysis "FemAnalysis" -p '{"References": [{"object_name": "Box001", "face": "Face1"}]}'
```

### FEM mesh (requires Part property)
```bash
freecad-create-obj "MyDoc" "Fem::FemMeshGmsh" "FemMesh" --analysis "FemAnalysis" -p '{"Part": "Box001", "ElementSizeMax": 10}'
```

### Using a properties file
```bash
freecad-create-obj "MyDoc" "Part::Box" "Box001" --properties-file /tmp/box_props.json
```

## Rules

- The `Part` property is **required** for FEM mesh objects.
- For FEM objects, always provide `--analysis` to associate them with an analysis.
- Use `Placement.Base` for position, `Placement.Rotation` for orientation.
- Use `ViewObject.ShapeColor` for RGBA color (values 0.0–1.0).
- For complex properties, prefer `--properties-file` over inline JSON.
