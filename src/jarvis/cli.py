"""Command-line interface for Jarvis."""

import argparse
import os
from pathlib import Path
import sys
from typing import Sequence

from jarvis.modules import DEFAULT_MODULES_DIR, ModuleConfigError, load_modules


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser for the jarvis CLI."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Local voice-driven task automation engine on macOS.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    modules_parser = subparsers.add_parser(
        "modules",
        help="List each module folder in modules/ with name and description.",
    )
    modules_parser.add_argument(
        "--modules-dir",
        type=Path,
        default=None,
        help="Override the modules directory path.",
    )
    up_parser = subparsers.add_parser("up", help="Listen, route and run module tasks.")
    up_parser.add_argument("--text", action="store_true", help="Read typed lines instead of the microphone.")
    up_parser.add_argument("--modules-dir", type=Path, default=None)
    dag_parser = subparsers.add_parser("dag", help="Check a task DAG.")
    dag_commands = dag_parser.add_subparsers(dest="dag_command", required=True)
    check_parser = dag_commands.add_parser("check", help="Validate dag.json.")
    check_parser.add_argument("path", type=Path)
    return parser


def _resolve_modules_dir(cli_dir: Path | None) -> Path:
    """Resolve the modules directory from CLI flag, environment variable, or default."""
    if cli_dir is not None:
        return cli_dir
    env_dir = os.environ.get("JARVIS_MODULES_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_MODULES_DIR


def cmd_modules(modules_dir: Path) -> int:
    """Print each discovered module's name and description."""
    try:
        modules = load_modules(modules_dir)
    except ModuleConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for mod in modules:
        print(f"{mod.name}: {mod.description}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the jarvis console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "modules":
        return cmd_modules(_resolve_modules_dir(args.modules_dir))

    if args.command == "dag":
        import json
        from jarvis.dag import check_dag

        try:
            errors = check_dag(json.loads(args.path.read_text()))
        except (OSError, ValueError) as exc:
            errors = [str(exc)]
        print("\n".join(errors) if errors else "OK")
        return 1 if errors else 0

    if args.command == "up":
        from jarvis.main import up

        try:
            return up(_resolve_modules_dir(args.modules_dir), text=args.text)
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
