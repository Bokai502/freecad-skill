# Version Updates

This document tracks notable workspace-level updates for `skills_test`.

Original baseline commit:

- `a31d64b` `initial project setup`

## v0.1.0 - Initial Baseline

Date: 2026-04-01

- Initialized the `skills_test` workspace.
- Added the FreeCAD CLI tool source tree under `freecad_cli_tools/`.
- Added startup scripts and data folders for YAML-driven FreeCAD assembly work.

## v0.2.0 - Startup And Skill Workflow Updates

Date: 2026-04-02

- Added GUI/headless startup switching in [start_wsl_freecad_rpc.ps1](./scripts/start_wsl_freecad_rpc.ps1).
- Added WSLg GUI startup script [start_freecad_gui_wsl.sh](./scripts/start_freecad_gui_wsl.sh).
- Updated the FreeCAD skill rules so move requests:
  - analyze first, then execute directly without waiting for an extra confirmation step
  - update the current CAD/YAML by default instead of rebuilding a new assembly automatically
- Synced the latest FreeCAD skill backup into the tracked backup directory under [`skill_backups/`](./skill_backups/).
- Simplified skill backup management so the workspace keeps only the latest snapshot.

## v0.3.0 - Collision Search And Sync Performance Optimization

Date: 2026-04-03

- Reworked [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) from dense path sampling to interval-based swept AABB analysis.
- Precomputed static obstacle bounds once per move request instead of recomputing them during every candidate test.
- Reduced the fallback sampling path from `2000 + 60` style probing to `256 + 24` only for edge cases.
- Changed the main safe-prefix search to a linear scan over obstacles instead of maintaining fragmented safe intervals.
- Added direct placement sync script [sync_component_placement.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_scripts/sync_component_placement.py).
- Removed the need for FreeCAD to reopen and parse YAML during `--sync-cad`; the final position and rotation are now passed directly over RPC.
- Skipped the extra RPC `ping()` round-trip before `execute_code`, reducing per-call latency in [rpc_client.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_client.py) and [cli_support.py](./freecad_cli_tools/src/freecad_cli_tools/cli_support.py).

## Functional Verification

Date: 2026-04-03

### Assembly Creation

- Created runtime verification assemblies under `data/` from [sample.yaml](./examples/sample.yaml):
  - `OriginalSingleUnit_Verify.FCStd`
  - `CompareSingleUnit_Verify.FCStd`
- Both documents opened successfully in FreeCAD:
  - `OriginalSingleUnit_Verify`
  - `CompareSingleUnit_Verify`

### Move Workflow

- Ran a real move test on `CompareSingleUnit_Verify`:
  - Component: `P005`
  - Target: `TOP` face, right-front direction
  - Output YAML: `data/compare_single_unit_verify.P005.top-right-front.yaml`
- Verified that:
  - `OriginalSingleUnit_Verify` kept `P005` at the original placement `[170.39544205001832, -32.163340202523656, -170.91101196102727]`
  - `CompareSingleUnit_Verify` updated `P005` to `[159.80590107668024, 53.18129340212163, 81.58361030306861]`
  - the compare document also received the expected rotated placement quaternion `[0.0, -0.7071067811865475, 0.0, 0.7071067811865476]`

## Performance Comparison

Benchmark case: `P005 -> TOP face right-front`, same machine, same YAML, same `--sync-cad` document update path unless noted.

| Scenario | Measured Time |
|---|---:|
| Current algorithm, no CAD sync | `0.42s` |
| Earlier optimized search, before sync-path optimization | `~5.20s` |
| Direct placement sync without YAML reread, before RPC round-trip optimization | `~4.80s` |
| Current version after RPC optimization | `~2.76s` |
| Current verification move on `CompareSingleUnit_Verify` | `~2.63s` |

Summary:

- Collision search is no longer the dominant bottleneck.
- The remaining major cost is now the actual FreeCAD document mutation and GUI-side update work.
- Compared with the earlier `~5.20s` sync path, the current `~2.76s` result is about a `47%` reduction in wall-clock time for the tested move path.

## v0.4.0 - Quality, CI, And Repo Hygiene

Date: 2026-04-03

- Added unit tests for the YAML safe-move core in [test_yaml_component_safe_move.py](./freecad_cli_tools/tests/test_yaml_component_safe_move.py).
- Added test path configuration in [pyproject.toml](./freecad_cli_tools/pyproject.toml).
- Added GitHub Actions CI in [ci.yml](./.github/workflows/ci.yml) to run `ruff`, `black --check`, and `pytest`.
- Bumped the package version from `0.1.0` to `0.4.0` in [pyproject.toml](./freecad_cli_tools/pyproject.toml) and [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py).
- Moved the tracked example YAML out of `data/` into [examples/sample.yaml](./examples/sample.yaml) so `data/` can remain a runtime/output-only directory.
- Added Python cache ignores and removed tracked `__pycache__` artifacts from version control.
- Added a reusable benchmark utility in [benchmark_yaml_safe_move.py](./scripts/benchmark_yaml_safe_move.py).

## v0.5.0 - Reusable Sync Module And Batch CAD Updates

Date: 2026-04-03

- Added reusable placement sync helpers in [freecad_sync.py](./freecad_cli_tools/src/freecad_cli_tools/freecad_sync.py) so CLI commands can share one normalization and RPC rendering path.
- Added batch placement sync CLI [sync_component_placements.py](./freecad_cli_tools/src/freecad_cli_tools/cli/sync_component_placements.py).
- Added FreeCAD-side batch sync script [sync_component_placements.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_scripts/sync_component_placements.py) to update multiple components in one RPC call and optionally recompute only once.
- Switched [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) to use the shared batch sync pathway even for single-component updates, reducing duplication in the sync flow.
- Fixed JSON file loading in [cli_support.py](./freecad_cli_tools/src/freecad_cli_tools/cli_support.py) so PowerShell-generated UTF-8 BOM files can be used directly with `--updates-file`.
- Updated [README.md](./freecad_cli_tools/README.md), [pyproject.toml](./freecad_cli_tools/pyproject.toml), and [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py) to document and expose the new sync interface.

## v0.6.0 - Documentation, Bilingual Guides, And Diagrams

Date: 2026-04-03

- Added the Chinese changelog [VERSION_UPDATES.zh-CN.md](./VERSION_UPDATES.zh-CN.md).
- Added workspace-level bilingual entry docs [README.md](./README.md) and [README.zh-CN.md](./README.zh-CN.md).
- Added architecture and workflow diagrams in [ARCHITECTURE.md](./docs/ARCHITECTURE.md).
- Clarified the relationship between workspace docs, package docs, examples, runtime outputs, and startup scripts.

## v0.7.0 - In-Place Move Workflow And Skill Backup Refresh

Date: 2026-04-03

- Added explicit `--spin` support for in-plane 90-degree rotation in [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py).
- Added unit coverage for same-face rotation and invalid spin input in [test_yaml_component_safe_move.py](./freecad_cli_tools/tests/test_yaml_component_safe_move.py).
- Updated the package docs in [freecad_cli_tools/README.md](./freecad_cli_tools/README.md) and [freecad_cli_tools/README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md) to document in-place YAML update examples and same-face rotation.
- Updated the workspace docs in [README.md](./README.md), [README.zh-CN.md](./README.zh-CN.md), and [ARCHITECTURE.md](./docs/ARCHITECTURE.md) to describe the default move/rotate workflow as: overwrite the source YAML and save the current `FCStd` document in place.
- Refreshed the tracked FreeCAD skill backup under [skill_backups/freecad](./skill_backups/freecad) and retired the older `skill_backups/freecad_skill` path.
- Bumped the package version from `0.5.0` to `0.7.0` in [pyproject.toml](./freecad_cli_tools/pyproject.toml) and [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py).

## v0.8.0 - Geometry Module Extraction And Schema Validation

Date: 2026-04-08

### Refactored

- Extracted all 44 pure geometry functions and 8 constants from [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) into a new dedicated module [geometry.py](./freecad_cli_tools/src/freecad_cli_tools/geometry.py). The CLI file shrinks from 1081 to ~280 lines and now only handles CLI parsing, YAML I/O, CAD sync, and orchestration.
- Added cross-reference comments in [rpc_script_fragments.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_script_fragments.py) mapping each FreeCAD-side string fragment function to its `geometry.py` equivalent, with a sync test to prevent silent divergence.
- Old import path `freecad_cli_tools.cli.yaml_component_safe_move` still works via backward-compatible re-exports; new code should import from `freecad_cli_tools.geometry`.

### Added

- New YAML assembly schema validation module [yaml_schema.py](./freecad_cli_tools/src/freecad_cli_tools/yaml_schema.py) with `validate_assembly()` and `AssemblyValidationError`. Called automatically after YAML loading in `freecad-yaml-safe-move`. Provides clear error messages including the component ID instead of cryptic `KeyError`.
- New test [test_yaml_schema.py](./freecad_cli_tools/tests/test_yaml_schema.py) with 15 tests for schema validation covering boxes, cylinders, missing fields, wrong types, and boundary cases.
- New test [test_fragment_sync.py](./freecad_cli_tools/tests/test_fragment_sync.py) cross-validating that `rpc_script_fragments.py` string fragments produce identical results to `geometry.py` functions for constants, rotation math, cylinder helpers, and position translation.
- New test [test_rpc_script_templates.py](./freecad_cli_tools/tests/test_rpc_script_templates.py) rendering all 6 RPC script templates with dummy placeholders and verifying valid Python syntax via `compile()`.
- Added [CHANGELOG.md](./freecad_cli_tools/CHANGELOG.md) to the package directory.

### Fixed

- Replaced manual `try/except/else` with `pytest.raises` in [test_yaml_component_safe_move.py](./freecad_cli_tools/tests/test_yaml_component_safe_move.py); also fixed a `AssertionError` typo in the original code.

### Updated

- Bumped the package version from `0.7.0` to `0.8.0` in [pyproject.toml](./freecad_cli_tools/pyproject.toml) and [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py).
- Updated Development Layout in [README.md](./freecad_cli_tools/README.md) and [README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md) to include `geometry.py`, `yaml_schema.py`, and `tests/`.
