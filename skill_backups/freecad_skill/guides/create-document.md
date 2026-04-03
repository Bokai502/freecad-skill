# FreeCAD: Create Document

Create a new empty document in FreeCAD via the RPC server.

## When to Use

- When the user wants to start a new FreeCAD project or design.
- Before creating any objects — a document must exist first.
- When the user says "new document", "create project", "start fresh", etc.

## Workflow

### Step 1: Verify FreeCAD Connection

Ensure the FreeCAD RPC server is running (the FreeCAD addon must be active).

### Step 2: Create the Document

```bash
freecad-create-doc "<document_name>"
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `<document_name>` | Yes | Name of the document to create (e.g. `MyProject`) |

**Optional flags:**
- `--host <host>` — FreeCAD RPC host (default: `localhost`)
- `--port <port>` — FreeCAD RPC port (default: `9875`)

### Step 3: Verify Result

The script outputs JSON. Check `"success": true` and `"document_name"` in the response.

Example success output:
```json
{
  "success": true,
  "document_name": "MyProject"
}
```

## Examples

Create a document named "GearBox":
```bash
freecad-create-doc "GearBox"
```

## Rules

- Document names should be descriptive and unique.
- If a document with the same name already exists, the operation may fail.
- Always create a document before attempting to add objects to it.
