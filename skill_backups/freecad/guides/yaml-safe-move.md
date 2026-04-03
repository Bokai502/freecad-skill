# FreeCAD: YAML Safe Move

Analyze and rewrite a component move inside a YAML assembly definition with collision checks and
envelope boundary checks via `freecad-yaml-safe-move`. This command can also sync the written YAML
result into a FreeCAD document and should be used in this skill with in-place file updates.

## Important

This is the recommended YAML-side analyzer and rewriter inside `safe-move-workflow.md`. Use it to
compute and apply a safe move before any optional assembly regeneration step.

## When to Use

- When the user wants to move a component in a YAML layout before importing it into FreeCAD.
- When the user wants collision-safe pre-processing for a YAML assembly definition.
- When the final deliverable must include the updated source YAML file.
- When the same YAML move result should also be pushed into an open FreeCAD document and saved back to the same `FCStd` file.

## Command

```bash
freecad-yaml-safe-move \
  --input data/sample.yaml \
  --output data/sample.yaml \
  --component P001 \
  --move 50 50 0

freecad-yaml-safe-move \
  --input data/sample.yaml \
  --output data/sample.yaml \
  --component P001 \
  --move 50 50 0 \
  --sync-cad \
  --doc-name SampleYamlAssembly

freecad-yaml-safe-move \
  --input data/sample.yaml \
  --output data/sample.yaml \
  --component P002 \
  --install-face 4 \
  --move 0 0 0

freecad-yaml-safe-move \
  --input data/sample.yaml \
  --output data/sample.yaml \
  --component P002 \
  --spin 90 \
  --move 0 0 0
```

## Behavior

- Treats each component as an axis-aligned box using:
  - `placement.position` as the box minimum corner
  - `dims` as the box size
- Preserves `placement.mount_face` as the component's own mounting face metadata.
- Uses `placement.envelope_face` to represent which envelope face the component is installed onto.
- Uses `placement.rotation_matrix` to represent the component orientation in the assembly.
- Without `--install-face`, preserves the current orientation and performs an in-plane safe move on
  the current envelope face.
- With `--spin`, rotates the component in place around the current or target envelope-face normal in
  multiples of `90` degrees while keeping the mount point fixed.
- With `--install-face`, rotates the component so its own `mount_face` is installed onto the
  requested envelope face, centers it on that face, and then applies the requested `--move` as an
  in-plane offset on the target face.
- `--install-face` and `--spin` can be combined so the component is first installed onto the target
  face and then rotated again within that face.
- Recomputes `mount_point` from the final position, component size, and face orientation.
- Rejects positions that collide with any other component box.
- Rejects positions that leave the target box outside `envelope.inner_size`.
- If the full requested move is safe, applies it directly.
- If the full move collides, searches along the same direction for the closest safe prefix.
- If no safe point exists on the requested segment, reports that no solution was found and still
  writes the constrained result back to the target YAML path.
- If `--sync-cad` is supplied, syncs the computed final placement into the matching component in
  the target FreeCAD document; in this skill, save that same document back to its existing `FCStd`
  path before reporting success.
- On this machine, CAD sync may target FreeCAD inside WSL, so use explicit `--host` / `--port`
  when Windows `localhost` forwarding is unstable.

## Output

The command prints a plain-text summary including:

- input and output paths
- target component
- requested move
- whether the requested position is safe
- blocker list such as component ids or `ENVELOPE_BOUNDARY`
- `component_mount_face`, `original_envelope_face`, `target_envelope_face`, and `rotation_matrix`
- `in_plane_spin_degrees_requested` and `in_plane_spin_quarter_turns_applied`
- whether a solution exists on the requested segment
- the final applied move, final position, and recomputed `mount_point`
- whether CAD sync was requested and the CAD sync result

## Typical Workflow

1. Run `freecad-yaml-safe-move` on the source YAML.
2. Inspect the reported blockers or safe move result.
3. Report whether the requested move was applied exactly or adjusted to the closest safe result.
4. Then sync the current CAD document with `--sync-cad --doc-name <doc>` when needed, or use the
   updated YAML with `load-yaml-data` or `create-assembly` only if the user explicitly wants a rebuild.

## Rules

- This is the preferred YAML-first implementation for move analysis in this skill.
- Without `--sync-cad`, it behaves as an offline YAML command and does not require RPC.
- With `--sync-cad`, it uses FreeCAD RPC only after the YAML move has already been computed and written.
- When FreeCAD runs inside WSL, pass `--host` and `--port` explicitly if Windows `localhost`
  forwarding is unstable.
- Use it before import when you want deterministic layout validation from YAML data.
- For move and rotation tasks in this skill, overwrite the source YAML by using the same file path for `--input` and `--output` unless the user explicitly asks for a separate copy.
- `placement.mount_face` identifies the component's own mounting face in the intended model.
- `placement.envelope_face` identifies the envelope face the component is installed onto.
- Reorientation is explicit: use `--install-face` when the user asks to move a component from one
  envelope face to another.
- Same-face rotation is also explicit: use `--spin` when the user wants to keep the same
  `envelope_face` but rotate the component in place by right angles.
- After `--sync-cad`, save the active document back to the existing `FCStd` path instead of producing a new `FCStd` file unless the user explicitly asks for a rebuilt copy.
- If no safe point exists on the requested segment, the command still writes the constrained placement state back to the target YAML path instead of reverting to the raw input layout.
