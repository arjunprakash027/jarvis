---
name: jarvis-module
description: Add or change a Jarvis module, which is one folder in modules/ with a module.toml, instructions, skills and extensions. Use when the person wants Jarvis to do a new type of task, wants to change what a module does, or a module does not show in `jarvis modules`.
compatibility: Needs the Jarvis repository on disk and uv.
---

# Jarvis module

A module teaches Jarvis one type of task. It is one folder. No other code changes.

```
modules/<name>/
  module.toml    settings: the router, the engine and the session read this file
  CLAUDE.md      instructions for the session, loaded after modules/_base/CLAUDE.md
  skills/        skills for this module's session only
  extensions/    pi extensions (.ts or .js) for this module's session only
  tasks/<id>/    files for each run. git ignores this folder.
```

## Steps

1. Copy the template. Use a short name with lowercase letters, digits and hyphens. `jarvis-<name>` must be 32 characters or less.

   ```sh
   cp -R modules/_example modules/<name>
   ```

2. Edit `modules/<name>/module.toml`. All eight keys are necessary. No other key is permitted.

   | Key | Value |
   | --- | --- |
   | `name` | The folder name. |
   | `description` | One sentence that says what the module does. The router reads only this sentence, so name the tasks and the sites. |
   | `agent` | `"pi"`. |
   | `model` | A `provider/model` that the person's `pi` can use. |
   | `directory` | `"modules/<name>"`. |
   | `task_size` | `"short"`, or `"long"` if a task first needs a written spec. |
   | `required_gates` | The gate ids that each plan must contain, for example `["pay"]`. Use `[]` for none. |
   | `mcp_servers` | The MCP server names for this module. Use `[]` for none. |

3. Write `modules/<name>/CLAUDE.md`. Keep it short. Say what the module does, what it must not do, and which skill to follow.

4. Add a skill in `modules/<name>/skills/<skill>/SKILL.md` that gives the procedure. If most plans have the same shape, add a sample `dag.json` next to it.

5. Check the module.

   ```sh
   uv run jarvis modules
   ```

   The module shows with its description. A running `jarvis up` finds a new module on the next request. No restart is necessary.

6. Test with a real request.

   ```sh
   uv run jarvis up --text
   ```

   Type a request for the module. Make sure that the router picks it, the plan passes the check and each gate asks.

## Rules that a module cannot change

`modules/_base/CLAUDE.md` holds these rules. `load_module()` refuses a `module.toml` that tries to turn one off.

- The engine owns each gate. A session does not skip or answer a gate.
- Each task has a `dag.json` plan with `step`, `test` and `gate` nodes. `docs/dag-format.md` gives the format.
- Each plan has one `test` node or more.
- Jarvis compacts the session when a run ends.

## Guidance

- Put a gate before each action that the person cannot reverse: a payment, a deletion, a message to a different person.
- Give each step that changes something an `undo` instruction.
- A step that finds options returns them as `choices` in its result. The next gate then shows a list, and the person does not type.
- Start each result with the key fact in 10 words or less. Jarvis speaks only the first 18 words.
- Do not put a secret, card data or a personal document in a module file.

## If the module does not show

| Sign | Cause |
| --- | --- |
| The module is not in the list | The folder name starts with `_` or `.`, or `module.toml` is absent. |
| `unsupported keys in module.toml` | A key is not one of the eight. |
| `missing required keys` | One of the eight keys is absent. |
| `Module directory must resolve to its module folder` | `directory` does not point to `modules/<name>`. |
| The router asks "Is this A or B?" | Two descriptions are too near. Make each one more specific. |
