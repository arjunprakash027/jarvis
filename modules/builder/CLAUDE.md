# Builder Module

This module builds something new from a spoken request, most often a new Jarvis module in `modules/<name>/`. It is a long-task module: one session writes the plan, then runs it.

## Rules

- The harness starts this session in `modules/builder/`. The repository root is `../..`; run repo commands with `cd ../..`. Paths below that start with `modules/` are relative to that root, not this session directory. Use the absolute task paths supplied by the harness (`spec.md`, `dag.json`, `log.md`); never pick a second task id. Code goes in the target folder (for a new module, `modules/<name>/`). Never write code in `tasks/`.
- Follow the skill `skills/build-module/SKILL.md` for every build. It holds the planner step, the executor step, the ClickUp steps and the module checklist.
- `module.toml` requires the gate `approve-plan`. The DAG must contain a `gate` node with that id. Do not skip it.
- Commit on the current branch only. Never push. Never run `gh`.
- Never put a secret, a token, card data or a personal document in a file you write.

## Folder

- `module.toml`: router description, model, long-task size and the required gate.
- `skills/build-module/SKILL.md`: how to plan, build, test and track a build.
- `skills/build-module/examples/`: a sample `spec.md` and `dag.json` for the request "build me a module that cleans my Mac's disk space".
- `extensions/`: no builder extension.
- `tasks/<id>/`: runtime files for each build. Not in git.
