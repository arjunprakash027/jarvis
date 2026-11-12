import json
import threading
from unittest.mock import Mock

from jarvis.cli import main
from jarvis.main import Jarvis
from jarvis.router import Route
from test_harness import example


def dag():
    return {"task": "test task", "nodes": [
        {"id": "test", "type": "test", "do": "Check", "needs": []},
        {"id": "confirm", "type": "gate", "do": "Continue?", "needs": ["test"]},
    ]}


def app_for(tmp_path, **kwargs):
    module = example(tmp_path)
    harness = Mock()
    harness.plan.return_value = dag()
    app = Jarvis([module], harness, say=Mock(), submit=Mock(return_value="inv1"),
                 result=Mock(return_value={"status": "done", "reason": ""}),
                 resolve=Mock(), status=lambda _: {}, **kwargs)
    return app, module, harness


def test_gate_answer_bypasses_router_and_targets_id(tmp_path):
    route = Mock()
    app, module, _ = app_for(tmp_path, route=route)
    app.status = lambda _: {"id": "gate123", "task": "basket", "question": "Pay?"}
    app.accept("yes")
    app.resolve.assert_called_once_with("gate123", {"answer": "yes", "text": ""})
    route.assert_not_called()
    app.close()


def test_unclear_gate_answers_never_become_new_requests(tmp_path):
    route = Mock()
    app, _, _ = app_for(tmp_path, route=route)
    app.status = lambda _: {"id": "gate123", "task": "basket", "question": "Pay?"}
    app.accept("add apples")
    app.accept("I don't know")
    route.assert_not_called()
    app.resolve.assert_not_called()
    assert app.say.call_count == 2
    app.close()


def test_oldest_gate_uses_open_order_not_module_iteration(tmp_path):
    app, _, _ = app_for(tmp_path, route=Mock(), popup=Mock())
    app.open_gate("old", "older task", "Go?")
    app.open_gate("new", "new task", "Go?")
    # Two module status responses in the reverse order to arrival.
    app.modules = {"new_module": None, "old_module": None}
    app.status = lambda n: {"id": "new" if n == "new_module" else "old"}
    app.accept("no")
    app.resolve.assert_called_once_with("old", {"answer": "no", "text": ""})
    app.close()


def test_question_answer_is_joined_and_routed_again(tmp_path):
    route = Mock(side_effect=[Route(kind="detail", question="Which items?"), Route(module="example")])
    app, _, harness = app_for(tmp_path, route=route)
    assert app.accept("buy groceries") is None
    future = app.accept("milk and eggs")
    assert future.result(timeout=3)["status"] == "done"
    assert route.call_args_list[1].args[0] == "buy groceries\nmilk and eggs"
    assert harness.plan.call_args.args[2] == "buy groceries\nmilk and eggs"
    app.close()


def test_invalid_dag_is_repaired_at_most_twice(tmp_path):
    app, module, harness = app_for(tmp_path)
    harness.plan.side_effect = [{"task": "bad", "nodes": []}, dag()]
    assert app.run_task(module, "request")["status"] == "done"
    assert harness.plan.call_count == 2
    assert harness.plan.call_args.args[-1]
    assert app.submit.call_count == 1
    # Valid executions rely on the engine's stored compaction step, not another one here.
    harness.compact.assert_not_called()
    harness.plan.reset_mock(side_effect=True)
    harness.plan.side_effect = [json.JSONDecodeError("bad json", "", 0)] * 3
    assert app.run_task(module, "bad request")["status"] == "error"
    assert harness.plan.call_count == 3
    harness.compact.assert_called_once_with("example")
    assert app.submit.call_count == 1
    app.close()


def test_second_request_waits_until_first_result(tmp_path):
    app, module, harness = app_for(tmp_path, route=Mock(return_value=Route(module="example")))
    started = threading.Event()
    release = threading.Event()

    def result(_):
        started.set()
        assert release.wait(3)
        return {"status": "done"}

    app.result = result
    first = app.accept("request one")
    assert started.wait(3)
    second = app.accept("request two")
    assert harness.plan.call_count == 1
    release.set()
    assert first.result(3)["status"] == second.result(3)["status"] == "done"
    assert harness.plan.call_count == 2
    app.close()


def test_dag_check_cli(tmp_path, capsys):
    path = tmp_path / "dag.json"
    path.write_text(json.dumps(dag()))
    assert main(["dag", "check", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "OK"
    path.write_text("not json")
    assert main(["dag", "check", str(path)]) == 1
    assert "Expecting value" in capsys.readouterr().out


def test_up_text_cli_dispatch(tmp_path, monkeypatch):
    from jarvis import main as main_module
    up = Mock(return_value=0)
    monkeypatch.setattr(main_module, "up", up)
    assert main(["up", "--text", "--modules-dir", str(tmp_path)]) == 0
    up.assert_called_once_with(tmp_path, text=True)


def test_status_call_sends_no_json_content_type_or_body(monkeypatch):
    from jarvis import main as main_module
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b"{}"
    urlopen = Mock(return_value=response)
    monkeypatch.setattr(main_module.urllib.request, "urlopen", urlopen)
    assert main_module.http("POST", "http://localhost/module/example/status") == {}
    request = urlopen.call_args.args[0]
    assert request.data is None
    assert not request.has_header("Content-type")


def test_modules_have_independent_queues(tmp_path):
    from dataclasses import replace
    module = example(tmp_path)
    other = replace(module, name="other")
    harness = Mock()
    harness.plan.return_value = dag()
    first_started = threading.Event()
    release = threading.Event()

    def result(invocation):
        if invocation == "example":
            first_started.set()
            assert release.wait(3)
        return {"status": "done"}

    app = Jarvis([module, other], harness, route=lambda text, _: Route(module=text),
                 say=Mock(), status=lambda _: {}, submit=lambda name, *args: name,
                 result=result)
    first = app.accept("example")
    assert first_started.wait(3)
    queued = app.accept("example")
    independent = app.accept("other")
    assert independent.result(3)["status"] == "done"
    release.set()
    assert first.result(3)["status"] == queued.result(3)["status"] == "done"
    app.close()


def test_gate_answer_keeps_detail_after_first_word(tmp_path):
    app, _, _ = app_for(tmp_path, route=Mock())
    app.status = lambda _: {"id": "gate9", "task": "movies", "question": "Which showing?"}
    app.accept("Yes, the 19:30 showing.")
    app.resolve.assert_called_once_with("gate9", {"answer": "yes", "text": "the 19:30 showing"})
    app.close()


def test_new_module_folder_is_picked_up_without_restart(tmp_path):
    app, module, harness = app_for(tmp_path, route=Mock(return_value=Route(kind="no_fit", question="No module fits.")))
    new = Mock(); new.name = "clean-space"; new.description = "Free disk space"
    app.reload = lambda: [module, new]
    app.accept("clean my space")
    assert "clean-space" in app.modules and "clean-space" in app.pools
    harness.add.assert_called_once_with(new)
    assert "clean-space" in app.route.call_args.args[1]
    app.close()


def test_spoken_text_is_brief_but_screen_keeps_all(tmp_path, capsys):
    app, _, _ = app_for(tmp_path, route=Mock())
    long = " ".join(f"w{i}" for i in range(40))
    app.tell(long)
    assert len(app.say.call_args.args[0].split()) == 18
    assert long in capsys.readouterr().out
    app.close()
