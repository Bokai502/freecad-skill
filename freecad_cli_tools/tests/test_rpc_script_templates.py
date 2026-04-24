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
_DUMMY_PATH = json.dumps("/tmp/dummy.json")
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
    "assembly_from_layout.py": {
        "__INPUT_PATH__": _DUMMY_PATH,
        "__DOC_NAME__": _DUMMY_STR,
        "__SAVE_PATH__": _DUMMY_PATH,
        "__FIT_VIEW__": "True",
        "__VIEW_NAME__": _DUMMY_STR,
        "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
        "__COMPONENT_SHAPE_HELPERS__": COMPONENT_SHAPE_HELPERS,
    },
    "sync_component_placements.py": {
        "__DOC_NAME__": _DUMMY_STR,
        "__UPDATES__": _DUMMY_UPDATES,
        "__RECOMPUTE__": "True",
        "__EXPORT_STEP_PATH__": _DUMMY_PATH,
        "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
    },
    "replace_component.py": {
        "__YAML_PATH__": _DUMMY_PATH,
        "__ASSEMBLY_PATH__": _DUMMY_PATH,
        "__REPLACEMENT_PATH__": _DUMMY_PATH,
        "__COMPONENT_NAME__": _DUMMY_STR,
        "__DOC_NAME__": _DUMMY_STR,
        "__FIT_VIEW__": "True",
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


def test_replace_component_restores_scene_view_style() -> None:
    rendered = render_rpc_script(
        "replace_component.py", SCRIPT_REPLACEMENTS["replace_component.py"]
    )

    assert "def restore_replacement_style(obj, imported_style, fallback_color):" in rendered
    assert "replacement_styles = capture_view_styles(new_objs)" in rendered
    assert "replacement_styles.get(obj.Name)" in rendered
    assert 'apply_color(obj, component_color, transparency=40)' in rendered
    assert 'view.Transparency = 0' in rendered
    assert "view.DiffuseColor = [rgba] * face_count" in rendered


def test_replace_component_preserves_non_target_placements() -> None:
    rendered = render_rpc_script(
        "replace_component.py", SCRIPT_REPLACEMENTS["replace_component.py"]
    )

    assert "def capture_assembly_placements(container, skip_names=None):" in rendered
    assert "preserved_placements = capture_assembly_placements(" in rendered
    assert 'skip_names={target_part.Name}' in rendered
    assert "restored_placements = restore_captured_placements(doc, preserved_placements)" in rendered
    assert '"restored_placements_count": len(restored_placements)' in rendered


def test_replace_component_prefers_reusable_document_before_step_import() -> None:
    rendered = render_rpc_script(
        "replace_component.py", SCRIPT_REPLACEMENTS["replace_component.py"]
    )

    assert "def find_reusable_document(doc_name):" in rendered
    assert "doc, assembly = find_reusable_document(DOC_NAME)" in rendered
    assert "document_reused = doc is not None" in rendered
    assert "doc, assembly = create_or_import_document(DOC_NAME, ASSEMBLY_PATH)" in rendered
    assert '"document_reused": document_reused' in rendered
    assert '"assembly_imported": assembly_imported' in rendered


def test_replace_component_applies_yaml_rotation_matrix() -> None:
    rendered = render_rpc_script(
        "replace_component.py", SCRIPT_REPLACEMENTS["replace_component.py"]
    )

    assert 'placement.get("rotation_matrix")' in rendered
    assert "component_contact_face_from_placement(" in rendered
    assert "yaml_component_center(" in rendered
    assert "local_rotation = rotation_to_align(src_flange_dir, local_flange_dir)" in rendered
    assert "rotation = placement_rotation.multiply(local_rotation)" in rendered
    assert '"component_contact_face": component_contact_face_id' in rendered
    assert '"placement_rotation_matrix": placement_rotation_rows' in rendered


def test_sync_component_placements_uses_delta_for_part_containers() -> None:
    rendered = render_rpc_script(
        "sync_component_placements.py",
        SCRIPT_REPLACEMENTS["sync_component_placements.py"],
    )

    assert "def apply_delta_placement(" in rendered
    assert "source_placement.inverse()" in rendered
    assert 'has_source_placement = (' in rendered
    assert 'part is not None and has_source_placement' in rendered
    assert '"mode": "delta"' in rendered


@pytest.mark.parametrize(
    "script_name",
    ["assembly_from_layout.py", "replace_component.py", "sync_component_placements.py"],
)
def test_exporting_scripts_also_emit_glb(script_name: str) -> None:
    rendered = render_rpc_script(script_name, SCRIPT_REPLACEMENTS[script_name])

    assert "def export_step_and_glb(objects, step_path):" in rendered
    assert 'glb_path = str(Path(step_path).with_suffix(".glb"))' in rendered
    assert "Import.export(objects, step_path)" in rendered
    assert "ImportGui.export(objects, glb_path)" in rendered
    assert '"glb_path": ' in rendered


def _no_unreplaced_placeholders(code: str) -> bool:
    """Return True if no __UPPER_CASE__ placeholder patterns remain."""
    import re

    return not re.search(r"__[A-Z][A-Z0-9_]*__", code)
