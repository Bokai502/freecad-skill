#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


TOOL_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = TOOL_ROOT / "runtime"
CODEX_AGENTS_ROOT = RUNTIME_ROOT / "codex_agents"
EXTRA_PYTHONPATH = Path("/tmp/codex_openpyxl_py313")

DEFAULT_WORKSPACE = Path("/data/lbk/codex_web/FreeCAD_data/v9_data")
APP_CONFIG_PATH = Path("/data/lbk/codex_web/config.json")
DEFAULT_PYTHON = Path("/data/conda/bin/python")
DEFAULT_SAMPLE_ID = "930001"
TOOL_NAME = "sim-run"
PROGRESS_STEPS = (
    ("simulation", "simulation_run"),
    ("field_export", "field_export"),
    ("postprocess", "postprocess"),
    ("case_build", "case_build"),
    ("analysis", "analysis"),
)

REQUIRED_INPUT_FILES = ("real_bom.json", "layout_topology.json", "geom.json")
REQUIRED_CAD_FILES = (
    "geometry_after.step",
    "geometry_after.geom.json",
    "geometry_after.layout_topology.json",
    "geometry_after_registry.json",
    "simulation_input.json",
    "comsol_inputs/coord.txt",
    "comsol_inputs/channels_input.npz",
)


def bootstrap_runtime() -> None:
    for path in (
        RUNTIME_ROOT,
        EXTRA_PYTHONPATH,
        CODEX_AGENTS_ROOT / "vendor",
        CODEX_AGENTS_ROOT / "vendor" / "layout_runtime",
        CODEX_AGENTS_ROOT / "vendor" / "shared_contracts",
    ):
        value = str(path)
        if value in sys.path:
            sys.path.remove(value)
        sys.path.insert(0, value)

    if "codex_agents" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "codex_agents",
            CODEX_AGENTS_ROOT / "__init__.py",
            submodule_search_locations=[str(CODEX_AGENTS_ROOT)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load copied runtime from {CODEX_AGENTS_ROOT}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["codex_agents"] = module
        spec.loader.exec_module(module)


bootstrap_runtime()

from codex_agents.config import BomExternalToolsPipelineConfig  # noqa: E402
from codex_agents.context import BomExternalToolsPipelineContext  # noqa: E402
from codex_agents.local_io import read_json, write_json  # noqa: E402
from codex_agents.logging_utils import configure_logging  # noqa: E402
from codex_agents.stage_adapters import case_stage, layout_stage_result  # noqa: E402
from codex_agents.steps import AnalysisStep, CaseBuildStep, FieldExportStep, PostprocessStep, SimulationStep  # noqa: E402
from input_normalize.normalize import normalize_bom_to_components  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        return handler(args)
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        if getattr(args, "json", False):
            print_json(payload)
        else:
            print(f"{TOOL_NAME}: error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Run copied cad_sim_agents runtime on 00_inputs + 01_cad and write outputs under 02_sim.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check whether the input set can run.")
    add_common_args(doctor)
    doctor.set_defaults(handler=handle_doctor)

    run = subparsers.add_parser("run", help="Prepare 02_sim and run simulation through analysis.")
    add_common_args(run)
    run.add_argument(
        "--simulation-backend",
        choices=("comsol_local", "mock_contract"),
        default=os.environ.get("SIMULATION_BACKEND", "comsol_local"),
    )
    run.add_argument("--sample-id", default=os.environ.get("SAMPLE_ID", DEFAULT_SAMPLE_ID))
    run.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "930001")))
    run.add_argument("--mph-port", type=int, default=int(os.environ.get("MPH_PORT", "32036")), help="Preferred COMSOL mphserver port. Defaults to 32036 to avoid the common 2036 port.")
    run.set_defaults(open_external_tools=True)
    run.add_argument("--open-tools", dest="open_external_tools", action="store_true", help="Open COMSOL/ParaView GUI tools after simulation. Enabled by default.")
    run.add_argument("--no-open-tools", dest="open_external_tools", action="store_false", help="Do not open COMSOL/ParaView GUI tools after simulation.")
    run.add_argument("--force", action="store_true", help="Ignore a stale run lock after verifying the recorded PID is not alive.")
    run.add_argument("--quiet", action="store_true")
    run.set_defaults(handler=handle_run)
    return parser


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-dir", type=Path, default=resolve_default_workspace())
    parser.add_argument("--input-dir", type=Path, default=None, help="Defaults to <workspace-dir>/00_inputs.")
    parser.add_argument("--cad-dir", type=Path, default=None, help="Defaults to <workspace-dir>/01_cad.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Defaults to <workspace-dir>/02_sim.")


def resolve_default_workspace() -> Path:
    for env_name in ("SIM_WORKSPACE_DIR", "FREECAD_WORKSPACE_DIR", "WORKSPACE_DIR"):
        workspace = os.environ.get(env_name)
        if workspace:
            return Path(workspace)
    if APP_CONFIG_PATH.exists():
        try:
            config = json.loads(APP_CONFIG_PATH.read_text(encoding="utf-8"))
            workspace = config.get("freecad", {}).get("workspaceDir")
            if workspace:
                return Path(workspace)
        except (OSError, json.JSONDecodeError):
            pass
    return DEFAULT_WORKSPACE


def handle_doctor(args: argparse.Namespace) -> int:
    paths = resolve_paths(args)
    missing = missing_required_files(paths["input_dir"], paths["cad_dir"])
    payload = {
        "ok": not missing and CODEX_AGENTS_ROOT.exists(),
        "tool": TOOL_NAME,
        "runtime": str(CODEX_AGENTS_ROOT),
        "paths": {key: str(value) for key, value in paths.items()},
        "missing_files": [str(path) for path in missing],
        "outputs": {
            "root": str(paths["output_dir"]),
            "simulation": str(paths["output_dir"] / "simulation"),
            "postprocess": str(paths["output_dir"] / "postprocess"),
            "case_build": str(paths["output_dir"] / "case_build"),
            "analysis": str(paths["output_dir"] / "analysis"),
        },
    }
    emit(payload, args.json)
    return 0 if payload["ok"] else 1


def handle_run(args: argparse.Namespace) -> int:
    paths = resolve_paths(args)
    missing = missing_required_files(paths["input_dir"], paths["cad_dir"])
    if missing:
        raise RuntimeError("missing required files: " + ", ".join(str(path) for path in missing))

    with run_lock(paths["output_dir"], force=bool(args.force)):
        config = BomExternalToolsPipelineConfig(
            bom_json=paths["input_dir"] / "real_bom.json",
            run_root=paths["output_dir"],
            sample_id=args.sample_id,
            seed=args.seed,
            simulation_backend=args.simulation_backend,
            mph_port=int(args.mph_port) if args.mph_port else None,
            open_external_tools=bool(args.open_external_tools),
        )
        configure_logging(run_root=config.run_root, log_file=paths["workspace_dir"] / "logs" / "pipeline.log", quiet=bool(args.quiet))
        write_run_state(paths["output_dir"], args)
        ctx = BomExternalToolsPipelineContext(config, restore_existing=False)
        bind_source_paths(ctx, paths)
        progress_path = ctx.paths["logs"] / "progress_percentages.json"
        initialize_tool_progress(progress_path, paths)
        prepare_contract_workspace(ctx, paths, args.sample_id, args.seed)

        for step in (SimulationStep(), FieldExportStep(), PostprocessStep(), CaseBuildStep(), AnalysisStep()):
            step_name = progress_step_name(step)
            update_tool_progress(progress_path, step_name, status="running", percent=5.0)
            execution = step.run(ctx)
            ctx.append_stage(execution.stage)
            finished_status = "completed" if execution.stage.get("status") in {"completed", "completed_with_unplaced"} else "failed"
            update_tool_progress(
                progress_path,
                step_name,
                status=finished_status,
                percent=100.0 if finished_status == "completed" else 99.0,
                stage=execution.stage,
            )
            if not execution.continue_pipeline:
                manifest = ctx.write_manifest()
                finalize_tool_progress(progress_path, ok=bool(manifest.get("ok")))
                emit(manifest, args.json)
                return 0 if manifest.get("ok") else 1

        manifest = ctx.write_manifest()
        finalize_tool_progress(progress_path, ok=bool(manifest.get("ok")))
        emit(manifest, args.json)
        return 0 if manifest.get("ok") else 1


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    workspace = args.workspace_dir.expanduser().resolve()
    return {
        "workspace_dir": workspace,
        "input_dir": (args.input_dir or workspace / "00_inputs").expanduser().resolve(),
        "cad_dir": (args.cad_dir or workspace / "01_cad").expanduser().resolve(),
        "output_dir": (args.output_dir or workspace / "02_sim").expanduser().resolve(),
    }


def missing_required_files(input_dir: Path, cad_dir: Path) -> list[Path]:
    missing: list[Path] = []
    for name in REQUIRED_INPUT_FILES:
        path = input_dir / name
        if not path.exists():
            missing.append(path)
    for name in REQUIRED_CAD_FILES:
        path = cad_dir / name
        if not path.exists():
            missing.append(path)
    return missing


class run_lock:
    def __init__(self, output_dir: Path, *, force: bool = False) -> None:
        self.output_dir = output_dir
        self.lock_path = output_dir / ".run.lock"
        self.force = force
        self.fd: int | None = None

    def __enter__(self) -> "run_lock":
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            lock = read_lock(self.lock_path)
            pid = int(lock.get("pid") or 0)
            if pid and pid_alive(pid):
                raise RuntimeError(f"run lock is active: {self.lock_path} pid={pid}")
            if not self.force:
                raise RuntimeError(f"stale run lock exists: {self.lock_path}; rerun with --force to remove it")
            self.lock_path.unlink()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        self.fd = os.open(self.lock_path, flags, 0o644)
        payload = {
            "pid": os.getpid(),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "output_dir": str(self.output_dir),
        }
        os.write(self.fd, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        os.fsync(self.fd)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def read_lock(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_run_state(output_dir: Path, args: argparse.Namespace) -> None:
    write_json(
        output_dir / "run_state.json",
        {
            "schema_version": "1.0",
            "pid": os.getpid(),
            "simulation_backend": args.simulation_backend,
            "mph_port": int(args.mph_port) if args.mph_port else None,
            "open_external_tools": bool(args.open_external_tools),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        },
    )


def progress_step_name(step: object) -> str:
    if isinstance(step, SimulationStep):
        return "simulation"
    if isinstance(step, FieldExportStep):
        return "field_export"
    if isinstance(step, PostprocessStep):
        return "postprocess"
    if isinstance(step, CaseBuildStep):
        return "case_build"
    if isinstance(step, AnalysisStep):
        return "analysis"
    raise RuntimeError(f"unknown progress step: {step.__class__.__name__}")


def initialize_tool_progress(progress_path: Path, paths: dict[str, Path]) -> None:
    started_at = timestamp()
    progress = read_progress_document(progress_path)
    progress["schema_version"] = progress.get("schema_version") or "freecad_progress/1.0"
    progress["workflow"] = "simulation"
    progress["command"] = "sim run"
    progress["stage"] = "simulation"
    progress["status"] = "running"
    progress["overall_percent"] = 0.0
    progress.setdefault("error", None)
    progress["paths"] = {
        **dict(progress.get("paths") or {}),
        "workspace_dir": str(paths["workspace_dir"]),
        "input_dir": str(paths["input_dir"]),
        "cad_dir": str(paths["cad_dir"]),
        "output_dir": str(paths["output_dir"]),
    }
    progress.setdefault("started_at", started_at)
    progress["current_run_started_at"] = started_at
    progress["finished_at"] = None
    progress["updated_at"] = started_at
    progress["steps"] = merge_progress_steps(progress.get("steps", []), reset=True)
    write_json(progress_path, progress)


def merge_progress_steps(existing_steps: Any, *, reset: bool) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    if isinstance(existing_steps, list):
        for step in existing_steps:
            if isinstance(step, dict) and step.get("command_name"):
                by_name[str(step["command_name"])] = dict(step)

    merged: list[dict[str, Any]] = []
    known_names = {command_name for command_name, _stage_name in PROGRESS_STEPS}
    for index, (command_name, stage_name) in enumerate(PROGRESS_STEPS, start=1):
        step = by_name.get(command_name, {})
        step.update(
            {
                "command_name": command_name,
                "stage_name": stage_name,
                "index": index,
                "weight_percent": round(100.0 / len(PROGRESS_STEPS), 4),
            }
        )
        if reset:
            step["status"] = "pending"
            step["percent"] = 0.0
            step["started_at"] = None
            step["finished_at"] = None
        else:
            step.setdefault("status", "pending")
            step.setdefault("percent", 0.0)
            step.setdefault("started_at", None)
            step.setdefault("finished_at", None)
        merged.append(step)

    for command_name, step in by_name.items():
        if command_name not in known_names:
            merged.append(step)
    return merged


def update_tool_progress(
    progress_path: Path,
    command_name: str,
    *,
    status: str,
    percent: float,
    stage: dict[str, Any] | None = None,
) -> None:
    progress = read_progress_document(progress_path)
    progress["steps"] = merge_progress_steps(progress.get("steps", []), reset=False)
    now = timestamp()
    found = False
    for step in progress.get("steps", []):
        if step.get("command_name") != command_name:
            continue
        found = True
        step["status"] = status
        step["percent"] = max(float(step.get("percent") or 0.0), percent) if status == "running" else percent
        step["started_at"] = step.get("started_at") or now
        if status in {"completed", "failed", "blocked"}:
            step["finished_at"] = now
        if stage is not None:
            step["stage_status"] = stage.get("status")
            if stage.get("errors"):
                step["errors"] = stage.get("errors")
            if stage.get("warnings"):
                step["warnings"] = stage.get("warnings")
        break
    if not found:
        progress["steps"].append(
            {
                "command_name": command_name,
                "stage_name": command_name,
                "status": status,
                "percent": percent,
                "started_at": now,
                "finished_at": now if status in {"completed", "failed", "blocked"} else None,
            }
        )
    progress["stage"] = command_name
    progress["status"] = "running" if status == "running" else progress.get("status", "running")
    progress["updated_at"] = now
    progress["overall_percent"] = overall_tool_percent(progress)
    if status == "failed" and stage is not None:
        progress["error"] = stage.get("errors") or stage.get("warnings") or "stage failed"
    progress["updated_at"] = now
    write_json(progress_path, progress)


def finalize_tool_progress(progress_path: Path, *, ok: bool) -> None:
    progress = read_progress_document(progress_path)
    now = timestamp()
    progress["status"] = "success" if ok else "failed"
    progress["stage"] = "completed" if ok else str(progress.get("stage") or "failed")
    progress["finished_at"] = now
    progress["updated_at"] = now
    progress["overall_percent"] = overall_tool_percent(progress)
    if ok:
        progress["error"] = None
        progress["last_success_at"] = now
    else:
        progress["last_failed_at"] = now
    progress["updated_at"] = now
    write_json(progress_path, progress)


def read_progress_document(progress_path: Path) -> dict[str, Any]:
    if not progress_path.exists():
        return {
            "schema_version": "freecad_progress/1.0",
            "workflow": "simulation",
            "command": "sim run",
            "stage": "simulation",
            "status": "running",
            "overall_percent": 0.0,
            "error": None,
            "steps": [],
        }
    try:
        existing = read_json(progress_path)
    except Exception:
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing.setdefault("schema_version", "freecad_progress/1.0")
    existing.setdefault("workflow", "simulation")
    existing.setdefault("command", "sim run")
    existing.setdefault("error", None)
    existing.setdefault("steps", [])
    return existing


def overall_tool_percent(tool: dict[str, Any]) -> float:
    total = 0.0
    for step in tool.get("steps", []):
        total += (float(step.get("percent") or 0.0) / 100.0) * float(step.get("weight_percent") or 0.0)
    return round(total, 2)


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def prepare_contract_workspace(
    ctx: BomExternalToolsPipelineContext,
    paths: dict[str, Path],
    sample_id: str,
    seed: int,
) -> None:
    ctx.paths["run_root"].mkdir(parents=True, exist_ok=True)
    ensure_components(paths["input_dir"], ctx.paths["run_root"] / "components.json")
    ensure_sample_yaml(paths["cad_dir"], paths["input_dir"], ctx.paths["run_root"] / "sample.yaml", sample_id, seed)

    layout_result = {
        "ok": True,
        "bom": str(paths["input_dir"] / "real_bom.json"),
        "run_dir": str(ctx.paths["run_root"]),
        "layout_dir": str(paths["input_dir"]),
        "component_info_dir": None,
        "stats": {"n_unplaced": 0},
    }
    geometry_result = {
        "ok": True,
        "run_dir": str(ctx.paths["run_root"]),
        "geometry_edit_dir": str(paths["cad_dir"]),
        "planner_execution_ok": True,
        "covered_missing_count": 0,
        "unresolved_missing_count": 0,
        "relayout_success": None,
        "relayout_n_unplaced": None,
        "cad_rebuilt": False,
        "step_copied_from_source": str(paths["cad_dir"] / "geometry_after.step"),
        "warnings": ["geometry_validate satisfied from existing 01_cad"],
        "errors": [],
    }
    layout_stage = layout_stage_result(layout_result)
    geometry_stage = case_stage("geometry_validate", geometry_result)
    ctx.layout_result = layout_result
    ctx.geometry_result = geometry_result
    ctx.write_stage_log("layout_generate_raw_result.json", layout_result)
    ctx.write_stage_log("layout_generate_stage_result.json", layout_stage)
    ctx.write_stage_log("geometry_validate_raw_result.json", geometry_result)
    ctx.write_stage_log("geometry_validate_stage_result.json", geometry_stage)
    ctx.append_stage(layout_stage)
    ctx.append_stage(geometry_stage)
    ctx.write_manifest()


def bind_source_paths(ctx: BomExternalToolsPipelineContext, paths: dict[str, Path]) -> None:
    ctx.paths["inputs"] = paths["input_dir"]
    ctx.paths["layout"] = paths["input_dir"]
    ctx.paths["geometry_edit"] = paths["cad_dir"]
    ctx.paths["logs"] = paths["workspace_dir"] / "logs"


def ensure_components(input_dir: Path, components_path: Path) -> None:
    bom = read_json(input_dir / "real_bom.json")
    components = normalize_bom_to_components(bom, source_file="real_bom.json")
    write_json(components_path, components)


def ensure_sample_yaml(geometry_dir: Path, input_dir: Path, sample_yaml: Path, sample_id: str, seed: int) -> None:
    simulation_input = read_json(geometry_dir / "simulation_input.json")
    geom = read_json(input_dir / "geom.json")
    sample_yaml.write_text(to_yaml(sample_document(sample_id, seed, simulation_input, geom)), encoding="utf-8")


def sample_document(sample_id: str, seed: int, simulation_input: dict[str, Any], geom: dict[str, Any]) -> dict[str, Any]:
    components = {}
    for component in simulation_input.get("components", []):
        component_id = component["component_id"]
        components[component_id] = {
            "bbox": component["bbox"],
            "power": component.get("power_W", 0.0),
            "category": component.get("category", ""),
            "kind": component.get("kind", ""),
            "mount_face_id": component.get("mount_face_id"),
            "thermal_interface": {"contact_resistance": component.get("contact_resistance")},
        }
    outer_shell = geom.get("outer_shell", {})
    return {
        "schema_version": "2.0",
        "units": {"length": "mm", "mass": "kg", "power": "W", "temperature": "K"},
        "sample_id": sample_id,
        "seed": seed,
        "outer_shell": outer_shell,
        "components": components,
        "install_faces": geom.get("install_faces", {}),
        "cabin_walls": geom.get("cabin_walls", []),
        "cabins": cabins_with_inner_bbox(geom.get("cabins", []), outer_shell),
    }


def cabins_with_inner_bbox(cabins: Any, outer_shell: dict[str, Any]) -> list[dict[str, Any]]:
    inner_bbox = outer_shell.get("inner_bbox")
    result: list[dict[str, Any]] = []
    for cabin in cabins if isinstance(cabins, list) else []:
        if not isinstance(cabin, dict):
            continue
        item = dict(cabin)
        if "inner_bbox" not in item and inner_bbox is not None:
            item["inner_bbox"] = inner_bbox
        result.append(item)
    return result


def to_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{yaml_scalar(value)}")
    return "\n".join(lines) + ("\n" if indent == 0 else "")


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
    else:
        print("ok" if payload.get("ok") else "failed")
        if payload.get("run_root"):
            print(f"run_root: {payload['run_root']}")


if __name__ == "__main__":
    raise SystemExit(main())
