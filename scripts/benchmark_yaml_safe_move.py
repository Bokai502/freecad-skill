from __future__ import annotations

import argparse
import statistics
import subprocess
import time
from pathlib import Path


def run_once(command: list[str], cwd: Path) -> float:
    start = time.perf_counter()
    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark freecad-yaml-safe-move wall-clock time."
    )
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs.")
    parser.add_argument(
        "--cwd",
        default=str(Path(__file__).resolve().parents[1]),
        help="Workspace root.",
    )
    parser.add_argument(
        "--input", default="examples/sample.yaml", help="Input YAML path."
    )
    parser.add_argument(
        "--output", default="data/benchmark.safe-move.yaml", help="Output YAML path."
    )
    parser.add_argument("--component", default="P005", help="Target component id.")
    parser.add_argument("--install-face", type=int, default=5, help="Envelope face id.")
    parser.add_argument(
        "--move",
        nargs=3,
        default=("228.83671815191935", "195.70657882164386", "0"),
        help="Move vector.",
    )
    parser.add_argument(
        "--sync-cad",
        action="store_true",
        help="Include CAD sync in the benchmark command.",
    )
    parser.add_argument(
        "--doc-name",
        default="CompareSingleUnit",
        help="FreeCAD document name when --sync-cad is used.",
    )
    args = parser.parse_args()

    workspace = Path(args.cwd).resolve()
    command = [
        "freecad-yaml-safe-move",
        "--input",
        args.input,
        "--output",
        args.output,
        "--component",
        args.component,
        "--install-face",
        str(args.install_face),
        "--move",
        *args.move,
    ]
    if args.sync_cad:
        command.extend(["--sync-cad", "--doc-name", args.doc_name])

    samples = [run_once(command, workspace) for _ in range(args.runs)]
    print("runs:", args.runs)
    print("samples:", ", ".join(f"{sample:.4f}s" for sample in samples))
    print("min:", f"{min(samples):.4f}s")
    print("mean:", f"{statistics.mean(samples):.4f}s")
    print("max:", f"{max(samples):.4f}s")


if __name__ == "__main__":
    main()
