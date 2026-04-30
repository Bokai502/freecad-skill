# Skills Test Workspace

`skills_test` is a FreeCAD-oriented workspace for layout-dataset assembly generation, collision-aware component movement, and CAD synchronization through XML-RPC.

## What This Workspace Contains

- `freecad_cli_tools/`: Python package that provides FreeCAD CLI commands, YAML-safe move logic, RPC helpers, tests, and package-level documentation.
- `01_layout/`: tracked source layout dataset inputs.
- `02_geometry_edit/`: generated geometry-edit outputs such as `geometry_after.step` and validation files.
- `data/`: runtime outputs such as generated STEP files, updated YAML files, screenshots, and temporary verification artifacts. This directory is intentionally ignored by git.
- `skill_backups/`: local backup of the current FreeCAD skill instructions.

## Key Capabilities

- Connect CLI tools to a locally running FreeCAD MCP/XML-RPC service.
- Build FreeCAD assemblies from `layout_topology.json + geom.json`.
- Export placeholder assemblies from `layout_topology.json + geom.json`.
- Export direct real-CAD-or-box assemblies from `layout_topology.json + geom.json + geom_component_info.json`.
- Move components safely with inner-envelope, external-face boundary, and collision constraints.
- Sync one or many computed placements into a live FreeCAD document.
- Benchmark safe-move performance and validate behavior with tests and CI.

## Quick Start

### 1. Start the FreeCAD RPC service

```bash
freecad
```

Make sure the FreeCADMCP addon is installed and has started the XML-RPC service.
Runtime defaults come from `FREECAD_RUNTIME_CONFIG`, a project config such as
`.freecad/freecad_runtime.conf`, the user config
`~/.config/freecad-cli-tools/runtime.conf`, or the legacy
[config/freecad_runtime.conf](./config/freecad_runtime.conf) fallback.

### 2. Install the CLI package

```bash
python -m pip install -e ./freecad_cli_tools[dev]
```

### 3. Create an assembly from the layout dataset

```powershell
freecad-create-assembly --doc-name LayoutAssembly
```

Or build a brand-new assembly directly from component info:

```powershell
freecad-create-assembly-from-component-info --doc-name DirectAssembly
```

### 4. Run a safe move and sync it back to CAD

```powershell
freecad-layout-safe-move --component P005 --install-face 5 --move 228.83671815191935 195.70657882164386 0 --sync-cad --doc-name LayoutAssembly
```

For external-face placements, the same command uses `envelope.outer_size` as the wall reference,
keeps the component on the outside of the shell, and still constrains motion to the selected face's
2D footprint so it cannot slide past the wall edge.

In the current workspace skill workflow, relative CLI paths are resolved against
`FREECAD_WORKSPACE_DIR` from the runtime config or environment.
By default, source inputs are read from `./01_layout`, while generated dataset,
STEP, and GLB outputs are written to `./02_geometry_edit` using the base name
`geometry_after` so the originals are not modified.

When `./01_layout/geom_component_info.json` exists, `freecad-create-assembly-from-component-info`
combines it with `layout_topology.json` and `geom.json`, uses
`display_info.assets.cad_rotated_path` when available, falls back to a box when
the STEP asset is missing or exceeds `--max-step-size-mb`, and writes
`geometry_after.step` plus sibling `geometry_after.glb`.

### 5. Batch-sync multiple placements

```powershell
freecad-sync-placements --doc-name LayoutAssembly --updates-file updates.json
```

## Documentation Map

- English changelog: [VERSION_UPDATES.md](./VERSION_UPDATES.md)
- Chinese changelog: [VERSION_UPDATES.zh-CN.md](./VERSION_UPDATES.zh-CN.md)
- Package guide (English): [freecad_cli_tools/README.md](./freecad_cli_tools/README.md)
- Package guide (Chinese): [freecad_cli_tools/README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md)
- Architecture and workflow diagrams: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- Startup guide: [FreeCAD Startup Overview (Chinese)](./FreeCAD_启动总览.md)

## Workspace Layout

```text
skills_test/
|-- freecad_cli_tools/      # CLI package, RPC helpers, tests
|-- 01_layout/             # tracked layout dataset inputs
|-- 02_geometry_edit/      # generated geometry-edit outputs
|-- data/                  # other runtime outputs, ignored by git
|-- docs/                   # architecture and flow diagrams
|-- skill_backups/          # latest FreeCAD skill backup
|-- VERSION_UPDATES.md
\-- README.md
```

## Recommended Reading Order

1. Read this workspace README for the high-level structure.
2. Read [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for the system view and main workflow.
3. Read [freecad_cli_tools/README.md](./freecad_cli_tools/README.md) or [freecad_cli_tools/README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md) for CLI usage details.
4. Read [VERSION_UPDATES.md](./VERSION_UPDATES.md) for historical context and performance changes.
