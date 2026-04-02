#!/usr/bin/env python3
"""Get all objects in a FreeCAD document."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Get all objects in a FreeCAD document")
    parser.add_argument("doc_name", help="Name of the document")
    add_connection_args(parser)
    args = parser.parse_args()
    run_rpc_command(args, "get_objects", args.doc_name)


if __name__ == "__main__":
    main()
