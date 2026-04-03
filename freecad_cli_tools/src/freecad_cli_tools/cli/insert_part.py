#!/usr/bin/env python3
"""Insert a part from FreeCAD library."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert a part from FreeCAD library")
    parser.add_argument("relative_path", help="Relative path of the part in library")
    add_connection_args(parser)
    args = parser.parse_args()
    run_rpc_command(
        args, "insert_part_from_library", args.relative_path, require_success=True
    )


if __name__ == "__main__":
    main()
