from __future__ import annotations

from pathlib import Path

from freecad_cli_tools.cli_support import load_json_input


def test_load_json_input_accepts_utf8_bom_file(tmp_path: Path) -> None:
    json_path = tmp_path / "updates.json"
    json_path.write_text('[{"component": "P001"}]', encoding="utf-8-sig")

    payload = load_json_input(file_path=str(json_path))

    assert payload == [{"component": "P001"}]
