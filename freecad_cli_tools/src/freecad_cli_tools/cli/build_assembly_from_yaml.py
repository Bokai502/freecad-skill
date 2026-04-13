#!/usr/bin/env python3
"""Build a FreeCAD assembly document from a YAML layout."""

import argparse
import json
from pathlib import Path

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_script_command, to_wsl_path
from freecad_cli_tools.rpc_script_fragments import (
    COMPONENT_SHAPE_HELPERS,
    PLACEMENT_HELPERS,
)
from freecad_cli_tools.rpc_script_loader import render_rpc_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a FreeCAD assembly document from a YAML layout."
    )
    parser.add_argument("--input", required=True, help="Path to the source YAML file.")
    parser.add_argument(
        "--doc-name", required=True, help="Name of the FreeCAD document to create."
    )
    parser.add_argument(
        "--output",
        help="Optional output FCStd path. Defaults to '<doc-name>.FCStd' beside the YAML file.",
    )
    parser.add_argument(
        "--view",
        default="Isometric",
        help="Preferred GUI view after creation. Currently uses an isometric fit workflow.",
    )
    parser.add_argument(
        "--no-fit-view",
        action="store_true",
        help="Skip automatic GUI view adjustment after generation.",
    )
    add_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{args.doc_name}.FCStd")
    )

    code = render_rpc_script(
        "assembly_from_yaml.py",
        {
            "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
            "__COMPONENT_SHAPE_HELPERS__": COMPONENT_SHAPE_HELPERS,
            "__YAML_PATH__": json.dumps(to_wsl_path(input_path)),
            "__DOC_NAME__": json.dumps(args.doc_name),
            "__SAVE_PATH__": json.dumps(to_wsl_path(output_path)),
            "__FIT_VIEW__": "False" if args.no_fit_view else "True",
            "__VIEW_NAME__": json.dumps(args.view),
        },
    )
    run_script_command(args, code)


if __name__ == "__main__":
    main()
