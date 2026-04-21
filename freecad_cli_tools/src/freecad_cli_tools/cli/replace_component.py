#!/usr/bin/env python3
"""Replace a named component in a FreeCAD assembly STEP with an external STEP file."""

import argparse
import json
from pathlib import Path

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import run_script_command, to_wsl_path
from freecad_cli_tools.rpc_script_loader import render_rpc_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replace a named component in a FreeCAD assembly with an external "
            "STEP file. The replacement is centered on the original component's "
            "bounding-box center (taken from the YAML position + dims) and the "
            "assembly STEP is overwritten in place, with a sibling GLB exported."
        )
    )
    parser.add_argument("--yaml", required=True, help="Source YAML layout file.")
    parser.add_argument(
        "--assembly",
        required=True,
        help="Existing assembly STEP file (overwritten in place, plus sibling .glb).",
    )
    parser.add_argument(
        "--replacement",
        required=True,
        help="Replacement component STEP file.",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Component id to replace (e.g. P022).",
    )
    parser.add_argument(
        "--doc-name",
        default=None,
        help="FreeCAD document name. Defaults to the assembly file stem.",
    )
    parser.add_argument(
        "--no-fit-view",
        action="store_true",
        help="Skip GUI view fit after the replacement.",
    )
    add_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assembly_path = Path(args.assembly)
    yaml_path = Path(args.yaml)
    replacement_path = Path(args.replacement)
    doc_name = args.doc_name or assembly_path.stem

    code = render_rpc_script(
        "replace_component.py",
        {
            "__YAML_PATH__": json.dumps(to_wsl_path(yaml_path)),
            "__ASSEMBLY_PATH__": json.dumps(to_wsl_path(assembly_path)),
            "__REPLACEMENT_PATH__": json.dumps(to_wsl_path(replacement_path)),
            "__COMPONENT_NAME__": json.dumps(args.name),
            "__DOC_NAME__": json.dumps(doc_name),
            "__FIT_VIEW__": "False" if args.no_fit_view else "True",
        },
    )
    run_script_command(args, code)


if __name__ == "__main__":
    main()
