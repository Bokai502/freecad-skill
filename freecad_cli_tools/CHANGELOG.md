# Changelog

## [0.8.0] - 2026-04-08

### Refactored

- Extract `geometry.py` module: all 44 pure geometry functions and 8 constants moved out of
  `yaml_component_safe_move.py` (1081 -> ~280 lines). CLI file now focuses on parsing, YAML I/O,
  CAD sync, and orchestration only.
- Add cross-reference comments in `rpc_script_fragments.py` mapping each FreeCAD-side fragment
  function to its `geometry.py` equivalent.
- Backward-compatible re-exports kept in `yaml_component_safe_move.py`; new code should import
  from `freecad_cli_tools.geometry` directly.

### Added

- `yaml_schema.py`: YAML assembly schema validation with `validate_assembly()` and
  `AssemblyValidationError`. Provides clear error messages (including component ID) instead of
  cryptic `KeyError`. Called automatically in `freecad-yaml-safe-move` after loading YAML.
- `tests/test_yaml_schema.py`: 15 tests for schema validation.
- `tests/test_fragment_sync.py`: cross-validation tests ensuring `rpc_script_fragments.py` string
  fragments stay in sync with `geometry.py` functions.
- `tests/test_rpc_script_templates.py`: renders all 6 RPC script templates with dummy placeholders
  and verifies valid Python syntax via `compile()`.

### Fixed

- Replace manual `try/except/else` with `pytest.raises` in test suite; fix `AssertionError` typo.

## [0.7.0] - 2025

### Added

- In-place move workflow with `--spin` and `--install-face` support.
- Cylinder shape support for YAML assemblies and safe moves.
- Batched CAD placement sync via `freecad-sync-placements`.

## [0.6.0] - 2025

### Added

- Bilingual documentation (English and Chinese).
- Architecture diagrams.

## [0.4.0 - 0.5.0] - 2025

### Added

- CI pipeline and test suite.
- Batched CAD sync helpers.

## [0.2.0 - 0.3.0] - 2025

### Improved

- Startup reliability and performance.
- Move workflow enhancements.

## [0.1.0] - 2025

### Added

- Initial project setup with XML-RPC client, CLI commands, and FreeCAD-side script templates.
