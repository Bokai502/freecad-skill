# FreeCAD: Get Object

Retrieve detailed properties of a specific object in a FreeCAD document via the RPC server.

## When to Use

- When the user wants to inspect a specific object's dimensions, placement, or properties.
- After editing an object, to verify that changes were applied correctly.
- Before editing, to discover available property names and current values.

## Workflow

### Step 1: Get Object Properties

```bash
freecad-get-obj "<doc_name>" "<obj_name>"
```

**Positional arguments:**
| Argument | Description |
|----------|-------------|
| `doc_name` | Name of the document containing the object |
| `obj_name` | Name of the object to inspect |

**Optional flags:**
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 2: Review Properties

The output is a JSON object containing all properties of the object (type, dimensions, placement, etc.).

## Examples

```bash
freecad-get-obj "MyDoc" "Box001"
```

## Rules

- Use this to discover property names before calling `edit-object`.
- Always use this after editing to verify changes were applied.
