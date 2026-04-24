from __future__ import annotations

import json
import sys
from pathlib import Path

from freecad_cli_tools.cli import replace_component


def test_replace_component_writes_registry_record(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    registry_dir = tmp_path / "registry"
    yaml_path = tmp_path / "sample.yaml"
    assembly_path = tmp_path / "SampleAssembly.step"
    replacement_path = tmp_path / "replacement.step"
    yaml_path.write_text("components: {}\n", encoding="utf-8")
    assembly_path.write_text("old-step", encoding="utf-8")
    replacement_path.write_text("replacement-step", encoding="utf-8")

    rendered: dict[str, object] = {}

    def fake_render(script_name: str, replacements: dict[str, str]) -> str:
        rendered["script_name"] = script_name
        rendered["replacements"] = replacements
        return "SCRIPT"

    def fake_execute(host: str, port: int, code: str) -> dict:
        assert code == "SCRIPT"
        assembly_path.write_text("new-step", encoding="utf-8")
        assembly_path.with_suffix(".glb").write_text("new-glb", encoding="utf-8")
        return {
            "success": True,
            "assembly_path": str(assembly_path),
            "glb_path": str(assembly_path.with_suffix(".glb")),
            "component": "P001",
        }

    monkeypatch.setattr(replace_component, "render_rpc_script", fake_render)
    monkeypatch.setattr(replace_component, "execute_script_payload", fake_execute)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-replace-component",
            "--yaml",
            str(yaml_path),
            "--assembly",
            str(assembly_path),
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
    assert payload["assembly_path"] == str(assembly_path)
    assert rendered["script_name"] == "replace_component.py"

    manifest = json.loads(
        (registry_dir / "runs" / "replace-run.json").read_text(encoding="utf-8")
    )
    assert manifest["operation"]["status"] == "success"
    assert manifest["outputs"]["step_path"] == str(assembly_path)
    assert manifest["outputs"]["glb_path"] == str(assembly_path.with_suffix(".glb"))
    assert manifest["artifacts"][3]["path"] == str(replacement_path)
