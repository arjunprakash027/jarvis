"""The fly-in HUD state. No window opens under pytest (hud.enabled() is False)."""

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
    assert put.call_args_list[-1].args[0] == (proc, None)  # stdin closes: the window fades out
    assert hud._proc is None
