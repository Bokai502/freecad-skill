#!/usr/bin/env python3
"""Check collisions for a FreeCAD document object and optional trial move."""

import argparse
import json

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_script_command
from freecad_cli_tools.rpc_script_loader import render_rpc_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check document-space collisions for a FreeCAD object and optional move."
    )
    parser.add_argument("doc_name", help="Name of the FreeCAD document.")
    parser.add_argument("obj_name", help="Name of the target object.")
    parser.add_argument(
        "--move",
        nargs=3,
        type=float,
        metavar=("DX", "DY", "DZ"),
        default=(0.0, 0.0, 0.0),
        help="Optional trial move vector in document coordinates.",
    )
    parser.add_argument(
        "--volume-eps",
        type=float,
        default=1e-6,
        help="Intersection volume threshold for treating contact as a collision.",
    )
    add_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    code = render_rpc_script(
        "check_document_collisions.py",
        {
            "__DOC_NAME__": json.dumps(args.doc_name),
            "__OBJ_NAME__": json.dumps(args.obj_name),
            "__DX__": str(args.move[0]),
            "__DY__": str(args.move[1]),
            "__DZ__": str(args.move[2]),
            "__VOLUME_EPS__": str(args.volume_eps),
        },
    )
    run_script_command(args, code)


if __name__ == "__main__":
    main()
