---
name: jarvis-setup
description: Explain what Jarvis is and set it up on a Mac. Jarvis is a local voice assistant that turns a spoken request into a checked task graph, runs it in an agent session and asks the person at each gate. Use when the person asks what Jarvis is, wants to install, run, check or repair Jarvis, or `jarvis up` fails.
compatibility: macOS only. Needs Homebrew, network access and the Jarvis repository on disk.
---

# Jarvis setup

## What Jarvis is

Jarvis is a voice assistant that runs on one Mac. The person speaks a request. Jarvis does these steps:

1. `whisper.cpp` changes the speech to text on the Mac.
2. The router asks TypeSafe (the Jev model) four questions. Python code then picks one module or asks one question.
3. The module's `pi` session writes a plan, `dag.json`. Python checks the plan.
4. The engine (a Restate workflow) runs the plan node by node in that same session.
5. At each `gate` node the engine stops, shows a popup and speaks the question. It continues only after the person answers.
6. When the run ends, Jarvis compacts the session context.

A module is one folder in `modules/`. Read `README.md` for the full picture and `docs/run.md` for run details.

## Rules

- Do not read, print or copy the contents of `.env`. Do not put a key in a command, a log or a commit.
- Do not sign in to an account for the person. Ask them to do it.
- Do not answer a gate for the person. Do not approve a payment.
- Run only one `jarvis up` at a time. Check with `hc ls` before you start one.
- Do not force-stop a run that waits at a gate. Ask the person to answer the popup.
- Do not commit `.env`, `HANDOFF.md`, `PLAN.md`, a `.tldraw` file or a `modules/*/tasks/` folder. `.gitignore` already excludes them.

## Steps

Run each command from the repository root.

1. Check the Mac. This command changes nothing.

   ```sh
   scripts/install.sh --check
   ```

   Each `miss` line is a part that is absent. Tell the person what is missing before you install.

2. Install the missing parts.

   ```sh
   scripts/install.sh
   ```

   The script installs `uv`, `whisper-cpp`, `restate-server`, `restate` and `pi-coding-agent` with Homebrew. It downloads the speech model (about 140 MB) and runs `uv sync`. It does not install `hc` (Herdr Core) or the Xcode command line tools. If one is missing, tell the person.

3. Ask the person for these three items. You cannot do them.

   - The TypeSafe key. The person puts it in `.env` as `TYPESAFE_API_KEY=...`.
   - A model provider sign-in in `pi`. The person runs `pi` and signs in.
   - Microphone access for the terminal app, when macOS asks.

4. Set the model. Each `modules/<name>/module.toml` has a `model` line. Ask the person which `provider/model` their `pi` can use, then set that value. A session with a model that `pi` cannot use fails at start.

5. Check the result.

   ```sh
   uv run jarvis modules
   uv run pytest -q
   ```

   `jarvis modules` lists each module with its description. One test needs `whisper-cli` and the speech model.

6. Start Jarvis with typed input. This needs no microphone.

   ```sh
   uv run jarvis up --text
   ```

   Wait for `Jarvis ready`. Ask the person to type a request and to answer the popup. For voice, the person runs `uv run jarvis up` and presses Option+Space.

## If a step fails

| Sign | Cause | Correction |
| --- | --- | --- |
| `TYPESAFE_API_KEY is not set` | No key in the environment or in `.env`. | Ask the person to add the key. |
| `Missing whisper model` | The model file is absent. | Run `scripts/install.sh`. |
| `Restate registration failed` | Port 9070, 8080 or 9080 is in use, or a second `jarvis up` runs. | Stop the other process. Read `hc read jarvis-restate`. |
| `restate-server` stops with `RT0002` | The stored data has a different host name. | Ask the person, then move `~/.local/share/jarvis/restate/restate-data` to a different name. |
| `jarvis-<name> is blocked` | The `pi` session shows a dialog. | Ask the person to answer it: `hc attach jarvis-<name>`. |
| `jarvis-<name> was started with a different model` | The model in `module.toml` changed while the session was alive. | Ask the person, then stop the old session with `hc kill jarvis-<name>`. |
| No window and no hotkey | `swiftc` is missing or `JARVIS_NO_HUD=1` is set. | Install the Xcode command line tools: `xcode-select --install`. |
| The first request is slow | The speech model loads on first use. | No correction is necessary. `jarvis up` warms the model at start. |

For a log of the last run, use `uv run jarvis logs`.
