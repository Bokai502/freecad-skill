#!/usr/bin/env python3
"""Get a specific object from FreeCAD."""

import argparse
import json

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_script_command
from freecad_cli_tools.rpc_script_loader import render_rpc_script


def main() -> None:
    parser = argparse.ArgumentParser(description="Get object properties from FreeCAD")
    parser.add_argument("doc_name", help="Name of the document")
    parser.add_argument("obj_name", help="Name of the object")
    add_connection_args(parser)
    args = parser.parse_args()
    code = render_rpc_script(
        "get_object.py",
        {
            "__DOC_NAME__": json.dumps(args.doc_name),
            "__OBJ_NAME__": json.dumps(args.obj_name),
        },
    )
    run_script_command(args, code)


if __name__ == "__main__":
    main()
