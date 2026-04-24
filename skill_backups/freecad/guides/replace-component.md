# FreeCAD: Replace Component

Replace one generated placeholder component in an existing assembly STEP with a
real external STEP part. This workflow changes CAD geometry only: it overwrites
the assembly STEP and sibling GLB, but it does not rewrite the YAML layout.

Use this after an assembly already exists and the user wants to swap one
placeholder such as `P022_part` for a detailed STEP model.

## Core Rules

- YAML remains the source of placement truth. Read the target component from
  `components[NAME]`.
- `placement.mount_face` is the box/envelope installation face, not the
  component's own contact face.
- Replace-component must not change YAML `placement.mount_face`, `position`,
  `dims`, or `mount_point`.
- If YAML contains `placement.rotation_matrix`, replace-component must apply it
  to the imported STEP so a previously rotated component keeps the same
  component-local contact face and in-plane orientation.
- If the user wants the component installed on a different box/envelope face,
  run `freecad-layout-safe-move --install-face <0..11>` first, then run
  `freecad-replace-component`.
- The replacement STEP is aligned to the YAML placeholder: its flange is seated
  on the selected box/envelope wall and its cross-section is centered on the
  placeholder bounding box.
- Non-target parts must keep their existing placements. Only `<NAME>_part` and
  its descendants are replaced.
- The assembly STEP is overwritten in place, and a sibling GLB is exported beside
  it.

## Face Model

`placement.mount_face` selects the box/envelope surface used for seating the
replacement flange.

| Face IDs | Meaning | Wall size source | Cross-section centering axes |
|----------|---------|------------------|------------------------------|
| `0`, `1`, `6`, `7` | `-X`, `+X`, external `-X`, external `+X` faces | `inner_size` for `0..1`, `outer_size` for `6..7` | `Y`, `Z` |
| `2`, `3`, `8`, `9` | `-Y`, `+Y`, external `-Y`, external `+Y` faces | `inner_size` for `2..3`, `outer_size` for `8..9` | `X`, `Z` |
| `4`, `5`, `10`, `11` | `-Z`, `+Z`, external `-Z`, external `+Z` faces | `inner_size` for `4..5`, `outer_size` for `10..11` | `X`, `Y` |

Internal faces are `0..5` and require `envelope.inner_size`. External faces are
`6..11` and require `envelope.outer_size`.

For external faces, the code derives the physical seating direction internally.
Do not convert an external YAML `mount_face` such as `11` into a component
contact-face ID such as `4`.

## Orientation Convention

The replacement STEP needs a flange direction so it can be seated on the selected
wall.

- `placement.mount_face` determines the world mount axis and target wall
  position.
- `placement.rotation_matrix`, when present, rotates the placeholder's local
  axes onto the final world axes. The replacement STEP must follow that same
  rotation.
- The component-local contact face is inferred from `mount_face` plus
  `rotation_matrix`; this preserves the same physical component face after a
  safe-move face change.
- The STEP-native thrust axis is auto-detected by comparing the STEP bounding-box
  extents with the YAML placeholder thickness along the component-local contact
  axis.
- `replacement.thrust_axis` can override the auto-detected STEP-native axis.
- `replacement.flange_sign` tells which end of the STEP-native thrust axis is the
  flange. The default is `+1`.
- `thrust_axis` and `flange_sign` describe the replacement STEP geometry only.
  They do not change the YAML installation face.

Optional YAML override:

```yaml
P022:
  ...
  replacement:
    step_file: DawnAerospace_B1_Thruster.STEP
    thrust_axis: y
    flange_sign: 1
```

Use overrides when the imported STEP appears reversed, points the nozzle into the
wall, or the auto-detection warning says the axis is ambiguous.

## Command Pattern

```bash
freecad-replace-component \
  --yaml <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --assembly <FREECAD_RUNTIME_DATA_DIR>/SampleAssembly.step \
  --replacement <FREECAD_RUNTIME_DATA_DIR>/parts/RealThruster.step \
  --name P022 \
  --doc-name SampleAssembly
```

`--doc-name` is optional. If omitted, it defaults to the assembly STEP stem.

## Inputs

| Flag | Required | Description |
|------|----------|-------------|
| `--yaml` | yes | Source YAML. Used to read `components[NAME]`, including `placement.position`, `placement.mount_face`, `dims`, `color`, and optional `replacement` overrides. |
| `--assembly` | yes | Existing assembly STEP. This file is overwritten in place. |
| `--replacement` | yes | Real replacement STEP file to import. |
| `--name` | yes | Component ID to replace, for example `P022`. The CLI targets `<NAME>_part` under the Assembly root. |
| `--doc-name` | no | FreeCAD document name. Defaults to the assembly file stem. |
| `--no-fit-view` | no | Skip the post-replace isometric/fit view. |
| `--host`, `--port` | no | FreeCAD RPC connection settings. Defaults come from `config/freecad_runtime.conf`. |

## Execution Steps

1. Confirm the assembly STEP can be overwritten.
2. Confirm the YAML component exists and has a valid `placement.mount_face`.
3. If the target face is external (`6..11`), confirm `envelope.outer_size`
   exists.
4. Run `freecad-replace-component` with `--yaml`, `--assembly`,
   `--replacement`, and `--name`.
5. Read the JSON output and verify `success: true`.
6. Verify both `assembly_path` and `glb_path` exist.
7. Report the assembly STEP path, GLB path, target component, mount face, and any
   orientation overrides used.

## Behavior

1. Reuse the currently open FreeCAD document when `--doc-name` matches an open
   assembly document; otherwise import the assembly STEP into a fresh document.
2. Locate the root `Assembly` container.
3. Validate `<NAME>_part` exists as a direct child of the Assembly root.
4. Read YAML `placement.mount_face` as the box/envelope installation face.
5. Compute the placeholder center from YAML after applying
   `placement.rotation_matrix`.
6. Import the replacement STEP before deleting the old component, so failures do
   not destroy the existing assembly.
7. Detect or read `thrust_axis` and `flange_sign`.
8. Rotate the replacement so its STEP flange first maps to the component-local
   contact face, then apply `placement.rotation_matrix` so the detailed part
   matches the rotated placeholder.
9. Translate the replacement so the flange seats on the wall and the cross-section
   is centered on the placeholder.
10. Remove only `<NAME>_part` and its descendants.
11. Wrap imported objects into a new `<NAME>_part` container and attach it to the
   Assembly root.
12. Restore/preserve non-target placements.
13. Export `Import.export([assembly], ASSEMBLY_PATH)` and a sibling GLB.
14. Fit the GUI view unless `--no-fit-view` is set.

## Output Fields To Check

- `success`: must be `true`.
- `assembly_path`: overwritten STEP path.
- `glb_path`: sibling GLB path.
- `component`: replaced component ID.
- `mount_face`: YAML box/envelope installation face used for seating.
- `component_contact_face`: component-local face kept against the wall.
- `placement_rotation_matrix`: YAML rotation applied to the imported STEP.
- `external`: whether the face was external.
- `wall_position`: wall coordinate used for flange seating.
- `thrust_axis`: STEP-native axis used as thrust/flange axis.
- `thrust_axis_source`: `yaml`, `step_bbox_match`, or fallback.
- `flange_sign`: which end of the STEP-native axis was treated as the flange.
- `flange_sign_source`: `yaml` or default.
- `translation_applied`: final translation applied to the imported STEP objects.
- `removed_objects`: old `<NAME>_part` objects removed.
- `new_objects`: imported replacement objects.
- `restored_placements_count`: non-target placements restored after replacement.

## Failure Handling

- If `<NAME>_part` is not found under the Assembly root, stop and report the
  available component IDs.
- If the replacement STEP imports no objects or no valid shape, stop and report
  the STEP as invalid or empty.
- If `thrust_axis` auto-detection is ambiguous, add
  `replacement.thrust_axis` to YAML and rerun.
- If the nozzle/flange is reversed, set `replacement.flange_sign` to `1` or `-1`
  and rerun.
- If GLB export is missing but STEP export succeeded, report partial success.

## Reporting Template

Report replacements in this order:

1. State which component was replaced.
2. State the YAML box/envelope mount face used, including whether it was internal
   or external.
3. State that the YAML component placement was not changed.
4. State orientation details when useful: `thrust_axis`, `flange_sign`, and their
   sources.
5. State updated STEP and GLB paths.

Do not say the operation fully succeeded unless both STEP and GLB were written.
