# Jarvis

Jarvis is a local voice-driven task automation engine on macOS that combines fixed task DAGs, an interactive `pi` coding session per module in `herdr`, and human gates for decisions. Spoken requests are transcribed locally with `whisper.cpp`, routed to a module by a TypeSafe judgment table, planned into a verified `dag.json` with mandatory `test` and `gate` nodes, walked step by step by the task engine, and compacted at the end of each run.

## File Map

| Path | What it does | Connects to |
| --- | --- | --- |
| `pyproject.toml` | Defines the `jarvis` Python package and `jarvis` console script. | `src/jarvis/cli.py` |
| `src/jarvis/__init__.py` | Exports the module base and module loader API. | `src/jarvis/modules.py` |
| `src/jarvis/cli.py` | Implements the `jarvis` CLI (`jarvis modules`). | `src/jarvis/modules.py` |
| `src/jarvis/modules.py` | Defines `ModuleBase`, `Module`, and the `modules/` folder loader. | `src/jarvis/cli.py`, `router.py`, `main.py` |
| `src/jarvis/voice.py` | Records push-to-talk audio, runs speech-to-text, and speaks replies. | `main.py`, `gate.py` |
| `src/jarvis/router.py`, `src/jarvis/router_questions.py` | Routes a spoken request to a module or asks one clarifying question. | `src/jarvis/modules.py`, `main.py` |
| `src/jarvis/dag.py` | Validates `dag.json` structure, topological order, gates, and test nodes. | `engine.py` |
| `src/jarvis/engine.py` | Walks the task DAG node by node per module and compacts the session at run end. | `dag.py`, `gate.py`, `harness.py` |
| `src/jarvis/gate.py` | Opens a macOS dialog, speaks the gate question, and returns the human answer. | `engine.py`, `voice.py` |
| `src/jarvis/harness.py` | Manages each module's single `pi` session in `herdr` (start, send, read, compact). | `engine.py`, `main.py` |
| `src/jarvis/main.py` | Runs `jarvis up`: listen, route, execute DAG, and report. | All `src/jarvis/` modules |
| `modules/_base/CLAUDE.md` | Base instructions and DAG rules loaded into every module session. | `src/jarvis/modules.py`, `harness.py` |
| `modules/_example/` | Reference module template (`module.toml`, `CLAUDE.md`, `skills/`, `extensions/`). | `src/jarvis/modules.py` |
| `docs/module-contract.md` | Documents the module folder structure, `module.toml` schema, and base rules. | `src/jarvis/modules.py`, `modules/_base/CLAUDE.md` |
| `tests/test_modules.py` | Tests module discovery, mandatory base inheritance, and rejection of base overrides. | `src/jarvis/modules.py`, `src/jarvis/cli.py` |
