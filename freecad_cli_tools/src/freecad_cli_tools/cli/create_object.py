#!/usr/bin/env python3
"""Create a new object in a FreeCAD document."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import load_json_input, run_rpc_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new object in FreeCAD")
    parser.add_argument("doc_name", help="Name of the document")
    parser.add_argument("obj_type", help="Object type (e.g. Part::Box)")
    parser.add_argument("obj_name", help="Name of the object to create")
    parser.add_argument("--properties", "-p", default="{}", help="JSON properties")
    parser.add_argument("--properties-file", help="JSON file with properties")
    parser.add_argument("--analysis", help="FEM analysis name")
    add_connection_args(parser)
    args = parser.parse_args()

    properties = load_json_input(args.properties, file_path=args.properties_file)
    obj_data = {
        "Name": args.obj_name,
        "Type": args.obj_type,
        "Properties": properties,
        "Analysis": args.analysis,
    }
    run_rpc_command(
        args, "create_object", args.doc_name, obj_data, require_success=True
    )


if __name__ == "__main__":
    main()
