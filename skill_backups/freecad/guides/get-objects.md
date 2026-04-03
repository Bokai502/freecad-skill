# FreeCAD: Get Objects

List all objects in a FreeCAD document via the RPC server.

## When to Use

- Before starting any modification task, to understand the current document state.
- When the user asks "what's in the document?" or needs an overview of all objects.
- To find object names for use with other actions (edit, delete, get-object).

## Workflow

### Step 1: List Objects

```bash
freecad-get-objs "<doc_name>"
```

**Positional argument:**
| Argument | Description |
|----------|-------------|
| `doc_name` | Name of the document to list objects from |

**Optional flags:**
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 2: Use the Results

The output is a JSON array of objects with their names and types. Use these names for further operations.

## Examples

```bash
freecad-get-objs "MyDoc"
```

## Rules

- Always call this before modifying a document to confirm the current state.
- The returned JSON list contains object names, types, and basic info.
