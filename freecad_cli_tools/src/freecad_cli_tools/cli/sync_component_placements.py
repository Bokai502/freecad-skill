#!/usr/bin/env python3
"""Sync one or more computed component placements into a FreeCAD document."""

from __future__ import annotations

import argparse

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import load_json_input, print_json
from freecad_cli_tools.freecad_sync import execute_batch_sync, normalize_sync_updates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync one or more component placements into an existing FreeCAD document."
    )
    parser.add_argument(
        "--doc-name",
        required=True,
        help="Target FreeCAD document name.",
    )
    parser.add_argument(
        "--updates",
        default="[]",
        help="Inline JSON list of placement updates.",
    )
    parser.add_argument(
        "--updates-file",
        help="Path to a JSON file containing a list of placement updates.",
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="Recompute the FreeCAD document once after all updates are applied.",
    )
    add_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_updates = load_json_input(args.updates, file_path=args.updates_file)
    updates = normalize_sync_updates(raw_updates)
    payload = execute_batch_sync(
        args.host,
        args.port,
        args.doc_name,
        updates,
        recompute=args.recompute,
    )
    print_json(payload)


if __name__ == "__main__":
    main()
