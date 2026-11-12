import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.harness import Harness
from jarvis.modules import Module, ModuleBase


def example(tmp_path):
    module_dir = tmp_path / "example"
    module_dir.mkdir()
    base = tmp_path / "_base"
    base.mkdir()
    (base / "extensions").mkdir()
    (base / "extensions" / "module-path.ts").write_text("// base")
    (base / "CLAUDE.md").write_text("Base rules")
    (module_dir / "CLAUDE.md").write_text("Module rules")
    (module_dir / "skills").mkdir()
    (module_dir / "extensions").mkdir()
    (module_dir / "extensions" / "tool.ts").write_text("// tool")
    return Module("example", "Example", "pi", "openai/gpt-6-luna", str(module_dir),
                  "short", ("confirm",), (), module_dir, ModuleBase(base_dir=base))


class FakeHC:
    def __init__(self):
        self.calls = []
        self.terminals = []
        self.prompt = ""
        self.result = {"ok": True, "output": "done"}

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        command = args[1]
        value = {}
        if command == "ls":
            value = {"terminals": self.terminals}
        elif command == "run":
            self.terminals.append({"name": args[args.index("--name") + 1],
                                   "state": "live", "address": "t1"})
            self.cwd = args[args.index("--cwd") + 1]
            value = {"address": "t1"}
        elif command == "get":
            value = {"argv": ["pi"], "cwd": self.cwd}
        elif command == "wait":
            value = {"ended": True, "status": "done"}
        elif command == "send":
            self.prompt = args[3]
            marker = "Write your result JSON to "
            if marker in self.prompt:
                path = Path(self.prompt.split(marker)[1].split(": ")[0])
                path.write_text(json.dumps(self.result))
            value = {"started": True}
        elif command == "read":
            return SimpleNamespace(stdout="fake terminal output")
        return SimpleNamespace(stdout=json.dumps(value))


def test_one_session_and_ordered_context(tmp_path):
    module = example(tmp_path)
    fake = FakeHC()
    harness = Harness([module], run=fake)
    harness.send_and_wait(module, "request one")
    harness.send_and_wait(module, "request two")
    launches = [c for c in fake.calls if c[1] == "run"]
    assert len(launches) == 1
    launch = launches[0]
    assert "-p" not in launch and "--print" not in launch
    assert launch[launch.index("--model") + 1] == module.model
    assert launch[launch.index("--cwd") + 1] == str(module.path)
    base_index = launch.index(str(module.base.base_claude_md))
    assert base_index < launch.index(str(module.path / "CLAUDE.md"))
    assert str(module.skills_dir) in launch
    assert str(module.extensions_dir / "tool.ts") in launch
    base_ext = launch.index(str(module.base.base_dir / "extensions" / "module-path.ts"))
    assert launch[base_ext - 1] == "-e"
    assert base_ext < launch.index(str(module.extensions_dir / "tool.ts"))
    sends = [c for c in fake.calls if c[1] == "send"]
    assert [c[2] for c in sends] == ["jarvis-example", "jarvis-example"]
    assert sum(c[1] == "read" for c in fake.calls) == 2


def test_executor_reads_fresh_json_per_attempt(tmp_path):
    module = example(tmp_path)
    fake = FakeHC()
    harness = Harness([module], run=fake)
    job = {"module": "example", "task_id": "task1", "task": "test", "node": {"id": "a"},
           "action": "do", "attempt": 1, "instruction": "Check something"}
    assert harness.executor(job) == {"ok": True, "output": "done"}
    fake.result = {"ok": False, "output": "failed"}
    assert harness.executor(job)["ok"] is False
    assert len(list((module.tasks_dir / "task1/nodes").glob("*.json"))) == 2


def test_rejects_malformed_result_and_task_traversal(tmp_path):
    module = example(tmp_path)
    fake = FakeHC()
    fake.result = {"ok": "false", "output": "oops"}
    harness = Harness([module], run=fake)
    with pytest.raises(ValueError, match="Invalid pi result"):
        harness._request(module, "task1", "do this")
    with pytest.raises(ValueError, match="task id"):
        harness.task_dir(module, "../outside")


def test_name_collision_does_not_launch_second_terminal(tmp_path):
    module = example(tmp_path)
    fake = FakeHC()
    fake.terminals = [{"name": "jarvis-example", "state": "live", "address": "t1"}]
    fake.cwd = "/not/the/module"
    harness = Harness([module], run=fake)
    with pytest.raises(RuntimeError, match="different program or directory"):
        harness.ensure_session(module)
    assert not any(c[1] == "run" for c in fake.calls)


def test_compact_uses_native_keys_and_persisted_event(tmp_path):
    module = example(tmp_path)
    fake = FakeHC()
    sessions = Harness.session_dir(module)
    sessions.mkdir(parents=True)
    session = sessions / "session.jsonl"
    session.write_text('{"type":"message","id":"before"}\n')

    def run(args, **kwargs):
        if args[1] == "keys":
            with session.open("a") as output:
                output.write('{"type":"compaction","id":"after","tokensBefore":47005}\n')
        return fake(args, **kwargs)

    Harness([module], run=run).compact(module.name)
    keys = next(c for c in fake.calls if c[1] == "keys")
    assert keys[3:] == ["/", "c", "o", "m", "p", "a", "c", "t", "enter"]
    assert not any(c[1] == "send" for c in fake.calls)


def test_compaction_never_types_into_blocked_dialog(tmp_path):
    module = example(tmp_path)
    fake = FakeHC()
    fake.terminals = [{"name": "jarvis-example", "state": "live", "address": "t1"}]
    fake.cwd = str(module.path)

    def run(args, **kwargs):
        response = fake(args, **kwargs)
        if args[1] == "get":
            value = json.loads(response.stdout)
            value["status"] = {"state": "blocked"}
            response.stdout = json.dumps(value)
        return response

    with pytest.raises(RuntimeError, match="blocked"):
        Harness([module], run=run).compact(module.name)
    assert not any(c[1] in ("keys", "send", "run") for c in fake.calls)


@pytest.mark.parametrize("message", ["Nothing to compact (session too small)", "Already compacted"])
def test_compaction_noop_is_not_a_failed_run(tmp_path, message):
    module = example(tmp_path)
    fake = FakeHC()
    requested = False

    def run(args, **kwargs):
        nonlocal requested
        response = fake(args, **kwargs)
        if args[1] == "keys":
            requested = True
        if args[1] == "get" and requested:
            return SimpleNamespace(stdout=json.dumps({"state": "live", "turn": 1,
                "status": {"state": "error", "msg": "Compaction failed: " + message}}))
        return response

    Harness([module], run=run, timeout=1).compact(module.name)
