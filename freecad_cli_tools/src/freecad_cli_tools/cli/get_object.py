#!/usr/bin/env python3
"""Get a specific object from FreeCAD."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Get object properties from FreeCAD")
    parser.add_argument("doc_name", help="Name of the document")
    parser.add_argument("obj_name", help="Name of the object")
    add_connection_args(parser)
    args = parser.parse_args()
    run_rpc_command(args, "get_object", args.doc_name, args.obj_name)


if __name__ == "__main__":
    main()
