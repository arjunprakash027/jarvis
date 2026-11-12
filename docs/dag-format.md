# DAG format

A task is one `dag.json` file. The session writes it. The engine checks it and then runs it.

## Shape

```json
{
  "task": "Add milk, eggs and bread to my Tesco basket",
  "nodes": [
    {"id": "search", "type": "step", "do": "Find each item", "needs": []},
    {"id": "basket", "type": "step", "do": "Add the items to the basket", "needs": ["search"],
     "undo": "Remove the items from the basket"},
    {"id": "verify", "type": "test", "do": "Confirm the basket holds the 3 items", "needs": ["basket"],
     "on_fail": "search"},
    {"id": "pay", "type": "gate", "do": "Tesco basket, total is 6.40. Do I pay?", "needs": ["verify"]}
  ]
}
```

## Node fields

- `id`: a unique name.
- `type`: `step`, `test` or `gate`.
- `do`: the instruction. For a gate, it is the question.
- `needs`: the ids that must finish first. Use `[]` for none.
- `undo`: optional. The instruction that reverses a step.
- `on_fail`: optional, on a `test` only. The id of an earlier node that the test needs.

## What the check refuses

The check is `check_dag` in `src/jarvis/dag.py`. It returns every problem as plain text. It refuses a DAG if:

- a node has no `id`, `type`, `do` or `needs`, or an id is used twice,
- `needs` names a node that does not exist, or the `needs` links form a loop (Kahn's algorithm finds loops),
- `on_fail` is on a node that is not a `test`, or it names a node that the test does not need,
- the module lists a required gate and the DAG has no `gate` node with that id,
- the DAG has no `test` node.

If the check fails, the run ends with the status `invalid` and the error text. The session fixes the DAG and sends it again.

## How the engine runs it

The engine runs the nodes in topological order. Nodes with the same rank keep the file order.

- A `step` calls the executor. If it fails, the engine calls it one more time. If it fails again, the engine asks at a gate: retry, skip or stop.
- A `test` calls the executor. If it fails, the engine runs the `undo` of each done node from the `on_fail` node up to the test, newest first. Then it goes back to the `on_fail` node. After 2 returns, the next failure asks at a gate: retry, skip or stop.
- A `gate` asks the question and waits. "Yes" continues. "No" ends the run with the status `declined`. If the text field of the "No" answer holds the word `undo`, the engine first undoes the done steps.
- When the run ends, the engine calls the compaction function for the module.

## Gates

- Each gate has its own id (a Restate awakeable id). An answer reaches that id only.
- The popup has the task name, the question, Yes, No and a text field. The engine also speaks the question with `say`. The first answer wins.
- For a retry, skip or stop question, type `retry`, `skip` or `stop` in the text field. Yes means retry. No means stop.
- A voice answer calls `jarvis.gate.resolve_gate(gate_id, {"answer": "yes", "text": ""})`.

## Result

A run returns `{"status", "reason", "trace"}`. The status is `done`, `stopped`, `declined` or `invalid`.

## Results flow forward

- Each node's instruction gets the results of the nodes in its `needs`, under "Results of earlier nodes".
- A gate's result is Arjun's answer, for example "Arjun answered yes: the 19:30 showing".
- A gate question gets the results of the nodes it needs. So "Do I pay?" after a test that read the basket shows the real total.
- A typed or spoken gate answer: the first word is the answer (yes, no, retry, skip, stop, undo). The rest is detail.
