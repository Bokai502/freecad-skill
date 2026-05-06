"""Progress percentage helpers for CLI result payloads."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from freecad_cli_tools.runtime_config import get_default_workspace_dir

PROGRESS_LOG_FILENAME = "progress_percentages.json"


def get_progress_log_path() -> Path:
    """Return the shared progress JSON path under the workspace logs directory."""
    return get_default_workspace_dir() / "logs" / PROGRESS_LOG_FILENAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def export_file_percent(
    step_path: str | Path | None,
    glb_path: str | Path | None,
    *,
    export_requested: bool,
) -> float:
    """Return export completion percent, counting STEP and GLB equally."""
    if not export_requested:
        return 0.0
    expected_count = 2
    exported_count = 0
    if step_path and Path(step_path).exists():
        exported_count += 1
    if glb_path and Path(glb_path).exists():
        exported_count += 1
    return (exported_count / expected_count) * 100.0


def output_file_entry(path: str | Path | None) -> dict[str, Any]:
    """Return a serializable output-file record."""
    if not path:
        return {"path": None, "exists": False}
    resolved_path = Path(path)
    return {
        "path": str(resolved_path),
        "exists": resolved_path.exists(),
    }


def output_file_records(**paths: str | Path | None) -> dict[str, dict[str, Any]]:
    """Build named output-file records for progress logs."""
    return {name: output_file_entry(path) for name, path in paths.items()}


def write_progress_log(
    *,
    tool: str,
    progress: dict[str, float],
    success: bool,
    output_files: dict[str, dict[str, Any]] | None = None,
    output_paths: dict[str, str | Path | None] | None = None,
) -> Path:
    """Write the latest CLI progress percentages to the workspace logs directory."""
    if output_files is None and output_paths is not None:
        output_files = output_file_records(**output_paths)
    path = get_progress_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool": tool,
        "updated_at": _utc_now_iso(),
        "success": success,
        "progress_percentages": progress,
        "output_files": output_files or {},
        **progress,
    }
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)
    return path


class ProgressLogWriter:
    """Write the shared progress JSON file from CLI-side stages."""

    def __init__(
        self,
        *,
        tool: str,
        progress: dict[str, float],
        output_paths: dict[str, str | Path | None],
        success: bool = False,
    ) -> None:
        self.tool = tool
        self.progress = dict(progress)
        self.output_paths = dict(output_paths)
        self.success = success
        self.path = get_progress_log_path()

    def start(self) -> "ProgressLogWriter":
        """Write the initial state immediately."""
        self.write()
        return self

    def update(
        self,
        *,
        progress: dict[str, float] | None = None,
        output_paths: dict[str, str | Path | None] | None = None,
        success: bool | None = None,
    ) -> Path:
        """Update state and write it immediately."""
        if progress is not None:
            self.progress = dict(progress)
        if output_paths is not None:
            self.output_paths = dict(output_paths)
        if success is not None:
            self.success = success
        return self.write()

    def write(self) -> Path:
        """Write the current state to disk."""
        self.path = write_progress_log(
            tool=self.tool,
            progress=dict(self.progress),
            success=self.success,
            output_paths=dict(self.output_paths),
        )
        return self.path


def attach_progress_log_path(payload: dict[str, Any], progress_log_path: Path) -> None:
    """Attach the progress JSON path to a CLI payload."""
    payload["progress_json_path"] = str(progress_log_path)


def progress_percentages(
    *,
    layout_complete: bool,
    modeling_requested: bool,
    modeling_complete: bool,
    step_path: str | Path | None,
    glb_path: str | Path | None,
    export_requested: bool,
) -> dict[str, float]:
    """Build standardized progress percentages for CLI outputs."""
    return {
        "layout_completion_percent": 100.0 if layout_complete else 0.0,
        "modeling_percent": (100.0 if modeling_requested and modeling_complete else 0.0),
        "export_file_percent": export_file_percent(
            step_path,
            glb_path,
            export_requested=export_requested,
        ),
    }


def attach_progress_percentages(
    payload: dict[str, Any],
    *,
    layout_complete: bool,
    modeling_requested: bool,
    modeling_complete: bool,
    step_path: str | Path | None,
    glb_path: str | Path | None,
    export_requested: bool,
) -> dict[str, float]:
    """Attach progress percentages as nested and top-level payload fields."""
    progress = progress_percentages(
        layout_complete=layout_complete,
        modeling_requested=modeling_requested,
        modeling_complete=modeling_complete,
        step_path=step_path,
        glb_path=glb_path,
        export_requested=export_requested,
    )
    payload["progress_percentages"] = progress
    payload.update(progress)
    return progress
