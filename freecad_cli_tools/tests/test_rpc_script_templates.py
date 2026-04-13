"""Validate that all RPC script templates produce valid Python after rendering.

Each template uses __PLACEHOLDER__ tokens that are replaced at runtime.
This test renders every template with dummy values and runs compile()
to catch syntax errors before they surface in a live FreeCAD session.
"""

from __future__ import annotations

import json

import pytest

from freecad_cli_tools.rpc_script_fragments import (
    COMPONENT_SHAPE_HELPERS,
    PLACEMENT_HELPERS,
)
from freecad_cli_tools.rpc_script_loader import render_rpc_script

_DUMMY_STR = json.dumps("dummy")
_DUMMY_PATH = json.dumps("/tmp/dummy.yaml")
_DUMMY_POS = json.dumps([0.0, 0.0, 0.0])
_DUMMY_MATRIX = json.dumps([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
_DUMMY_UPDATES = json.dumps(
    [
        {
            "component": "P001",
            "solid_name": "P001",
            "part_name": "P001_part",
            "position": [0.0, 0.0, 0.0],
            "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        }
    ]
)

SCRIPT_REPLACEMENTS: dict[str, dict[str, str]] = {
    "assembly_from_yaml.py": {
        "__YAML_PATH__": _DUMMY_PATH,
        "__DOC_NAME__": _DUMMY_STR,
        "__SAVE_PATH__": _DUMMY_PATH,
        "__FIT_VIEW__": "True",
        "__VIEW_NAME__": _DUMMY_STR,
        "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
        "__COMPONENT_SHAPE_HELPERS__": COMPONENT_SHAPE_HELPERS,
    },
    "check_document_collisions.py": {
        "__DOC_NAME__": _DUMMY_STR,
        "__OBJ_NAME__": _DUMMY_STR,
        "__DX__": "0.0",
        "__DY__": "0.0",
        "__DZ__": "0.0",
        "__VOLUME_EPS__": "1e-6",
    },
    "move_document_object.py": {
        "__DOC_NAME__": _DUMMY_STR,
        "__OBJ_NAME__": _DUMMY_STR,
        "__MODE__": _DUMMY_STR,
        "__X__": "0.0",
        "__Y__": "0.0",
        "__Z__": "0.0",
    },
    "sync_component_from_yaml.py": {
        "__DOC_NAME__": _DUMMY_STR,
        "__YAML_PATH__": _DUMMY_PATH,
        "__COMPONENT_ID__": _DUMMY_STR,
        "__SOLID_NAME__": _DUMMY_STR,
        "__PART_NAME__": _DUMMY_STR,
        "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
    },
    "sync_component_placement.py": {
        "__DOC_NAME__": _DUMMY_STR,
        "__YAML_PATH__": _DUMMY_PATH,
        "__COMPONENT_ID__": _DUMMY_STR,
        "__SOLID_NAME__": _DUMMY_STR,
        "__PART_NAME__": _DUMMY_STR,
        "__TARGET_POSITION__": _DUMMY_POS,
        "__ROTATION_ROWS__": _DUMMY_MATRIX,
        "__RECOMPUTE__": "True",
        "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
    },
    "sync_component_placements.py": {
        "__DOC_NAME__": _DUMMY_STR,
        "__UPDATES__": _DUMMY_UPDATES,
        "__RECOMPUTE__": "True",
        "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
    },
}


@pytest.mark.parametrize("script_name", sorted(SCRIPT_REPLACEMENTS))
def test_rendered_script_has_valid_syntax(script_name: str) -> None:
    replacements = SCRIPT_REPLACEMENTS[script_name]
    rendered = render_rpc_script(script_name, replacements)

    # Should not contain any unreplaced placeholders
    assert "__" not in rendered or _no_unreplaced_placeholders(
        rendered
    ), f"{script_name} still contains unreplaced __PLACEHOLDER__ tokens"

    # Must be valid Python
    compile(rendered, f"<rpc_scripts/{script_name}>", "exec")


def _no_unreplaced_placeholders(code: str) -> bool:
    """Return True if no __UPPER_CASE__ placeholder patterns remain."""
    import re

    return not re.search(r"__[A-Z][A-Z0-9_]*__", code)
