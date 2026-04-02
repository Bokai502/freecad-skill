#!/usr/bin/env python3
"""Execute Python code in FreeCAD."""

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import (
    read_text_input,
    require_non_empty_text,
    run_rpc_command,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute Python code in FreeCAD")
    parser.add_argument("code", nargs="?", help="Python code to execute")
    parser.add_argument("--file", "-f", help="Path to Python file to execute")
    add_connection_args(parser)
    args = parser.parse_args()

    code = read_text_input(args.code, file_path=args.file, allow_stdin=True)
    require_non_empty_text(code, error_message="ERROR: No code provided.")
    run_rpc_command(args, "execute_code", code, require_success=True)


if __name__ == "__main__":
    main()
