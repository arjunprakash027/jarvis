# sys-widget

Taskbar and tooltip widget displaying consumed RAM and SSD space on macOS. Inherit all rules in `modules/_base/CLAUDE.md`. Use the single configured session; the engine owns all gates.

## Folder map
- `module.toml`: module contract with 8 keys, agent pi, model antigravity/gemini-3-8-flash:high, required_gates = [].
- `CLAUDE.md`: module instructions and folder map.
- `skills/sys-widget/SKILL.md`: procedures for reading RAM and SSD usage, running the widget, and writing task DAGs.
- `scripts/`: widget scripts (`widget.sh`) to query and format memory and disk metrics.
- `extensions/`: reserved extension folder with `.gitkeep`.
- `tasks/<id>/`: ignored runtime DAGs, execution logs, and node results.

## Safety contract
- Read-only inspection: queries memory via `vm_stat` / `sysctl` and SSD via `df -h /`.
- Never modify system configuration, terminate processes, or mutate disk partitions.
- Write and validate a runtime DAG before execution (`query` -> `format` -> `verify`).
- Report RAM and SSD usage accurately with units (GB, %) and total machine capacity.
