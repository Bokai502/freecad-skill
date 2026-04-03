# FreeCAD: Get View & AI Review

Capture screenshots of the active FreeCAD model from multiple angles, save them to a dedicated folder, then review the images and propose actionable modification plans for the user to choose from.

## When to Use

- When the user wants to see and review the current 3D model.
- When verifying visual results after creation or editing.
- When the user wants AI-driven improvement suggestions for their model.
- When the user says "show me", "review my model", "check the design", "how does it look", etc.

## Workflow

### Step 1: Capture Multi-Angle Screenshots

Use `--all` to capture all 7 standard views into a timestamped folder:

```bash
freecad-get-view --all
```

This saves screenshots to `./freecad_views/<YYYYMMDD_HHMMSS>/` with files:
`isometric.png`, `front.png`, `top.png`, `right.png`, `back.png`, `left.png`, `bottom.png`
and a `manifest.json` listing all captured images.

**Alternatively, capture a subset of views:**
```bash
freecad-get-view --views Isometric Front Top Right
```

**Or capture to a specific directory:**
```bash
freecad-get-view --all --output-dir ./freecad_views/my_model
```

### Step 2: Review All Screenshots

Read each screenshot image file using the `Read` tool. This allows you (the AI) to visually inspect the model from every angle.

For each image in the output directory:
```
Read the image file at <output_dir>/<view>.png
```

### Step 3: AI Analysis & Propose Modifications

After reviewing all screenshots, analyze the model and generate **3–5 concrete modification proposals**. Each proposal should include:

1. **Title** — short summary of the change
2. **Problem** — what issue or improvement opportunity was identified from the screenshots
3. **Action** — the specific FreeCAD commands or code to execute
4. **Impact** — what the model will look like after the change

Format proposals as a numbered list and present them to the user. For example:

```
Based on reviewing the model from 7 angles, here are my suggestions:

1. **Fix wing symmetry** — The right wing appears shorter than the left.
   Action: Edit WingRight Length from 45 to 50.

2. **Add rounded edges to tabletop** — Sharp corners look unrealistic.
   Action: Use freecad-exec-code to apply fillets.

3. **Adjust engine position** — Engines overlap with the wing.
   Action: Move EngineLeft/EngineRight down by 5 units.
```

### Step 4: User Chooses Action

Ask the user which proposal(s) to execute. Wait for explicit confirmation before making any changes.

- If the user selects one or more proposals, execute them using the appropriate FreeCAD actions (`edit-object`, `execute-code`, etc.).
- After executing changes, **repeat from Step 1** to capture new screenshots and verify the result.
- If the user is satisfied, stop.

## CLI Reference

### Single view
```bash
freecad-get-view Isometric -o /tmp/view.png
```

### All views (recommended)
```bash
freecad-get-view --all
```

### Specific views
```bash
freecad-get-view --views Front Top Right
```

### Custom output directory
```bash
freecad-get-view --all -d ./freecad_views/review_round1
```

### With custom resolution
```bash
freecad-get-view --all --width 1920 --height 1080
```

### Focus on a specific object
```bash
freecad-get-view --all --focus "Box001"
```

**Available views:** `Isometric`, `Front`, `Top`, `Right`, `Back`, `Left`, `Bottom`, `Dimetric`, `Trimetric`

## Rules

- **Always capture multiple angles** (at minimum: Isometric + Front + Top + Right) to get a complete picture before proposing changes.
- **Never auto-execute modifications** — always present proposals and wait for user confirmation.
- Screenshots are saved to `./freecad_views/<timestamp>/` by default. Each run creates a new timestamped subfolder to preserve history.
- A `manifest.json` is written alongside the images for programmatic access.
- After executing user-approved changes, always re-capture to verify the result.
- Screenshots are unavailable in non-3D views (TechDraw, Spreadsheet).
