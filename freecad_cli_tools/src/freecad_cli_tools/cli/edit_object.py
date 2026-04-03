#!/usr/bin/env python3
"""Edit an existing object in FreeCAD."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import load_json_input, run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Edit an object in FreeCAD")
    parser.add_argument("doc_name", help="Name of the document")
    parser.add_argument("obj_name", help="Name of the object to edit")
    parser.add_argument("properties", nargs="?", default="{}", help="JSON properties")
    parser.add_argument("--properties-file", help="JSON file with properties")
    add_connection_args(parser)
    args = parser.parse_args()

    properties = load_json_input(args.properties, file_path=args.properties_file)
    run_rpc_command(
        args,
        "edit_object",
        args.doc_name,
        args.obj_name,
        {"Properties": properties},
        require_success=True,
    )


if __name__ == "__main__":
    main()
