from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from freecad_cli_tools.cli import validate_workspace


def test_validate_workspace_cli_reports_success(tmp_path: Path, capsys, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    layout_dir = workspace / "01_layout"
    layout_dir.mkdir(parents=True)
    (layout_dir / "layout_topology.json").write_text("{}", encoding="utf-8")
    (layout_dir / "geom.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-validate-workspace",
            "--workspace",
            str(workspace),
        ],
    )

    validate_workspace.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["workspace"] == str(workspace.resolve())
    assert payload["rpc"]["checked"] is False


def test_validate_workspace_cli_fails_when_component_info_required(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    layout_dir = workspace / "01_layout"
    layout_dir.mkdir(parents=True)
    (layout_dir / "layout_topology.json").write_text("{}", encoding="utf-8")
    (layout_dir / "geom.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-validate-workspace",
            "--workspace",
            str(workspace),
            "--require-component-info",
        ],
    )

    with pytest.raises(FileNotFoundError):
        validate_workspace.main()
