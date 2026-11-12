# Shopping Module (Tesco)

Builds a grocery basket on tesco.ie with ego-browser and stops at a payment gate.

## Rules
- Use the `tesco` skill for every page step. Browser: ego-browser only.
- Never pay. Never type or show card data. Never open the payment page.
- If Tesco asks for a sign-in, do not enter credentials. Hand the ego-browser task space to the user (`task.handOff()`) and wait.
- The last DAG node is the engine-owned gate `pay`, on the basket review page. Its question states the current estimated total and included charges; disclose that delivery is not selected. The verify node must return the observed products, quantities, estimated total, charges and no-slot caveat in its result output. The engine appends this output to the pay gate question through needs; do not try to mutate the submitted DAG.
- Either gate answer ends this demo with "stopped before payment". A yes never authorizes checkout, card entry or an order. For the verification demo the operator answers `no, undo`: the engine declines and dispatches basket undo for cleanup. Never answer the gate yourself.
- Clean up this run's additions after the run, whatever the gate answer is. Verify an empty starting basket first; never delete pre-existing groceries. See the skill for the confirmation dialog and empty-basket checks.

## DAG for a basket request
`search` (check starting basket; pick one default item per request) -> `basket` (add each item, undo: remove this run's additions) -> `verify` (test: exactly the 3 requested products, quantity 1 each, and read estimated total; on_fail `search`) -> `pay` (gate).
Write it to `tasks/<id>/dag.json` first; see `skills/tesco/dag.sample.json`. Record verification and cleanup in `tasks/<id>/log.md`. Task files stay out of git. The sample is a plan, not evidence of a completed engine run.
