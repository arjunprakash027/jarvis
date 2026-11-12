# Shopping Module (Tesco)

Builds a grocery basket on tesco.ie with ego-browser and stops at a payment gate.

## Rules
- Use the `tesco` skill for every page step. Browser: ego-browser only.
- Never pay. Never type or show card data. Never open the payment page.
- If Tesco asks for a sign-in, do not enter credentials. Hand the ego-browser task space to the user (`task.handOff()`) and wait.
- The last DAG node is the gate `pay`. Its question states the basket total, for example: "Tesco basket, total is EUR 4.20. Do I pay?"
- Empty the basket after the run, whatever the gate answer is.

## DAG for a basket request
`search` (pick one default item per request) -> `basket` (add each item, undo: empty the basket) -> `verify` (test: basket holds every item, on_fail `search`) -> `pay` (gate).
Write it to `tasks/<id>/dag.json` first. `tasks/<id>/sample-dag.json` style: see `skills/tesco/dag.sample.json`.
