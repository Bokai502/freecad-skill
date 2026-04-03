# FreeCAD: Get Parts List

List all available parts in the FreeCAD parts library via the RPC server.

## When to Use

- Before creating objects from scratch, check if a suitable part already exists.
- When the user asks what standard parts are available.
- As the first step before using `insert-part-from-library`.

## Workflow

### Step 1: Get the Parts List

```bash
freecad-get-parts
```

**No positional arguments required.**

**Optional flags:**
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 2: Review and Select

The output is a JSON array of relative paths. Use the desired path with `insert-part-from-library`.

## Examples

```bash
freecad-get-parts
```

## Rules

- If no parts are found, the FreeCAD `parts_library` addon needs to be installed.
- The returned paths are relative paths to be used with `insert-part-from-library`.
