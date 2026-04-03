# FreeCAD: List Documents

List all currently open documents in FreeCAD via the RPC server.

## When to Use

- When you need to know which documents are open.
- To find the correct document name to pass to other actions.
- As a first step when the user doesn't specify which document to work with.

## Workflow

### Step 1: List Documents

```bash
freecad-list-docs
```

**No positional arguments required.**

**Optional flags:**
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 2: Use the Results

The output is a JSON array of document names. Use these names with other actions.

## Examples

```bash
freecad-list-docs
```

## Rules

- Returns an empty list if no documents are open.
- Use this to verify a document exists before attempting operations on it.
