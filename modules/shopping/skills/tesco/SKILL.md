---
name: tesco
description: Build and verify a Tesco Ireland grocery basket with ego-browser, stop before payment, then clean up the demo basket.
---

# Tesco basket

Run `ego-browser skill` and follow its current guide. Use one TaskSpace per request; resume its numeric ID between calls. No other browser tool. These page steps were explored with a signed-in account in Phase A.

## Safety and starting state
- Never click Checkout, book a slot, open a payment page, type card data, or place an order. Even a yes at the engine's final gate ends the demo with **stopped before payment**.
- Credentials belong to the user. If Add redirects to `/account/login/en-IE`, call `task.handOff()`, report the sign-in blocker and wait. After confirmation use `takeOverTaskSpace(id)` and navigate back to the trolley: the old login document may still be displayed even when the account is signed in elsewhere.
- First open `https://www.tesco.ie/shop/en-IE/trolley` and inspect the basket. The three-item demo requires an empty starting basket. If there are existing groceries, stop for instructions rather than deleting the user's items. Track every product and quantity changed by this run.

## Search and choose
1. Navigate the same Page to `https://www.tesco.ie/shop/en-IE/search?query=<encoded item>`. If the consent banner appears, choose `text="Reject all"`.
2. Take a full-page snapshot. Each product list item shows its link, price, unit price and `add 1 <exact product name>` button. Use the actual name from the current page, not a guessed selector.
3. Follow explicit preferences first. For the unqualified demo request choose ordinary Tesco fresh milk (1 litre), a Tesco free-range medium egg carton, and an ordinary Tesco sliced white loaf. Skip sponsored products and premium/special-diet variants unless requested. One carton counts as one basket item, not one egg. Observed defaults (availability/prices may change):
   - `Tesco Fresh Milk1ltr`: EUR 1.15, product 292769732.
   - `Tesco Free Range Eggs Medium Box Of 12`: EUR 4.35, product 260300754.
   - `Tesco Medium Sliced White Bread 800g`: EUR 0.85, product 306278295.
   If unavailable, choose a comparable ordinary own-brand product and record the substitution; do not silently ignore dietary requirements.

## Add and verify persistence
4. Click `loc=css:button[aria-label="add 1 <exact product name>"]` once per chosen pack. Before clicking, check whether it is already in the basket. Wait for the quantity to become the target value and for the Basket Summary to update before navigating away. The result-card decrement label is `remove 1 <name> from trolley`. Its appearance alone is not proof the server has saved the change.
5. Open `/shop/en-IE/trolley`. Reload if a recent addition is missing; inspect before retrying Add, since late updates can otherwise double the quantity. Verify every line by product name and `spinbutton "Quantity of <name>"` = 1. Require exactly three lines/items for the demo. Correct unintended extra quantities with `remove 1 <name> from trolley`, then recheck.
6. Read **Basket Summary**, not just the search-page guide price. During exploration the three products cost EUR 6.35, the minimum-basket charge was EUR 3.00, and **Total (estimated)** was EUR 9.35. No delivery/collection slot was booked, so this is an estimate, not a final payable total. Always read current amounts; never hard-code these prices.

## Gate and cleanup
7. End the DAG on `pay`, on the basket review page, with needs `["verify"]`. The verify result JSON output must state the three observed products/quantities, current estimated total, guide price, included charges and no-slot caveat. The engine appends that output to the gate question; editing dag.json after submission does not change the engine's copy. The engine alone asks and records the answer; never simulate approval. For this verification demo the operator answers `no, undo`, which declines payment and dispatches the basket step's undo. Either answer must never open checkout/payment.
8. When the engine dispatches basket undo after `no, undo`, clean up and verify it in that node result. Do not add a node after the final gate. If the run ends without dispatching undo, report cleanup as outstanding; never claim it happened. When this run started with an empty basket, click `text="Empty Basket"`, then the confirmation dialog's `Empty basket` button using a fresh snapshot ref (capitalization differs). Wait for `Your basket is empty`, reload, and verify Items = 0 and Guide price = EUR 0.00. The empty trolley may still show a EUR 3.00 minimum charge and estimated total: those are not leftover groceries. If other groceries appeared meanwhile, remove only this run's additions using `remove <name> from trolley`, preserving unrelated items.
9. Record the observed products, quantities, estimated total, stopped-before-payment result and cleanup in the local task log. On success finish the TaskSpace with `finish({keep:[]})`. Do not claim an engine-run pass from manual exploration.
