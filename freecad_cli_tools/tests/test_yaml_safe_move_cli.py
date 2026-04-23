from __future__ import annotations

import json
import sys
from pathlib import Path

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
