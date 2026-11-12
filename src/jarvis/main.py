"""jarvis up: local input, module planning, Restate execution and gate replies."""

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import engine, gate, router, voice
from .log import event, log_path
from .dag import check_dag
from .harness import Harness
from .modules import ModuleConfigError, load_modules


def http(method: str, url: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={} if data is None else {"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read() or b"null")


class Jarvis:
    def __init__(self, modules, harness, *, route=router.route, say=voice.speak,
                 submit=engine.submit, result=engine.result, resolve=gate.resolve_gate,
                 status=None, popup=gate.spawn_gate, reload=None):
        self.reload = reload  # returns the current modules; a new module works with no restart
        self.modules = {m.name: m for m in modules}
        self.harness, self.route, self.say = harness, route, say
        self.submit, self.result, self.resolve = submit, result, resolve
        self.status = status or self._status
        self.popup = popup
        self.pending = ""
        self.waiting = {}  # insertion order is the order in which gates opened
        self.gate_lock = threading.Lock()
        self.module_locks = {m.name: threading.Lock() for m in modules}
        self.unclear = set()
        self.pools = {m.name: ThreadPoolExecutor(max_workers=1) for m in modules}
        self.futures = []

    def add_new_modules(self):
        """Pick up module folders added since start, for example one the builder just made."""
        if self.reload is None:
            return
        try:
            current = self.reload()
        except ModuleConfigError as exc:  # a half-built module must not stop Jarvis
            event("module", f"list not reloaded: {exc}")
            return
        for m in current:
            if m.name not in self.modules:
                self.modules[m.name] = m
                self.module_locks[m.name] = threading.Lock()
                self.pools[m.name] = ThreadPoolExecutor(max_workers=1)
                self.harness.add(m)
                event("module", f"new module picked up: {m.name}")

    def close(self):
        for pool in self.pools.values():
            pool.shutdown(wait=True)

    def tell(self, text):
        print(text, flush=True)  # the full text stays on screen
        self.say(gate.brief(text))

    def _status(self, name):
        return http("POST", f"{gate.ingress_url()}/module/{urllib.parse.quote(name, safe='')}/status")

    def open_gate(self, gate_id, task, question, choices=None, multi=False):
        info = {"id": gate_id, "task": task, "question": question}
        if choices:
            info.update(choices=choices, multi=multi)
        with self.gate_lock:
            self.waiting[gate_id] = info
        self.popup(gate_id, task, question, *((choices, multi) if choices else ()))

    def oldest_gate(self):
        # Shared status is available even while the exclusive run sleeps at a gate.
        # It also discovers waiting gates after Jarvis itself restarts.
        active = {}
        for name in self.modules:
            current = self.status(name)
            if current:
                active[current["id"]] = current
        with self.gate_lock:
            self.waiting = {k: v for k, v in self.waiting.items() if k in active}
            for key, value in active.items():
                self.waiting.setdefault(key, value)
            return next(iter(self.waiting.values()), None)

    def accept(self, text: str, heard_seconds: float | None = None):
        text = text.strip()
        if not text:
            return None
        event("heard", f'"{text}"' + (f" ({heard_seconds:.1f} s)" if heard_seconds else ""))
        waiting = self.oldest_gate()
        if waiting:
            picked = gate.pick_choices(text, waiting["choices"], waiting.get("multi", False)) if waiting.get("choices") else []
            if picked:  # a number or a name from the popup list
                self.resolve(waiting["id"], {"answer": "yes", "text": ", ".join(picked)})
                return None
            # The first word is the answer; the rest is detail, e.g. "yes, the 19:30 showing".
            first, _, rest = text.lower().strip(" .!?").partition(" ")
            answer, detail = first.strip(" ,.!?"), rest.strip(" ,.!?")
            if answer not in ("yes", "no", "retry", "skip", "stop", "undo"):
                if waiting["id"] not in self.unclear:
                    self.unclear.add(waiting["id"])
                    self.tell(f"{waiting['task']}: please say yes or no, or use the popup.")
                else:
                    self.tell(f"{waiting['task']}: please answer in the popup.")
                return None  # Never route an unclear gate answer as a new request.
            word = "" if answer in ("yes", "no") else answer
            payload = {"answer": "yes" if answer in ("yes", "retry") else "no",
                       "text": " ".join(x for x in (word, detail) if x)}
            self.resolve(waiting["id"], payload)
            return None
        self.add_new_modules()
        request = f"{self.pending}\n{text}" if self.pending else text
        decision = self.route(request, {m.name: m.description for m in self.modules.values()})
        if decision.module is None:
            event("route", f"{decision.kind}: asking \"{decision.question}\"")
            self.pending = "" if decision.kind == "no_fit" else request
            self.tell(decision.question or "No module fits.")
            return None
        event("route", f"{decision.module} ({decision.score:.2f}) · detail ok" + (" · long task" if decision.long_task else ""))
        self.pending = ""
        module = self.modules[decision.module]
        future = self.pools[module.name].submit(self.run_task, module, request, decision.long_task)
        self.futures.append(future)
        return future

    def run_task(self, module, request, long_task=False):
        # Planning belongs to the same queue as execution: never let a second request
        # overwrite the session's active task while the first is at a gate.
        with self.module_locks[module.name]:
            task_id = uuid.uuid4().hex
            submitted = False
            try:
                errors = ""
                for attempt in range(3):
                    try:
                        dag = self.harness.plan(module, task_id, request, long_task, errors)
                        problems = check_dag(dag, module.required_gates)
                    except (json.JSONDecodeError, FileNotFoundError) as exc:
                        problems = [str(exc)]
                    event("plan", "check OK" if not problems else f"check failed: {problems[0][:80]}")
                    if not problems:
                        break
                    errors = "; ".join(problems)
                else:
                    raise ValueError(f"DAG rejected after two repairs: {errors}")
                invocation = self.submit(module.name, task_id, dag, module.required_gates)
                submitted = True
                event("task", f"{module.name}: submitted to Restate")
                # Attach timeouts do not resubmit the DAG or release the module queue.
                while True:
                    try:
                        outcome = self.result(invocation)
                        break
                    except (TimeoutError, urllib.error.URLError):
                        # A lost connection is not evidence that this invocation ended.
                        # Keep its queue occupied; never plan a second task in its session.
                        threading.Event().wait(1)
                event("result", f"{module.name}: {outcome['status']}")
                message = f"{module.name}: {outcome['status']}. {outcome.get('reason', '')}"
                if outcome.get("trace"):
                    message += "\n" + "\n".join(outcome["trace"])
                self.tell(message)
                return outcome
            except Exception as exc:
                event("result", f"{module.name}: error: {type(exc).__name__}")
                self.tell(f"{module.name}: {type(exc).__name__}: {exc}")
                return {"status": "error", "reason": str(exc)}
            finally:
                # Valid executions compact in the engine's stored end step. A rejected
                # plan never reaches that step, so compact its session here instead.
                if not submitted:
                    try:
                        self.harness.compact(module.name)
                    except Exception as exc:
                        self.tell(f"{module.name}: compaction failed: {exc}")


def start_services(app: Jarvis, *, service_port=9080):
    """Reuse the local Restate server; serve this process's module executor."""
    admin = os.environ.get("JARVIS_RESTATE_ADMIN", "http://127.0.0.1:9070")
    try:
        http("GET", admin + "/health")
    except (OSError, urllib.error.URLError):
        terminals = app.harness.hc("ls").get("terminals", [])
        if not any(t.get("name") == "jarvis-restate" and t.get("state") == "live" for t in terminals):
            state_dir = Path.home() / ".local/share/jarvis/restate"
            state_dir.mkdir(parents=True, exist_ok=True)
            app.harness.hc("run", "--bg", "--name", "jarvis-restate", "--cwd", str(state_dir), "restate-server")
    errors = []

    def serve():
        try:
            engine.serve(app.harness.executor, app.open_gate, app.harness.compact, port=service_port)
        except BaseException as exc:
            errors.append(exc)

    threading.Thread(target=serve, daemon=True).start()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if errors:
            raise RuntimeError(f"Engine could not start: {errors[0]}")
        try:
            engine.register(f"http://127.0.0.1:{service_port}", admin)
            return
        except (OSError, urllib.error.URLError):
            threading.Event().wait(0.25)
    raise RuntimeError("Restate registration failed; check ports 9070, 9080 and docs/run.md")


def up(modules_dir: Path, *, text: bool = False) -> int:
    modules = load_modules(modules_dir)
    if not modules:
        raise ValueError("No modules found. Copy modules/_example to a non-underscore folder first.")
    app = Jarvis(modules, Harness(modules), reload=lambda: load_modules(modules_dir))
    start_services(app)
    if not text:
        fixture = Path(__file__).resolve().parents[2] / "tests/fixtures/request.wav"
        voice.transcribe(fixture)  # warm whisper once; the first transcription is slow
    print("Jarvis ready. Ctrl-C to stop.", flush=True)
    event("ready", "log file: " + str(log_path()))
    try:
        while True:
            try:
                line = input("> ") if text else voice.listen()
                app.accept(line, None if text else voice.last_seconds)
            except (OSError, ValueError, RuntimeError) as exc:
                app.tell(f"Request failed: {exc}")
    except (EOFError, KeyboardInterrupt):
        print("Input stopped. Waiting for active tasks; answer any open popup.", flush=True)
    finally:
        app.close()
    return 0
