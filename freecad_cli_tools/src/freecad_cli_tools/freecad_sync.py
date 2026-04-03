"""Helpers for syncing computed placements into FreeCAD over RPC."""

from __future__ import annotations

import json
from typing import Any

from .cli_support import execute_script_payload
from .rpc_script_fragments import PLACEMENT_HELPERS
from .rpc_script_loader import render_rpc_script


def normalize_sync_updates(raw_updates: Any) -> list[dict[str, Any]]:
    """Validate and normalize placement updates for batch CAD sync."""
    if isinstance(raw_updates, dict):
        updates = raw_updates.get("updates", [])
    else:
        updates = raw_updates

    if not isinstance(updates, list) or not updates:
        raise ValueError(
            "Sync updates must be a non-empty list or an object with an 'updates' list."
        )

    normalized = []
    for index, item in enumerate(updates, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Sync update #{index} must be an object.")

        component_id = str(
            item.get("component") or item.get("component_id") or ""
        ).strip()
        if not component_id:
            raise ValueError(f"Sync update #{index} is missing 'component'.")

        position = item.get("position")
        rotation_matrix = item.get("rotation_matrix")
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError(
                f"Sync update #{index} must include a 3-item 'position' list."
            )
        if not isinstance(rotation_matrix, list) or len(rotation_matrix) != 3:
            raise ValueError(
                f"Sync update #{index} must include a 3x3 'rotation_matrix' list."
            )
        for row in rotation_matrix:
            if not isinstance(row, list) or len(row) != 3:
                raise ValueError(
                    f"Sync update #{index} must include a 3x3 'rotation_matrix' list."
                )

        normalized.append(
            {
                "component": component_id,
                "solid_name": item.get("solid_name")
                or item.get("component_object")
                or component_id,
                "part_name": item.get("part_name")
                or item.get("part_object")
                or f"{component_id}_part",
                "position": [float(value) for value in position],
                "rotation_matrix": [
                    [int(value) for value in row] for row in rotation_matrix
                ],
            }
        )
    return normalized


def render_batch_sync_script(
    doc_name: str,
    updates: list[dict[str, Any]],
    *,
    recompute: bool = False,
) -> str:
    """Render the FreeCAD-side batch placement sync script."""
    return render_rpc_script(
        "sync_component_placements.py",
        {
            "__PLACEMENT_HELPERS__": PLACEMENT_HELPERS,
            "__DOC_NAME__": json.dumps(doc_name),
            "__UPDATES__": json.dumps(updates),
            "__RECOMPUTE__": "True" if recompute else "False",
        },
    )


def execute_batch_sync(
    host: str,
    port: int,
    doc_name: str,
    updates: list[dict[str, Any]],
    *,
    recompute: bool = False,
) -> dict[str, Any]:
    """Execute a batch placement sync against the target FreeCAD document."""
    code = render_batch_sync_script(doc_name, updates, recompute=recompute)
    payload = execute_script_payload(host, port, code)
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or "CAD sync failed")
    return payload
