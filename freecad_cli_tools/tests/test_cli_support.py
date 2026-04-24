from __future__ import annotations

import json
from pathlib import Path

import pytest

from freecad_cli_tools.artifact_registry import (
    artifact_entry,
    finalize_registry_run,
    start_registry_run,
)
from freecad_cli_tools.cli_support import (
    describe_rpc_failure,
    extract_output_payload,
    normalize_runtime_path,
)
from freecad_cli_tools.runtime_config import (
    get_default_artifact_registry_dir,
    get_default_geometry_after_step_path,
    get_default_workspace_dir,
    parse_runtime_config,
    resolve_geometry_after_step_path,
    resolve_workspace_path,
)


def test_parse_runtime_config_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    config_path = tmp_path / "freecad_runtime.conf"
    config_path.write_text(
        "\n# comment\nFREECAD_RPC_PORT=9876\nFREECAD_WORKSPACE_DIR=/tmp/workspace\n",
        encoding="utf-8",
    )

    config = parse_runtime_config(config_path)

    assert config == {
        "FREECAD_RPC_PORT": "9876",
        "FREECAD_WORKSPACE_DIR": "/tmp/workspace",
    }


def test_normalize_runtime_path_resolves_path(tmp_path: Path) -> None:
    target = tmp_path / "example.step"
    target.write_text("ok", encoding="utf-8")

    assert normalize_runtime_path(target) == str(target.resolve())


def test_describe_rpc_failure_includes_error_message_and_raw_result() -> None:
    message = describe_rpc_failure(
        {"success": False, "error": "permission denied", "message": "generic failure"}
    )

    assert "permission denied" in message
    assert "generic failure" in message
    assert '"success": false' in message


def test_extract_output_payload_surfaces_rpc_error_details() -> None:
    with pytest.raises(RuntimeError, match="permission denied"):
        extract_output_payload({"success": False, "error": "permission denied"})


def test_extract_output_payload_accepts_log_lines_before_json() -> None:
    payload = extract_output_payload(
        {
            "success": True,
            "message": 'Output:\nSome FreeCAD log line\n{"success": true, "items": [1, 2]}',
        }
    )

    assert payload == {"success": True, "items": [1, 2]}


def test_extract_output_payload_accepts_message_without_marker_when_json_present() -> None:
    payload = extract_output_payload(
        {
            "success": True,
            "message": 'noise before json\n[{"name": "Doc1"}]',
        }
    )

    assert payload == [{"name": "Doc1"}]


def test_runtime_directory_getters_honor_environment_overrides(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FREECAD_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("FREECAD_ARTIFACT_REGISTRY_DIR", raising=False)

    assert get_default_workspace_dir() == tmp_path / "workspace"
    assert get_default_artifact_registry_dir() == (
        tmp_path / "workspace" / "registry"
    )


def test_resolve_workspace_path_uses_configured_workspace_root(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FREECAD_WORKSPACE_DIR", str(tmp_path / "workspace"))

    assert resolve_workspace_path("./01_layout/geom.json") == (
        tmp_path / "workspace" / "01_layout" / "geom.json"
    )
    absolute = tmp_path / "abs" / "geom.json"
    assert resolve_workspace_path(absolute) == absolute


def test_resolve_geometry_after_step_path_forces_geometry_after_basename(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FREECAD_WORKSPACE_DIR", str(tmp_path / "workspace"))

    assert get_default_geometry_after_step_path() == (
        tmp_path / "workspace" / "02_geometry_edit" / "geometry_after.step"
    )
    assert resolve_geometry_after_step_path("exports/custom_name.step") == (
        tmp_path / "workspace" / "exports" / "geometry_after.step"
    )
    assert resolve_geometry_after_step_path("exports") == (
        tmp_path / "workspace" / "exports" / "geometry_after.step"
    )


def test_start_and_finalize_registry_run_write_manifest_and_index(
    monkeypatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / "registry"
    yaml_path = tmp_path / "sample.yaml"
    step_path = tmp_path / "sample.step"
    yaml_path.write_text("components: {}\n", encoding="utf-8")
    step_path.write_text("step-data", encoding="utf-8")
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))

    args = type(
        "Args",
        (),
        {
            "run_id": "run-123",
            "session_id": "session-123",
            "thread_id": "thread-123",
            "turn_id": "turn-123",
        },
    )()

    registry_run = start_registry_run(
        args,
        tool="freecad-create-assembly",
        operation_type="create_assembly",
        inputs={"yaml_path": str(yaml_path)},
    )

    assert registry_run is not None
    finalize_registry_run(
        registry_run,
        status="success",
        outputs={"yaml_path": str(yaml_path), "step_path": str(step_path)},
        result={"success": True},
        artifacts=[
            artifact_entry("yaml", yaml_path),
            artifact_entry("step", step_path),
        ],
    )

    manifest = json.loads((registry_dir / "runs" / "run-123.json").read_text(encoding="utf-8"))
    assert manifest["operation"]["status"] == "success"
    assert manifest["session_id"] == "session-123"
    assert manifest["outputs"]["step_path"] == str(step_path)
    assert manifest["artifacts"][1]["exists"] is True

    index = json.loads((registry_dir / "index.json").read_text(encoding="utf-8"))
    assert index["runs"]["run-123"] == "runs/run-123.json"
    assert index["sessions"]["session-123"] == ["runs/run-123.json"]


def test_start_registry_run_is_non_fatal_when_write_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "freecad_cli_tools.artifact_registry.get_default_artifact_registry_dir",
        lambda: Path("/tmp/ignored"),
    )
    monkeypatch.setattr(
        "freecad_cli_tools.artifact_registry._write_run_record",
        lambda registry_run: (_ for _ in ()).throw(PermissionError("no write")),
    )

    registry_run = start_registry_run(
        None,
        tool="freecad-create-assembly",
        operation_type="create_assembly",
        inputs={"yaml_path": "/tmp/sample.yaml"},
    )

    assert registry_run is None
