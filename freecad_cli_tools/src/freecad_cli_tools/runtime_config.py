"""Shared runtime configuration loader for the FreeCAD skill repo."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

CONFIG_ENV_VAR = "FREECAD_RUNTIME_CONFIG"
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "freecad_runtime.conf"
)
FALLBACK_RPC_HOST = "localhost"
FALLBACK_RPC_PORT = "9876"
FALLBACK_RUNTIME_DATA_DIR = "/tmp/freecad_data"


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


@lru_cache(maxsize=1)
def load_runtime_config() -> dict[str, str]:
    """Load repo runtime config from disk once per process."""
    config_path = Path(os.getenv(CONFIG_ENV_VAR, str(DEFAULT_CONFIG_PATH)))
    if not config_path.is_file():
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


def get_default_runtime_data_dir() -> Path:
    """Return the configured shared runtime data directory."""
    return Path(
        get_runtime_setting("FREECAD_RUNTIME_DATA_DIR", FALLBACK_RUNTIME_DATA_DIR)
    )


def get_default_artifact_registry_dir() -> Path:
    """Return the configured artifact registry directory."""
    return Path(
        get_runtime_setting(
            "FREECAD_ARTIFACT_REGISTRY_DIR",
            str(get_default_runtime_data_dir() / "registry"),
        )
    )


DEFAULT_RPC_HOST = get_default_rpc_host()
DEFAULT_RPC_PORT = get_default_rpc_port()
DEFAULT_RUNTIME_DATA_DIR = get_default_runtime_data_dir()
DEFAULT_ARTIFACT_REGISTRY_DIR = get_default_artifact_registry_dir()
