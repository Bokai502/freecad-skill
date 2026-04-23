from __future__ import annotations

import json
import sys

from freecad_cli_tools.cli import list_documents


def test_list_documents_prints_name_and_label(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        list_documents,
        "execute_script_payload",
        lambda host, port, code: [{"name": "Unnamed", "label": "BlueBoxDemo"}],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-list-docs",
        ],
    )

    list_documents.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload == [{"name": "Unnamed", "label": "BlueBoxDemo"}]
