"""Explicit workspace helpers for FreeCAD CLI commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from freecad_cli_tools.runtime_config import (
    get_default_geom_component_info_path,
    get_default_geom_path,
    get_default_layout_topology_path,
    get_default_workspace_dir,
    set_default_workspace_dir,
)


def add_workspace_arg(parser: argparse.ArgumentParser) -> None:
    """Add a shared explicit workspace argument."""
    parser.add_argument(
        "--workspace",
        help=(
            "Absolute or relative workspace root. When provided, all default input/output "
            "paths resolve under this directory and override runtime config discovery."
        ),
    )


def apply_workspace_override(workspace: str | Path | None) -> Path:
    """Apply an explicit workspace override, or return the configured default workspace."""
    if workspace is not None:
        return set_default_workspace_dir(workspace)
    return get_default_workspace_dir().expanduser().resolve()


def validate_workspace_root(workspace: str | Path | None) -> Path:
    """Resolve the workspace and ensure the root directory exists."""
    workspace_root = apply_workspace_override(workspace)
    if not workspace_root.exists():
        raise FileNotFoundError(f"workspace not found: {workspace_root}")
    if not workspace_root.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {workspace_root}")
    return workspace_root


def required_workspace_inputs(
    *,
    require_layout_topology: bool = True,
    require_geom: bool = True,
    require_component_info: bool = False,
) -> dict[str, Path]:
    """Return the required default workspace input files."""
    inputs: dict[str, Path] = {}
    if require_layout_topology:
        inputs["layout_topology"] = get_default_layout_topology_path().resolve()
    if require_geom:
        inputs["geom"] = get_default_geom_path().resolve()
    if require_component_info:
        inputs["geom_component_info"] = get_default_geom_component_info_path().resolve()
    return inputs


def validate_workspace_inputs(
    workspace: str | Path | None,
    *,
    require_layout_topology: bool = True,
    require_geom: bool = True,
    require_component_info: bool = False,
) -> tuple[Path, dict[str, Path]]:
    """Resolve the workspace and ensure the required default inputs exist."""
    workspace_root = validate_workspace_root(workspace)
    inputs = required_workspace_inputs(
        require_layout_topology=require_layout_topology,
        require_geom=require_geom,
        require_component_info=require_component_info,
    )
    missing = [path for path in inputs.values() if not path.exists()]
    if missing:
        missing_paths = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"missing required workspace input files: {missing_paths}")
    return workspace_root, inputs
