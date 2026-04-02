#!/usr/bin/env python3
"""Create a new document in FreeCAD."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new FreeCAD document")
    parser.add_argument("name", help="Name of the document to create")
    add_connection_args(parser)
    args = parser.parse_args()
    run_rpc_command(args, "create_document", args.name, require_success=True)


if __name__ == "__main__":
    main()
