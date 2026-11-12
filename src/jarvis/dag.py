"""Check a task DAG (dag.json) before the engine runs it. See docs/dag-format.md."""

import json
from collections import deque
from collections.abc import Iterable

NODE_TYPES = ("step", "test", "gate")


class DagError(ValueError):
    """The DAG is not fit to run. The message lists every problem found."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_dag(dag: object, required_gates: Iterable[str] = ()) -> list[str]:
    """Return the list of problems. An empty list means the DAG is fit to run."""
    if not isinstance(dag, dict):
        return ["dag.json must be a JSON object with a 'task' and a 'nodes' list."]
    errors: list[str] = []
    if not _text(dag.get("task")):
        errors.append("'task' must be a non-empty string.")
    nodes = dag.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("'nodes' must be a non-empty list.")
        return errors

    ids: dict[str, dict] = {}
    for i, node in enumerate(nodes):
        where = f"node {i + 1}"
        if not isinstance(node, dict):
            errors.append(f"{where} must be an object.")
            continue
        node_id = node.get("id")
        if _text(node_id):
            where = f"node '{node_id}'"
            if node_id in ids:
                errors.append(f"{where}: the id is used twice.")
            ids[node_id] = node
        else:
            errors.append(f"{where}: 'id' must be a non-empty string.")
        if node.get("type") not in NODE_TYPES:
            errors.append(f"{where}: 'type' must be one of {', '.join(NODE_TYPES)}.")
        if not _text(node.get("do")):
            errors.append(f"{where}: 'do' (the instruction) must be a non-empty string.")
        needs = node.get("needs")
        if not isinstance(needs, list) or not all(isinstance(n, str) for n in needs):
            errors.append(f"{where}: 'needs' must be a list of node ids (use [] for none).")
        if "undo" in node and not _text(node["undo"]):
            errors.append(f"{where}: 'undo' must be a non-empty string when present.")
    if errors:
        return errors

    for node in nodes:
        for need in node["needs"]:
            if need not in ids:
                errors.append(f"node '{node['id']}' needs '{need}', which does not exist.")
            elif need == node["id"]:
                errors.append(f"node '{node['id']}' needs itself.")
    if errors:
        return errors

    order = topological_order(nodes)
    if order is None:
        return ["the 'needs' links form a loop. 'needs' links must go forward only."]

    for node in nodes:
        if "on_fail" not in node:
            continue
        target = node["on_fail"]
        if node["type"] != "test":
            errors.append(f"node '{node['id']}': 'on_fail' is allowed on test nodes only.")
        elif target not in ids:
            errors.append(f"node '{node['id']}': on_fail '{target}' does not exist.")
        elif target not in _ancestors(node["id"], ids):
            errors.append(
                f"node '{node['id']}': on_fail '{target}' must be an earlier node "
                "that the test needs, directly or through other nodes."
            )

    gates = {n["id"] for n in nodes if n["type"] == "gate"}
    for name in required_gates:
        if name not in gates:
            errors.append(f"the module requires a gate node with id '{name}'. The DAG has none.")
    if not any(n["type"] == "test" for n in nodes):
        errors.append("the DAG has no test node. Add at least one.")
    return errors


def _ancestors(node_id: str, ids: dict[str, dict]) -> set[str]:
    seen: set[str] = set()
    todo = list(ids[node_id]["needs"])
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo.extend(ids[n]["needs"])
    return seen


def topological_order(nodes: list[dict]) -> list[str] | None:
    """Kahn's algorithm. Ties keep the file order. Returns None if there is a loop."""
    left = {n["id"]: len(set(n["needs"])) for n in nodes}
    after: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for n in nodes:
        for need in set(n["needs"]):
            after[need].append(n["id"])
    ready = deque(n["id"] for n in nodes if left[n["id"]] == 0)
    order: list[str] = []
    while ready:
        current = ready.popleft()
        order.append(current)
        for nxt in after[current]:
            left[nxt] -= 1
            if left[nxt] == 0:
                ready.append(nxt)
    return order if len(order) == len(nodes) else None


def parse_dag(text: str, required_gates: Iterable[str] = ()) -> dict:
    """Parse dag.json text and check it. Raise DagError with the full error text."""
    try:
        dag = json.loads(text)
    except json.JSONDecodeError as e:
        raise DagError([f"dag.json is not valid JSON: {e}."]) from e
    errors = check_dag(dag, required_gates)
    if errors:
        raise DagError(errors)
    return dag
