# Run Jarvis locally

Run from the repository root on macOS. Install `uv`, `hc` (Herdr Core), interactive `pi`, and `restate-server`. Configure the module model's provider in pi first. Set `TYPESAFE_API_KEY` in the environment or the repository's ignored `.env`. Do not put credentials in module files.

```sh
uv sync
cp -R modules/_example modules/example
```

Edit `modules/example/module.toml`. Set `directory` to the absolute module folder (or `.`), `agent` to `pi`, and `model` to an available `provider/model`. Give the module a useful description. Each name must fit the hc name `jarvis-<name>` (32 lowercase letters, digits, hyphens or underscores at most, including the prefix).

```sh
uv run jarvis up
```

Jarvis starts or reuses the local Restate server on ports 9070/8080. It serves its executor on 9080 and registers it. Run only one `jarvis up` process for these ports. It warms whisper once using `tests/fixtures/request.wav`. Press Enter to record, speak, then press Enter to stop. See `docs/voice.md` for the model and microphone setup.

For typed input without whisper or microphone access:

```sh
uv run jarvis up --text
```

Type one request per line. The router may ask a question; the next line is joined to the original request and routed again. Planning and execution run in the background. Requests for the same module wait until its previous task and compaction finish. Other modules can run independently.

The engine shows a native macOS gate popup and speaks its question. The next input answers the oldest waiting gate, not the router. Say or type `yes` or `no`. Recovery gates also accept `retry`, `skip`, `stop` or `undo`. For a longer answer use the popup's text field. Unclear answers ask once more, then defer to the popup. The engine's awakeable id sends the answer to that specific task. A popup answer and an input answer race at Restate: only the first resolves the gate.

Pi stays interactive in hc. Find it with `hc ls` and inspect with `hc read jarvis-example`. The harness reuses that named terminal. It does not kill another terminal or create a second live session for a module. On restart it uses a stable project session id in `modules/<name>/tasks/.sessions/`. Base instructions precede module instructions; module skills and explicit extension files are added at launch. Global pi provider extensions remain available. Complete any trust or provider sign-in in the terminal yourself; Jarvis does not bypass a blocked dialog.

All task plans and result JSON files live under the module's ignored `tasks/` folder. Pi writes a plan first. The checker sends errors back for at most two repairs. The Restate engine executes the accepted DAG and compacts the session at the end. See `docs/compaction.md` for the native command and measured behavior. A session too small to compact is reported without inventing a reduction.

Check a DAG manually:

```sh
uv run jarvis dag check modules/example/tasks/TASK_ID/dag.json
```

Use `JARVIS_MODULES_DIR` or `--modules-dir` to select a different module root. Advanced local Restate overrides are `JARVIS_RESTATE_INGRESS` and `JARVIS_RESTATE_ADMIN`; an external server must already listen at those addresses.

Ctrl-C or EOF stops input and waits for active tasks. Answer any waiting popup to let them finish. Do not force-stop a live purchase or expect an unanswered gate to complete. Task durability belongs to Restate; after a restart do not resubmit a request whose outcome is unknown. Jarvis does not automatically recreate the local input queue after process death.
