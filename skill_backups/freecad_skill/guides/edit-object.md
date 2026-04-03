# FreeCAD: Edit Object

Modify properties of an existing object in a FreeCAD document via the RPC server.

## When to Use

- When the user wants to change dimensions, placement, color, or other properties of an existing object.
- When adjustments are needed after object creation.
- When the user says "change", "modify", "resize", "move", "recolor", etc.

## Workflow

### Step 1: Inspect Current State

Use `get-object` to see the current properties of the target object.

### Step 2: Edit the Object

```bash
freecad-edit-obj "<doc_name>" "<obj_name>" '<properties_json>'
```

**Positional arguments:**
| Argument | Description |
|----------|-------------|
| `doc_name` | Name of the document containing the object |
| `obj_name` | Name of the object to edit |
| `properties` | JSON string of properties to update (optional positional, default `{}`) |

**Optional flags:**
- `--properties-file <path>` — Path to a JSON file with properties to update
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 3: Verify Changes

Use `get-object` to confirm properties were applied correctly.

## Examples

### Change dimensions
```bash
freecad-edit-obj "MyDoc" "Box001" '{"Length": 20, "Width": 15, "Height": 10}'
```

### Move an object
```bash
freecad-edit-obj "MyDoc" "Cylinder001" '{"Placement": {"Base": {"x": 50, "y": 0, "z": 0}}}'
```

### Using a properties file
```bash
freecad-edit-obj "MyDoc" "Box001" --properties-file /tmp/new_props.json
```

## Rules

- Only include properties you want to change; omitted properties remain unchanged.
- Always verify changes with `get-object` after editing.
- Use `get-object` before editing to discover available property names.
