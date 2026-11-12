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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
