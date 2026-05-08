# FreeCAD: Create CAD-Asset Assembly From Component Info

Build a brand-new FreeCAD assembly from component-info CAD assets:

- `layout_topology.json`
- `geom.json`
- `geom_component_info.json`

Use this workflow only when the request needs the extra
`geom_component_info.json` data, especially
`display_info.assets.cad_rotated_path`. It is the CAD-asset build path: import
real STEP/STP components when available, and fall back to simple boxes only for
components whose CAD asset is missing, unreadable, not STEP/STP, or too large.

Do not use this guide for the plain placeholder build from only
`layout_topology.json + geom.json`; use `create-assembly.md` for that case.

This workflow creates a new document, builds the envelope from
`geom.outer_shell`, imports real STEP components from `cad_rotated_path` when
available, falls back to box placeholders when needed, and exports:

- `component_info_assembly.step`
- `component_info_assembly.glb`

## Core Rules

- `layout_topology.json` provides installation-face truth:
  - `mount_face_id`
  - `component_mount_face_id`
  - `alignment`
- `geom.json` provides envelope truth through `outer_shell`.
- `geom_component_info.json` provides component build truth:
  - target bbox or `position + dims`
  - `category`
  - `color`
  - `display_info.assets.cad_rotated_path`
- If `cad_rotated_path` exists and the file is a readable STEP/STP, import it.
- If `cad_rotated_path` is missing, unreadable, not a STEP/STP, or exceeds
  `--max-step-size-mb`, generate an axis-aligned box from the target bbox
  instead.
- Identical STEP paths are imported once per build and then reused for later
  components that reference the same `cad_rotated_path`.
- This workflow creates a new assembly. It does not preserve objects from an
  older STEP assembly and does not modify `layout_topology.json`,
  `geom.json`, or `geom_component_info.json`.

## Inputs

| Flag | Required | Description |
|------|----------|-------------|
| `--layout-topology` | no | Source `layout_topology.json`. Defaults to `./01_layout/layout_topology.json`. |
| `--geom` | no | Source `geom.json`. Defaults to `./01_layout/geom.json`. |
| `--geom-component-info` | no | Source `geom_component_info.json`. Defaults to `./01_layout/geom_component_info.json`. |
| `--doc-name` | yes | FreeCAD document name to create. |
| `--output` | no | Optional STEP output path or directory. Export names remain `component_info_assembly.step` and `component_info_assembly.glb`. |
| `--max-step-size-mb` | no | Maximum STEP/STP size to import before falling back to a box. Defaults to `FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB`, then `/data/lbk/codex_web/config.json` field `freecad.componentInfoMaxStepSizeMb`, then `100`. Use `-1` to disable the limit. |
| `--no-fit-view` | no | Skip GUI fit/view update. |
| `--host`, `--port` | no | FreeCAD RPC settings. Defaults come from `FREECAD_RPC_HOST` / `FREECAD_RPC_PORT`, then `/data/lbk/codex_web/config.json` fields `freecad.rpcHost` / `freecad.rpcPort`. |

## Data Mapping

### Envelope

Use `geom.outer_shell`:

- `outer_bbox.min/max` -> envelope outer size
- `inner_bbox.min/max` -> envelope inner size
- `thickness` -> shell thickness

### Components

For each component in `geom_component_info.json`:

1. Match `component_id` to `layout_topology.placements[*].component_id`.
2. Read:
   - `mount_face_id`
   - `component_mount_face_id`
   - `alignment`
3. Read the target geometry from `geom_component_info.json`:
   - preferred: `bbox.min/max`
   - fallback: `position + dims`
4. Read `cad_rotated_path` from `display_info.assets.cad_rotated_path`.
5. If the STEP exists and is within the allowed size threshold, import it,
   derive the runtime orientation from `component_mount_face_id ->
   mount_face_id` plus `alignment.in_plane_rotation_deg`, rotate the geometry
   into that orientation first, then align the rotated bbox to the target bbox.
6. If the STEP is unavailable or oversized, create a `Part::Box` exactly
   covering the target bbox.

## Command Pattern

Read resolved defaults first:

```bash
freecad-runtime-config
```

```bash
freecad-create-assembly-from-component-info \
  --layout-topology ./01_layout/layout_topology.json \
  --geom ./01_layout/geom.json \
  --geom-component-info ./01_layout/geom_component_info.json \
  --max-step-size-mb 100 \
  --doc-name DirectAssembly
```

## Output Files

Note: this command can be slow when it imports real STEP/STP CAD assets and
exports STEP/GLB files. Be patient and wait for the progress log or final
artifacts before assuming the build has stalled.

The command writes CAD artifacts under the configured workspace reported by
`freecad-runtime-config` by default:

- STEP: `<configured workspace>/02_geometry_edit/component_info_assembly.step`
- GLB: `<configured workspace>/02_geometry_edit/component_info_assembly.glb`
- Progress JSON: `<configured workspace>/logs/progress_percentages.json`

If `--output` is provided, it only selects the output directory or parent path.
The exported filenames still remain `component_info_assembly.step` and
`component_info_assembly.glb`.

The workflow does not write replacement dataset files. In particular, it does
not produce `geometry_after.layout_topology.json` or `geometry_after.geom.json`;
those are produced by the safe-move workflow.

## Output Fields To Check

- `success`
- `save_path`
- `glb_path`
- `component_count`
- `progress_percentages`
- `progress_json_path`
- progress log `output_files.step` and `output_files.glb`
- `layout_completion_percent`
- `modeling_percent`
- `export_file_percent`
- `step_component_ids`
- `box_component_ids`
- `fallback_box_component_ids`
- `fallback_components_by_reason`

Within each `components[*]` record, also check:

- `source_step_path`
- `requested_step_path`
- `step_size_bytes`
- `fallback_reason`
- `cache_hit`
- `shape_object_count`

## Reporting Template

Report direct builds in this order:

1. State that a new assembly was created from `layout_topology.json + geom.json + geom_component_info.json`.
2. State how many components were imported from STEP.
3. State how many components fell back to box placeholders.
4. If any boxes were fallbacks, state the main `fallback_reason` categories.
5. State `layout_completion_percent`, `modeling_percent`, and `export_file_percent`.
6. State `progress_json_path`.
7. State the output STEP and GLB paths from the payload and progress log `output_files`.
