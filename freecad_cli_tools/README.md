# FreeCAD CLI Tools

Command-line tools for interacting with FreeCAD documents, layout datasets, and
direct assembly-build workflows. The package includes both XML-RPC-based
commands and offline dataset utilities.

Chinese version: [README.zh-CN.md](./README.zh-CN.md)

## Installation

### Method 1: Install from source

```bash
cd /data/lbk/freecad_skills/freecad-skill/freecad_cli_tools
python -m pip install -e .
```

### Method 2: Build and install wheel

```bash
cd /data/lbk/freecad_skills/freecad-skill/freecad_cli_tools
python -m pip install build
python -m build
python -m pip install dist/freecad_cli_tools-*.whl
```

## Usage

After installation, all commands are available directly:

```bash
# Document operations
freecad-create-doc "MyDocument"
freecad-list-docs

# Object operations
freecad-create-obj "MyDoc" "Part::Box" "Box1" -p '{"Length": 100}'
freecad-edit-obj "MyDoc" "Box1" '{"Length": 200}'
freecad-del-obj "MyDoc" "Box1"
freecad-get-objs "MyDoc"
freecad-get-obj "MyDoc" "Box1"

# Library operations
freecad-get-parts
freecad-insert-part "Fasteners/Screws/M6x20.FCStd"

# Code execution and view
freecad-exec-code "import FreeCAD; print(FreeCAD.ActiveDocument.Name)"
freecad-get-view Isometric --output table.png
freecad-create-assembly --doc-name LayoutAssembly
freecad-create-assembly-from-component-info --doc-name DirectAssembly

# Safe move with layout_topology.json + geom.json
freecad-layout-safe-move --component P001 --move 50 50 0
freecad-layout-safe-move --component P001 --move 50 50 0 --sync-cad --doc-name LayoutAssembly
freecad-layout-safe-move --component P002 --install-face 4 --move 0 0 0
freecad-sync-placements --doc-name LayoutAssembly --updates-file updates.json

# Document-only fallback commands
freecad-check-collision "MyDoc" "P001_part" --move 0 0 -10
freecad-move-obj "MyDoc" "P001_part" 0 0 -10 --mode delta
```

By default, relative CLI paths are resolved against `FREECAD_WORKSPACE_DIR` from
the runtime config or environment. `freecad-create-assembly` reads
`./01_layout/layout_topology.json` and `./01_layout/geom.json`, then writes
`./02_geometry_edit/geometry_after.step` and sibling `geometry_after.glb` unless
you pass explicit paths.

`freecad-create-assembly-from-component-info` reads
`./01_layout/layout_topology.json`, `./01_layout/geom.json`, and
`./01_layout/geom_component_info.json`, then imports each component from
`display_info.assets.cad_rotated_path` when a readable STEP/STP exists. Missing
or unreadable STEP assets fall back to `Part::Box`. Oversized STEP assets also
fall back to `Part::Box`; use `--max-step-size-mb` to control that threshold or
`-1` to disable it. The direct-build workflow also exports
`./02_geometry_edit/geometry_after.step` and sibling `geometry_after.glb`.

## Recommended Move Workflow

Use the layout dataset as the source of truth whenever you have
`layout_topology.json` and `geom.json`:

1. Run `freecad-layout-safe-move` on the dataset pair.
2. Let it compute a safe move and write new dataset files under `./02_geometry_edit`.
3. If needed, pass `--sync-cad --doc-name <doc>` so the same command updates the FreeCAD document.
4. Only run `freecad-create-assembly` when you explicitly need a regenerated CAD document.

Use `freecad-check-collision` and `freecad-move-obj` only as document-only
fallbacks when no dataset source is available.

## Layout Dataset Safe Move Command

`freecad-layout-safe-move` is the layout-dataset move command. It can run as an
offline dataset preprocessing command, and it can also sync the approved result
into a running FreeCAD document.

Use it when you want to:

- move one component in `layout_topology.json + geom.json`
- detect component collisions against other components using their current bounded geometry
- preserve the component's current orientation while moving it, or explicitly reorient it onto a
  different envelope face
- keep internal components (faces 0–5) inside `envelope.inner_size`, or place external components
  (faces 6–11) on the outside of the envelope using `envelope.outer_size`
- write the updated dataset placement and geometry fields into new JSON files under `./02_geometry_edit`
- optionally update the matching component in an open FreeCAD document
- keep external-face moves inside the selected wall's in-plane 2D footprint and surface
  `FACE_BOUNDARY` when a requested path would slide past the wall edge

To build a new CAD document from the layout dataset, use:

```bash
freecad-create-assembly \
  --doc-name LayoutAssembly
```

This command creates:

- an `Assembly` container
- an `Envelope_part` with an `EnvelopeShell` when the normalized dataset envelope exists
- one `App::Part` plus one solid per component, currently `Part::Box` or `Part::Cylinder`
- a placeholder `.step` export and a sibling `.glb` export for the assembly
- an automatic fitted GUI view after generation

The command treats `placement.position` as the component local-bounds minimum
corner and performs collision-safe moves for the component's current
orientation by default. In the current normalized model, `placement.mount_face`
stores the *installation face* (0–11): faces 0–5 are internal (inside
the envelope, wall reference = `inner_size`); faces 6–11 are external (outside the envelope, wall
reference = `outer_size`). `placement.rotation_matrix` captures the assembly
orientation. When `--install-face` is supplied (accepts 0–11), the command
rotates the component so its own contact face is installed onto the requested envelope face, starts
from the centered position on that face, and applies the requested move as an in-plane offset there.
For external faces, the component is oriented outward (contact face points inward toward the
envelope center) and the envelope-boundary containment check is skipped. `--install-face` and
the requested move can be combined. If the full requested move is safe, it applies it directly. If not, it
finds the closest safe prefix on that segment. If no safe point exists on the requested segment, it
reports that no solution was found and still writes the constrained dataset
state. When `--sync-cad` is supplied, it then updates the matching component object in the target
FreeCAD document directly from the computed final placement.

External-face note: although faces `6-11` skip the inner-envelope containment check, they are still
clamped to the selected wall's in-plane boundary using `envelope.outer_size`. When the requested
segment would cross that footprint, the command truncates the move to the closest safe prefix and
includes `FACE_BOUNDARY` in the blocker list.

In the `skills_test` workspace workflow, move and rotation requests now default
to reading from `./01_layout` and writing new dataset files plus
`geometry_after.step` / `geometry_after.glb` under `./02_geometry_edit`, so the
source dataset remains unchanged unless the user explicitly overrides the paths.

Runtime defaults are resolved in this order: `FREECAD_RUNTIME_CONFIG`, project
`.freecad/freecad_runtime.conf`, project `freecad_runtime.conf`, user
`~/.config/freecad-cli-tools/runtime.conf`, then the legacy
[../config/freecad_runtime.conf](../config/freecad_runtime.conf) fallback.

For multi-component placement updates, `freecad-sync-placements` accepts a JSON list like:

```json
[
  {
    "component": "P006",
    "position": [-103.72, 139.72, -170.91],
    "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  },
  {
    "component": "P018",
    "position": [-249.72, 179.32, -170.91],
    "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  }
]
```

## Development Layout

- `src/freecad_cli_tools/cli/`: thin command entry points
- `src/freecad_cli_tools/geometry.py`: pure geometry, collision detection, and component-shape helpers (no external dependencies)
- `src/freecad_cli_tools/layout_dataset.py`: layout dataset normalization and reverse write-back
- `src/freecad_cli_tools/layout_dataset_common.py`: shared validation helpers for layout dataset parsing
- `src/freecad_cli_tools/layout_dataset_faces.py`: install-face mapping and reverse face resolution
- `src/freecad_cli_tools/layout_dataset_io.py`: atomic JSON I/O helpers for layout dataset files
- `src/freecad_cli_tools/component_info_assembly.py`: normalization for direct assembly builds from `geom_component_info.json`
- `src/freecad_cli_tools/freecad_sync.py`: reusable placement sync helpers for single or batched CAD updates
- `src/freecad_cli_tools/cli_support.py`: shared CLI-side helpers for RPC calls, output parsing, and file input
- `src/freecad_cli_tools/rpc_scripts/`: FreeCAD-side Python scripts executed over XML-RPC
- `src/freecad_cli_tools/rpc_script_loader.py`: packaged script loader and placeholder renderer
- `src/freecad_cli_tools/rpc_script_fragments.py`: reusable FreeCAD-side code fragments injected into script templates
- `tests/`: unit tests for geometry algorithms, schema validation, fragment sync verification, and RPC template syntax

## Requirements

- For RPC commands: FreeCAD with the MCP addon running on the host/port from the runtime config or environment
- Relative input and output paths are resolved against `FREECAD_WORKSPACE_DIR` from the runtime config or environment
- For offline layout-dataset use of `freecad-layout-safe-move`: Python 3.9+ only
- Python 3.9+

## License

MIT
