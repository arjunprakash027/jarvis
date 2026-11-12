# Clean Space

Inspect Mac disk usage and safely move explicitly approved old top-level Downloads to Trash. Inherit all rules in `modules/_base/CLAUDE.md`. Use the single configured session; the engine owns all gates.

## Folder map
- `module.toml`: exact module contract and required `confirm-trash` gate.
- `skills/clean-space/SKILL.md`: inspection, approval, Trash verification and Finder restoration instructions.
- `extensions/`: reserved extension folder.
- `tasks/<id>/`: ignored runtime DAGs, inventories, errors, original locations and move journals. Never commit personal inventories or documents.

## Safety contract
- Write and validate a runtime DAG before execution: scan -> show -> confirm-trash (engine gate) -> trash (restore undo) -> verify (test, on_fail scan). Never answer, simulate or skip a gate.
- Read-only scan: caches informational only; eligible proposals are top-level Downloads older than 30 days by default. Report Finder Trash count and lower-bound size; never inspect Trash from the terminal.
- Never follow symlinks, mutate live caches, use rm or empty Trash. Unknown measurements are partial coverage, not zero. Scan every readable folder and explicitly list inaccessible folders as `skipped: no permission`.
- Freeze exact candidate paths, sizes and identities before approval; show names and total. Move only unchanged approved items. Any changes require rescan, presentation and fresh engine approval.
- Use `/usr/bin/trash` and journal each move/original location in ignored runtime files. Verify original disappearance and exact Finder Trash presence. Reconcile interrupted moves before retry.
- Restore only journaled items through Finder to original locations. Stop on ambiguous Trash identity or destination conflicts; never overwrite or restore unrelated items.
- Report moved bytes separately from measured free space. Moving files to Trash does not immediately reclaim disk blocks. This module never empties Trash.
- Build tests use actual commands on unique disposable fixtures in a dedicated temporary directory, never personal Downloads/live caches. Verify exact Trash identification, original-path restoration and unchanged contents; leave fixtures restored. No simulated approvals.
- Scan tests pass only when every readable folder is scanned and every permission skip explicitly reported. Protected cache folders alone do not fail an honestly partial scan; missing required tools, Finder permissions, unexplained errors, unreported omissions or fixture failures do fail. Never weaken other tests.
