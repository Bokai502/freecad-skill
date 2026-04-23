# FreeCAD: Replace Component

Swap a named placeholder component in an existing assembly STEP with an external STEP file
(real CAD geometry). The replacement is aligned to the placeholder via `mount_face`: the
flange end of the STEP is seated on the envelope wall, and the body is centered on the
placeholder's bounding box. The assembly STEP is **overwritten in place**.

Use this when the user has a generated assembly (boxes/cylinders) and wants to drop in a
detailed part for one component.

## Orientation Convention

The **thrust axis is auto-detected** by matching the STEP's native bounding box
against the YAML placeholder `dims`. Specifically:

- Read the STEP's native bbox extents `[sx, sy, sz]`.
- The STEP axis whose extent is closest to `yaml_dims[mount_axis]` (the placeholder's
  thickness along the mount axis) is treated as the STEP-native thrust axis.
- A rotation is then applied to align that STEP axis with the world mount axis.

Flange sign defaults to `+1` (flange at the positive end of the detected thrust axis
in STEP native coords). If the result places the nozzle against the wall instead of
the flange, override via YAML (see below).

If the auto-detected result is wrong (e.g. ambiguous bbox, or the flange is at the
negative end), override per-component in the YAML (optional):

```yaml
P022:
  ...
  replacement:
    step_file: DawnAerospace_B1_Thruster.STEP   # informational (not auto-loaded)
    thrust_axis: y          # x | y | z — STEP-native axis
    flange_sign: 1          # +1 or -1 — which end of that axis is the flange
```

Both fields are optional; omit them to use the auto-detected defaults (bbox match + flange_sign=+1).

## Preferred CLI

```bash
freecad-replace-component \
  --yaml <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --assembly <FREECAD_RUNTIME_DATA_DIR>/SampleAssembly.step \
  --replacement parts/RealThruster.STEP \
  --name P022
```

## Inputs

| Flag | Required | Description |
|------|----------|-------------|
| `--yaml` | yes | Source YAML — used to look up `components[NAME].placement.position`, `dims`, `color`. |
| `--assembly` | yes | Existing assembly STEP file. Overwritten in place. |
| `--replacement` | yes | Replacement STEP file containing the new geometry. |
| `--name` | yes | Component id to replace (e.g. `P022`). Matched against object `Label`/`Name` and `<NAME>_part`. |
| `--doc-name` | no | FreeCAD document name; defaults to the assembly file stem. |
| `--no-fit-view` | no | Skip the post-replace isometric/fit view. |
| `--host`, `--port` | no | Standard RPC connection flags. |

## Behavior

1. Open the assembly STEP into a fresh document.
2. Locate the root `Assembly` container (`App::Part`/`Assembly::AssemblyObject`).
3. **Validate** `<NAME>_part` exists as a direct child of the Assembly. If not, error out listing the available component ids.
4. Look up the component in the YAML; compute the **target center**:
   - `box`: `position + dims/2`
   - `cylinder`: derived from mount-face axis + radius/height
5. Remove the `<NAME>_part` sub-Part and its descendants.
6. `Import.insert` the replacement STEP into the same document.
7. Resolve `thrust_axis` / `flange_sign`: read YAML `replacement` overrides if present; otherwise auto-detect thrust axis by matching STEP bbox extents to `yaml_dims`, and default flange_sign to `+1`.
8. Rotate the STEP so its flange aligns with the wall; translate so its flange sits on the wall and its cross-section is centered on the placeholder.
9. Apply the YAML color and wrap the new objects in a fresh `App::Part` named `<NAME>_part`; attach it under the Assembly container.
10. `Import.export([assembly], ASSEMBLY_PATH)` — the Assembly root carries the whole hierarchy.
11. Switch GUI to isometric / fit (unless `--no-fit-view`).

### Validation

The CLI only targets components that exist as `<NAME>_part` children of the Assembly root. Bare labels outside the Assembly are ignored. On miss:

```json
{ "success": false, "error": "Component 'P099' not found in Assembly. Available components: P000, P001, ..., P022" }
```

## Output (JSON)

```json
{
  "success": true,
  "document": "...",
  "assembly_path": "...",
  "replacement_path": "...",
  "component": "P022",
  "assembly_container": "Assembly",
  "assembly_component_count": 23,
  "removed_objects": ["...P022_part and its descendants..."],
  "new_objects": ["...imported..."],
  "container": "P022_part",
  "target_center": [x, y, z],
  "translation_applied": [dx, dy, dz],
  "view_updated": true
}
```

## Rules

- The assembly file is **overwritten** — confirm with the user before running on a production file.
- Rotation is applied when `thrust_axis` / `flange_sign` (derived or overridden) require it; translation seats the part on the mount wall and centers it on the placeholder.
- The YAML is **not** modified — placeholder dims remain as a reference. To reflect the new geometry, re-export the YAML manually.
- After replacement, optionally run `freecad-check-collision` to verify the new geometry doesn't intersect neighbors.

## Fallbacks

- If the component name is not found in the assembly, the CLI errors out. Check `freecad-get-objs` or open the STEP in FreeCAD to verify labels.
- If the replacement STEP yields no valid bounding box, the CLI errors out — the file is likely empty or non-solid.
