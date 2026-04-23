from __future__ import annotations

import json
import sys

from freecad_cli_tools.cli import get_objects


def test_get_objects_renders_script_and_prints_payload(monkeypatch, capsys) -> None:
    rendered = {}

    def fake_render(script_name: str, replacements: dict[str, str]) -> str:
        rendered["script_name"] = script_name
        rendered["replacements"] = replacements
        return "print('hello')"

    monkeypatch.setattr(get_objects, "render_rpc_script", fake_render)
    monkeypatch.setattr(
        get_objects,
        "run_script_command",
        lambda args, code: [{"Name": "Box", "Label": "Box", "ViewObject": {"TypeId": "Gui"}}],
    )
    monkeypatch.setattr(sys, "argv", ["freecad-get-objs", "DemoDoc"])

    get_objects.main()

    assert rendered == {
        "script_name": "get_objects.py",
        "replacements": {"__DOC_NAME__": json.dumps("DemoDoc")},
    }


def test_get_objects_uses_run_script_command(monkeypatch) -> None:
    calls = {}

    monkeypatch.setattr(get_objects, "render_rpc_script", lambda *args, **kwargs: "SCRIPT")

    def fake_run(args, code):
        calls["doc_name"] = args.doc_name
        calls["code"] = code
        return []

    monkeypatch.setattr(get_objects, "run_script_command", fake_run)
    monkeypatch.setattr(sys, "argv", ["freecad-get-objs", "DemoDoc"])

    get_objects.main()

    assert calls == {"doc_name": "DemoDoc", "code": "SCRIPT"}
