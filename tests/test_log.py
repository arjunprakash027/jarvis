import threading

from jarvis import log
from jarvis.cli import main
from jarvis.harness import Harness
from test_harness import FakeHC, example


def test_event_format_and_file_append(capsys, log_file):
    log.event("heard", '"hello" (1.3 s)')
    log.event("done", "builder: done in 5 m")
    lines = log_file.read_text().splitlines()
    assert capsys.readouterr().out.splitlines() == lines
    assert lines[0][8:] == ' heard    "hello" (1.3 s)'
    assert lines[0][2] == lines[0][5] == ":"
    assert lines[1][9:17] == "done    "


def test_event_creates_folder_and_calls_listeners(tmp_path, monkeypatch):
    path = tmp_path / "new/dir/jarvis.log"
    monkeypatch.setenv("JARVIS_LOG", str(path))
    seen = []
    log.listeners.append(lambda kind, text: seen.append((kind, text)))
    try:
        log.event("gate", "x: waiting for you")
    finally:
        log.listeners.clear()
    assert path.is_file() and seen == [("gate", "x: waiting for you")]


def test_headline_is_first_sentence_and_short():
    assert log.headline("Spec ready: 3 files. More text here.") == "Spec ready: 3 files"
    assert len(log.headline("x" * 200)) == 80


def test_heartbeat_every_beat_while_waiting(tmp_path, capsys):
    now = [0.0]

    class Slow(FakeHC):
        def __call__(self, args, **kwargs):
            if args[1] == "wait":
                now[0] += 10  # each wait call takes 10 fake seconds
                done = now[0] >= 65
                return type("P", (), {"stdout": '{"ended": true}' if done else "{}", "returncode": 0})()
            return super().__call__(args, **kwargs)

    module = example(tmp_path)
    harness = Harness([module], run=Slow(), clock=lambda: now[0])
    harness._wait("jarvis-example", "write_spec")
    beats = [l for l in capsys.readouterr().out.splitlines() if "still running" in l]
    assert [b.split("write_spec: ")[1] for b in beats] == ["still running (30 s)", "still running (60 s)"]


def test_logs_command_prints_last_lines(log_file):
    log_file.write_text("".join(f"line {i}\n" for i in range(60)))
    out = []
    log.follow(type("S", (), {"write": lambda self, t: out.append(t), "flush": lambda self: None})(), stop=lambda: True)
    assert "".join(out).splitlines()[0] == "line 10" and len("".join(out).splitlines()) == 50


def test_logs_help():
    import pytest
    with pytest.raises(SystemExit) as exit:
        main(["logs", "--help"])
    assert exit.value.code == 0


def kinds(log_file):
    return [line[9:].split()[0] for line in log_file.read_text().splitlines()]


def test_main_events_in_order(tmp_path, log_file):
    from unittest.mock import Mock
    from jarvis.router import Route
    from test_main import app_for
    app, _, _ = app_for(tmp_path, route=Mock(return_value=Route(module="example", score=0.91, long_task=True)))
    app.accept("build me a module", 1.3).result(3)
    lines = log_file.read_text().splitlines()
    assert kinds(log_file) == ["heard", "route", "plan", "task", "result"]
    assert 'heard    "build me a module" (1.3 s)' in lines[0]
    assert "example (0.91) · detail ok · long task" in lines[1]
    app.close()


def test_engine_events_in_order(log_file):
    import asyncio
    from jarvis import engine

    class Ctx:
        def key(self): return "builder"
        def set(self, *a): pass
        def clear(self, *a): pass
        def awakeable(self):
            f = asyncio.get_event_loop().create_future()
            f.set_result({"answer": "yes", "text": ""})
            return "g1", f
        async def run_typed(self, name, fn): return await fn()

    dag = {"task": "t", "nodes": [
        {"id": "write_spec", "type": "step", "do": "Spec", "needs": []},
        {"id": "check", "type": "test", "do": "Check", "needs": ["write_spec"]},
        {"id": "approve", "type": "gate", "do": "Go?", "needs": ["check"]},
    ]}
    calls = []

    def executor(job):
        calls.append(job["node"]["id"])
        if job["node"]["id"] == "write_spec" and calls.count("write_spec") == 1:
            return {"ok": False, "output": "boom"}
        return {"ok": True, "output": "Spec ready: 3 files. More."}

    run = engine._Run(Ctx(), {"task_id": "x", "dag": dag}, executor, lambda *a: None, None)
    assert asyncio.run(run.go())["status"] == "done"
    lines = log_file.read_text().splitlines()
    text = [l[9:] for l in lines]
    want = ['node     write_spec: running', 'node     write_spec: failed · "boom"', 'node     write_spec: retrying',
            'node     write_spec: running (try 2)', 'node     write_spec: ok · "Spec ready: 3 files"',
            'node     check: running', 'gate     approve: waiting for you', 'gate     approve: yes']
    at = [text.index(w) for w in want]
    assert at == sorted(at)
    assert text[-1].startswith("done     builder: done in ")
