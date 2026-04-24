# FreeCAD: Safe Move Workflow

Default workflow for moving an existing component safely. YAML is the source of
truth: first update YAML, then sync the live FreeCAD document, then re-export
STEP and GLB.

## Core Rules

- Prefer the YAML branch. Use `freecad-yaml-safe-move` whenever a source YAML
  file exists.
- A move is always constrained to the current installation surface. Only the four
  in-plane directions of that surface are valid movement directions.
- Any requested movement component along the surface normal is ignored and should
  be reported via `normal_move_component_ignored`.
- The box/envelope installation face can change when the user explicitly asks to
  install the component on another face.
- The component's own contact/mount face does not change during safe-move. It is
  reused to place the component against the selected box/envelope surface.
- A component can be installed onto any box/envelope `mount_face` (`0..11`). When
  the target box/envelope face changes, rotate the component so the original
  component contact face still touches the new box/envelope face.
- Do not rebuild the whole assembly for a move. Update YAML in place, sync the
  open FreeCAD document, then overwrite the existing STEP and sibling GLB.
- During CAD sync, move an existing `<NAME>_part` container by the rigid delta
  from the previous YAML pose to the new YAML pose. Do not directly overwrite a
  container with the new absolute `position`, because replaced STEP children may
  already carry their own local placement and would otherwise detach from the
  selected installation face.

## Face Model

`placement.mount_face` in YAML stores the box/envelope installation face, not the
component's own contact face.

| Face IDs | Meaning | Wall size source | Allowed move axes |
|----------|---------|------------------|-------------------|
| `0`, `1`, `6`, `7` | `-X`, `+X`, external `-X`, external `+X` faces | `inner_size` for `0..1`, `outer_size` for `6..7` | `±Y`, `±Z` |
| `2`, `3`, `8`, `9` | `-Y`, `+Y`, external `-Y`, external `+Y` faces | `inner_size` for `2..3`, `outer_size` for `8..9` | `±X`, `±Z` |
| `4`, `5`, `10`, `11` | `-Z`, `+Z`, external `-Z`, external `+Z` faces | `inner_size` for `4..5`, `outer_size` for `10..11` | `±X`, `±Y` |

Internal faces are `0..5` and use `envelope.inner_size`. External faces are
`6..11` and require `envelope.outer_size`.

When the component stays on the same box/envelope face, the component contact
face can be derived from the current YAML `mount_face`. When the box/envelope
face changes, preserve that original component contact face and rotate the
component to make it touch the new target face. Never replace the original
component contact face with a contact face derived only from the new target
`mount_face`.

## Face Change And Rotation

Safe-move supports changing the box/envelope installation face to any target
`--install-face <0..11>`, including switching between different axes and between
internal/external surfaces.

The invariant is:

- `target_envelope_face` may change to any valid box/envelope face.
- `component_mount_face` is the component-local contact face and must remain the
  same as before the face change.
- The component rotation changes as needed so that the unchanged
  `component_mount_face` contacts the new `target_envelope_face`.
- The workflow writes/updates `placement.rotation_matrix` in YAML when a
  non-identity rotation is required. Later CAD sync and YAML rebuilds must use
  this matrix.
- After the face change, the requested `--move` vector is projected onto the new
  target face plane.

Example:

- A component currently has `mount_face: 11`. Its component-local contact face is
  `4`.
- If the user asks to install it on box/envelope `mount_face: 10`, that is
  allowed.
- The workflow must rotate the component so component face `4` touches box face
  `10`.
- The YAML `placement.mount_face` becomes `10`, but the reported
  `component_mount_face` should remain `4`.

## Inputs

Collect these before running a move:

- `component`: target component ID, for example `P022`.
- `move`: requested world vector, but only the two axes in the installation face
  plane will be applied.
- `input/output`: source YAML path. For normal operation use the same path so the
  YAML is overwritten in place.
- `doc-name`: live FreeCAD document name when syncing CAD.
- `step-output`: existing assembly STEP path when it is not the default
  `<doc-name>.step` beside the YAML.

## Command Patterns

### Move On Current Face

Use this when the user only asks to move a component on its current installation
surface.

```bash
freecad-yaml-safe-move \
  --input <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --output <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --component P022 \
  --move 20 0 0 \
  --sync-cad \
  --doc-name SampleYamlAssembly \
  --step-output <FREECAD_RUNTIME_DATA_DIR>/SampleYamlAssembly.step
```

If `P022` is on face `11` (`external +Z`), `--move 20 0 0` is valid because
`±X` and `±Y` are in-plane directions for Z faces. If the component is on an X
face, the same `+X` request is normal to the face and will be ignored.

### Change Box/Envelope Installation Face

Use `--install-face <0..11>` only when the user explicitly asks to move the
component to another box/envelope surface. The target face can be any valid
internal or external box/envelope face.

```bash
freecad-yaml-safe-move \
  --input <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --output <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --component P022 \
  --install-face 10 \
  --move 20 0 0 \
  --sync-cad \
  --doc-name SampleYamlAssembly \
  --step-output <FREECAD_RUNTIME_DATA_DIR>/SampleYamlAssembly.step
```

This changes the YAML `placement.mount_face` to the selected box/envelope face.
It must rotate the component as needed so the same component-local contact face
continues to touch the box. For example, moving a component from `mount_face: 11`
to `--install-face 10` should keep component contact face `4`, rotate the
component, write `placement.rotation_matrix`, and then seat face `4` on
box/envelope face `10`.

### Offline YAML-Only Analysis

Use this when FreeCAD is not running or the user only wants a YAML-safe result.

```bash
freecad-yaml-safe-move \
  --input <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --output <FREECAD_RUNTIME_DATA_DIR>/sample.yaml \
  --component P022 \
  --move 20 0 0
```

This updates YAML only. It does not update STEP or GLB.

## Execution Steps

1. Detect the source YAML. If it exists, use the YAML branch.
2. Identify the current YAML `placement.mount_face`.
3. Derive the current component contact face from the current `mount_face`.
4. Decide the target box/envelope face. If the user did not request a face
   change, keep the current `placement.mount_face`.
5. If the user requested a face change, pass `--install-face <0..11>` and ensure
   the workflow rotates the component so the original component contact face is
   used on the new target face.
6. Check whether the requested vector lies in the target face plane.
7. Run `freecad-yaml-safe-move` with the same `--input` and `--output` path.
8. When CAD artifacts must be updated, include `--sync-cad`, `--doc-name`, and
   `--step-output`.
9. Confirm CAD sync used the previous YAML pose and new YAML pose as a rigid
   transform for `<NAME>_part` when the component is represented by a container.
10. Read the output fields and report the effective move, ignored normal
   component, blockers, YAML path, STEP path, and GLB path.

## Safety Behavior

- If the full in-plane move is safe, it is applied directly.
- If collision or face-boundary violation is detected, the tool searches for the
  closest safe prefix along the requested segment.
- If no safe point exists, the constrained result is written to YAML and the
  failure/adjustment must be reported.
- Internal-face boundary violations appear as `ENVELOPE_BOUNDARY`.
- External-face boundary violations appear as `FACE_BOUNDARY`.
- Post-move CAD sync can return partial success if YAML was updated but STEP or
  GLB export failed. Report this clearly.

## Output Fields To Check

- `output_file`: updated YAML path.
- `step_path`: updated STEP path when `--sync-cad` is used.
- `glb_path`: updated GLB path when `--sync-cad` is used.
- `target_envelope_face`: final box/envelope installation face.
- `component_mount_face`: component contact face used for placement. When
  `--install-face` is used, this must remain the same as the pre-move component
  contact face even if `target_envelope_face` changes.
- `rotation_matrix`: rotation used to keep the original component contact face
  seated on the target box/envelope face.
- `normal_move_component_ignored`: normal-direction move component that was
  removed.
- `requested_move_is_safe`: whether the original in-plane request was safe.
- `applied_move`: actual move after projection and safety adjustment.
- `final_position`: final YAML placement position.
- `final_mount_point`: recomputed mount point.
- `cad_sync_result`: FreeCAD document sync and export result.

## Reporting Template

Report moves in this order:

1. State whether the requested move was applied exactly or adjusted.
2. State the final box/envelope face and confirm that the component contact face
   stayed the same.
3. State any ignored normal component.
4. State blockers if any.
5. State the updated YAML, STEP, and GLB paths.

Do not say the operation fully succeeded unless YAML, STEP, and GLB are all
updated when CAD sync was requested.
