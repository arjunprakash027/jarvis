"""The module's one interactive pi terminal, addressed by its stable hc name."""

import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .log import event, headline
from .modules import Module


class Harness:
    def __init__(self, modules: list[Module], *, run=subprocess.run, timeout: float = 600,
                 clock=time.monotonic, beat: float = 30):
        self.modules = {m.name: m for m in modules}
        self.run = run
        self.timeout = timeout
        self.clock, self.beat = clock, beat  # a heartbeat line every `beat` seconds of waiting
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
                event("session", f"{name}: reused ({module.model})")
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
            space = self._herdr_space()
            label = ["--label", f"herdr.space={space}"] if space else []
            args = ["run", "--bg", "--name", name, *label, "--cwd", str(module.path), "pi",
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
            started = self.hc(*args)
            event("session", f"{name}: started ({module.model})")
            if space:
                self._name_tab(started.get("address", ""), name)
            self._wait(name)
            return name

    def _herdr_space(self) -> str:
        """The Herdr space that `jarvis up` runs in, so each module session gets its own visible tab there."""
        me = os.environ.get("HC_TERMINAL_ID")
        if not me:
            return ""
        try:
            return (self.hc("get", me).get("labels") or {}).get("herdr.space", "")
        except Exception:
            return ""  # no Herdr app: the session still runs in hc

    def _name_tab(self, address: str, name: str) -> None:
        """Name the session's tab after it (cosmetic; the app may adopt the tab a moment later)."""
        for _ in range(10):
            try:
                proc = self.run(["herdr-app", "ls"], capture_output=True, text=True, check=True)
                for space in json.loads(proc.stdout).get("spaces", []):
                    for tab in space.get("tabs", []):
                        if any(t.get("terminal") == address for t in tab.get("terminals", [])):
                            self.run(["herdr-app", "do", "tab.rename", "--id", tab["id"], "--name", name],
                                     capture_output=True, text=True, check=False)
                            return
            except Exception:
                return
            time.sleep(0.3)

    def _wait(self, name: str, label: str = "") -> None:
        deadline = time.monotonic() + self.timeout
        start = self.clock()
        due = self.beat
        while time.monotonic() < deadline:
            reply = self.hc("wait", name, "--timeout", "10")
            if label and not reply.get("ended") and self.clock() - start >= due:
                event("node", f"{label}: still running ({int(self.clock() - start)} s)")
                due += self.beat
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

    def send_and_wait(self, module: Module, text: str, label: str = "") -> str:
        with self.locks[module.name]:
            name = self.ensure_session(module)
            reply = self.hc("send", name, text)
            if reply.get("started") is not True:
                raise RuntimeError(f"hc did not deliver to {name}; inspect before retrying")
            self._wait(name, label)
            return self.hc("read", name, "--lines", "40", json_output=False)

    def _request(self, module: Module, task_id: str, text: str, node_id: str = "") -> dict:
        label = node_id or "plan"
        with self.locks[module.name]:
            directory = self.task_dir(module, task_id) / "nodes"
            directory.mkdir(exist_ok=True)
            # A fresh path per attempt prevents an old node result from passing a retry.
            name = f"{node_id}-{uuid.uuid4().hex[:8]}" if node_id else uuid.uuid4().hex
            path = directory / f"{name}.json"
            self.send_and_wait(module, text + f'\nWrite your result JSON to {path}: '
                               '{"ok": true or false, "output": "plain result or failure reason"} '
                               '(add "choices": ["...", ...] when Arjun must pick from options). '
                               'Write the file before ending your turn. Do not start another session.', label)
            result = json.loads(path.read_text())
            if not isinstance(result, dict) or type(result.get("ok")) is not bool or not isinstance(result.get("output"), str) \
                    or not all(isinstance(c, str) for c in result.get("choices", [])):
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
        dag = json.loads((directory / "dag.json").read_text())
        event("plan", f"dag.json written: {len(dag.get('nodes', []))} nodes")
        return dag

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
                    new = [e for e in entries() if e.get("type") == "compaction" and e.get("id") not in before]
                    if new:
                        was = new[-1].get("tokensBefore")
                        event("compact", f"{name}: compacted" + (f" (was {was // 1000}k tokens)" if was else ""))
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
                        event("compact", f"{name}: nothing new to compact")
                        return
                    raise RuntimeError(f"{name}: {status.get('msg', 'compaction failed')}")
                threading.Event().wait(0.5)
            raise TimeoutError(f"Compaction not confirmed for {name}; inspect its terminal")

    def cleanup(self, module_name: str, task_id: str, dag: dict, status: str, trace: list[str]) -> None:
        """Write tasks/<id>/result.md, then delete tmp/ and nodes/ except paths in the DAG's keep.

        Only paths that resolve inside the task folder are touched."""
        module = self.modules[module_name]
        task = (module.tasks_dir / task_id).resolve()
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", task_id) or not task.is_dir():
            return
        heads = {}  # node id -> headline of its newest result file
        files = sorted((task / "nodes").glob("*.json"), key=lambda p: p.stat().st_mtime) if (task / "nodes").is_dir() else []
        for path in files:
            try:
                data = json.loads(path.read_text())
                heads[path.stem.rsplit("-", 1)[0] if "-" in path.stem else path.stem] = (data.get("ok"), headline(data.get("output", "")))
            except (OSError, ValueError, AttributeError):
                pass
        lines = [f"# Result: {dag.get('task', task_id)}", "", f"Status: {status}", ""]
        for node in dag.get("nodes", []):
            ok, head = heads.get(node["id"], (None, ""))
            state = "ok" if ok is True else "failed" if ok is False else "not run"
            lines.append(f"- {node['id']}: {state}" + (f" - {head}" if head else ""))
        (task / "result.md").write_text("\n".join(lines) + "\n")

        keep = []
        for rel in dag.get("keep", []):
            path = (task / rel).resolve()
            if path.is_relative_to(task):
                keep.append(path)
            else:
                event("cleanup", f"{module_name}: refused keep path outside the task folder: {rel}")
        count = size = 0
        for name in ("tmp", "nodes"):
            top = task / name
            if not top.exists() or top.is_symlink() or not top.resolve().is_relative_to(task):
                continue
            for path in sorted(top.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                real = path.resolve()
                if any(real == k or real.is_relative_to(k) or k.is_relative_to(real) for k in keep):
                    continue  # kept, or the folder of something kept
                if path.is_symlink() or path.is_file():
                    size += path.lstat().st_size
                    path.unlink()
                    count += 1
                elif path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
            if top.is_dir() and not any(top.iterdir()):
                top.rmdir()
        event("cleanup", f"{module_name}: removed {count} files ({size / 1e6:.1f} MB), kept result.md")
