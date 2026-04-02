#!/usr/bin/env python3
"""List all open documents in FreeCAD."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="List open FreeCAD documents")
    add_connection_args(parser)
    args = parser.parse_args()
    run_rpc_command(args, "list_documents")


if __name__ == "__main__":
    main()
