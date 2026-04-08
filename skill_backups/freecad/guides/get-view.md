# FreeCAD: Get View & Visual Review

Capture screenshots of the active FreeCAD model from multiple angles.

## Capture

```bash
# All standard views (recommended)
freecad-get-view --all

# Specific views
freecad-get-view --views Isometric Front Top Right

# Custom output directory
freecad-get-view --all --output-dir ./freecad_views/my_model

# Custom resolution
freecad-get-view --all --width 1920 --height 1080

# Focus on a specific object
freecad-get-view --all --focus "Box001"
```

Saves to `./freecad_views/<YYYYMMDD_HHMMSS>/` with a `manifest.json`.

**Available views:** `Isometric`, `Front`, `Top`, `Right`, `Back`, `Left`, `Bottom`, `Dimetric`, `Trimetric`

## Review Workflow

1. **Capture**: Run `freecad-get-view --all` (minimum: Isometric + Front + Top + Right).
2. **Read images**: Use the `Read` tool on each screenshot file.
3. **Optional — AI analysis**: If the user asks for review/suggestions, propose 3-5 concrete modifications with title, problem, action, and impact. Present as a numbered list.
4. **User confirmation**: Never auto-execute modifications. Wait for explicit user selection.
5. **Iterate**: After executing approved changes, re-capture to verify.

## Rules

- Screenshots are unavailable in non-3D views (TechDraw, Spreadsheet).
- Each run creates a new timestamped subfolder to preserve history.
