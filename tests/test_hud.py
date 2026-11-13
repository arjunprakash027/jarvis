"""The fly-in HUD state. No window opens under pytest (hud.enabled() is False)."""

import json
import queue
import time
from unittest.mock import Mock, patch

from jarvis import hud, log
from jarvis.router import Route
from test_main import app_for

NODES = [
    {"id": "write_spec", "type": "step", "do": "Spec", "needs": []},
    {"id": "check", "type": "test", "do": "Check", "needs": ["write_spec"]},
    {"id": "approve", "type": "gate", "do": "Go?", "needs": ["check"]},
]


def statuses():
    return [(n["id"], n["status"]) for n in hud.snapshot()["nodes"]]


def test_no_window_under_pytest_or_with_flag(monkeypatch):
    assert not hud.enabled()
    monkeypatch.delitem(__import__("sys").modules, "pytest")
    monkeypatch.setenv("JARVIS_NO_HUD", "1")
    assert not hud.enabled()


def test_lifecycle_tracks_nodes_from_log_events():
    with patch.object(hud, "_spawn") as spawn:
        hud.start("builder", "t1", "build me a module")
        spawn.assert_not_called()
        hud.update_dag(NODES)
        assert statuses() == [("write_spec", "waiting"), ("check", "waiting"), ("approve", "waiting")]
        log.event("node", "write_spec: running")
        log.event("node", 'write_spec: failed · "boom"')
        log.event("node", "write_spec: retrying")
        log.event("node", "write_spec: running (try 2)")
        log.event("node", 'write_spec: ok · "Spec ready: 3 files"')
        log.event("node", "check: still running (30 s)")
        log.event("gate", "approve: waiting for you")
        assert statuses() == [("write_spec", "done"), ("check", "running"), ("approve", "gate")]
        assert hud.snapshot()["nodes"][0]["note"] == "Spec ready: 3 files"
        log.event("gate", "approve: yes")
        log.event("done", "builder: done in 5 s")
        hud.stop()
    s = hud.snapshot()
    assert s["module"] == "builder" and s["task_id"] == "t1"
    assert statuses()[2] == ("approve", "done")
    assert len(s["log"]) == hud.LOG_LINES and s["log"][-1] == "done builder: done in 5 s"
    assert "done     builder" not in "\n".join(s["log"])  # kinds are not padded in the HUD


def test_render_uses_status_icons():
    hud.start("shopping", "t2", "order apples")
    hud.update_dag(NODES[:2])
    hud.add_log("node", "write_spec: running")
    hud.add_log("node", 'check: failed · "no file"')
    lines = hud.render().splitlines()
    assert lines[0] == "shopping: order apples"
    assert lines[1] == "● write_spec" and lines[2] == "✗ check · no file"
    assert lines[-1] == '  node check: failed · "no file"'
    hud.stop()


def test_node_change_ignores_other_kinds():
    assert hud.node_change("route", "builder (0.91)") is None
    assert hud.node_change("node", "x: unknown thing") is None
    assert hud.node_change("node", "x: failed, returning to y") == ("x", "failed", "failed, returning to y")


def test_run_task_starts_and_stops_the_hud(tmp_path):
    app, _, _ = app_for(tmp_path, route=Mock(return_value=Route(module="example", score=0.9, long_task=False)))
    with patch.object(hud, "start") as start, patch.object(hud, "update_dag") as update, patch.object(hud, "stop") as stop:
        app.accept("do the example").result(3)
    start.assert_called_once()
    assert start.call_args.args[0] == "example" and start.call_args.args[2] == "do the example"
    update.assert_called_once()
    stop.assert_called_once()
    app.close()


def test_start_spawns_when_enabled(monkeypatch):
    proc = Mock()
    proc.poll.return_value = None
    with patch.object(hud, "enabled", return_value=True), patch.object(hud, "_spawn", return_value=proc) as spawn, \
            patch.object(hud._queue, "put") as put:
        hud.start("builder", "t3", "x")
        hud.stop()
        spawn.assert_called_once()
        assert json.loads(put.call_args_list[-1].args[0][1]) == {"idle": True}  # the window stays for the hotkey
        assert hud._proc is proc
        hud.close()
        assert put.call_args_list[-1].args[0] == (proc, None)  # stdin closes: the window fades out
    assert hud._proc is None


class FakeWindow:
    """Stands in for bin/jarvis-hud: `lines` feeds its stdout, `sent` collects what Python wrote to stdin."""

    def __init__(self):
        self.lines: queue.Queue = queue.Queue()
        self.sent = []
        self.stdin = Mock(write=lambda s: self.sent.append(json.loads(s)), flush=lambda: None, close=lambda: None)
        self.stdout = iter(self.lines.get, None)

    def poll(self):
        return None

    def print(self, **message):
        self.lines.put(json.dumps(message) + "\n")


def wait_for(check):
    for _ in range(300):
        if check():
            return True
        time.sleep(0.01)
    return False


def test_hotkey_recording_is_transcribed_routed_and_shown(tmp_path):
    wav = tmp_path / "request.wav"
    wav.write_bytes(b"RIFF")
    route = Mock(return_value=Route(module="example", score=0.9))
    app, _, _ = app_for(tmp_path, route=route, transcribe=Mock(return_value=" buy apples "))
    fake = FakeWindow()
    fake_binary = tmp_path / "jarvis-hud"
    fake_binary.touch()
    with patch.object(hud, "enabled", return_value=True), patch.object(hud, "BINARY", fake_binary), \
            patch.object(hud.subprocess, "Popen", return_value=fake):
        hud.open_window(app.on_window)
        fake.print(event="ready", text="press option+space to speak")
        fake.print(event="recorded", wav=str(wav))
        assert wait_for(lambda: route.called and {"heard": "buy apples"} in fake.sent)
        assert route.call_args.args[0] == "buy apples"
        assert wait_for(lambda: any(m.get("module") == "example" and m.get("request") == "buy apples" for m in fake.sent))
        assert wait_for(lambda: {"idle": True} in fake.sent)  # the task ended, the window may hide
        assert not wav.exists()  # the temp recording is deleted
        hud.close()
        fake.lines.put(None)
    app.close()


def test_hotkey_cancel_sends_nothing(tmp_path):
    route = Mock()
    app, _, _ = app_for(tmp_path, route=route, transcribe=Mock())
    with patch.object(hud, "heard") as heard:
        app.on_window({"event": "cancelled"})
    route.assert_not_called()
    app.transcribe.assert_not_called()
    heard.assert_not_called()
    app.close()


def test_hotkey_unclear_speech_shows_nothing_understood_and_routes_nothing(tmp_path):
    wav = tmp_path / "request.wav"
    wav.write_bytes(b"RIFF")
    route = Mock()
    app, _, _ = app_for(tmp_path, route=route, transcribe=Mock(side_effect=FileNotFoundError("no model")))
    with patch.object(hud, "heard") as heard:
        app.on_window({"event": "recorded", "wav": str(wav)})
    heard.assert_called_once_with("")
    route.assert_not_called()
    assert not wav.exists()
    app.close()


def test_question_is_shown_in_the_window(tmp_path):
    route = Mock(return_value=Route(kind="detail", question="Which items?"))
    app, _, _ = app_for(tmp_path, route=route)
    with patch.object(hud, "notice") as notice:
        app.accept("buy groceries")
    notice.assert_called_once_with("Which items?")
    app.close()
