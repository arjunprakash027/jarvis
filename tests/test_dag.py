import json

import pytest

from jarvis.dag import DagError, check_dag, parse_dag, topological_order

GOOD = {
    "task": "Add milk to my Tesco basket",
    "nodes": [
        {"id": "search", "type": "step", "do": "Find the item", "needs": []},
        {"id": "basket", "type": "step", "do": "Add it", "needs": ["search"], "undo": "Remove it"},
        {"id": "verify", "type": "test", "do": "Check", "needs": ["basket"], "on_fail": "search"},
        {"id": "pay", "type": "gate", "do": "Ask: pay?", "needs": ["verify"]},
    ],
}


def dag(**changes):
    d = json.loads(json.dumps(GOOD))
    for key, value in changes.items():
        d[key] = value
    return d


def node(i, **changes):
    d = json.loads(json.dumps(GOOD))
    d["nodes"][i].update(changes)
    return d


def has(errors, text):
    return any(text in e for e in errors)


def test_good_dag_passes_and_sorts():
    assert check_dag(GOOD, required_gates=["pay"]) == []
    assert topological_order(GOOD["nodes"]) == ["search", "basket", "verify", "pay"]


def test_order_ignores_file_order():
    d = json.loads(json.dumps(GOOD))
    d["nodes"].reverse()
    assert topological_order(d["nodes"]) == ["search", "basket", "verify", "pay"]


def test_bad_json_and_shape():
    with pytest.raises(DagError, match="not valid JSON"):
        parse_dag("{nope")
    assert has(check_dag([]), "must be a JSON object")
    assert has(check_dag({"task": "x", "nodes": []}), "non-empty list")
    assert has(check_dag(dag(task="")), "'task'")


@pytest.mark.parametrize("field", ["id", "type", "do", "needs"])
def test_missing_node_field(field):
    d = json.loads(json.dumps(GOOD))
    del d["nodes"][1][field]
    assert has(check_dag(d), field)


def test_bad_type_and_duplicate_id():
    assert has(check_dag(node(1, type="magic")), "'type' must be one of")
    assert has(check_dag(node(1, id="search")), "used twice")


def test_needs_unknown_and_self():
    assert has(check_dag(node(1, needs=["ghost"])), "'ghost', which does not exist")
    assert has(check_dag(node(1, needs=["basket"])), "needs itself")


def test_loop():
    d = node(0, needs=["verify"])
    assert has(check_dag(d), "loop")


def test_on_fail_only_on_test():
    assert has(check_dag(node(1, on_fail="search")), "test nodes only")


def test_on_fail_must_point_back():
    assert has(check_dag(node(2, on_fail="pay")), "must be an earlier node")
    assert has(check_dag(node(2, on_fail="ghost")), "does not exist")
    assert has(check_dag(node(2, on_fail="verify")), "must be an earlier node")


def test_required_gate_missing():
    errors = check_dag(GOOD, required_gates=["confirm"])
    assert has(errors, "gate node with id 'confirm'")


def test_needs_a_test_node():
    d = json.loads(json.dumps(GOOD))
    d["nodes"] = [n for n in d["nodes"] if n["type"] != "test"]
    d["nodes"][-1]["needs"] = ["basket"]
    assert has(check_dag(d), "no test node")


def test_parse_dag_returns_dag_and_raises_all_errors():
    assert parse_dag(json.dumps(GOOD), ["pay"])["task"] == GOOD["task"]
    d = node(2, on_fail="pay")
    with pytest.raises(DagError) as e:
        parse_dag(json.dumps(d), ["confirm"])
    assert len(e.value.errors) == 2


def test_keep_accepts_relative_paths():
    assert check_dag(dag(keep=["out/report.csv", "notes.txt"])) == []


@pytest.mark.parametrize("keep", [["/etc/passwd"], ["../x"], ["a/../../x"], "tmp", [1], ["~/x"]])
def test_keep_rejects_bad_values(keep):
    assert any("keep" in e for e in check_dag(dag(keep=keep)))
