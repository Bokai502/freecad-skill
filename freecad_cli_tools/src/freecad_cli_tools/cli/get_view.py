#!/usr/bin/env python3
"""Get screenshots of the active FreeCAD view from one or multiple angles."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from freecad_cli_tools import add_connection_args, get_connection
from freecad_cli_tools.cli_support import write_base64_file

ALL_VIEWS = ["Isometric", "Front", "Top", "Right", "Back", "Left", "Bottom"]


def capture_one(conn, view_name, output_path, width=None, height=None, focus=None):
    """Capture a single screenshot and save it."""
    screenshot = conn.get_active_screenshot(view_name, width, height, focus)
    if screenshot is None:
        return None
    return write_base64_file(screenshot, output_path)


def requested_views(args: argparse.Namespace) -> list[str]:
    """Resolve the list of requested view names from CLI arguments."""
    if args.all:
        return ALL_VIEWS
    if args.views:
        return args.views
    return [args.view_name]


def main() -> None:
    parser = argparse.ArgumentParser(description="Get screenshots of FreeCAD view")
    parser.add_argument("view_name", nargs="?", default="Isometric",
                        choices=ALL_VIEWS + ["Dimetric", "Trimetric"],
                        help="View angle (ignored when --all is used)")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Capture all standard views (Isometric, Front, Top, Right, Back, Left, Bottom)")
    parser.add_argument("--views", nargs="+",
                        choices=ALL_VIEWS + ["Dimetric", "Trimetric"],
                        help="Capture specific multiple views")
    parser.add_argument("--output-dir", "-d", default=None,
                        help="Output directory for screenshots (default: ./freecad_views/<timestamp>)")
    parser.add_argument("--output", "-o", default=None, help="Output PNG file (single view only)")
    parser.add_argument("--width", type=int, help="Screenshot width in pixels")
    parser.add_argument("--height", type=int, help="Screenshot height in pixels")
    parser.add_argument("--focus", help="Object name to focus on")
    add_connection_args(parser)
    args = parser.parse_args()

    conn = get_connection(args.host, args.port)
    views = requested_views(args)

    # Single view mode
    if len(views) == 1 and not args.all:
        output_path = Path(args.output or args.output_dir or "freecad_view.png")
        if output_path.is_dir():
            output_path = output_path / f"{views[0].lower()}.png"
        path = capture_one(conn, views[0], output_path, args.width, args.height, args.focus)
        if path is None:
            print("ERROR: Cannot get screenshot in current view.", file=sys.stderr)
            sys.exit(1)
        print(f"Screenshot saved to {path}")
        return

    # Multi-view mode
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else Path("freecad_views") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    failed = []
    for view in views:
        out_path = output_dir / f"{view.lower()}.png"
        path = capture_one(conn, view, out_path, args.width, args.height, args.focus)
        if path:
            saved.append({"view": view, "path": str(path)})
            print(f"  [{view}] saved to {path}")
        else:
            failed.append(view)
            print(f"  [{view}] FAILED", file=sys.stderr)

    # Write manifest for easy consumption
    manifest = {
        "timestamp": timestamp,
        "output_dir": str(output_dir),
        "images": saved,
        "failed": failed,
    }
    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)

    print(f"\n{len(saved)}/{len(views)} screenshots saved to {output_dir}/")
    if failed:
        print(f"Failed views: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
