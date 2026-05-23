"""Progress percentage helpers for CLI result payloads."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from freecad_cli_tools.runtime_config import get_default_workspace_dir

PROGRESS_LOG_FILENAME = "progress_percentages.json"
PROGRESS_SCHEMA_VERSION = "freecad_progress/1.0"
PROGRESS_KEYS = (
    "modeling_percent",
    "export_file_percent",
    "validation_percent",
)
CAD_BUILD_COMMANDS = {"cad build", "freecad-tools cad build"}
CAD_VALIDATE_COMMANDS = {"cad validate", "freecad-tools cad validate"}
CAD_MODIFY_COMMANDS = {"layout safe-move", "freecad-layout-safe-move", "freecad-tools layout safe-move"}


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


def normalize_progress(progress: dict[str, float]) -> dict[str, float]:
    """Return progress with every standard percentage key present."""
    normalized = {key: 0.0 for key in PROGRESS_KEYS}
    for key, value in progress.items():
        normalized[key] = float(value)
    return normalized


def overall_percent(progress: dict[str, float]) -> float:
    """Return a simple average across the standard FreeCAD progress fields."""
    normalized = normalize_progress(progress)
    return round(sum(normalized[key] for key in PROGRESS_KEYS) / len(PROGRESS_KEYS), 2)


def visible_progress_for_command(
    progress: dict[str, float],
    *,
    tool: str,
    command: str | None,
) -> dict[str, float]:
    """Return the progress fields that should be exposed in the shared progress log."""
    normalized = normalize_progress(progress)
    names = {tool.strip().lower()}
    if command:
        names.add(command.strip().lower())

    if names & CAD_VALIDATE_COMMANDS:
        return {"validation_percent": normalized["validation_percent"]}

    if names & CAD_BUILD_COMMANDS:
        modeling_values = [normalized["modeling_percent"]]
        if "export_file_percent" in progress:
            modeling_values.append(normalized["export_file_percent"])
        return {"modeling_percent": round(sum(modeling_values) / len(modeling_values), 2)}

    return {key: value for key, value in normalized.items() if key != "layout_completion_percent"}


def visible_overall_percent(progress: dict[str, float]) -> float:
    """Return an overall percent using only the visible progress fields."""
    if not progress:
        return 0.0
    return round(sum(progress.values()) / len(progress), 2)


def _read_existing_progress(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_existing_progress_log() -> dict[str, Any]:
    """Return the current progress log payload if it exists."""
    return _read_existing_progress(get_progress_log_path())


def infer_validation_workflow(default: str = "cad_validation") -> str:
    """Infer whether cad validate is completing the create or modify workflow."""
    existing = read_existing_progress_log()
    workflow = existing.get("workflow")
    if workflow in {"create_cad", "modify_cad"}:
        return str(workflow)

    tools = existing.get("tools")
    if isinstance(tools, dict):
        for tool_name in (
            "freecad-tools cad build",
            "freecad-layout-safe-move",
            "freecad-tools layout safe-move",
        ):
            entry = tools.get(tool_name)
            if isinstance(entry, dict) and entry.get("workflow") in {"create_cad", "modify_cad"}:
                return str(entry["workflow"])
    return default


def _progress_for_tool_payload(tool: str, payload: dict[str, Any]) -> dict[str, float]:
    progress = payload.get("progress_percentages")
    if not isinstance(progress, dict):
        return {}

    command = str(payload.get("command") or tool).strip().lower()
    tool_name = str(payload.get("tool") or tool).strip().lower()
    names = {command, tool_name}
    normalized = normalize_progress(progress)

    if names & CAD_VALIDATE_COMMANDS:
        return {"validation_percent": normalized["validation_percent"]}

    if names & CAD_BUILD_COMMANDS:
        return {
            "modeling_percent": normalized["modeling_percent"],
            "export_file_percent": normalized["export_file_percent"],
        }

    return {
        key: float(value)
        for key, value in normalized.items()
        if key in PROGRESS_KEYS
    }


def _aggregate_progress_from_tools(
    tools: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, float]:
    aggregated = {key: 0.0 for key in PROGRESS_KEYS}
    for tool_name, tool_payload in tools.items():
        if not isinstance(tool_payload, dict):
            continue
        for key, value in _progress_for_tool_payload(str(tool_name), tool_payload).items():
            aggregated[key] = max(aggregated[key], float(value))

    # Legacy progress files may not have a tools map yet. Preserve any existing
    # completed scalar fields so starting a later stage does not regress them.
    fallback_progress = fallback.get("progress_percentages")
    if isinstance(fallback_progress, dict):
        for key in PROGRESS_KEYS:
            value = fallback_progress.get(key)
            if isinstance(value, (int, float)):
                aggregated[key] = max(aggregated[key], float(value))
    for key in PROGRESS_KEYS:
        value = fallback.get(key)
        if isinstance(value, (int, float)):
            aggregated[key] = max(aggregated[key], float(value))

    return aggregated


def _starts_cad_workflow(payload: dict[str, Any]) -> bool:
    command = str(payload.get("command") or "").strip().lower()
    tool = str(payload.get("tool") or "").strip().lower()
    names = {command, tool}
    return bool(names & (CAD_BUILD_COMMANDS | CAD_MODIFY_COMMANDS))


def _merge_progress_payload(
    path: Path,
    tool: str,
    payload: dict[str, Any],
    *,
    merge_output_files: bool,
) -> dict[str, Any]:
    existing = _read_existing_progress(path)
    merged = dict(existing)
    merged.update(payload)

    tools = existing.get("tools")
    if not isinstance(tools, dict):
        tools = {}
    merged_tools = dict(tools)
    if _starts_cad_workflow(payload):
        for stale_tool in list(merged_tools):
            stale_payload = merged_tools.get(stale_tool)
            if not isinstance(stale_payload, dict):
                continue
            stale_command = str(stale_payload.get("command") or stale_tool).strip().lower()
            stale_tool_name = str(stale_payload.get("tool") or stale_tool).strip().lower()
            if {stale_command, stale_tool_name} & CAD_VALIDATE_COMMANDS:
                merged_tools.pop(stale_tool, None)
    merged_tools[tool] = payload
    for tool_payload in merged_tools.values():
        if isinstance(tool_payload, dict):
            tool_payload.pop("output_files", None)
    merged["tools"] = merged_tools
    merged["progress_percentages"] = _aggregate_progress_from_tools(merged_tools, existing)
    merged.pop("history", None)
    if not merge_output_files:
        merged.pop("output_files", None)

    return merged


def _status_from_success(success: bool | None) -> str:
    if success is None:
        return "running"
    return "success" if success else "failed"


def write_progress_log(
    *,
    tool: str,
    progress: dict[str, float],
    success: bool | None,
    output_files: dict[str, dict[str, Any]] | None = None,
    output_paths: dict[str, str | Path | None] | None = None,
    workflow: str | None = None,
    command: str | None = None,
    stage: str | None = None,
    status: str | None = None,
    error: dict[str, Any] | None = None,
    merge_output_files: bool = True,
) -> Path:
    """Write the latest CLI progress percentages to the workspace logs directory."""
    path = get_progress_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    command_name = command or tool
    visible_progress = visible_progress_for_command(progress, tool=tool, command=command_name)
    payload = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "workflow": workflow,
        "command": command_name,
        "stage": stage,
        "status": status or _status_from_success(success),
        "tool": tool,
        "updated_at": _utc_now_iso(),
        "success": bool(success) if success is not None else False,
        "overall_percent": visible_overall_percent(visible_progress),
        "progress_percentages": normalize_progress(progress),
        "error": error,
        **visible_progress,
    }
    if merge_output_files and output_paths:
        payload["output_files"] = output_file_records(**output_paths)

    payload = _merge_progress_payload(
        path,
        tool,
        payload,
        merge_output_files=merge_output_files,
    )
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
        success: bool | None = None,
        workflow: str | None = None,
        command: str | None = None,
        stage: str | None = None,
        status: str | None = None,
        merge_output_files: bool = False,
    ) -> None:
        self.tool = tool
        self.progress = dict(progress)
        self.output_paths = dict(output_paths)
        self.success = success
        self.workflow = workflow
        self.command = command or tool
        self.stage = stage
        self.status = status
        self.error: dict[str, Any] | None = None
        self.path = get_progress_log_path()
        self.merge_output_files = merge_output_files

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
        status: str | None = None,
        stage: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> Path:
        """Update state and write it immediately."""
        if progress is not None:
            self.progress = dict(progress)
        if output_paths is not None:
            self.output_paths = dict(output_paths)
        if success is not None:
            self.success = success
        if status is not None:
            self.status = status
        if stage is not None:
            self.stage = stage
        if error is not None:
            self.error = error
        return self.write()

    def write(self) -> Path:
        """Write the current state to disk."""
        self.path = write_progress_log(
            tool=self.tool,
            progress=dict(self.progress),
            success=self.success,
            output_paths=dict(self.output_paths),
            workflow=self.workflow,
            command=self.command,
            stage=self.stage,
            status=self.status,
            error=self.error,
            merge_output_files=self.merge_output_files,
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
        "validation_percent": 0.0,
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
