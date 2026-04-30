"""Shared runtime configuration loader for FreeCAD CLI tools."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

CONFIG_ENV_VAR = "FREECAD_RUNTIME_CONFIG"
PROJECT_CONFIG_PATHS = (
    Path(".freecad") / "freecad_runtime.conf",
    Path("freecad_runtime.conf"),
)
USER_CONFIG_RELATIVE_PATH = Path("freecad-cli-tools") / "runtime.conf"
LEGACY_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "freecad_runtime.conf"
DEFAULT_CONFIG_PATH = LEGACY_CONFIG_PATH
FALLBACK_RPC_HOST = "localhost"
FALLBACK_RPC_PORT = "9876"
FALLBACK_WORKSPACE_DIR = "."
FALLBACK_COMPONENT_INFO_MAX_STEP_SIZE_MB = "100"
DEFAULT_LAYOUT_INPUT_DIR = Path("./01_layout")
DEFAULT_GEOMETRY_EDIT_DIR = Path("./02_geometry_edit")
DEFAULT_GEOMETRY_AFTER_STEM = "geometry_after"


def parse_runtime_config(path: str | Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE config file."""
    config: dict[str, str] = {}
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        config[key.strip()] = value.strip()
    return config


def get_user_runtime_config_path() -> Path:
    """Return the user-level runtime config path."""
    config_home = os.getenv("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / USER_CONFIG_RELATIVE_PATH
    return Path.home() / ".config" / USER_CONFIG_RELATIVE_PATH


def get_runtime_config_candidates() -> list[Path]:
    """Return runtime config paths in lookup order."""
    explicit_path = os.getenv(CONFIG_ENV_VAR)
    if explicit_path:
        return [Path(explicit_path).expanduser()]

    cwd = Path.cwd()
    return [
        *(cwd / path for path in PROJECT_CONFIG_PATHS),
        get_user_runtime_config_path(),
        LEGACY_CONFIG_PATH,
    ]


def resolve_runtime_config_path() -> Path | None:
    """Return the first existing runtime config path, if any."""
    for candidate in get_runtime_config_candidates():
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_runtime_config() -> dict[str, str]:
    """Load runtime config from disk once per process."""
    config_path = resolve_runtime_config_path()
    if config_path is None:
        return {}
    return parse_runtime_config(config_path)


def get_runtime_setting(key: str, default: str) -> str:
    """Return a runtime setting, preferring environment overrides."""
    return os.getenv(key, load_runtime_config().get(key, default))


def get_default_rpc_host() -> str:
    """Return the configured default RPC host."""
    return get_runtime_setting("FREECAD_RPC_HOST", FALLBACK_RPC_HOST)


def get_default_rpc_port() -> int:
    """Return the configured default RPC port."""
    return int(get_runtime_setting("FREECAD_RPC_PORT", FALLBACK_RPC_PORT))


def get_default_workspace_dir() -> Path:
    """Return the configured workspace root for relative dataset paths."""
    return Path(get_runtime_setting("FREECAD_WORKSPACE_DIR", FALLBACK_WORKSPACE_DIR))


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
    """Resolve a STEP export target whose basename is always geometry_after.step.

    When a path is provided:
    - absolute or relative file paths keep their parent directory
    - directory-like paths (no suffix) place the file under that directory
    """
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
    return Path(
        get_runtime_setting(
            "FREECAD_ARTIFACT_REGISTRY_DIR",
            str(get_default_workspace_dir() / "registry"),
        )
    )


DEFAULT_RPC_HOST = get_default_rpc_host()
DEFAULT_RPC_PORT = get_default_rpc_port()
DEFAULT_WORKSPACE_DIR = get_default_workspace_dir()
DEFAULT_COMPONENT_INFO_MAX_STEP_SIZE_MB = get_default_component_info_max_step_size_mb()
DEFAULT_ARTIFACT_REGISTRY_DIR = get_default_artifact_registry_dir()
