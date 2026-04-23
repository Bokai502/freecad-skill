"""Shared helpers for FreeCAD CLI entry points."""

from __future__ import annotations

import base64
import errno
import json
import socket
import sys
import xmlrpc.client
from pathlib import Path
from typing import Any

from .rpc_client import get_connection
from .rpc_client import print_result as print_json
from .runtime_config import get_runtime_setting

OUTPUT_MARKER = "Output:"


def _iter_exception_chain(exc: BaseException) -> list[BaseException]:
    """Flatten an exception with its causes/contexts for pattern matching."""
    seen: set[int] = set()
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def format_rpc_connection_error(exc: BaseException, host: str, port: int) -> str:
    """Return a friendly message when the FreeCAD XML-RPC endpoint is unreachable."""
    chain = _iter_exception_chain(exc)
    for current in chain:
        if isinstance(current, socket.gaierror):
            detail = str(current)
            return (
                f"Cannot connect to FreeCAD RPC server at {host}:{port}: cannot resolve "
                f"host '{host}'. Check --host/--port or start FreeCAD with the "
                f"FreeCAD MCP addon active. Details: {detail}"
            )

        if isinstance(current, OSError) and current.errno == errno.ECONNREFUSED:
            detail = str(current)
            return (
                f"Cannot connect to FreeCAD RPC server at {host}:{port}: connection "
                f"refused. Start FreeCAD with the FreeCAD MCP addon active, or pass "
                f"--host/--port if the server is listening elsewhere. Details: {detail}"
            )

        if isinstance(current, ConnectionRefusedError):
            detail = str(current)
            return (
                f"Cannot connect to FreeCAD RPC server at {host}:{port}: connection "
                f"refused. Start FreeCAD with the FreeCAD MCP addon active, or pass "
                f"--host/--port if the server is listening elsewhere. Details: {detail}"
            )

    if any(isinstance(current, (OSError, xmlrpc.client.ProtocolError)) for current in chain):
        detail = str(chain[0])
        return (
            f"Cannot connect to FreeCAD RPC server at {host}:{port}. Check that FreeCAD "
            f"is running with the FreeCAD MCP addon active and that --host/--port match "
            f"the listening address. Details: {detail}"
        )

    return str(exc)


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


def describe_rpc_failure(result: Any) -> str:
    """Build a useful error message from an RPC failure payload."""
    if not isinstance(result, dict):
        return f"FreeCAD code execution failed: {result!r}"

    details: list[str] = []
    for key in ("error", "message"):
        value = result.get(key)
        if value:
            details.append(str(value).strip())

    if not details:
        details.append("FreeCAD code execution failed")

    raw_result = json.dumps(result, ensure_ascii=False)
    if raw_result not in details:
        details.append(f"RPC result: {raw_result}")
    return " | ".join(details)


def extract_output_payload(result: dict) -> dict:
    """Extract the JSON payload printed by execute_code-based RPC commands."""
    def parse_payload_text(text: str) -> Any:
        candidates: list[str] = []
        stripped = text.strip()
        if stripped:
            candidates.append(stripped)
            lines = [line.strip() for line in stripped.splitlines() if line.strip()]
            if lines:
                candidates.append(lines[-1])
                candidates.extend(
                    line for line in reversed(lines) if line[:1] in {"{", "["}
                )
            for marker in ("{", "["):
                index = stripped.find(marker)
                if index != -1:
                    candidates.append(stripped[index:])

        seen: set[str] = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise json.JSONDecodeError("No JSON payload found", text, 0)

    message = result.get("message", "")
    if OUTPUT_MARKER not in message:
        if not result.get("success"):
            raise RuntimeError(describe_rpc_failure(result))
        try:
            return parse_payload_text(message)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Unexpected RPC response: {message}") from exc

    payload = message.split(OUTPUT_MARKER, 1)[1].strip()
    try:
        return parse_payload_text(payload)
    except json.JSONDecodeError:
        return parse_payload_text(message)


def execute_script_payload(host: str, port: int, code: str) -> dict:
    """Execute a Python script in FreeCAD and return the embedded JSON payload."""
    try:
        result = call_rpc_method(host, port, "execute_code", code, verify_connection=False)
    except Exception as exc:
        raise RuntimeError(format_rpc_connection_error(exc, host, port)) from exc
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
        with Path(file_path).open("r", encoding="utf-8-sig") as handle:
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


def normalize_runtime_path(path: Path) -> str:
    """Return a resolved path string visible to the local FreeCAD runtime."""
    return str(path.resolve())


def write_base64_file(encoded_data: str, output_path: str | Path) -> Path:
    """Decode a base64 payload and write it to disk."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(encoded_data))
    return target
