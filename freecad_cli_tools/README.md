# FreeCAD CLI Tools

Command-line tools for interacting with FreeCAD documents and related YAML layout files. The
package includes both XML-RPC-based commands and offline YAML utilities.

Chinese version: [README.zh-CN.md](./README.zh-CN.md)

## Installation

### Method 1: Install from source

```bash
cd D:\workspace\skills_test\freecad_cli_tools
conda run -n base pip install -e .
```

### Method 2: Build and install wheel

```bash
cd D:\workspace\skills_test\freecad_cli_tools
conda run -n base pip install build
conda run -n base python -m build
conda run -n base pip install dist/freecad_cli_tools-*.whl
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
freecad-create-assembly --input examples/sample.yaml --doc-name SampleYamlAssembly

# YAML-first safe move and optional CAD sync
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P001 --move 50 50 0
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P001 --move 50 50 0 --sync-cad --doc-name SampleYamlAssembly
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P002 --install-face 4 --move 0 0 0
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P021 --install-face 9 --move 60 0 0
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P002 --spin 90 --move 0 0 0
freecad-sync-placements --doc-name SampleYamlAssembly --updates-file updates.json

# Document-only fallback commands
freecad-check-collision "MyDoc" "P001_part" --move 0 0 -10
freecad-move-obj "MyDoc" "P001_part" 0 0 -10 --mode delta
```

`freecad-create-assembly` writes `<doc-name>.step` beside the YAML by default and also exports a
same-stem `.glb` beside it. If you pass `--output`, the sibling `.glb` follows that STEP path.

## Recommended Move Workflow

Use YAML as the source of truth whenever you have a configuration file:

1. Run `freecad-yaml-safe-move` on the YAML file.
2. Let it compute a safe move and write the updated YAML.
3. If needed, pass `--sync-cad --doc-name <doc>` so the same command updates the FreeCAD document.
4. Only run `freecad-create-assembly` when you explicitly need a regenerated CAD document.

Use `freecad-check-collision` and `freecad-move-obj` only as document-only fallbacks when no YAML
source is available.

## YAML Offline Move Command

`freecad-yaml-safe-move` is the YAML-first move command. It can run as an offline YAML
pre-processing command, and it can also sync the approved result into a running FreeCAD document.

Use it when you want to:

- move one component in a YAML assembly definition
- detect component collisions against other components using their current bounded geometry
- preserve the component's current orientation while moving it, or explicitly reorient it onto a
  different envelope face
- keep internal components (faces 0–5) inside `envelope.inner_size`, or place external components
  (faces 6–11) on the outside of the envelope using `envelope.outer_size`
- write the updated YAML placement with the new position, `mount_point`, `envelope_face`, and optional
  `rotation_matrix`
- optionally update the matching component in an open FreeCAD document
- keep external-face moves inside the selected wall's in-plane 2D footprint and surface
  `FACE_BOUNDARY` when a requested path would slide past the wall edge

To build a new CAD document from the updated YAML, use:

```bash
freecad-create-assembly --input examples/sample.yaml --doc-name SampleYamlAssembly
```

This command creates:

- an `Assembly` container
- an `Envelope_part` with an `EnvelopeShell` when YAML `envelope` data exists
- one `App::Part` plus one solid per component, currently `Part::Box` or `Part::Cylinder`
- a `.step` export and a sibling `.glb` export for the assembly
- an automatic fitted GUI view after generation

The command treats `placement.position` as the component local-bounds minimum corner and performs translation-only
collision-safe moves for the component's current orientation by default. In the current YAML/CLI
model, `placement.mount_face` stores the *installation face* (0–11): faces 0–5 are internal (inside
the envelope, wall reference = `inner_size`); faces 6–11 are external (outside the envelope, wall
reference = `outer_size`). `placement.envelope_face` is an optional explicit override for the
envelope face. `placement.rotation_matrix` captures the assembly orientation. With `--spin`, the
command rotates the component in place around the installed face normal in multiples of `90` degrees
while keeping the mount point fixed. When `--install-face` is supplied (accepts 0–11), the command
rotates the component so its own contact face is installed onto the requested envelope face, starts
from the centered position on that face, and applies the requested move as an in-plane offset there.
For external faces, the component is oriented outward (contact face points inward toward the
envelope center) and the envelope-boundary containment check is skipped. `--install-face` and
`--spin` can be combined. If the full requested move is safe, it applies it directly. If not, it
finds the closest safe prefix on that segment. If no safe point exists on the requested segment, it
reports that no solution was found and still writes an output YAML for the constrained placement
state. When `--sync-cad` is supplied, it then updates the matching component object in the target
FreeCAD document directly from the computed final placement.

External-face note: although faces `6-11` skip the inner-envelope containment check, they are still
clamped to the selected wall's in-plane boundary using `envelope.outer_size`. When the requested
segment would cross that footprint, the command truncates the move to the closest safe prefix and
includes `FACE_BOUNDARY` in the blocker list.

In the `skills_test` workspace workflow, move and rotation requests now default to overwriting the
source YAML path and re-exporting the existing `STEP` file in place, plus a sibling `.glb`, after
sync unless the user explicitly asks for a separate rebuilt output.

On this machine, FreeCAD may run inside WSL while the CLI runs on Windows. In that setup:

- use the normal Windows path for `--input` and `--output`
- the CLI still writes a YAML result to disk, but `--sync-cad` no longer requires FreeCAD to reopen that YAML file
- if Windows `localhost:9875` forwarding is unstable, pass `--host <current-wsl-ip> --port 9875`

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
- `src/freecad_cli_tools/yaml_schema.py`: YAML assembly schema validation with descriptive error messages
- `src/freecad_cli_tools/freecad_sync.py`: reusable placement sync helpers for single or batched CAD updates
- `src/freecad_cli_tools/cli_support.py`: shared CLI-side helpers for RPC calls, output parsing, and file input
- `src/freecad_cli_tools/rpc_scripts/`: FreeCAD-side Python scripts executed over XML-RPC
- `src/freecad_cli_tools/rpc_script_loader.py`: packaged script loader and placeholder renderer
- `src/freecad_cli_tools/rpc_script_fragments.py`: reusable FreeCAD-side code fragments injected into script templates
- `tests/`: unit tests for geometry algorithms, schema validation, fragment sync verification, and RPC template syntax

## Requirements

- For RPC commands: FreeCAD with the MCP addon running (RPC server on localhost:9875)
- For offline YAML-only use of `freecad-yaml-safe-move`: Python 3.9+ only
- Python 3.9+

## License

MIT
