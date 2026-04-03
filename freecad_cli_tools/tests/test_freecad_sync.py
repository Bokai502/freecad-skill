from __future__ import annotations

import pytest

from freecad_cli_tools.freecad_sync import normalize_sync_updates


def test_normalize_sync_updates_accepts_wrapped_payload_and_defaults_names() -> None:
    updates = normalize_sync_updates(
        {
            "updates": [
                {
                    "component": "P005",
                    "position": [1, 2, 3],
                    "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                }
            ]
        }
    )

    assert updates == [
        {
            "component": "P005",
            "solid_name": "P005",
            "part_name": "P005_part",
            "position": [1.0, 2.0, 3.0],
            "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        }
    ]


def test_normalize_sync_updates_rejects_missing_component() -> None:
    with pytest.raises(ValueError, match="missing 'component'"):
        normalize_sync_updates(
            [
                {
                    "position": [1, 2, 3],
                    "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                }
            ]
        )
