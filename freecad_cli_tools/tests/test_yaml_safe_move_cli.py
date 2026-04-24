from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

from freecad_cli_tools.cli import yaml_component_safe_move


def write_layout(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "envelope": {
                    "inner_size": [100.0, 100.0, 100.0],
                },
                "components": {
                    "P001": {
                        "shape": "box",
                        "dims": [10.0, 10.0, 10.0],
                        "placement": {
                            "position": [0.0, 0.0, 0.0],
                            "mount_face": 1,
                            "mount_point": [10.0, 5.0, 5.0],
                        },
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_external_layout(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "envelope": {
                    "inner_size": [100.0, 100.0, 100.0],
                    "outer_size": [110.0, 110.0, 110.0],
                },
                "components": {
                    "P022": {
                        "shape": "box",
                        "dims": [10.0, 20.0, 30.0],
                        "placement": {
                            "position": [1.0, 2.0, 3.0],
                            "mount_face": 11,
                            "mount_point": [6.0, 12.0, 3.0],
                        },
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_yaml_safe_move_writes_registry_record(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "sample.yaml"
    output_path = tmp_path / "sample.updated.yaml"
    registry_dir = tmp_path / "registry"
    write_layout(input_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-yaml-safe-move",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--component",
            "P001",
            "--move",
            "10",
            "0",
            "0",
            "--run-id",
            "move-run",
            "--session-id",
            "session-move",
        ],
    )

    exit_code = yaml_component_safe_move.main()

    assert exit_code == 0
    manifest = json.loads(
        (registry_dir / "runs" / "move-run.json").read_text(encoding="utf-8")
    )
    assert manifest["operation"]["status"] == "success"
    assert manifest["outputs"]["yaml_path"] == str(output_path)
    assert Path(manifest["outputs"]["yaml_path"]).exists()


def test_yaml_safe_move_install_face_writes_rotation_matrix(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "sample.yaml"
    output_path = tmp_path / "sample.updated.yaml"
    write_external_layout(input_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-yaml-safe-move",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--component",
            "P022",
            "--install-face",
            "10",
            "--move",
            "0",
            "0",
            "0",
        ],
    )

    exit_code = yaml_component_safe_move.main()

    assert exit_code == 0
    updated = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    placement = updated["components"]["P022"]["placement"]
    assert placement["mount_face"] == 10
    assert placement["rotation_matrix"] != [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def test_sync_yaml_result_to_cad_sends_source_pose(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_execute_batch_sync(host, port, doc_name, updates, **kwargs):
        captured["updates"] = updates
        captured["kwargs"] = kwargs
        return {"success": True, "document": doc_name}

    monkeypatch.setattr(
        yaml_component_safe_move,
        "execute_batch_sync",
        fake_execute_batch_sync,
    )
    output_path = tmp_path / "sample.yaml"
    args = SimpleNamespace(
        sync_cad=True,
        doc_name="DemoDoc",
        step_output=None,
        host="localhost",
        port=9876,
        component_object=None,
        part_object=None,
        component="P022",
    )
    source_component = {
        "shape": "box",
        "dims": [10.0, 20.0, 30.0],
        "placement": {
            "position": [1.0, 2.0, 3.0],
            "mount_face": 11,
        },
    }
    updated_component = {
        "shape": "box",
        "dims": [10.0, 20.0, 30.0],
        "placement": {
            "position": [55.0, -10.0, 5.0],
            "mount_face": 7,
            "rotation_matrix": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
        },
    }

    payload = yaml_component_safe_move.sync_yaml_result_to_cad(
        args,
        output_path,
        "P022",
        updated_component,
        source_component=source_component,
    )

    assert payload["enabled"] is True
    update = captured["updates"][0]
    assert update["source_position"] == [1.0, 2.0, 3.0]
    assert update["source_rotation_matrix"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    assert update["position"] == [55.0, -10.0, 5.0]
    assert update["rotation_matrix"] == [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]


def test_yaml_safe_move_records_partial_success_when_cad_sync_fails(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "sample.yaml"
    output_path = tmp_path / "sample.updated.yaml"
    registry_dir = tmp_path / "registry"
    write_layout(input_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setattr(
        yaml_component_safe_move,
        "sync_yaml_result_to_cad",
        lambda *args, **kwargs: {
            "enabled": True,
            "success": False,
            "error": "sync failed",
            "document": "DemoDoc",
            "component": "P001",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-yaml-safe-move",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--component",
            "P001",
            "--move",
            "10",
            "0",
            "0",
            "--sync-cad",
            "--doc-name",
            "DemoDoc",
            "--run-id",
            "move-partial-run",
        ],
    )

    exit_code = yaml_component_safe_move.main()

    assert exit_code == 2
    manifest = json.loads(
        (registry_dir / "runs" / "move-partial-run.json").read_text(encoding="utf-8")
    )
    assert manifest["operation"]["status"] == "partial_success"
    assert manifest["error"]["code"] == "CAD_SYNC_FAILED"


def test_yaml_safe_move_records_step_and_glb_outputs_on_sync_success(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "sample.yaml"
    output_path = tmp_path / "sample.updated.yaml"
    registry_dir = tmp_path / "registry"
    step_path = tmp_path / "DemoDoc.step"
    glb_path = tmp_path / "DemoDoc.glb"
    write_layout(input_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))

    def fake_sync(*args, **kwargs):
        step_path.write_text("step-data", encoding="utf-8")
        glb_path.write_text("glb-data", encoding="utf-8")
        return {
            "enabled": True,
            "success": True,
            "document": "DemoDoc",
            "component": "P001",
            "step_path": str(step_path),
            "glb_path": str(glb_path),
        }

    monkeypatch.setattr(yaml_component_safe_move, "sync_yaml_result_to_cad", fake_sync)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-yaml-safe-move",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--component",
            "P001",
            "--move",
            "10",
            "0",
            "0",
            "--sync-cad",
            "--doc-name",
            "DemoDoc",
            "--run-id",
            "move-sync-success-run",
        ],
    )

    exit_code = yaml_component_safe_move.main()

    assert exit_code == 0
    manifest = json.loads(
        (registry_dir / "runs" / "move-sync-success-run.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["operation"]["status"] == "success"
    assert manifest["outputs"]["yaml_path"] == str(output_path)
    assert manifest["outputs"]["step_path"] == str(step_path)
    assert manifest["outputs"]["glb_path"] == str(glb_path)
    assert Path(manifest["outputs"]["step_path"]).exists()
    assert Path(manifest["outputs"]["glb_path"]).exists()


def test_yaml_safe_move_records_partial_success_when_glb_export_missing(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "sample.yaml"
    output_path = tmp_path / "sample.updated.yaml"
    registry_dir = tmp_path / "registry"
    step_path = tmp_path / "DemoDoc.step"
    glb_path = tmp_path / "DemoDoc.glb"
    write_layout(input_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))

    def fake_sync(*args, **kwargs):
        step_path.write_text("step-data", encoding="utf-8")
        return {
            "enabled": True,
            "success": True,
            "document": "DemoDoc",
            "component": "P001",
            "step_path": str(step_path),
            "glb_path": str(glb_path),
        }

    monkeypatch.setattr(yaml_component_safe_move, "sync_yaml_result_to_cad", fake_sync)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-yaml-safe-move",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--component",
            "P001",
            "--move",
            "10",
            "0",
            "0",
            "--sync-cad",
            "--doc-name",
            "DemoDoc",
            "--run-id",
            "move-glb-missing-run",
        ],
    )

    exit_code = yaml_component_safe_move.main()

    assert exit_code == 2
    manifest = json.loads(
        (registry_dir / "runs" / "move-glb-missing-run.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["operation"]["status"] == "partial_success"
    assert manifest["outputs"]["step_path"] == str(step_path)
    assert manifest["outputs"]["glb_path"] == str(glb_path)
    assert manifest["error"]["code"] == "GLB_EXPORT_INCOMPLETE"
