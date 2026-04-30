from __future__ import annotations

import json
import sys
from pathlib import Path

from freecad_cli_tools.cli import build_assembly
from freecad_cli_tools.rpc_script_fragments import COMPONENT_SHAPE_HELPERS


def load_shape_helpers() -> dict:
    namespace: dict = {}
    exec(COMPONENT_SHAPE_HELPERS, namespace)
    return namespace


def placement_spec(
    component_id: str,
    *,
    position: list[float],
    mount_face_id: str = "outer.zmax_inner",
    component_mount_face_id: str | None = None,
    in_plane_rotation_deg: float = 0.0,
) -> dict[str, object]:
    return {
        "position": position,
        "mount_face_id": mount_face_id,
        "component_mount_face_id": (component_mount_face_id or f"{component_id}.local_zmax"),
        "alignment": {
            "normal_alignment": "opposite",
            "component_u_axis_to_target_u_axis": True,
            "in_plane_rotation_deg": in_plane_rotation_deg,
        },
    }


def sample_normalized_dataset() -> dict[str, object]:
    return {
        "schema_version": "layout_dataset_normalized/1.0",
        "units": {"length": "mm"},
        "envelope": {
            "outer_size": [313.5, 290.0, 202.0],
            "inner_size": [307.8, 284.2, 196.2],
            "shell_thickness": 2.8,
        },
        "components": {
            "P000": {
                "id": "P000",
                "component_id": "P000",
                "shape": "box",
                "dims": [10.0, 20.0, 30.0],
                "placement": placement_spec(
                    "P000",
                    position=[1.0, 2.0, 3.0],
                    mount_face_id="outer.zmax_inner",
                    component_mount_face_id="P000.local_zmax",
                ),
            },
            "E000": {
                "id": "E000",
                "component_id": "E000",
                "shape": "box",
                "dims": [40.0, 50.0, 60.0],
                "placement": placement_spec(
                    "E000",
                    position=[7.0, 8.0, 9.0],
                    mount_face_id="outer.zmin_outer",
                    component_mount_face_id="E000.local_zmin",
                ),
            },
        },
    }


def test_build_component_shape_spec_keeps_box_base_position() -> None:
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]

    spec = build_component_shape_spec(
        "P001",
        {
            "shape": "box",
            "dims": [10, 20, 30],
            "placement": placement_spec("P001", position=[1, 2, 3]),
        },
    )

    assert spec["object_type"] == "Part::Box"
    assert spec["placement_position"] == [1.0, 2.0, 3.0]
    assert spec["length"] == 10.0
    assert spec["width"] == 20.0
    assert spec["height"] == 30.0


def test_build_component_shape_spec_offsets_cylinder_base_center() -> None:
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]

    spec = build_component_shape_spec(
        "P020",
        {
            "shape": "cylinder",
            "radius": 5,
            "height": 12,
            "placement": placement_spec(
                "P020",
                position=[10, 20, 30],
                mount_face_id="outer.zmax_inner",
                component_mount_face_id="P020.local_zmax",
                in_plane_rotation_deg=90.0,
            ),
        },
    )

    assert spec["object_type"] == "Part::Cylinder"
    assert spec["placement_position"] == [5.0, 25.0, 30.0]
    assert spec["radius"] == 5.0
    assert spec["height"] == 12.0


def test_main_stages_runtime_files_and_rewrites_export_paths(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    captured: dict = {}

    def fake_render(script_name: str, replacements: dict) -> str:
        captured["script_name"] = script_name
        captured["replacements"] = replacements
        return "rendered-code"

    def fake_execute_script_payload(host: str, port: int, code: str) -> dict:
        assert code == "rendered-code"
        staged_output = Path(json.loads(captured["replacements"]["__SAVE_PATH__"]))
        staged_output.parent.mkdir(parents=True, exist_ok=True)
        staged_output.write_text("step-data", encoding="utf-8")
        staged_output.with_suffix(".glb").write_text("glb-data", encoding="utf-8")
        return {
            "success": True,
            "document": "SampleLayoutAssembly",
            "save_path": str(staged_output),
            "glb_path": str(staged_output.with_suffix(".glb")),
            "component_count": 2,
        }

    monkeypatch.setenv("FREECAD_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(build_assembly, "render_rpc_script", fake_render)
    monkeypatch.setattr(build_assembly, "execute_script_payload", fake_execute_script_payload)
    monkeypatch.setattr(
        build_assembly,
        "load_and_normalize_layout_dataset",
        lambda *args, **kwargs: sample_normalized_dataset(),
    )
    requested_output_path = tmp_path / "exports" / "sample.step"
    output_path = tmp_path / "exports" / "geometry_after.step"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-create-assembly",
            "--doc-name",
            "SampleLayoutAssembly",
            "--output",
            str(requested_output_path),
        ],
    )

    build_assembly.main()

    staged_input = Path(json.loads(captured["replacements"]["__INPUT_PATH__"]))
    normalized = json.loads(staged_input.read_text(encoding="utf-8"))
    assert normalized["components"]["P000"]["placement"]["mount_face_id"] == "outer.zmax_inner"
    assert output_path.read_text(encoding="utf-8") == "step-data"
    assert output_path.with_suffix(".glb").read_text(encoding="utf-8") == "glb-data"

    payload = json.loads(capsys.readouterr().out)
    assert payload["save_path"] == str(output_path)
    assert payload["glb_path"] == str(output_path.with_suffix(".glb"))
