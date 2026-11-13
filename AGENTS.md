# AGENTS.md

Guidance for a coding agent that works in this repository.

## What this is

Jarvis is a local voice assistant for macOS. A spoken request becomes a checked task graph (`dag.json`). An engine runs the graph node by node in one `pi` session for each module, and asks the person at each gate. Read `README.md` first.

## Skills

- `skills/jarvis-setup/SKILL.md`: install, check and repair Jarvis.
- `skills/jarvis-module/SKILL.md`: add or change a module.

## Commands

```sh
scripts/install.sh --check   # report what is missing, change nothing
uv sync                      # install the Python package
uv run pytest -q             # run the tests
uv run jarvis modules        # list the modules
uv run jarvis up --text      # run with typed input
```

## Rules

- Do not read, print or commit `.env`. Do not put a key, card data or a personal document in a file.
- Do not answer a gate or approve a payment for the person.
- Run only one `jarvis up` at a time.
- Code is Python, kept simple. Put each text that the router sends to Jev in `src/jarvis/router_questions.py`.
- A new type of task is a new folder in `modules/`. Do not add a task type in `src/jarvis/`.
- A module cannot turn off a base rule in `modules/_base/CLAUDE.md`.
- Each pull request lists each file it adds or changes: what the file does, how it connects to other files and why it is needed. Update the file map in `README.md` when you add a file.
