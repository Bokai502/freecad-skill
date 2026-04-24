from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from freecad_cli_tools.cli import build_assembly_from_yaml
from freecad_cli_tools.rpc_script_fragments import COMPONENT_SHAPE_HELPERS


def load_shape_helpers() -> dict:
    namespace: dict = {}
    exec(COMPONENT_SHAPE_HELPERS, namespace)
    return namespace


def test_build_component_shape_spec_keeps_box_base_position() -> None:
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]

    spec = build_component_shape_spec(
        "P001",
        {
            "shape": "box",
            "dims": [10, 20, 30],
            "placement": {
                "position": [1, 2, 3],
            },
        },
    )

    assert spec["object_type"] == "Part::Box"
    assert spec["placement_position"] == [1.0, 2.0, 3.0]
    assert spec["length"] == 10.0
    assert spec["width"] == 20.0
    assert spec["height"] == 30.0


def test_build_component_shape_spec_applies_box_rotation_matrix() -> None:
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]

    rotation = [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
    spec = build_component_shape_spec(
        "P001",
        {
            "shape": "box",
            "dims": [10, 20, 30],
            "placement": {
                "position": [1, 2, 3],
                "rotation_matrix": rotation,
            },
        },
    )

    assert spec["object_type"] == "Part::Box"
    assert spec["placement_position"] == [1.0, 2.0, 3.0]
    assert spec["rotation_rows"] == rotation


def test_build_component_shape_spec_offsets_cylinder_base_center() -> None:
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]

    spec = build_component_shape_spec(
        "P020",
        {
            "shape": "cylinder",
            "radius": 5,
            "height": 12,
            "placement": {
                "position": [10, 20, 30],
                "rotation_matrix": [
                    [0, -1, 0],
                    [1, 0, 0],
                    [0, 0, 1],
                ],
            },
        },
    )

    assert spec["object_type"] == "Part::Cylinder"
    assert spec["placement_position"] == [5.0, 25.0, 30.0]
    assert spec["radius"] == 5.0
    assert spec["height"] == 12.0


def test_build_component_shape_spec_can_infer_cylinder_values_from_dims() -> None:
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]

    spec = build_component_shape_spec(
        "P005",
        {
            "shape": "cylinder",
            "dims": [16, 18, 40],
            "placement": {
                "position": [0, 0, 0],
            },
        },
    )

    assert spec["radius"] == 8.0
    assert spec["height"] == 40.0
    assert spec["placement_position"] == [8.0, 8.0, 0.0]


def test_build_component_shape_spec_supports_two_value_cylinder_dims_on_mount_axis() -> (
    None
):
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]
    apply_rotation_rows = helpers["apply_rotation_rows"]

    spec = build_component_shape_spec(
        "P021",
        {
            "shape": "cylinder",
            "dims": [8, 20],
            "placement": {
                "position": [1, 2, 3],
                "mount_face": 1,
            },
        },
    )

    assert spec["object_type"] == "Part::Cylinder"
    assert spec["radius"] == 4.0
    assert spec["height"] == 20.0
    assert spec["placement_position"] == [1.0, 6.0, 7.0]
    assert apply_rotation_rows(spec["rotation_rows"], [0.0, 0.0, 1.0]) == [
        1.0,
        0.0,
        0.0,
    ]


def test_build_component_shape_spec_uses_mount_axis_for_legacy_three_value_cylinder_dims() -> (
    None
):
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]
    apply_rotation_rows = helpers["apply_rotation_rows"]

    spec = build_component_shape_spec(
        "P022",
        {
            "shape": "cylinder",
            "dims": [10, 12, 10],
            "placement": {
                "position": [1, 2, 3],
                "mount_face": 2,
            },
        },
    )

    assert spec["radius"] == 5.0
    assert spec["height"] == 12.0
    assert spec["placement_position"] == [6.0, 2.0, 8.0]
    assert apply_rotation_rows(spec["rotation_rows"], [0.0, 0.0, 1.0]) == [
        0.0,
        1.0,
        0.0,
    ]


def test_updated_sample_yaml_cylinder_components_build_shape_specs() -> None:
    helpers = load_shape_helpers()
    build_component_shape_spec = helpers["build_component_shape_spec"]
    apply_rotation_rows = helpers["apply_rotation_rows"]
    sample_path = Path(__file__).resolve().parents[2] / "examples" / "sample.yaml"
    sample = yaml.safe_load(sample_path.read_text(encoding="utf-8"))

    expected = {
        "P005": {
            "placement_position": [
                170.39544205001832,
                18.63333898339918,
                -132.6849685999266,
            ],
            "axis": [1.0, 0.0, 0.0],
        },
        "P010": {
            "placement_position": [
                -193.44925497516803,
                -246.5032580075667,
                -60.670465703455946,
            ],
            "axis": [0.0, 1.0, 0.0],
        },
        "P011": {
            "placement_position": [
                -189.99231640981162,
                163.5609819120264,
                132.30312475973884,
            ],
            "axis": [0.0, 1.0, 0.0],
        },
    }

    for component_id, expectations in expected.items():
        spec = build_component_shape_spec(
            component_id, sample["components"][component_id]
        )
        assert spec["object_type"] == "Part::Cylinder"
        assert spec["placement_position"] == expectations["placement_position"]
        assert (
            apply_rotation_rows(spec["rotation_rows"], [0.0, 0.0, 1.0])
            == expectations["axis"]
        )


def test_main_injects_component_shape_helpers(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_render(script_name: str, replacements: dict) -> str:
        captured["script_name"] = script_name
        captured["replacements"] = replacements
        return "rendered-code"

    monkeypatch.setattr(build_assembly_from_yaml, "render_rpc_script", fake_render)

    def fake_execute_script_payload(host: str, port: int, code: str) -> dict:
        captured["host"] = host
        captured["port"] = port
        captured["code"] = code
        staged_output = Path(json.loads(captured["replacements"]["__SAVE_PATH__"]))
        staged_output.parent.mkdir(parents=True, exist_ok=True)
        staged_output.write_text("step-data", encoding="utf-8")
        staged_output.with_suffix(".glb").write_text("glb-data", encoding="utf-8")
        return {
            "success": True,
            "document": "sample_0001",
            "save_path": str(staged_output),
            "glb_path": str(staged_output.with_suffix(".glb")),
            "component_count": 0,
        }

    monkeypatch.setattr(
        build_assembly_from_yaml,
        "execute_script_payload",
        fake_execute_script_payload,
    )
    monkeypatch.setenv("FREECAD_RUNTIME_DATA_DIR", str(tmp_path / "runtime"))

    yaml_path = tmp_path / "sample.yaml"
    yaml_path.write_text("components: {}\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-create-assembly",
            "--input",
            str(yaml_path),
            "--doc-name",
            "sample_0001",
        ],
    )

    build_assembly_from_yaml.main()

    assert captured["script_name"] == "assembly_from_yaml.py"
    assert "__COMPONENT_SHAPE_HELPERS__" in captured["replacements"]
    assert (
        "build_component_shape_spec"
        in captured["replacements"]["__COMPONENT_SHAPE_HELPERS__"]
    )
    expected_step = yaml_path.with_name("sample_0001.step")
    staged_step = Path(json.loads(captured["replacements"]["__SAVE_PATH__"]))
    assert staged_step.name == expected_step.name
    assert captured["code"] == "rendered-code"


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
            "document": "SampleYamlAssembly",
            "save_path": str(staged_output),
            "glb_path": str(staged_output.with_suffix(".glb")),
            "component_count": 0,
        }

    monkeypatch.setenv("FREECAD_RUNTIME_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(build_assembly_from_yaml, "render_rpc_script", fake_render)
    monkeypatch.setattr(
        build_assembly_from_yaml,
        "execute_script_payload",
        fake_execute_script_payload,
    )

    yaml_path = tmp_path / "sample.yaml"
    yaml_path.write_text("components: {}\n", encoding="utf-8")
    output_path = tmp_path / "exports" / "sample.step"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-create-assembly",
            "--input",
            str(yaml_path),
            "--doc-name",
            "SampleYamlAssembly",
            "--output",
            str(output_path),
        ],
    )

    build_assembly_from_yaml.main()

    staged_input = Path(json.loads(captured["replacements"]["__YAML_PATH__"]))
    assert staged_input.read_text(encoding="utf-8") == "components: {}\n"
    assert output_path.read_text(encoding="utf-8") == "step-data"
    assert output_path.with_suffix(".glb").read_text(encoding="utf-8") == "glb-data"

    payload = json.loads(capsys.readouterr().out)
    assert payload["save_path"] == str(output_path)
    assert payload["glb_path"] == str(output_path.with_suffix(".glb"))


def test_main_writes_artifact_registry_record(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict = {}

    def fake_render(script_name: str, replacements: dict) -> str:
        captured["replacements"] = replacements
        return "rendered-code"

    def fake_execute_script_payload(host: str, port: int, code: str) -> dict:
        staged_output = Path(json.loads(captured["replacements"]["__SAVE_PATH__"]))
        staged_output.parent.mkdir(parents=True, exist_ok=True)
        staged_output.write_text("step-data", encoding="utf-8")
        staged_output.with_suffix(".glb").write_text("glb-data", encoding="utf-8")
        return {
            "success": True,
            "document": "SampleYamlAssembly",
            "save_path": str(staged_output),
            "glb_path": str(staged_output.with_suffix(".glb")),
            "component_count": 0,
        }

    monkeypatch.setenv("FREECAD_RUNTIME_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(tmp_path / "registry"))
    monkeypatch.setattr(build_assembly_from_yaml, "render_rpc_script", fake_render)
    monkeypatch.setattr(
        build_assembly_from_yaml,
        "execute_script_payload",
        fake_execute_script_payload,
    )

    yaml_path = tmp_path / "sample.yaml"
    yaml_path.write_text("components: {}\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-create-assembly",
            "--input",
            str(yaml_path),
            "--doc-name",
            "SampleYamlAssembly",
            "--run-id",
            "assembly-run",
            "--session-id",
            "assembly-session",
        ],
    )

    build_assembly_from_yaml.main()

    manifest = json.loads(
        (tmp_path / "registry" / "runs" / "assembly-run.json").read_text(
            encoding="utf-8"
        )
    )
    expected_step = yaml_path.with_name("SampleYamlAssembly.step")
    assert manifest["operation"]["status"] == "success"
    assert manifest["session_id"] == "assembly-session"
    assert manifest["outputs"]["step_path"] == str(expected_step)
    assert manifest["outputs"]["glb_path"] == str(expected_step.with_suffix(".glb"))
