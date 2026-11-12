"""Task engine on Restate: one Virtual Object for each module, keyed by the module name.

Restate lets one `run` in at a time for a key, so a second request for the same module
waits until the first ends. Each executor call is a stored step, so after a restart
a done node does not run again. A gate is an awakeable: the run sleeps until it is answered.
See docs/restate.md and docs/dag-format.md.
"""

import asyncio
import inspect
import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import timedelta

import restate

from .dag import check_dag, topological_order
from .gate import ingress_url, resolve_gate, spawn_gate

__all__ = ["make_app", "serve", "register", "submit", "result", "resolve_gate"]

MAX_RETURNS = 2
YES = {"yes", "y", "ok", "true", "go"}


def parse_answer(answer: object) -> tuple[bool, str]:
    """A gate answer is "yes", "no" or {"answer": "yes"|"no", "text": "..."}. Return (yes, text)."""
    if isinstance(answer, dict):
        word, text = str(answer.get("answer", "")), str(answer.get("text", ""))
    else:
        word, text = str(answer), ""
    return word.strip().lower() in YES, text.strip().lower()


def _choice(answer: object) -> str:
    """Read a try again / skip / stop answer. An unclear answer means stop."""
    yes, text = parse_answer(answer)
    for word in ("skip", "stop"):
        if word in text:
            return word
    if "retry" in text or "try" in text or yes:
        return "retry"
    return "stop"


class _Run:
    def __init__(self, ctx, req, executor, open_gate, compact) -> None:
        self.ctx, self.req = ctx, req
        self.executor, self.open_gate, self.compact = executor, open_gate, compact
        self.seq = 0
        self.trace: list[str] = []

    def note(self, node_id: str, event: str) -> None:
        self.trace.append(f"{node_id}: {event}")

    async def _in_thread(self, fn, *args):
        """Call fn. A plain function runs in a thread so it does not block other modules."""
        if inspect.iscoroutinefunction(fn):
            return await fn(*args)
        return await asyncio.to_thread(fn, *args)

    async def call(self, node: dict, action: str, attempt: int) -> tuple[bool, str]:
        """One stored executor call. The executor never raises out of the stored step."""
        self.seq += 1
        job = {
            "module": self.ctx.key(),
            "task_id": self.req.get("task_id", ""),
            "task": self.req["dag"]["task"],
            "node": node,
            "action": action,
            "instruction": node["undo"] if action == "undo" else node["do"],
            "attempt": attempt,
        }

        async def act() -> dict:
            try:
                r = await self._in_thread(self.executor, job)
            except Exception as e:  # Restate would retry an error forever
                return {"ok": False, "output": f"{type(e).__name__}: {e}"}
            if isinstance(r, dict):
                return {"ok": bool(r.get("ok")), "output": str(r.get("output", ""))}
            return {"ok": bool(r), "output": ""}

        r = await self.ctx.run_typed(f"{action}:{node['id']}#{self.seq}", act)
        return r["ok"], r["output"]

    async def ask(self, node_id: str, question: str) -> object:
        """Open a gate and sleep until its id is answered."""
        self.seq += 1
        task = self.req["dag"]["task"]
        gate_id, answer = self.ctx.awakeable()
        self.ctx.set("gate", {"id": gate_id, "node": node_id, "task": task, "question": question})

        async def open_it() -> dict:
            await self._in_thread(self.open_gate, gate_id, task, question)
            return {"opened": True}

        await self.ctx.run_typed(f"gate:{node_id}#{self.seq}", open_it)
        self.note(node_id, f"waits at gate {gate_id}")
        reply = await answer
        self.ctx.clear("gate")
        return reply

    async def recover(self, node_id: str, problem: str) -> str:
        reply = await self.ask(
            node_id,
            f"{problem} Try again, skip, or stop? Type retry, skip or stop. "
            "Yes means try again. No means stop.",
        )
        choice = _choice(reply)
        self.note(node_id, f"gate answer: {choice}")
        return choice

    async def undo(self, node_ids: list[str], byid: dict, done: set) -> None:
        for node_id in reversed(node_ids):
            node = byid[node_id]
            if node_id in done and "undo" in node:
                ok, _ = await self.call(node, "undo", 1)
                self.note(node_id, "undone" if ok else "undo failed")
            done.discard(node_id)

    async def work(self, node: dict) -> str:
        """Run a step. One retry, then ask. Return ok, skip or stop."""
        while True:
            out = ""
            for attempt in (1, 2):
                ok, out = await self.call(node, "do", attempt)
                self.note(node["id"], "ok" if ok else f"failed (try {attempt})")
                if ok:
                    return "ok"
            choice = await self.recover(node["id"], f"Task '{self.req['dag']['task']}', step '{node['id']}' failed twice: {out[:200]}.")
            if choice != "retry":
                return choice

    async def go(self) -> dict:
        dag = self.req["dag"]
        errors = check_dag(dag, self.req.get("required_gates", ()))
        if errors:
            return {"status": "invalid", "reason": "; ".join(errors), "errors": errors, "trace": []}
        byid = {n["id"]: n for n in dag["nodes"]}
        order = topological_order(dag["nodes"])
        done: set[str] = set()
        returns: dict[str, int] = {}
        status, reason, i = "done", "", 0

        while i < len(order):
            node = byid[order[i]]
            kind = node["type"]

            if kind == "gate":
                yes, text = parse_answer(await self.ask(node["id"], node["do"]))
                self.note(node["id"], "gate yes" if yes else "gate no")
                if not yes:
                    if "undo" in text:
                        await self.undo(order[:i], byid, done)
                    status, reason = "declined", f"declined at gate '{node['id']}'"
                    break
                done.add(node["id"])
                i += 1

            elif kind == "step":
                outcome = await self.work(node)
                if outcome == "stop":
                    status, reason = "stopped", f"stopped at step '{node['id']}'"
                    break
                if outcome == "ok":
                    done.add(node["id"])
                i += 1

            else:  # test
                ok, out = await self.call(node, "do", 1)
                self.note(node["id"], "passed" if ok else "failed")
                if ok:
                    done.add(node["id"])
                    i += 1
                    continue
                target = order.index(node["on_fail"]) if "on_fail" in node else None
                if target is not None and returns.get(node["id"], 0) < MAX_RETURNS:
                    returns[node["id"]] = returns.get(node["id"], 0) + 1
                    await self.undo(order[target:i], byid, done)
                    self.note(node["id"], f"return to {node['on_fail']}")
                    i = target
                    continue
                choice = await self.recover(
                    node["id"], f"Task '{dag['task']}', test '{node['id']}' failed: {out[:200]}."
                )
                if choice == "stop":
                    status, reason = "stopped", f"stopped at test '{node['id']}'"
                    break
                if choice == "skip":
                    done.add(node["id"])
                    i += 1
                elif target is not None:
                    returns[node["id"]] = 0
                    await self.undo(order[target:i], byid, done)
                    i = target

        await self.compact_session()
        return {"status": status, "reason": reason, "trace": self.trace}

    async def compact_session(self) -> None:
        if self.compact is None:
            return
        module = self.ctx.key()

        async def act() -> dict:
            try:
                await self._in_thread(self.compact, module)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "error": f"{type(e).__name__}: {e}"}

        r = await self.ctx.run_typed("compact", act)
        self.note("compact", "ok" if r["ok"] else f"failed: {r['error']}")


def make_app(executor: Callable, open_gate: Callable = spawn_gate, compact: Callable | None = None):
    """Build the Restate app.

    executor(job) runs one node and returns {"ok": bool, "output": str}. job has module,
    task_id, task, node, action ("do" or "undo"), instruction and attempt.
    open_gate(gate_id, task, question) shows the popup. compact(module) compacts the session.
    """
    module = restate.VirtualObject("module")

    @module.handler(inactivity_timeout=timedelta(hours=2), abort_timeout=timedelta(hours=2))
    async def run(ctx: restate.ObjectContext, req: dict) -> dict:
        return await _Run(ctx, req, executor, open_gate, compact).go()

    @module.handler(kind="shared")
    async def status(ctx: restate.ObjectSharedContext) -> dict:
        """The gate that this module waits at now, or {}."""
        return await ctx.get("gate") or {}

    return restate.app([module])


def serve(executor: Callable, open_gate: Callable = spawn_gate, compact: Callable | None = None, port: int = 9080):
    """Serve the engine for a Restate server to call. Runs until SIGINT or SIGTERM."""
    asyncio.run(restate.serve(make_app(executor, open_gate, compact), host="127.0.0.1", port=port))


def _http(method: str, url: str, body: object = None, timeout: float = 30):
    data = None if body is None else json.dumps(body).encode()
    headers = {} if data is None else {"content-type": "application/json"}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"null")


def register(service_url: str, admin_url: str = "http://127.0.0.1:9070") -> None:
    """Tell the Restate server where the engine service listens."""
    _http("POST", f"{admin_url}/deployments", {"uri": service_url, "force": True})


def submit(module: str, task_id: str, dag: dict, required_gates=(), ingress: str | None = None) -> str:
    """Queue a run for the module and return the invocation id at once."""
    url = f"{ingress or ingress_url()}/module/{urllib.parse.quote(module)}/run/send"
    body = {"task_id": task_id, "dag": dag, "required_gates": list(required_gates)}
    return _http("POST", url, body)["invocationId"]


def result(invocation_id: str, ingress: str | None = None, timeout: float = 60) -> dict:
    """Wait for a run to end and return its result."""
    return _http("GET", f"{ingress or ingress_url()}/restate/invocation/{invocation_id}/attach", timeout=timeout)
