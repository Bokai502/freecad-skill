# FreeCAD: Safe Move Workflow

Default high-safety workflow for moving a part. Prefer YAML as the source of truth: analyze from
the YAML configuration first, then write the fully safe move or the closest safe result on the
requested path, and sync the CAD model from that YAML without creating a new assembly by default.

## When to Use

- When the user asks to move a part in YAML.
- When the user asks to move a part in an already opened FreeCAD document.
- When overlap, interference, or invalid layout is possible.
- When the final deliverable should include an updated YAML file and, optionally, an updated CAD document.

## Input Expectations

Collect these inputs before final execution:

- target part or component id
- requested move vector
- source YAML path
- if starting from a FreeCAD document: document name and object name

If the task starts from a FreeCAD document, still require a source YAML path before final execution.
Without source YAML, stop after analysis and explain that final YAML output cannot be completed.

## Workflow

### Step 1: Detect the source of truth

- If a source YAML file exists, use the YAML branch below and treat that file as the source of truth.
- If the request starts from a FreeCAD document object, first locate the source YAML. Only use the
  document-only branch when no YAML source can be found.

### Step 2: Analyze before moving

Never apply the final move yet.

#### YAML branch

1. Run `freecad-yaml-safe-move` with the requested target and move.
2. Read the output summary:
   - whether the requested move is fully safe
   - blockers such as component ids or boundary constraints
   - whether the move preserves orientation or changes `envelope_face`
   - the chosen `rotation_matrix` when a face change is requested
   - the safe applied move or the fact that no safe point exists on the requested segment
3. Convert that result into a user-facing move summary.
4. If the user also wants the open FreeCAD model updated, plan to rerun the same command with
   `--sync-cad --doc-name <doc>` during execution.

#### FreeCAD document branch

1. Use this branch only if no YAML source exists.
2. Inspect the target object and current placement.
3. Run `freecad-check-collision` as the document-only fallback analyzer.
4. If the CLI is unavailable or broken in the current environment, fall back to the `check-collision.md` scripted workflow, using descendant solids transformed by `getGlobalPlacement()` so container moves are checked in document coordinates.
5. If needed, compute the maximum safe move distance or safe position before mutation.
6. Convert that result into a user-facing move summary.

## Step 3: Execute the safe move plan

Before mutation, determine and record:

- the requested move
- whether the part can move exactly as requested
- if not, the closest safe move or maximum safe move
- what constraints caused the adjustment

## Step 4: Write YAML, sync CAD, and report the result

### YAML branch execution

1. Run `freecad-yaml-safe-move` so the safe move result is written to a new YAML file.
2. If the target CAD document should be updated in place, run the same command with `--sync-cad --doc-name <doc>`.
3. Do not create a new assembly by default. Use `freecad-create-assembly` only when the user explicitly asks for a rebuilt assembly file or document.
4. Return:
   - the new YAML path
   - the updated document result when CAD sync was requested
   - a short summary of the requested move and any safety adjustment

### FreeCAD document branch execution

1. Apply the computed safe move using `freecad-move-obj` or an equivalent scripted operation.
2. Re-run collision verification immediately after the move using the same global-shape method as the pre-check.
3. If the post-move check reports any unexpected collision, surface that failure clearly and do not describe the move as successful.
4. Reflect the final safe position back into the source YAML.
5. Keep the existing document updated in place by default. Use `load-yaml-data` or `create-assembly` only when the user explicitly asks for a rebuild.
6. Return:
   - the new YAML path
   - the updated document result
   - a short summary of the requested move and any safety adjustment

## Required Behavior

- Do not directly move a part just because the user asked to move it.
- Always analyze first.
- Prefer the YAML branch whenever a configuration file exists.
- For YAML-driven motion, use `freecad-yaml-safe-move` rather than reimplementing the logic manually.
- Use `freecad-yaml-safe-move --sync-cad` to update CAD from the approved YAML result when possible.
- When the user wants to move a component to another envelope face, use `freecad-yaml-safe-move --install-face <0..5>` so the workflow explicitly rotates the component and keeps `mount_face` as the component's own face.
- For full regeneration from YAML, use `freecad-create-assembly` only when the user explicitly asks for a new assembly output.
- For document collision analysis, use `freecad-check-collision` only as a fallback when the YAML source is unavailable.
- If there is collision or overlap risk, compute and execute the safe movement scheme, then report the adjustment to the user.
- For container targets such as `App::Part`, collision analysis must be based on moved descendant solids in global coordinates, not the container's local shape.
- A successful pre-check is not enough by itself; the workflow must include a post-move collision verification step before reporting success.
- If there is no source YAML for a document-based task, do not fabricate one silently; stop after
  analysis and explain what is missing.

## Related Guides

- Use `yaml-safe-move.md` for YAML-side collision-safe motion and YAML rewriting.
- Use `check-collision.md` for document-side collision analysis only when YAML is unavailable.
- Use `move-object.md` only after the safe final move has been computed and only when YAML-driven execution cannot be used.
- Use `create-assembly.md` only when the user explicitly asks for a rebuilt assembly after the move.
