from __future__ import annotations

import json
import sys
from pathlib import Path

from freecad_cli_tools.cli import replace_component


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
            "P001": {
                "id": "P001",
                "shape": "box",
                "dims": [10.0, 20.0, 30.0],
                "color": [1.0, 0.5, 0.2, 1.0],
                "placement": {
                    "position": [1.0, 2.0, 3.0],
                    "mount_face": 3,
                    "component_mount_face": 1,
                    "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                },
            }
        },
    }


def test_replace_component_writes_registry_record(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    layout_topology_path = workspace / "01_layout" / "layout_topology.json"
    geom_path = workspace / "01_layout" / "geom.json"
    registry_dir = tmp_path / "registry"
    assembly_input_path = workspace / "SampleAssembly.step"
    output_path = workspace / "02_geometry_edit" / "geometry_after.step"
    replacement_path = workspace / "replacement.step"
    assembly_input_path.write_text("old-step", encoding="utf-8")
    replacement_path.write_text("replacement-step", encoding="utf-8")

    rendered: dict[str, object] = {}

    def fake_render(script_name: str, replacements: dict[str, str]) -> str:
        rendered["script_name"] = script_name
        rendered["replacements"] = replacements
        return "SCRIPT"

    def fake_execute(host: str, port: int, code: str) -> dict:
        assert code == "SCRIPT"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("new-step", encoding="utf-8")
        output_path.with_suffix(".glb").write_text("new-glb", encoding="utf-8")
        return {
            "success": True,
            "assembly_path": str(output_path),
            "glb_path": str(output_path.with_suffix(".glb")),
            "component": "P001",
        }

    monkeypatch.setattr(replace_component, "render_rpc_script", fake_render)
    monkeypatch.setattr(replace_component, "execute_script_payload", fake_execute)
    monkeypatch.setattr(
        replace_component,
        "load_and_normalize_layout_dataset",
        lambda *args, **kwargs: sample_normalized_dataset(),
    )
    monkeypatch.setenv("FREECAD_WORKSPACE_DIR", str(workspace))
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-replace-component",
            "--layout-topology",
            str(layout_topology_path),
            "--geom",
            str(geom_path),
            "--assembly",
            str(assembly_input_path),
            "--replacement",
            str(replacement_path),
            "--name",
            "P001",
            "--run-id",
            "replace-run",
            "--session-id",
            "session-replace",
        ],
    )

    replace_component.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["assembly_path"] == str(output_path)
    assert rendered["script_name"] == "replace_component.py"

    manifest = json.loads(
        (registry_dir / "runs" / "replace-run.json").read_text(encoding="utf-8")
    )
    assert manifest["operation"]["status"] == "success"
    assert manifest["inputs"]["layout_topology_path"] == str(layout_topology_path)
    assert manifest["inputs"]["geom_path"] == str(geom_path)
    assert manifest["inputs"]["assembly_input_path"] == str(assembly_input_path)
    assert manifest["outputs"]["step_path"] == str(output_path)
    assert manifest["outputs"]["glb_path"] == str(output_path.with_suffix(".glb"))
    assert manifest["artifacts"][4]["path"] == str(replacement_path)


def test_replace_component_uses_workspace_relative_dataset_paths_and_overrides(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    workspace = tmp_path / "workspace"
    assembly_input_path = workspace / "assemblies" / "input.step"
    output_path = workspace / "02_geometry_edit" / "geometry_after.step"
    replacement_path = workspace / "parts" / "replacement.step"
    assembly_input_path.parent.mkdir(parents=True, exist_ok=True)
    replacement_path.parent.mkdir(parents=True, exist_ok=True)
    assembly_input_path.write_text("old-step", encoding="utf-8")
    replacement_path.write_text("replacement-step", encoding="utf-8")

    rendered: dict[str, object] = {}

    def fake_render(script_name: str, replacements: dict[str, str]) -> str:
        rendered["script_name"] = script_name
        rendered["replacements"] = replacements
        return "SCRIPT"

    def fake_execute(host: str, port: int, code: str) -> dict:
        assert code == "SCRIPT"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("new-step", encoding="utf-8")
        output_path.with_suffix(".glb").write_text("new-glb", encoding="utf-8")
        return {
            "success": True,
            "assembly_path": str(output_path),
            "glb_path": str(output_path.with_suffix(".glb")),
            "component": "P001",
        }

    monkeypatch.setattr(replace_component, "render_rpc_script", fake_render)
    monkeypatch.setattr(replace_component, "execute_script_payload", fake_execute)
    monkeypatch.setattr(
        replace_component,
        "load_and_normalize_layout_dataset",
        lambda *args, **kwargs: sample_normalized_dataset(),
    )
    monkeypatch.setenv("FREECAD_WORKSPACE_DIR", str(workspace))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-replace-component",
            "--assembly",
            "assemblies/input.step",
            "--replacement",
            "parts/replacement.step",
            "--name",
            "P001",
            "--thrust-axis",
            "y",
            "--flange-sign",
            "-1",
        ],
    )

    replace_component.main()

    payload = json.loads(capsys.readouterr().out)
    replacements = rendered["replacements"]
    staged_input = Path(json.loads(replacements["__INPUT_PATH__"]))
    normalized = json.loads(staged_input.read_text(encoding="utf-8"))
    component = normalized["components"]["P001"]
    assert payload["assembly_path"] == str(output_path)
    assert json.loads(replacements["__ASSEMBLY_INPUT_PATH__"]) == str(
        assembly_input_path.resolve()
    )
    assert json.loads(replacements["__EXPORT_PATH__"]) == str(output_path.resolve())
    assert json.loads(replacements["__REPLACEMENT_PATH__"]) == str(
        replacement_path.resolve()
    )
    assert component["placement"]["mount_face"] == 3
    assert component["replacement"] == {"thrust_axis": "y", "flange_sign": -1}
