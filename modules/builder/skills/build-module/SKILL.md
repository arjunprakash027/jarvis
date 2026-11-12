---
name: build-module
description: Build a new Jarvis module (or another small tool) from a spoken request. Plan in spec.md and dag.json, run the nodes one after the other, test the result, and track the work in ClickUp.
---

# build-module

You are the builder session. You build in two steps inside this one session: the planner step, then the executor step. This is a short form of Keel.

Read first: `modules/_base/CLAUDE.md`, `docs/module-contract.md`, `docs/dag-format.md`, `modules/_example/`, and the sample in `skills/build-module/examples/`.

## Destination and use

If the request does not say where the module goes, ask: “Where should I put it? Default: `modules/<name>/` in this repository.” Return planning `ok: false` with that question instead of inventing an answer or writing code. The next request can confirm the default. Never silently choose an external project or overwrite an existing module. If the request already gives its target, use it after checking the folder belongs to this repo and is safe to change.

The caller runs `uv run jarvis up --text` (or voice `uv run jarvis up`) at the repo root, requests the build, approves the plan, and then requests the new module by its description. Jarvis reloads modules before routing each new request; no restart is needed on the current harness. Each new module gets one named session `jarvis-<name>`; never start that session yourself. To inspect the result, use `uv run jarvis modules` and `uv run jarvis dag check modules/<name>/tasks/<id>/dag.json`.

## Complete module recipe

All of this belongs in the generated module; global skills are disabled by the harness. Never assume another session’s skills are present. If a tool is needed, document exact CLI commands locally in its skill; for a browser use only ego CLI and include navigation, inspection and confirmation instructions without machine-specific paths or secrets. Missing tools/permissions are reported, never bypassed.

```text
modules/<name>/
  module.toml
  CLAUDE.md
  skills/<skill-name>/SKILL.md
  extensions/.gitkeep
  tasks/<id>/dag.json     # runtime only, ignored
  tasks/<id>/log.md       # runtime only, ignored
  tasks/<id>/spec.md      # long tasks only, ignored
```

Use exactly these eight settings (replace the name and description):

```toml
name = "my-module"
description = "One clear task this module performs"
agent = "pi"
model = "antigravity/gemini-4-argon"
directory = "modules/my-module"
task_size = "short"
required_gates = ["confirm"]
mcp_servers = []
```

Use `long` for a build needing a spec. The description is the router’s interface: distinguish the new task from building a new tool. MCP names do not magically configure a missing integration. CLAUDE.md explains the module, safe boundaries and file map; SKILL.md has YAML `name`/`description` and the complete commands, planning/execution procedure, tests and undo. Extensions are optional `.ts`/`.js` files; prefer a small skill over new code unless needed.

A task DAG is a JSON object with nonempty `task` and `nodes`. Each node needs unique `id`, `type` (`step`, `test`, `gate`), nonempty `do`, and `needs` (ids, `[]` at the start). `needs` must reference existing nodes and be acyclic. Put all prerequisites before dependents. At least one test is mandatory. Optional `on_fail` belongs only to a test and points to an earlier ancestor. Every configured required gate must be a gate node **and a dependency of the action it protects**; merely listing it is not sufficient protection. Gate text identifies the task and exact proposed action. The engine pauses, shows/speaks it and waits; never ask the session to approve itself.

Use small DAGs: inspect -> show -> confirm gate -> action with undo -> test. Write plans before execution. Freeze the action scope before confirmation. `undo` on a mutating step must reverse only that step’s own changes from a recorded baseline, never unrelated files. Failed tests trigger reverse-order undo and return to `on_fail`; repeated failures ask retry/skip/stop. A failed step gets one retry before recovery. If undo cannot finish safely, report the conflict and stop, not another destructive pass. A no at a gate stops; do not treat it as approval. Verify repeated attempts cannot duplicate external changes.

Test the exact generated instructions, not a substitute: module loader and exact TOML keys; real `check_dag` including missing-gate/missing-test rejection; real read-only inspection; isolated fixture mutation/undo; declined gate leaves user data untouched. A source review is not an execution test. Keep logs/inventories ignored and commit only intended code/docs. One task uses the harness-supplied task id and one existing session; the engine handles queuing and native compaction. Never launch helpers or subagents.

Every result starts with the key fact in ten words or fewer. Spoken text is at most 18 words; put details in the ignored task log and normal terminal output. No secrets, tokens, personal documents, inventories, payment data, or machine-specific home paths in committed files. Prefer the smallest useful module, no feature flags, no speculative abstractions. Never push.

## 1. Planner step

Run it when the request arrives. The engine has not started yet.

1. Use the task id and absolute task folder from the harness prompt. The folder is `modules/builder/tasks/<id>/` under the repo root (`../..` from this session). Do not invent a second task folder. All `modules/` paths below are repo-relative. Run `uv` and `git` commands at that repo root.
2. Write `tasks/<id>/spec.md`. Keep it short:
   - Goal in one sentence, and the target folder (for a new module, `modules/<name>/`).
   - Files to create and what each one does.
   - What the thing does when it runs, which gates it needs, and how deletion or any other change is reversed.
   - How to test it.
3. Write `tasks/<id>/dag.json` in the DAG contract of the base. Use these nodes, in this order:
   - `clickup-open` (step): find or create the ClickUp task, see section 3. `undo`: comment that the build was rolled back and remove the `in-progress` tag.
   - `approve-plan` (gate, required): asks Arjun to approve the spec before any code is written. `needs` `clickup-open`.
   - one or more build steps (`scaffold`, `skill`, and so on). Each step that creates files has an `undo` that moves them to the Trash with `trash`.
   - one or more `test` nodes, each with `on_fail` pointing to the build step that caused the failure. A test runs the thing for real.
   - `commit` (step): commit the target folder on the current branch. Never push.
   - `clickup-close` (step): comment the result on the ClickUp task and mark it complete, see section 3.
4. Check the DAG with the real function. Fix the file until the list of problems is empty:
   ```
   uv run python -c "import json,sys; from jarvis.dag import check_dag; print(check_dag(json.load(open(sys.argv[1])), ['approve-plan']))" modules/builder/tasks/<id>/dag.json
   ```
5. Write the first line of `tasks/<id>/log.md`: `planner: spec.md and dag.json written, check_dag passed`.

Stop after the planner step. The engine runs the nodes next.

## 2. Executor step

The engine sends you one node instruction at a time, in DAG order. For each instruction:

- Do exactly that node. Write code only in the target folder. Never write code in `tasks/`.
- Append to `tasks/<id>/log.md`: the node id, the attempt number, `ok` or `failed`, and one line on what happened (the command run, the file written, the error).
- A `test` node runs the thing for real and answers failed if the result is wrong. Do not weaken a test to make it pass.
- macOS normally protects some folders. When a scan cannot read a folder because of permissions, skip it and list that folder as `skipped: no permission` in what it shows Arjun. The scan test passes if every readable folder was scanned and each skipped folder is listed. Encode this in the spec, DAG test instructions, and generated skill; do not require full cache access. All other tests remain mandatory, including the real Trash/restore fixture test, Trash-only mutation and the gate before any user-file move.
- An `undo` instruction reverses its step. Use `trash`, never `rm`.
- Do not skip, simulate or answer a gate. The engine owns each gate.
- Reply with `ok` or `failed` and one line of detail. End each reply with the node id.

## 3. ClickUp (the `clickup` CLI)

The build gets one ClickUp task. The list is `Jarvis Relay` (id `901617700405`, in the `Projects` folder). Use the CLI only. Do not print or write a token. If `clickup auth status` says you are not logged in, answer `failed` with that text. Do not look for a token.

1. Search first, so you never create a duplicate:
   ```
   clickup task search "<module name>" --json
   ```
   Reuse a task whose name starts with `Jarvis build:` and names the same module.
2. If there is none, create it:
   ```
   clickup task create --list-id 901617700405 --name "Jarvis build: <module name>" --markdown-description "<the request, the target folder, the task id>" --json
   ```
3. Mark it in progress and note the plan:
   ```
   clickup task edit <task-id> --add-tags in-progress
   clickup comment add <task-id> "Plan: modules/builder/tasks/<id>/spec.md. Target: modules/<name>/."
   ```
4. Write the ClickUp task id and its link in `log.md`.
5. At the end (`clickup-close`), comment the result (files built, test results, commit hash) and close it:
   ```
   clickup comment add <task-id> "Built and tested. Commit <hash>. Log: modules/builder/tasks/<id>/log.md"
   clickup task edit <task-id> --status complete --remove-tags in-progress
   ```
   Statuses are `to do` and `complete` only. A blocked build gets the tag `blocked` and a comment.

## 4. Module checklist (when the target is a new module)

- `modules/<name>/module.toml` has exactly these 8 keys: `name`, `description`, `agent`, `model`, `directory`, `task_size`, `required_gates`, `mcp_servers`. `agent = "pi"`. Set `directory = "modules/<name>"` relative to the repo root; the harness requires it to resolve to the new module folder. Use `model = "antigravity/gemini-4-argon"` unless the spec says otherwise. Never an Anthropic-billed Claude Code model. `description` is one plain line that the router reads.
- `modules/<name>/CLAUDE.md`: what the module is and what is in the folder.
- `modules/<name>/skills/<skill-name>/SKILL.md`: how to do the task, with front matter `name` and `description`.
- `modules/<name>/extensions/`: keep it, with a `.gitkeep` if empty.
- Any module that deletes or changes user files lists a gate in `required_gates`, and its skill tells the session to write that gate into every DAG. Deletion moves files to the Trash with `trash`. Never `rm`. Freeze the exact candidate paths before the gate; show names, sizes, and the total. Do not follow symlinks, empty Trash, delete live app caches, or include new paths after approval. Trash does not free disk blocks until emptied: report moved bytes separately from free space. Never promise immediate reclaimed space.
- For clean-space, ship a read-only scan and a real Trash/restore test using only unique throwaway fixtures, not user Downloads or live caches. The actual cleanup run must still ask its own gate. Keep scan inventories in the ignored task folder; never commit local filenames. Treat size/permission errors as partial coverage, not zero bytes.
- Check that the module loads: `uv run jarvis modules` lists it.
- Commit with `git add modules/<name> && git commit -m "feat(<name>): <one line>"`. Never push.

## 5. Mac facts found while exploring (clean-space)

- `~/.Trash` cannot be read from a terminal (`Operation not permitted`). Count and size come from Finder: `osascript -e 'tell application "Finder" to get count of items of trash'` and `osascript -e 'tell application "Finder" to get physical size of every item of trash'` (sum the numbers, ignore `missing value`, say that the size is at least that).
- `/usr/bin/trash FILE...` moves files to the Trash. Use it, never `rm`.
- To restore a trashed item, move it back with Finder (`put away` does not work): `osascript -e 'tell application "Finder" to move (every item of trash whose name is "NAME") to (POSIX file "ORIGINAL_FOLDER" as alias)'`. Write the original folder of each trashed item in the run log, because the Trash cannot be read from a terminal.
- `du -sk ~/Library/Caches/<app>` works for each cache folder. `find ~/Downloads -maxdepth 1 -mtime +N` lists the top-level items older than N days.

## 6. The standard module path

Every module gets `modules/_base/extensions/module-path.ts` from the base. The harness loads it before the module's own extensions, so a new module must not copy it or add its own version. It checks each write in `tasks/<id>/`: `dag.json` runs `jarvis dag check`; `nodes/<x>.json` needs `ok` (bool) and `output` (string, first sentence 10 words or less). If the session ends a node without its result file, it is told once to write it. `/where` in the module session shows the module, task folder, `dag.json`, each node with its status, and `log.md`.
