from __future__ import annotations

import json
import sys

from freecad_cli_tools.cli import get_object


def test_get_object_renders_script_and_invokes_runner(monkeypatch) -> None:
    rendered = {}
    calls = {}

    def fake_render(script_name: str, replacements: dict[str, str]) -> str:
        rendered["script_name"] = script_name
        rendered["replacements"] = replacements
        return "SCRIPT"

    def fake_run(args, code):
        calls["doc_name"] = args.doc_name
        calls["obj_name"] = args.obj_name
        calls["code"] = code
        return {"Name": "Box"}

    monkeypatch.setattr(get_object, "render_rpc_script", fake_render)
    monkeypatch.setattr(get_object, "run_script_command", fake_run)
    monkeypatch.setattr(sys, "argv", ["freecad-get-obj", "DemoDoc", "Box"])

    get_object.main()

    assert rendered == {
        "script_name": "get_object.py",
        "replacements": {
            "__DOC_NAME__": json.dumps("DemoDoc"),
            "__OBJ_NAME__": json.dumps("Box"),
        },
    }
    assert calls == {"doc_name": "DemoDoc", "obj_name": "Box", "code": "SCRIPT"}
