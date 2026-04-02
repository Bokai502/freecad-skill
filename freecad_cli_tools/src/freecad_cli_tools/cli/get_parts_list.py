#!/usr/bin/env python3
"""Get parts list from FreeCAD library."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Get parts list from FreeCAD library")
    add_connection_args(parser)
    args = parser.parse_args()
    run_rpc_command(args, "get_parts_list")


if __name__ == "__main__":
    main()
