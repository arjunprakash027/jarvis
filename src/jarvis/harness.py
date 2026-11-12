"""The module's one interactive pi terminal, addressed by its stable hc name."""

import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .modules import Module


class Harness:
    def __init__(self, modules: list[Module], *, run=subprocess.run, timeout: float = 600):
        self.modules = {m.name: m for m in modules}
        self.run = run
        self.timeout = timeout
        self.locks = {m.name: threading.RLock() for m in modules}

    def add(self, module: Module) -> None:
        """Know a module added after start. Its session starts on its first request."""
        self.modules.setdefault(module.name, module)
        self.locks.setdefault(module.name, threading.RLock())

    def hc(self, *args: str, json_output: bool = True):
        proc = self.run(["hc", *args], capture_output=True, text=True, check=True)
        return json.loads(proc.stdout) if json_output else proc.stdout

    @staticmethod
    def name(module: Module) -> str:
        name = f"jarvis-{module.name}"
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", name):
            raise ValueError("Module name cannot form a valid hc terminal name")
        return name

    @staticmethod
    def session_dir(module: Module) -> Path:
        return module.tasks_dir / ".sessions"

    def ensure_session(self, module: Module) -> str:
        with self.locks[module.name]:
            name = self.name(module)
            terminals = self.hc("ls").get("terminals", [])
            existing = next((t for t in terminals if t.get("name") == name and t.get("state") == "live"), None)
            if existing:
                info = self.hc("get", existing["address"])
                argv = info.get("argv", [])
                if not argv or Path(argv[0]).name != "pi" or Path(info["cwd"]).resolve() != module.path.resolve():
                    raise RuntimeError(f"{name} already belongs to a different program or directory")
                if (info.get("status") or {}).get("state") == "blocked":
                    raise RuntimeError(f"{name} is blocked; answer its dialog yourself")
                if "--model" in argv and argv[argv.index("--model") + 1] != module.model:
                    raise RuntimeError(f"{name} was started with a different model")
                return name
            if module.agent != "pi":
                raise ValueError("Jarvis modules require agent = 'pi'")
            # A module folder is its configured working directory; reject ambiguous configs.
            directory = Path(module.directory).expanduser()
            if not directory.is_absolute():
                local = module.path / directory
                directory = local if local.resolve() == module.path.resolve() else module.path.parent.parent / directory
            if directory.resolve() != module.path.resolve():
                raise ValueError("Module directory must resolve to its module folder")
            sessions = self.session_dir(module)
            sessions.mkdir(parents=True, exist_ok=True)
            session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(module.path.resolve())))
            args = ["run", "--bg", "--name", name, "--cwd", str(module.path), "pi",
                    "--model", module.model, "--session-dir", str(sessions),
                    "--session-id", session_id, "--no-context-files", "--no-skills", "--no-prompt-templates"]
            for path in module.claude_md_files:
                args.extend(["--append-system-prompt", str(path)])
            if module.skills_dir.is_dir():
                args.extend(["--skill", str(module.skills_dir)])
            # The base extensions come first and every module gets them.
            for directory in (module.base.base_dir / "extensions", module.extensions_dir):
                if directory.is_dir():
                    for path in sorted(directory.iterdir()):
                        if path.suffix in (".ts", ".js"):
                            args.extend(["-e", str(path)])
            self.hc(*args)
            self._wait(name)
            return name

    def _wait(self, name: str) -> None:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            reply = self.hc("wait", name, "--timeout", "10")
            status = reply.get("status")
            if status in ("blocked", "error") or reply.get("reason") == "exit":
                raise RuntimeError(f"{name}: {status or 'exited'}; inspect with hc read {name}")
            if reply.get("ended"):
                return
        raise TimeoutError(f"{name} did not finish; not starting another session")

    @staticmethod
    def task_dir(module: Module, task_id: str) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", task_id):
            raise ValueError("Invalid task id")
        path = module.tasks_dir / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def send_and_wait(self, module: Module, text: str) -> str:
        with self.locks[module.name]:
            name = self.ensure_session(module)
            reply = self.hc("send", name, text)
            if reply.get("started") is not True:
                raise RuntimeError(f"hc did not deliver to {name}; inspect before retrying")
            self._wait(name)
            return self.hc("read", name, "--lines", "40", json_output=False)

    def _request(self, module: Module, task_id: str, text: str, node_id: str = "") -> dict:
        with self.locks[module.name]:
            directory = self.task_dir(module, task_id) / "nodes"
            directory.mkdir(exist_ok=True)
            # A fresh path per attempt prevents an old node result from passing a retry.
            name = f"{node_id}-{uuid.uuid4().hex[:8]}" if node_id else uuid.uuid4().hex
            path = directory / f"{name}.json"
            self.send_and_wait(module, text + f'\nWrite your result JSON to {path}: '
                               '{"ok": true or false, "output": "plain result or failure reason"}. '
                               'Write the file before ending your turn. Do not start another session.')
            result = json.loads(path.read_text())
            if not isinstance(result, dict) or type(result.get("ok")) is not bool or not isinstance(result.get("output"), str):
                raise ValueError(f"Invalid pi result in {path}")
            return result

    def plan(self, module: Module, task_id: str, request: str, long_task: bool = False, errors: str = "") -> dict:
        directory = self.task_dir(module, task_id)
        prompt = (f"Plan this request, do not execute any steps: {request}\n"
                  f"Write {directory / 'dag.json'} using the base DAG contract. "
                  f"Required gate ids: {list(module.required_gates)}. The engine owns all gates. "
                  "Every DAG needs a test node. Stop after writing the plan.\n")
        if long_task or module.task_size == "long":
            prompt += f"First write a short spec to {directory / 'spec.md'}.\n"
        if errors:
            prompt += f"The previous DAG was rejected. Fix these errors: {errors}\n"
        result = self._request(module, task_id, prompt)
        if not result["ok"]:
            raise RuntimeError(result["output"])
        return json.loads((directory / "dag.json").read_text())

    def executor(self, job: dict) -> dict:
        module = self.modules[job["module"]]
        return self._request(module, job["task_id"],
                             f"Task: {job['task']}\nNode: {job['node']['id']} ({job['action']}, attempt {job['attempt']})\n"
                             f"Execute only this instruction: {job['instruction']}\n"
                             "Report ok=false if it failed (including a failing test). Never answer or skip gates.",
                             node_id=job["node"]["id"])

    def compact(self, module_name: str) -> None:
        module = self.modules[module_name]
        with self.locks[module_name]:
            name = self.ensure_session(module)
            sessions = self.session_dir(module)

            def entries():
                return [json.loads(line) for path in sessions.glob("*.jsonl")
                        for line in path.read_text().splitlines() if line.strip()]

            before = {e.get("id") for e in entries() if e.get("type") == "compaction"}
            previous_turn = self.hc("get", name).get("turn", 0)
            self.hc("keys", name, "/", "c", "o", "m", "p", "a", "c", "t", "enter")
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                try:
                    if any(e.get("type") == "compaction" and e.get("id") not in before for e in entries()):
                        return
                except json.JSONDecodeError:  # pi may be appending a line right now
                    pass
                # Slash commands do not reliably advance hc's turn/status. Watch the persisted
                # completion event, not an old 'done' status from the preceding model turn.
                info = self.hc("get", name)
                status = info.get("status") or {}
                if info.get("state") == "finished":
                    raise RuntimeError(f"{name} exited during compaction")
                if info.get("turn", 0) > previous_turn and status.get("state") == "error":
                    if any(reason in status.get("msg", "") for reason in ("Nothing to compact", "Already compacted")):
                        print(f"{name}: nothing new to compact")
                        return
                    raise RuntimeError(f"{name}: {status.get('msg', 'compaction failed')}")
                threading.Event().wait(0.5)
            raise TimeoutError(f"Compaction not confirmed for {name}; inspect its terminal")
