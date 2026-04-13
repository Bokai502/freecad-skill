from __future__ import annotations

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
    monkeypatch.setattr(
        build_assembly_from_yaml,
        "run_script_command",
        lambda args, code: captured.update({"args": args, "code": code}),
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
    assert captured["code"] == "rendered-code"
