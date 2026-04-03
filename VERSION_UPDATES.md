# Version Updates

This workspace currently has one committed baseline:

- `a31d64b` `【add】初始化项目`

Everything below summarizes the updates made in the working tree after that commit.

## v0.1.0 - Initial Baseline

Date: 2026-04-01

- Initialized the `skills_test` workspace.
- Added the FreeCAD CLI tool source tree under `freecad_cli_tools/`.
- Added startup scripts and data folders for YAML-driven FreeCAD assembly work.

## v0.2.0 - Startup And Skill Workflow Updates

Date: 2026-04-02

- Added GUI/headless startup switching in [start_wsl_freecad_rpc.ps1](/D:/workspace/skills_test/scripts/start_wsl_freecad_rpc.ps1).
- Added WSLg GUI startup script [start_freecad_gui_wsl.sh](/D:/workspace/skills_test/scripts/start_freecad_gui_wsl.sh).
- Updated the FreeCAD skill rules so move requests:
  - analyze first, then execute directly without waiting for an extra confirmation step
  - update the current CAD/YAML by default instead of rebuilding a new assembly automatically
- Synced the latest FreeCAD skill backup into [freecad_skill_20260403](/D:/workspace/skills_test/skill_backups/freecad_skill_20260403).
- The latest backup supersedes the previous backup in [freecad_skill_20260402](/D:/workspace/skills_test/skill_backups/freecad_skill_20260402).

## v0.3.0 - Collision Search And Sync Performance Optimization

Date: 2026-04-03

- Reworked [yaml_component_safe_move.py](/D:/workspace/skills_test/freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) from dense path sampling to interval-based swept AABB analysis.
- Precomputed static obstacle bounds once per move request instead of recomputing them during every candidate test.
- Reduced the fallback sampling path from `2000 + 60` style probing to `256 + 24` only for edge cases.
- Changed the main safe-prefix search to a linear scan over obstacles instead of maintaining fragmented safe intervals.
- Added direct placement sync script [sync_component_placement.py](/D:/workspace/skills_test/freecad_cli_tools/src/freecad_cli_tools/rpc_scripts/sync_component_placement.py).
- Removed the need for FreeCAD to reopen and parse YAML during `--sync-cad`; the final position and rotation are now passed directly over RPC.
- Skipped the extra RPC `ping()` round-trip before `execute_code`, reducing per-call latency in [rpc_client.py](/D:/workspace/skills_test/freecad_cli_tools/src/freecad_cli_tools/rpc_client.py) and [cli_support.py](/D:/workspace/skills_test/freecad_cli_tools/src/freecad_cli_tools/cli_support.py).

## Functional Verification

Date: 2026-04-03

### Assembly Creation

- Created [OriginalSingleUnit_Verify.FCStd](/D:/workspace/skills_test/data/OriginalSingleUnit_Verify.FCStd) from [sample.yaml](/D:/workspace/skills_test/data/sample.yaml).
- Created [CompareSingleUnit_Verify.FCStd](/D:/workspace/skills_test/data/CompareSingleUnit_Verify.FCStd) from [sample.yaml](/D:/workspace/skills_test/data/sample.yaml).
- Both documents opened successfully in FreeCAD:
  - `OriginalSingleUnit_Verify`
  - `CompareSingleUnit_Verify`

### Move Workflow

- Ran a real move test on `CompareSingleUnit_Verify`:
  - Component: `P005`
  - Target: `TOP` face, right-front direction
  - Output YAML: [compare_single_unit_verify.P005.top-right-front.yaml](/D:/workspace/skills_test/data/compare_single_unit_verify.P005.top-right-front.yaml)
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
