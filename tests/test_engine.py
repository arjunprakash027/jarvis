"""Engine tests. They start a real restate-server and a service with a fake executor.

The fake executor, gate opener and compaction write one JSON line to events.jsonl each,
so a test can see what ran, even across a restart of the service.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
from pathlib import Path

import pytest

from jarvis import engine

pytestmark = pytest.mark.skipif(shutil.which("restate-server") is None, reason="restate-server is not installed")

SERVICE = textwrap.dedent(
    """
    import json, os, time
    from pathlib import Path
    from jarvis import engine

    D = Path(os.environ["FAKE_DIR"])

    def events():
        f = D / "events.jsonl"
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    def log(**kw):
        with open(D / "events.jsonl", "a") as f:
            f.write(json.dumps(kw) + "\\n")

    def executor(job):
        node, task, action = job["node"]["id"], job["task"], job["action"]
        before = [e for e in events() if e["kind"] == "exec" and e["task"] == task
                  and e["node"] == node and e["action"] == action]
        log(kind="exec", task=task, node=node, action=action, attempt=job["attempt"], module=job["module"])
        fails = json.loads((D / "scenario.json").read_text()).get(task, {}).get(node, 0)
        if action == "do" and len(before) < fails:
            return {"ok": False, "output": "fake failure"}
        return {"ok": True, "output": "fine"}

    def open_gate(gate_id, task, question):
        log(kind="gate", id=gate_id, task=task, question=question)

    def compact(module):
        log(kind="compact", module=module)

    engine.serve(executor, open_gate, compact, port=int(os.environ["SERVICE_PORT"]))
    """
)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(check, what, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def wait_http(url):
    def up():
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return True
        except OSError:
            return False

    wait_for(up, url)


class Stack:
    """restate-server plus the engine service, with a fake executor."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.dir = root / "fake"
        self.dir.mkdir()
        self.ingress_port, self.admin_port, self.node_port, self.service_port = (free_port() for _ in range(4))
        self.ingress = f"http://127.0.0.1:{self.ingress_port}"
        self.admin = f"http://127.0.0.1:{self.admin_port}"
        self.service_proc = None
        self.set_scenario({})

    def set_scenario(self, scenario: dict) -> None:
        (self.dir / "scenario.json").write_text(json.dumps(scenario))

    def start_server(self) -> None:
        (self.root / "data").mkdir()
        config = self.root / "restate.toml"
        config.write_text(
            f'[ingress]\nbind-address = "127.0.0.1:{self.ingress_port}"\n'
            f'[admin]\nbind-address = "127.0.0.1:{self.admin_port}"\n'
        )
        self.server = subprocess.Popen(
            ["restate-server", "--no-logo", "--listen-mode", "tcp", "--base-dir", str(self.root / "data"),
             "--bind-port", str(self.node_port), "-c", str(config)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        wait_http(f"{self.admin}/health")

    def start_service(self) -> None:
        script = self.root / "service.py"
        script.write_text(SERVICE)
        env = {**os.environ, "FAKE_DIR": str(self.dir), "SERVICE_PORT": str(self.service_port)}
        self.service_proc = subprocess.Popen([sys.executable, str(script)], env=env,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_for(lambda: _port_open(self.service_port), "the service port")
        engine.register(f"http://127.0.0.1:{self.service_port}", self.admin)

    def kill_service(self) -> None:
        self.service_proc.kill()
        self.service_proc.wait()

    def stop(self) -> None:
        for p in (self.service_proc, getattr(self, "server", None)):
            if p and p.poll() is None:
                p.terminate()
                p.wait(timeout=20)

    def events(self, kind=None, task=None):
        f = self.dir / "events.jsonl"
        rows = [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []
        return [e for e in rows if (kind is None or e["kind"] == kind) and (task is None or e["task"] == task)]

    def execs(self, task):
        return [f"{e['action']}:{e['node']}" for e in self.events("exec", task)]

    def gates(self, task):
        return self.events("gate", task)

    def answer(self, gate_id, word, text=""):
        engine.resolve_gate(gate_id, {"answer": word, "text": text}, self.ingress)

    def submit(self, module, task, dag=None, **kw):
        return engine.submit(module, task, dag or make_dag(task), ingress=self.ingress, **kw)

    def result(self, invocation):
        return engine.result(invocation, self.ingress, timeout=60)

    def next_gate(self, task, n=1):
        return wait_for(lambda: len(self.gates(task)) >= n and self.gates(task)[n - 1], f"gate {n} of {task}")["id"]


def _port_open(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    s = Stack(tmp_path_factory.mktemp("restate"))
    s.start_server()
    s.start_service()
    yield s
    s.stop()


def make_dag(task):
    dag = {
        "task": task,
        "nodes": [
            {"id": "search", "type": "step", "do": "Find the items", "needs": []},
            {"id": "basket", "type": "step", "do": "Add the items", "needs": ["search"],
             "undo": "Remove the items"},
            {"id": "verify", "type": "test", "do": "Check the basket", "needs": ["basket"],
             "on_fail": "search"},
            {"id": "pay", "type": "gate", "do": "Do I pay?", "needs": ["verify"]},
        ],
    }
    return dag


def test_stops_at_gate_then_continues_after_answer(stack):
    task = "gate-continue"
    inv = stack.submit("m-gate", task, required_gates=["pay"])
    gate_id = stack.next_gate(task)
    assert stack.execs(task) == ["do:search", "do:basket", "do:verify"]
    status = engine._http("POST", f"{stack.ingress}/module/m-gate/status")
    assert status["id"] == gate_id and status["node"] == "pay" and status["task"] == task
    time.sleep(0.5)
    assert stack.events("compact") == [] or all(e["module"] != "m-gate" for e in stack.events("compact"))

    stack.answer(gate_id, "yes")
    res = stack.result(inv)
    assert res["status"] == "done"
    assert any(e["module"] == "m-gate" for e in stack.events("compact"))
    assert engine._http("POST", f"{stack.ingress}/module/m-gate/status") == {}


def test_no_at_gate_declines(stack):
    task = "gate-no"
    inv = stack.submit("m-no", task)
    stack.answer(stack.next_gate(task), "no", "undo please")
    res = stack.result(inv)
    assert res["status"] == "declined"
    assert stack.execs(task)[-1] == "undo:basket"


def test_answer_reaches_only_its_own_gate(stack):
    a, b = "own-a", "own-b"
    inv_a, inv_b = stack.submit("m-own-a", a), stack.submit("m-own-b", b)
    gate_a, gate_b = stack.next_gate(a), stack.next_gate(b)
    assert gate_a != gate_b
    stack.answer(gate_b, "yes")
    assert stack.result(inv_b)["status"] == "done"
    time.sleep(0.5)
    assert engine._http("POST", f"{stack.ingress}/module/m-own-a/status")["id"] == gate_a
    stack.answer(gate_a, "yes")
    assert stack.result(inv_a)["status"] == "done"


def test_survives_restart_while_waiting_at_gate(stack):
    task = "restart"
    inv = stack.submit("m-restart", task)
    gate_id = stack.next_gate(task)
    before = stack.execs(task)

    stack.kill_service()
    time.sleep(1)
    stack.start_service()
    time.sleep(2)
    assert stack.execs(task) == before  # nothing ran again
    assert len(stack.gates(task)) == 1

    stack.answer(gate_id, "yes")
    res = stack.result(inv)
    assert res["status"] == "done"
    assert stack.execs(task) == ["do:search", "do:basket", "do:verify"]  # each node ran once


def test_failed_test_returns_to_on_fail_with_undo(stack):
    task = "return"
    stack.set_scenario({task: {"verify": 1}})
    inv = stack.submit("m-return", task)
    stack.answer(stack.next_gate(task), "yes")
    res = stack.result(inv)
    assert res["status"] == "done"
    assert stack.execs(task) == [
        "do:search", "do:basket", "do:verify",  # verify fails
        "undo:basket",  # crossed back over basket
        "do:search", "do:basket", "do:verify",
    ]
    assert "verify: return to search" in res["trace"]
    assert len(stack.gates(task)) == 1  # only the pay gate


@pytest.mark.parametrize("word,text,status", [("no", "stop", "stopped"), ("yes", "skip", "done"), ("yes", "retry", "done")])
def test_two_returns_then_asks(stack, word, text, status):
    task = f"two-returns-{text}"
    # retry case: the test fails 3 times, then passes after the second ask
    stack.set_scenario({task: {"verify": 3 if text == "retry" else 99}})
    inv = stack.submit(f"m-{task}", task)
    gate_id = stack.next_gate(task)
    execs = stack.execs(task)
    assert execs.count("do:verify") == 3 and execs.count("undo:basket") == 2
    assert "Try again, skip, or stop" in stack.gates(task)[0]["question"]
    stack.answer(gate_id, word, text)
    if status == "done":
        stack.answer(stack.next_gate(task, 2), "yes")
    res = stack.result(inv)
    assert res["status"] == status


def test_failed_step_retries_once(stack):
    task = "step-retry"
    stack.set_scenario({task: {"basket": 1}})
    inv = stack.submit("m-step-retry", task)
    stack.answer(stack.next_gate(task), "yes")
    assert stack.result(inv)["status"] == "done"
    assert stack.execs(task).count("do:basket") == 2
    assert len(stack.gates(task)) == 1


def test_failed_step_asks_after_retry(stack):
    task = "step-ask"
    stack.set_scenario({task: {"basket": 99}})
    inv = stack.submit("m-step-ask", task)
    gate_id = stack.next_gate(task)
    assert stack.execs(task).count("do:basket") == 2
    assert "failed twice" in stack.gates(task)[0]["question"]
    stack.answer(gate_id, "no", "stop")
    res = stack.result(inv)
    assert res["status"] == "stopped" and "basket" in res["reason"]
    assert any(e["module"] == "m-step-ask" for e in stack.events("compact"))


def test_second_request_for_same_module_waits(stack):
    first, second, other = "queue-first", "queue-second", "queue-other"
    inv1 = stack.submit("m-queue", first)
    gate1 = stack.next_gate(first)
    inv2 = stack.submit("m-queue", second)
    inv3 = stack.submit("m-queue-other", other)

    stack.next_gate(other)  # a different module is not blocked
    time.sleep(1)
    assert stack.execs(second) == []  # the same module waits

    stack.answer(gate1, "yes")
    assert stack.result(inv1)["status"] == "done"
    gate2 = stack.next_gate(second)  # now the second one runs
    stack.answer(gate2, "yes")
    assert stack.result(inv2)["status"] == "done"
    stack.answer(stack.next_gate(other), "yes")
    assert stack.result(inv3)["status"] == "done"


def test_invalid_dag_is_refused_with_text(stack):
    dag = make_dag("invalid")
    dag["nodes"] = [n for n in dag["nodes"] if n["type"] != "test"]
    dag["nodes"][-1]["needs"] = ["basket"]
    res = stack.result(stack.submit("m-invalid", "invalid", dag))
    assert res["status"] == "invalid" and "no test node" in res["reason"]
    assert stack.execs("invalid") == []


def test_required_gate_is_enforced(stack):
    res = stack.result(stack.submit("m-req", "required", required_gates=["confirm"]))
    assert res["status"] == "invalid" and "'confirm'" in res["reason"]


def test_open_gate_speaks_and_sends_first_answer_only():
    from jarvis.gate import open_gate

    spoken, sent = [], []
    open_gate(
        "gate-1", "Tesco basket", "Do I pay?",
        popup=lambda gate_id, task, question: {"answer": "yes", "text": gate_id},
        say=lambda task, question: spoken.append((task, question)),
        resolve=lambda gate_id, answer: sent.append((gate_id, answer)),
    )
    assert spoken == [("Tesco basket", "Do I pay?")]
    assert sent == [("gate-1", {"answer": "yes", "text": "gate-1"})]


def test_closed_popup_sends_nothing():
    from jarvis.gate import open_gate

    sent = []
    open_gate("gate-2", "t", "q", popup=lambda *a: None, say=lambda *a: None,
              resolve=lambda *a: sent.append(a))
    assert sent == []


def test_gate_question_and_next_node_see_earlier_results():
    run = engine._Run(None, {"dag": {"task": "t"}}, None, None, None)
    run.outputs = {"verify": "Basket total EUR 9.35", "choose": "Arjun answered yes: the 19:30 showing"}
    gate = {"id": "pay", "type": "gate", "do": "Tesco basket: do I pay?", "needs": ["verify"]}
    assert run.gate_question(gate) == "Tesco basket: do I pay? Basket total EUR 9.35"
    step = {"id": "seats", "type": "step", "do": "Pick 2 seats", "needs": ["choose"]}
    assert "the 19:30 showing" in run.with_inputs(step, step["do"])
    assert run.with_inputs({"id": "a", "do": "x", "needs": []}, "x") == "x"


def test_gate_question_shows_needed_output(stack):
    task = "gate-context"
    stack.submit("m-ctx", task)
    stack.next_gate(task)
    question = [e for e in stack.events("gate") if e["task"] == task][-1]["question"]
    assert question.endswith("fine")
