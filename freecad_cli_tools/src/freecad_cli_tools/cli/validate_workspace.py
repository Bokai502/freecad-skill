#!/usr/bin/env python3
"""Validate a FreeCAD workspace and optional RPC connectivity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import format_rpc_connection_error
from freecad_cli_tools.rpc_client import FreeCADConnection, print_result as print_json
from freecad_cli_tools.workspace import validate_workspace_inputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a FreeCAD workspace root, required input files, and optional RPC "
            "connectivity before running a heavier build command."
        )
    )
    parser.add_argument("--workspace", required=True, help="Workspace root to validate.")
    parser.add_argument(
        "--require-component-info",
        action="store_true",
        help="Also require 01_layout/geom_component_info.json.",
    )
    parser.add_argument(
        "--check-rpc",
        action="store_true",
        help="Also verify that the configured FreeCAD RPC server is reachable.",
    )
    add_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root, inputs = validate_workspace_inputs(
        args.workspace,
        require_component_info=args.require_component_info,
    )

    payload: dict[str, object] = {
        "success": True,
        "workspace": str(workspace_root),
        "inputs": {name: str(path) for name, path in inputs.items()},
        "rpc": {
            "checked": bool(args.check_rpc),
            "reachable": None,
            "host": args.host,
            "port": args.port,
        },
    }

    if args.check_rpc:
        try:
            conn = FreeCADConnection(args.host, args.port)
            reachable = bool(conn.ping())
            payload["rpc"] = {
                "checked": True,
                "reachable": reachable,
                "host": args.host,
                "port": args.port,
            }
            if not reachable:
                raise RuntimeError(
                    f"Cannot connect to FreeCAD RPC server at {args.host}:{args.port}."
                )
        except Exception as exc:
            payload["success"] = False
            payload["rpc"] = {
                "checked": True,
                "reachable": False,
                "host": args.host,
                "port": args.port,
                "error": format_rpc_connection_error(exc, args.host, args.port),
            }
            print_json(payload)
            raise SystemExit(1)

    print_json(payload)


if __name__ == "__main__":
    main()
