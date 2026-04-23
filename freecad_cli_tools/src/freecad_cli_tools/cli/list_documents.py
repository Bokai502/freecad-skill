#!/usr/bin/env python3
"""List all open documents in FreeCAD."""

import argparse
import sys

from freecad_cli_tools import add_connection_args
from freecad_cli_tools.cli_support import execute_script_payload
from freecad_cli_tools.rpc_client import print_result as print_json

LIST_DOCUMENTS_CODE = """
import json
import FreeCAD

docs = []
for doc in FreeCAD.listDocuments().values():
    docs.append(
        {
            "name": doc.Name,
            "label": getattr(doc, "Label", "") or doc.Name,
        }
    )

print(json.dumps(docs))
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="List open FreeCAD documents")
    add_connection_args(parser)
    args = parser.parse_args()
    try:
        payload = execute_script_payload(args.host, args.port, LIST_DOCUMENTS_CODE)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print_json(payload)


if __name__ == "__main__":
    main()
