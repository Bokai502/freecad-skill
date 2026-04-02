# FreeCAD: Delete Object

Remove an object from a FreeCAD document via the RPC server.

## When to Use

- When the user wants to remove a specific object from a document.
- When cleaning up or rebuilding parts of a design.
- When the user says "delete", "remove", "get rid of", etc.

## Workflow

### Step 1: Confirm Target

Use `get-objects` to list all objects and confirm the target object exists.

### Step 2: Delete the Object

```bash
freecad-del-obj "<doc_name>" "<obj_name>"
```

**Positional arguments:**
| Argument | Description |
|----------|-------------|
| `doc_name` | Name of the document |
| `obj_name` | Name of the object to delete |

**Optional flags:**
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 3: Verify Deletion

Use `get-objects` to confirm the object was removed.

## Examples

```bash
freecad-del-obj "MyDoc" "Box001"
```

## Rules

- Deletion is irreversible — confirm with the user before deleting.
- Dependent objects (e.g., FEM constraints referencing a shape) may break if the referenced object is deleted.
- Always verify with `get-objects` after deletion.
