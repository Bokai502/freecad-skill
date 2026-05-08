"""Minimal runtime settings for FreeCAD CLI tools.

Workspace resolution is intentionally strict:
- prefer explicit `--workspace` handled by CLI entry points
- otherwise require `FREECAD_WORKSPACE_DIR` in the environment

No project config, user config, or legacy config discovery remains.
"""

from __future__ import annotations

import os
from pathlib import Path

FALLBACK_RPC_HOST = "localhost"
FALLBACK_RPC_PORT = "9877"
FALLBACK_COMPONENT_INFO_MAX_STEP_SIZE_MB = "100"
DEFAULT_LAYOUT_INPUT_DIR = Path("./01_layout")
DEFAULT_GEOMETRY_EDIT_DIR = Path("./02_geometry_edit")
DEFAULT_GEOMETRY_AFTER_STEM = "geometry_after"


def get_runtime_setting(key: str, default: str) -> str:
    """Return a runtime setting from environment only."""
    return os.getenv(key, default)


def get_default_rpc_host() -> str:
    """Return the configured default RPC host."""
    return get_runtime_setting("FREECAD_RPC_HOST", FALLBACK_RPC_HOST)


def get_default_rpc_port() -> int:
    """Return the configured default RPC port."""
    return int(get_runtime_setting("FREECAD_RPC_PORT", FALLBACK_RPC_PORT))


def get_default_workspace_dir() -> Path:
    """Return the workspace root from environment, or fail fast."""
    raw = os.getenv("FREECAD_WORKSPACE_DIR")
    if raw is None or not raw.strip():
        raise RuntimeError(
            "FREECAD_WORKSPACE_DIR is not set. Pass --workspace to the CLI entry point "
            "or export FREECAD_WORKSPACE_DIR before running the command."
        )
    return Path(raw).expanduser().resolve()


def set_default_workspace_dir(path: str | Path) -> Path:
    """Set the workspace root explicitly for the current process."""
    resolved = Path(path).expanduser().resolve()
    os.environ["FREECAD_WORKSPACE_DIR"] = str(resolved)
    return resolved


def get_default_component_info_max_step_size_mb() -> float:
    """Return the configured default max STEP size for component-info builds."""
    return float(
        get_runtime_setting(
            "FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB",
            FALLBACK_COMPONENT_INFO_MAX_STEP_SIZE_MB,
        )
    )


def resolve_workspace_path(path: str | Path) -> Path:
    """Resolve a path against the configured workspace root when it is relative."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return get_default_workspace_dir() / candidate


def get_default_layout_topology_path() -> Path:
    """Return the default layout_topology.json path."""
    return resolve_workspace_path(DEFAULT_LAYOUT_INPUT_DIR / "layout_topology.json")


def get_default_geom_path() -> Path:
    """Return the default geom.json path."""
    return resolve_workspace_path(DEFAULT_LAYOUT_INPUT_DIR / "geom.json")


def get_default_geom_component_info_path() -> Path:
    """Return the default geom_component_info.json path."""
    return resolve_workspace_path(DEFAULT_LAYOUT_INPUT_DIR / "geom_component_info.json")


def get_default_geometry_edit_dir() -> Path:
    """Return the default output directory for geometry-edit artifacts."""
    return resolve_workspace_path(DEFAULT_GEOMETRY_EDIT_DIR)


def get_default_geometry_after_step_path() -> Path:
    """Return the default STEP output path for CLI-generated geometry."""
    return get_default_geometry_edit_dir() / f"{DEFAULT_GEOMETRY_AFTER_STEM}.step"


def resolve_geometry_after_step_path(path: str | Path | None = None) -> Path:
    """Resolve a STEP export target whose basename is always geometry_after.step."""
    if path is None:
        return get_default_geometry_after_step_path()

    candidate = resolve_workspace_path(path)
    if candidate.suffix:
        return candidate.with_name(f"{DEFAULT_GEOMETRY_AFTER_STEM}.step")
    return candidate / f"{DEFAULT_GEOMETRY_AFTER_STEM}.step"


def get_default_geometry_after_layout_topology_path() -> Path:
    """Return the default layout_topology output path for non-destructive edits."""
    return get_default_geometry_edit_dir() / f"{DEFAULT_GEOMETRY_AFTER_STEM}.layout_topology.json"


def get_default_geometry_after_geom_path() -> Path:
    """Return the default geom output path for non-destructive edits."""
    return get_default_geometry_edit_dir() / f"{DEFAULT_GEOMETRY_AFTER_STEM}.geom.json"


def get_default_artifact_registry_dir() -> Path:
    """Return the configured artifact registry directory."""
    raw = os.getenv("FREECAD_ARTIFACT_REGISTRY_DIR")
    if raw is not None and raw.strip():
        return Path(raw).expanduser().resolve()
    return get_default_workspace_dir() / "logs" / "registry"


DEFAULT_RPC_HOST = get_default_rpc_host()
DEFAULT_RPC_PORT = get_default_rpc_port()
