# Shopping Module (Tesco)

Builds a grocery basket on tesco.ie with ego-browser and stops at a payment gate.

## Rules
- Use the `tesco` skill for every page step. Browser: ego-browser only.
- Never pay. Never type or show card data. Never open the payment page.
- If Tesco asks for a sign-in, do not enter credentials. Hand the ego-browser task space to the user (`task.handOff()`) and wait.
- The last DAG node is the engine-owned gate `pay`, on the basket review page. Its question states the current estimated total and included charges; disclose that delivery is not selected. The verify node must return the observed products, quantities, estimated total, charges and no-slot caveat in its result output. The engine appends this output to the pay gate question through needs; do not try to mutate the submitted DAG.
- Either gate answer ends the run with "stopped before payment". A yes never authorizes checkout, card entry or an order. Never answer the gate yourself.
- Never delete groceries that were in the basket before this run. A `no, undo` at the gate removes only this run's additions.

## Request types

Plan for what Arjun asks. Do not turn every request into the 3-item demo basket.

- **Price check** ("what do eggs cost", "check the price of X"): read only, change nothing in the basket. DAG: `search` (find the item, read price and unit price) -> `check` (test: a price was read for each item; on_fail `search`) -> `pay` (gate, needs `check`). The gate question: "<item>: EUR <price>. Add to basket?" A yes or no ends the run; Jarvis does not add anything in this task. Arjun asks to add in a new request.
- **Add to basket** ("add milk and eggs", "buy me X"): `search` -> `basket` (undo: remove this run's additions) -> `verify` (test: the requested products and quantities are in the basket, read the estimated total; on_fail `search`) -> `pay` (gate on the basket review page). Use exactly the items Arjun named, not the demo list.
- **What is in my basket**: read only. `read` -> `check` (test) -> `pay` (gate: "<n> items, EUR <total>. Anything else?").

Every DAG ends with the engine-owned gate `pay`. Temporary files go in `tasks/<id>/tmp/`. See `skills/tesco/dag.sample.json` for the add-to-basket shape.
