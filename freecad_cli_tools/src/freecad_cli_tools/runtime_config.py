"""Minimal runtime settings for FreeCAD CLI tools.

Workspace resolution is intentionally strict:
- prefer explicit `--workspace` handled by CLI entry points
- otherwise use `FREECAD_WORKSPACE_DIR`, `WORKSPACE_DIR`, or the codex-web config

No project config, user config, or legacy config discovery remains.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CODEX_WEB_CONFIG_PATH = Path("/data/lbk/codex_web/config.json")
_CONFIG_CACHE: dict[str, Any] | None = None


def _load_codex_web_config() -> dict[str, Any]:
    """Return the codex-web config if it is available and valid."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    try:
        payload = json.loads(CODEX_WEB_CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        payload = {}

    _CONFIG_CACHE = payload if isinstance(payload, dict) else {}
    return _CONFIG_CACHE


def _get_freecad_config_value(key: str, default: str | None = None) -> str | None:
    freecad_config = _load_codex_web_config().get("freecad", {})
    if not isinstance(freecad_config, dict):
        return default

    value = freecad_config.get(key)
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    return str(value)


def _get_config_workspace_dir() -> str | None:
    config = _load_codex_web_config()
    value = config.get("WORKSPACE_DIR")
    if isinstance(value, str) and value.strip():
        return value
    return _get_freecad_config_value("workspaceDir")


FALLBACK_RPC_HOST = "localhost"
FALLBACK_RPC_PORT = _get_freecad_config_value("rpcPort", "9877")
FALLBACK_COMPONENT_INFO_MAX_STEP_SIZE_MB = "100"
CONFIG_WORKSPACE_DIR = _get_config_workspace_dir()
FREECAD_WORKSPACE_DIR = CONFIG_WORKSPACE_DIR
DEFAULT_LAYOUT_INPUT_DIR = Path("./01_layout")
DEFAULT_COMPONENT_INFO_INPUT_DIR = Path("./component_info")
DEFAULT_GEOMETRY_EDIT_DIR = Path("./02_geometry_edit")
DEFAULT_GEOMETRY_AFTER_STEM = "geometry_after"


def get_runtime_setting(key: str, default: str, config_key: str | None = None) -> str:
    """Return a runtime setting from environment, codex-web config, or fallback."""
    env_value = os.getenv(key)
    if env_value is not None and env_value.strip():
        return env_value
    if config_key is not None:
        config_value = _get_freecad_config_value(config_key)
        if config_value is not None:
            return config_value
    return default


def get_default_rpc_host() -> str:
    """Return the configured default RPC host."""
    return get_runtime_setting("FREECAD_RPC_HOST", FALLBACK_RPC_HOST, "rpcHost")


def get_default_rpc_port() -> int:
    """Return the configured default RPC port."""
    return int(get_runtime_setting("FREECAD_RPC_PORT", FALLBACK_RPC_PORT, "rpcPort"))


def get_default_workspace_dir() -> Path:
    """Return the workspace root from environment or codex-web config."""
    raw = os.getenv("FREECAD_WORKSPACE_DIR")
    if raw is None or not raw.strip():
        raw = os.getenv("WORKSPACE_DIR")
    if raw is None or not raw.strip():
        raw = FREECAD_WORKSPACE_DIR
    if raw is None or not raw.strip():
        raise RuntimeError(
            "FREECAD_WORKSPACE_DIR is not set, WORKSPACE_DIR is not set, "
            "and freecad.workspaceDir is not configured "
            f"in {CODEX_WEB_CONFIG_PATH}. Pass --workspace to the CLI entry point, export "
            "FREECAD_WORKSPACE_DIR, export WORKSPACE_DIR, or configure freecad.workspaceDir "
            "before running the command."
        )
    return Path(raw).expanduser().resolve()


def set_default_workspace_dir(path: str | Path) -> Path:
    """Set the workspace root explicitly for the current process."""
    resolved = Path(path).expanduser().resolve()
    os.environ["FREECAD_WORKSPACE_DIR"] = str(resolved)
    os.environ["WORKSPACE_DIR"] = str(resolved)
    return resolved


def get_default_component_info_max_step_size_mb() -> float:
    """Return the configured default max STEP size for component-info builds."""
    return float(
        get_runtime_setting(
            "FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB",
            FALLBACK_COMPONENT_INFO_MAX_STEP_SIZE_MB,
            "componentInfoMaxStepSizeMb",
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
    return resolve_workspace_path(DEFAULT_COMPONENT_INFO_INPUT_DIR / "geom_component_info.json")


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
