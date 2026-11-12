# Jarvis Module Base Rules

Every Jarvis module session loads this file first and must follow all four base rules. A module cannot disable any rule in this file.

## 1. Gate Rule
- The task engine owns every gate. An agent session never skips, auto-approves, or simulates a gate.
- Every gate listed in `required_gates` in `module.toml` must appear as a `gate` node in the task DAG.
- At a `gate` node, the engine pauses the run, opens a macOS dialog and speaks the question, and resumes only when the human answers.

## 2. DAG Contract
- For every task `<id>`, write the plan to `tasks/<id>/dag.json` inside the module folder before executing steps.
- Keep all task state and logs (`dag.json`, `log.md`, and `spec.md` for long tasks) inside `tasks/<id>/`.
- `dag.json` must match this structure:

```json
{
  "task": "Add milk, eggs and bread to my Tesco basket",
  "nodes": [
    {"id": "search", "type": "step", "do": "Find each item", "needs": []},
    {"id": "basket", "type": "step", "do": "Add the items to the basket", "needs": ["search"],
     "undo": "Remove the items from the basket"},
    {"id": "verify", "type": "test", "do": "Confirm the basket holds the 3 items", "needs": ["basket"],
     "on_fail": "search"},
    {"id": "pay", "type": "gate", "do": "Ask: Tesco basket, total is X. Do I pay?", "needs": ["verify"]}
  ]
}
```

- Valid node `type` values: `step`, `test`, `gate`.
- Every node requires `id`, `type`, `do`, and `needs`.
- `needs` links must reference existing nodes, go forward only, and pass a topological sort with no cycles.
- `on_fail` links are allowed only on `test` nodes and must point to an earlier node in the DAG.

## 3. Test-Node Rule
- Every DAG must contain at least one `test` node. A DAG without a `test` node is rejected by `jarvis dag check`.
- If a `test` node fails, the engine runs the `undo` instruction of each step along the reversal path and returns the run to the node named in `on_fail`.

## 4. One Session and Compaction Step
- Each module uses its single predefined interactive `pi` session in `herdr` as configured in `module.toml` (`agent`, `model`, `directory`). Never spawn a second session.
- For `short` tasks, write `tasks/<id>/dag.json` and execute each node as the engine dispatches it.
- For `long` tasks, first write `tasks/<id>/spec.md` and `tasks/<id>/dag.json`, then execute each node in order and record attempts in `tasks/<id>/log.md`.
- When a run ends, Jarvis compacts the context of the module's session so short memory carries forward without context bloat.

## 5. Cleanup
- Put temporary files (scratch, screenshots, scans) in `tasks/<id>/tmp/`. When a run ends, the engine writes `tasks/<id>/result.md` and deletes `tmp/` and `nodes/`.
- The last node closes anything opened outside the task folder: the browser task space, temp files elsewhere.
- To keep an extra file, list it in `"keep": ["relative/path"]` in `dag.json` (relative to the task folder, no `..`). `dag.json`, `spec.md`, `log.md`, `result.md` and built code in its target folder always stay.

## Keep it short

Jarvis speaks only the first 18 words of a result or a gate question. Start every result with the key fact in 10 words or less, for example "Basket total EUR 9.35, 3 items." Put detail after it.

## Stay focused

- Start from this module's folder: its CLAUDE.md, skills, extensions and `tasks/`. The DAG rules are above.
- Read other code (the Jarvis source, tests, docs, git history, other projects) only when the task needs it, for example when the builder builds a module or the task is about that code. Do not read it just to learn how Jarvis works.
- Plan only what the request asks. A question ("what does X cost?") is a read-only task: do not change anything.
