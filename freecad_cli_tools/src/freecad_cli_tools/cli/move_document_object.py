#!/usr/bin/env python3
"""Move a document-space FreeCAD object by delta or absolute placement."""

import argparse
import json

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_script_command
from freecad_cli_tools.rpc_script_loader import render_rpc_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move a FreeCAD object.")
    parser.add_argument("doc_name", help="Name of the FreeCAD document.")
    parser.add_argument("obj_name", help="Name of the target object.")
    parser.add_argument("x", type=float, help="X coordinate or delta.")
    parser.add_argument("y", type=float, help="Y coordinate or delta.")
    parser.add_argument("z", type=float, help="Z coordinate or delta.")
    parser.add_argument(
        "--mode",
        choices=["delta", "absolute"],
        default="delta",
        help="Whether the vector is a relative delta or an absolute placement.",
    )
    add_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    code = render_rpc_script(
        "move_document_object.py",
        {
            "__DOC_NAME__": json.dumps(args.doc_name),
            "__OBJ_NAME__": json.dumps(args.obj_name),
            "__MODE__": json.dumps(args.mode),
            "__X__": str(args.x),
            "__Y__": str(args.y),
            "__Z__": str(args.z),
        },
    )
    run_script_command(args, code)


if __name__ == "__main__":
    main()
