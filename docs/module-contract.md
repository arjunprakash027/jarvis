# Module Contract

Each Jarvis module is one folder inside `modules/`. Folders starting with `_` (such as `_base` and `_example`) are internal templates and are skipped by `jarvis modules`.

## Folder Layout

```
modules/<name>/
  module.toml    Module settings for the router, engine, and session harness.
  CLAUDE.md      Optional module notes loaded after modules/_base/CLAUDE.md.
  skills/        Skills loaded only into this module's pi session.
  extensions/    pi extensions loaded only into this module's pi session.
  tasks/<id>/    Runtime task files (dag.json, log.md, spec.md). Kept out of git.
```

## `module.toml` Fields

Every `module.toml` defines eight keys:

- `name`: Short module identifier.
- `description`: Plain description read by the router.
- `agent`: Agent harness for the module's single session.
- `model`: Model identifier for the module's single session.
- `directory`: Working directory for the module's session.
- `task_size`: `"short"` or `"long"`.
- `required_gates`: List of gate names that every task DAG for this module must contain.
- `mcp_servers`: List of MCP server names enabled for this module.

## Mandatory Base Rules

Every module extends `ModuleBase` from `src/jarvis/modules.py` and loads `modules/_base/CLAUDE.md`. The base gives every module four fixed parts:

1. **Gate rule (`gate_rule`)**: The engine owns every gate. The agent cannot skip a gate, and all `required_gates` must appear in the DAG.
2. **DAG contract (`dag_contract`)**: Every task writes `tasks/<id>/dag.json` with `step`, `test`, and `gate` nodes, forward `needs` links, and backward `on_fail` links only on `test` nodes.
3. **Test-node rule (`test_node_rule`)**: Every task DAG must contain at least one `test` node.
4. **Compaction step (`compaction_step`)**: When a task run finishes, Jarvis compacts the context of the module's single `pi` session.

A module cannot turn off or override any of these four base parts in `module.toml`. Any key that tries to disable a base part is refused by `load_module()`.

## Standard Module Path

- `modules/_base/extensions/module-path.ts` is loaded into every module session before the module's own extensions. A module must not copy or skip it.
- It checks each write in `tasks/<id>/` (`dag.json` with `jarvis dag check`, `nodes/<x>.json` for `ok`, `output` and a short first sentence), and tells the session once to write a missing node result file.
- `/where` shows the module, task folder, `dag.json`, each node with its status (done, failed, waiting) and `log.md`.
