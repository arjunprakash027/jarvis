# Example Module

This folder is the minimal reference template for a Jarvis module.

## Contents
- `module.toml`: module name, description, single session agent/model/directory, task size (`short` or `long`), required gates, and MCP servers.
- `CLAUDE.md`: module-specific instructions loaded after `modules/_base/CLAUDE.md`.
- `skills/`: module-specific skills loaded into the module's pi session.
- `extensions/`: module-specific pi extensions loaded into the module's pi session.
- `tasks/<id>/`: runtime folder for each task's `dag.json` and logs (ignored by git).
