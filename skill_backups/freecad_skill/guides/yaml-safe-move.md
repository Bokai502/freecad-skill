# FreeCAD: YAML Safe Move

Analyze and rewrite a component move inside a YAML assembly definition with collision checks and
envelope boundary checks via `freecad-yaml-safe-move`. This command can also sync the written YAML
result into a FreeCAD document.

## Important

This is the recommended YAML-side analyzer and rewriter inside `safe-move-workflow.md`. Use it to
compute and apply a safe move before any optional assembly regeneration step.

## When to Use

- When the user wants to move a component in a YAML layout before importing it into FreeCAD.
- When the user wants collision-safe pre-processing for a YAML assembly definition.
- When the final deliverable must include an updated YAML file.
- When the same YAML move result should also be pushed into an open FreeCAD document.

## Command

```bash
freecad-yaml-safe-move \
  --input data/sample.yaml \
  --output data/sample.updated.yaml \
  --component P001 \
  --move 50 50 0

freecad-yaml-safe-move \
  --input data/sample.yaml \
  --output data/sample.updated.yaml \
  --component P001 \
  --move 50 50 0 \
  --sync-cad \
  --doc-name SampleYamlAssembly

freecad-yaml-safe-move \
  --input data/sample.yaml \
  --output data/sample.reoriented.yaml \
  --component P002 \
  --install-face 4 \
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
- With `--install-face`, rotates the component so its own `mount_face` is installed onto the
  requested envelope face, centers it on that face, and then applies the requested `--move` as an
  in-plane offset on the target face.
- Recomputes `mount_point` from the final position, component size, and face orientation.
- Rejects positions that collide with any other component box.
- Rejects positions that leave the target box outside `envelope.inner_size`.
- If the full requested move is safe, applies it directly.
- If the full move collides, searches along the same direction for the closest safe prefix.
- If no safe point exists on the requested segment, reports that no solution was found and still
  writes an output YAML file.
- If `--sync-cad` is supplied, reads the written output YAML and updates the matching component in
  the target FreeCAD document.
- On this machine, CAD sync may target FreeCAD inside WSL, so the YAML path read by FreeCAD must be
  visible from WSL.

## Output

The command prints a plain-text summary including:

- input and output paths
- target component
- requested move
- whether the requested position is safe
- blocker list such as component ids or `ENVELOPE_BOUNDARY`
- `component_mount_face`, `original_envelope_face`, `target_envelope_face`, and `rotation_matrix`
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
- Keep the original YAML untouched by writing to a new `--output` path.
- `placement.mount_face` identifies the component's own mounting face in the intended model.
- `placement.envelope_face` identifies the envelope face the component is installed onto.
- Reorientation is explicit: use `--install-face` when the user asks to move a component from one
  envelope face to another.
- If no safe point exists on the requested segment, the command still writes an output YAML for the constrained placement state instead of reverting to the raw input layout.
