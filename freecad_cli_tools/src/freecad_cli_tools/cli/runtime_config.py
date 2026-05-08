#!/usr/bin/env python3
"""Print resolved FreeCAD CLI runtime configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from freecad_cli_tools import runtime_config

RUNTIME_CONFIG_KEYS = (
    "config_path",
    "workspace_dir",
    "rpc_host",
    "rpc_port",
    "component_info_max_step_size_mb",
    "layout_topology_path",
    "geom_path",
    "geom_component_info_path",
    "geometry_edit_dir",
    "geometry_after_step_path",
    "geometry_after_layout_topology_path",
    "geometry_after_geom_path",
    "artifact_registry_dir",
)


def _path_payload(path: Path) -> str:
    return str(path)


def build_runtime_config_payload() -> dict[str, Any]:
    """Return resolved runtime configuration values used by CLI commands."""
    workspace_dir = runtime_config.get_default_workspace_dir()
    geometry_edit_dir = runtime_config.get_default_geometry_edit_dir()
    return {
        "config_path": str(runtime_config.CODEX_WEB_CONFIG_PATH),
        "workspace_dir": _path_payload(workspace_dir),
        "rpc_host": runtime_config.get_default_rpc_host(),
        "rpc_port": runtime_config.get_default_rpc_port(),
        "component_info_max_step_size_mb": (
            runtime_config.get_default_component_info_max_step_size_mb()
        ),
        "layout_topology_path": _path_payload(runtime_config.get_default_layout_topology_path()),
        "geom_path": _path_payload(runtime_config.get_default_geom_path()),
        "geom_component_info_path": _path_payload(
            runtime_config.get_default_geom_component_info_path()
        ),
        "geometry_edit_dir": _path_payload(geometry_edit_dir),
        "geometry_after_step_path": _path_payload(
            runtime_config.get_default_geometry_after_step_path()
        ),
        "geometry_after_layout_topology_path": _path_payload(
            runtime_config.get_default_geometry_after_layout_topology_path()
        ),
        "geometry_after_geom_path": _path_payload(
            runtime_config.get_default_geometry_after_geom_path()
        ),
        "artifact_registry_dir": _path_payload(runtime_config.get_default_artifact_registry_dir()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print resolved FreeCAD CLI runtime configuration as JSON."
    )
    parser.add_argument(
        "--key",
        choices=RUNTIME_CONFIG_KEYS,
        help="Print only one resolved runtime configuration value.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_runtime_config_payload()
    if args.key:
        print(json.dumps({args.key: payload[args.key]}, indent=2, ensure_ascii=False))
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
