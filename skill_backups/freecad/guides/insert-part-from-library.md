# FreeCAD: Insert Part from Library

Insert a part from the FreeCAD parts library addon into the active document.

## When to Use

- When a standard or pre-made part is needed (screws, nuts, bearings, profiles, etc.).
- Always check the library first before creating objects from scratch.
- When the user says "insert from library", "use a standard part", etc.

## Workflow

### Step 1: Browse Available Parts

Use `get-parts-list` to find the relative path of the desired part.

### Step 2: Insert the Part

```bash
freecad-insert-part "<relative_path>"
```

**Positional argument:**
| Argument | Description |
|----------|-------------|
| `relative_path` | Relative path of the part in the library (from `freecad-get-parts` output) |

**Optional flags:**
- `--host <host>` / `--port <port>` — RPC connection settings

### Step 3: Verify and Adjust

Use `get-objects` to find the inserted object, then `edit-object` to adjust placement if needed.

## Examples

```bash
freecad-insert-part "Fasteners/Screws/M6x20_Hex_Head.FCStd"
```

## Rules

- The parts library addon must be installed and populated in FreeCAD.
- If no parts are found, the `parts_library` addon needs to be installed.
- After insertion, use `get-objects` to find the newly inserted object name.
