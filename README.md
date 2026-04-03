# Skills Test Workspace

`skills_test` is a FreeCAD-oriented workspace for YAML-driven assembly generation, collision-aware component movement, and CAD synchronization through XML-RPC.

## What This Workspace Contains

- `freecad_cli_tools/`: Python package that provides FreeCAD CLI commands, YAML-safe move logic, RPC helpers, tests, and package-level documentation.
- `scripts/`: startup scripts, benchmarking utilities, and workspace-side helper scripts.
- `examples/`: tracked example input files such as [sample.yaml](./examples/sample.yaml).
- `data/`: runtime outputs such as generated FCStd files, updated YAML files, screenshots, and temporary verification artifacts. This directory is intentionally ignored by git.
- `skill_backups/`: local backup of the current FreeCAD skill instructions.

## Key Capabilities

- Start FreeCAD in GUI or headless mode through WSL/WSLg.
- Build FreeCAD assemblies from YAML definitions.
- Move components safely with envelope and collision constraints.
- Sync one or many computed placements into a live FreeCAD document.
- Benchmark safe-move performance and validate behavior with tests and CI.

## Quick Start

### 1. Start the FreeCAD RPC service

```powershell
& "D:\workspace\skills_test\scripts\start_wsl_freecad_rpc.ps1" -Gui
```

For headless mode:

```powershell
& "D:\workspace\skills_test\scripts\start_wsl_freecad_rpc.ps1" -Mode Headless
```

### 2. Install the CLI package

```powershell
python -m pip install -e .\freecad_cli_tools[dev]
```

### 3. Create an assembly from YAML

```powershell
freecad-create-assembly --input examples\sample.yaml --doc-name SampleYamlAssembly
```

### 4. Run a safe move and sync it back to CAD

```powershell
freecad-yaml-safe-move --input examples\sample.yaml --output data\sample.updated.yaml --component P005 --install-face 5 --move 228.83671815191935 195.70657882164386 0 --sync-cad --doc-name SampleYamlAssembly
```

### 5. Batch-sync multiple placements

```powershell
freecad-sync-placements --doc-name SampleYamlAssembly --updates-file updates.json
```

## Documentation Map

- English changelog: [VERSION_UPDATES.md](./VERSION_UPDATES.md)
- Chinese changelog: [VERSION_UPDATES.zh-CN.md](./VERSION_UPDATES.zh-CN.md)
- Package guide (English): [freecad_cli_tools/README.md](./freecad_cli_tools/README.md)
- Package guide (Chinese): [freecad_cli_tools/README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md)
- Architecture and workflow diagrams: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- Startup guides:
  - [FreeCAD Startup Overview (Chinese)](./FreeCAD_启动总览.md)
  - [WSL_FreeCAD_Startup_Guide.md](./WSL_FreeCAD_Startup_Guide.md)

## Workspace Layout

```text
skills_test/
|-- freecad_cli_tools/      # CLI package, RPC helpers, tests
|-- scripts/                # startup and benchmark scripts
|-- examples/               # tracked sample inputs
|-- data/                   # runtime outputs, ignored by git
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
