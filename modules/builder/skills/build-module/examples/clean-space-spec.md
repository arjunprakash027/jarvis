# Spec: clean-space module

Request: "build me a module that cleans my Mac's disk space".

## Goal

A Jarvis module `clean-space` that finds disk space Arjun can free, shows it, asks at a gate, and moves the chosen files to the Trash. Nothing is deleted with `rm`, so Arjun can reverse it.

## Target folder

`modules/clean-space/`. No code in `modules/builder/tasks/`.

## Files

| File | What it does |
| --- | --- |
| `module.toml` | Name, one-line router description, `agent = "pi"`, model `antigravity/claude-sonnet-5-5`, `directory = "."`, `task_size = "short"`, `required_gates = ["confirm-trash"]`, `mcp_servers = []`. |
| `CLAUDE.md` | What the module is, the Trash-only rule, the folder map. |
| `skills/clean-space/SKILL.md` | How to scan, how to write the DAG, how to trash. |
| `extensions/.gitkeep` | Keeps the folder. |

## What a run does

1. Scan (read only):
   - Caches: size of each folder in `~/Library/Caches` (`du -sk`), largest 10.
   - Downloads: top-level items in `~/Downloads` older than N days (default 30; the request may give N), with sizes.
   - Trash: item count and size from Finder (`osascript`), because `~/.Trash` cannot be read from a terminal.
2. Show: print one table with the three groups, the size of each item and the total that can be freed.
3. Gate `confirm-trash`: "clean-space: X GB in caches, Y GB in old Downloads. Move them to the Trash?" Yes continues. No ends the run and nothing moves.
4. Trash: `trash` each approved item. Never `rm`. Never touch the Trash itself. Never empty it.
5. Test: each trashed item is gone from its folder, and the free space did not shrink. The reply says how many items moved and that they are in the Trash and can be restored.

## DAG for each run (the skill tells the session to write it)

`scan` (step) -> `show` (step) -> `confirm-trash` (gate) -> `trash` (step, `undo`: move the items back with Finder) -> `verify` (test, `on_fail`: `scan`).

## Gates

`confirm-trash`, required in `module.toml`.

## Reversal

The `undo` of the `trash` step moves each item back to its original folder with Finder (`move ... of trash to <folder>`). The `trash` step writes the original folder of each item in the run log, because the Trash cannot be read from a terminal.

## Tests for this build

1. `uv run jarvis modules` lists `clean-space` and `load_module` accepts it.
2. The sample DAG in the module skill passes `check_dag` with the required gate `confirm-trash`.
3. A throwaway file under `/tmp` is moved with the module's trash command: the file is gone from `/tmp` and Finder lists it in the Trash. Then restore it with the module's undo command and confirm it is back in `/tmp`. Remove the throwaway file with `trash` at the end.
4. The scan prints the three groups and writes nothing.

## ClickUp

One task `Jarvis build: clean-space` in the list `Jarvis Relay`. Search first. Tag `in-progress` while building. Comment the plan and the result. Mark `complete` at the end.
