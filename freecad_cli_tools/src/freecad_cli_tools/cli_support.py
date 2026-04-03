"""Shared helpers for FreeCAD CLI entry points."""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

from .rpc_client import get_connection, print_result as print_json


OUTPUT_MARKER = "Output:"
def exit_on_failure(result: Any) -> None:
    """Exit with status 1 when a JSON result reports failure."""
    if isinstance(result, dict) and not result.get("success"):
        raise SystemExit(1)


def call_rpc_method(
    host: str,
    port: int,
    method_name: str,
    *method_args: Any,
    verify_connection: bool = True,
) -> Any:
    """Call a named RPC method through the shared FreeCAD connection."""
    conn = get_connection(host, port, verify=verify_connection)
    method = getattr(conn, method_name)
    return method(*method_args)


def call_rpc_from_args(args: Any, method_name: str, *method_args: Any) -> Any:
    """Call a named RPC method using a CLI namespace with host/port attributes."""
    return call_rpc_method(args.host, args.port, method_name, *method_args)


def run_rpc_command(
    args: Any,
    method_name: str,
    *method_args: Any,
    require_success: bool = False,
) -> Any:
    """Run an RPC method, print the JSON result, and optionally fail on success=false."""
    result = call_rpc_from_args(args, method_name, *method_args)
    print_json(result)
    if require_success:
        exit_on_failure(result)
    return result


def extract_output_payload(result: dict) -> dict:
    """Extract the JSON payload printed by execute_code-based RPC commands."""
    if not result.get("success"):
        raise RuntimeError(result.get("message") or "FreeCAD code execution failed")

    message = result.get("message", "")
    if OUTPUT_MARKER not in message:
        raise RuntimeError(f"Unexpected RPC response: {message}")

    payload = message.split(OUTPUT_MARKER, 1)[1].strip()
    return json.loads(payload)


def execute_script_payload(host: str, port: int, code: str) -> dict:
    """Execute a Python script in FreeCAD and return the embedded JSON payload."""
    result = call_rpc_method(host, port, "execute_code", code, verify_connection=False)
    return extract_output_payload(result)


def run_script_command(args: Any, code: str, require_success: bool = True) -> dict:
    """Execute a Python script in FreeCAD, print the parsed payload, and optionally fail."""
    try:
        payload = execute_script_payload(args.host, args.port, code)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print_json(payload)
    if require_success:
        exit_on_failure(payload)
    return payload


def load_json_input(raw_value: str = "{}", *, file_path: str | None = None) -> Any:
    """Load JSON either from an inline string or from a file."""
    if file_path:
        with Path(file_path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(raw_value)


def read_text_input(
    raw_value: str | None = None,
    *,
    file_path: str | None = None,
    allow_stdin: bool = False,
) -> str:
    """Read text from a file, an inline value, or stdin."""
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    if raw_value is not None:
        return raw_value
    if allow_stdin:
        return sys.stdin.read()
    return ""


def require_non_empty_text(text: str, *, error_message: str) -> str:
    """Exit with a friendly error when required text input is empty."""
    if text.strip():
        return text
    print(error_message, file=sys.stderr)
    raise SystemExit(1)


def to_wsl_path(path: Path) -> str:
    """Convert a Windows path to a WSL-visible path when needed."""
    resolved = str(path.resolve())
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", resolved)
    if not match:
        return resolved
    drive = match.group(1).lower()
    remainder = match.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{remainder}"


def write_base64_file(encoded_data: str, output_path: str | Path) -> Path:
    """Decode a base64 payload and write it to disk."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(encoded_data))
    return target
