# FreeCAD: Replace Component

Replace one generated placeholder component in an existing assembly STEP with a
real external STEP part. This workflow changes CAD geometry only: it exports
updated CAD artifacts to the fixed `geometry_after.step` and sibling
`geometry_after.glb` paths, but it does not rewrite `layout_topology.json` or
`geom.json`.

Use this after an assembly already exists and the user wants to swap one
placeholder such as `P022_part` for a detailed STEP model.

## Core Rules

- `layout_topology.json + geom.json` remain the source of placement truth. The
  CLI normalizes them before calling FreeCAD.
- Replace-component must not change the dataset-derived component
  `placement.mount_face`, `position`, `dims`, or `component_mount_face`.
- If the normalized component contains `placement.rotation_matrix`,
  replace-component must apply it to the imported STEP so a previously rotated
  component keeps the same component-local contact face and in-plane
  orientation.
- If the user wants the component installed on a different box/envelope face,
  run `freecad-layout-safe-move --install-face <0..11>` first, then run
  `freecad-replace-component`.
- The replacement STEP is aligned to the dataset placeholder: its flange is
  seated on the selected box/envelope wall and its cross-section is centered on
  the placeholder bounding box.
- Non-target parts must keep their existing placements. Only `<NAME>_part` and
  its descendants are replaced.
- The source assembly STEP is read as input only. Exported CAD artifacts are
  always written as `./02_geometry_edit/geometry_after.step` and sibling
  `geometry_after.glb`.

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
Do not convert an external `mount_face` such as `11` into a component
contact-face ID such as `4`.

## Orientation Convention

The replacement STEP needs a flange direction so it can be seated on the
selected wall.

- `placement.mount_face` determines the world mount axis and target wall
  position.
- `placement.rotation_matrix`, when present, rotates the placeholder's local
  axes onto the final world axes. The replacement STEP must follow that same
  rotation.
- The component-local contact face is inferred from `mount_face` plus
  `rotation_matrix`; this preserves the same physical component face after a
  safe-move face change.
- The STEP-native thrust axis is auto-detected by comparing the STEP bounding-box
  extents with the normalized placeholder thickness along the component-local
  contact axis.
- `--thrust-axis` can override the auto-detected STEP-native axis.
- `--flange-sign` tells which end of the STEP-native thrust axis is the flange.
  The default is `+1`.
- `thrust_axis` and `flange_sign` describe the replacement STEP geometry only.
  They do not change the dataset installation face.

Use overrides when the imported STEP appears reversed, points the nozzle into
the wall, or the auto-detection warning says the axis is ambiguous.

## Command Pattern

```bash
freecad-replace-component \
  --layout-topology ./01_layout/layout_topology.json \
  --geom ./01_layout/geom.json \
  --assembly ./assemblies/current.step \
  --replacement ./parts/RealThruster.step \
  --name P022
```

Relative paths are resolved from `FREECAD_WORKSPACE_DIR`.

`--doc-name` is optional. If omitted, it defaults to the source assembly STEP stem.

## Inputs

| Flag | Required | Description |
|------|----------|-------------|
| `--layout-topology` | no | Source `layout_topology.json`. Defaults to `./01_layout/layout_topology.json` under `FREECAD_WORKSPACE_DIR`. |
| `--geom` | no | Source `geom.json`. Defaults to `./01_layout/geom.json` under `FREECAD_WORKSPACE_DIR`. |
| `--assembly` | yes | Existing assembly STEP to import before replacement. Relative paths resolve from `FREECAD_WORKSPACE_DIR`. The exported STEP/GLB names are still fixed to `geometry_after.step` and `geometry_after.glb`. |
| `--replacement` | yes | Real replacement STEP file to import. Relative paths resolve from `FREECAD_WORKSPACE_DIR`. |
| `--name` | yes | Component ID to replace, for example `P022`. The CLI targets `<NAME>_part` under the Assembly root. |
| `--thrust-axis` | no | Optional override for the replacement STEP native thrust axis: `x`, `y`, or `z`. |
| `--flange-sign` | no | Optional override for which end of the native thrust axis is the flange: `1` or `-1`. |
| `--doc-name` | no | FreeCAD document name. Defaults to the assembly file stem. |
| `--no-fit-view` | no | Skip the post-replace isometric/fit view. |
| `--host`, `--port` | no | FreeCAD RPC connection settings. Defaults come from `config/freecad_runtime.conf`. |

## Execution Steps

1. Confirm the source assembly STEP exists and is readable.
2. Confirm the target component exists in the normalized layout dataset and has
   a valid `placement.mount_face`.
3. If the target face is external (`6..11`), confirm `envelope.outer_size`
   exists.
4. Run `freecad-replace-component` with `--layout-topology`, `--geom`,
   `--assembly`, `--replacement`, and `--name`.
5. Read the JSON output and verify `success: true`.
6. Verify both `assembly_path` and `glb_path` exist and are named `geometry_after.*`.
7. Report the assembly STEP path, GLB path, target component, mount face, and
   any orientation overrides used.

## Behavior

1. Reuse the currently open FreeCAD document when `--doc-name` matches an open
   assembly document; otherwise import the assembly STEP into a fresh document.
2. Locate the root `Assembly` container.
3. Validate `<NAME>_part` exists as a direct child of the Assembly root.
4. Read the normalized component `placement.mount_face` as the box/envelope
   installation face.
5. Compute the placeholder center after applying `placement.rotation_matrix`.
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
13. Export `Import.export([assembly], ./02_geometry_edit/geometry_after.step)` and a sibling GLB.
14. Fit the GUI view unless `--no-fit-view` is set.

## Output Fields To Check

- `success`: must be `true`.
- `assembly_path`: exported STEP path, always ending with `geometry_after.step`.
- `glb_path`: sibling GLB path, always ending with `geometry_after.glb`.
- `component`: replaced component ID.
- `mount_face`: dataset box/envelope installation face used for seating.
- `component_contact_face`: component-local face kept against the wall.
- `placement_rotation_matrix`: dataset rotation applied to the imported STEP.
- `external`: whether the face was external.
- `wall_position`: wall coordinate used for flange seating.
- `thrust_axis`: STEP-native axis used as thrust/flange axis.
- `thrust_axis_source`: `cli`, `step_bbox_match`, or fallback.
- `flange_sign`: which end of the STEP-native axis was treated as the flange.
- `flange_sign_source`: `cli` or default.
- `translation_applied`: final translation applied to the imported STEP objects.
- `removed_objects`: old `<NAME>_part` objects removed.
- `new_objects`: imported replacement objects.
- `restored_placements_count`: non-target placements restored after replacement.

## Failure Handling

- If `<NAME>_part` is not found under the Assembly root, stop and report the
  available component IDs.
- If the replacement STEP imports no objects or no valid shape, stop and report
  the STEP as invalid or empty.
- If `thrust_axis` auto-detection is ambiguous, rerun with `--thrust-axis`.
- If the nozzle/flange is reversed, rerun with `--flange-sign 1` or
  `--flange-sign -1`.
- If GLB export is missing but STEP export succeeded, report partial success.

## Reporting Template

Report replacements in this order:

1. State which component was replaced.
2. State the dataset box/envelope mount face used, including whether it was
   internal or external.
3. State that the source dataset component placement was not changed.
4. State orientation details when useful: `thrust_axis`, `flange_sign`, and
   their sources.
5. State updated STEP and GLB paths.

Do not say the operation fully succeeded unless both STEP and GLB were written.
