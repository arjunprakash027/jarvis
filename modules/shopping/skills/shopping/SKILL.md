---
name: shopping
description: Buy, price-check or read the cart on any online shop with ego-browser. Find, choose, add, check, then stop at the pay gate before payment.
---

# Shopping on any shop

Request types: **buy** (groceries, a product, tickets), **price check** (read only, change nothing), **what is in my cart** (read only).
Browser: ego-browser only. Read `skills/ego-browser/SKILL.md`. Temporary files go in `tasks/<id>/tmp/`.
Start each node result with its key fact in 10 words or fewer. Put names, quantities, prices, caveats after it.

## Site note
If `skills/sites/<shop>.md` exists, read it first (`tesco`, `cineworld`, `amazon`). It holds the page steps. If there is none, work from this process. At the end write a short note for that shop in `skills/sites/<shop>.md`: URL, search, add button, cart page, where the total shows, any sign-in or consent step.

## Process
1. **Understand.** Item, shop (if Arjun named none, pick a sensible one), quantity, limits (budget, size, date). Use exactly what he named, not a demo list.
2. **Find.** Search the shop. Read real options and prices from the page. Never invent availability or price.
3. **Choose.** If there is a real choice, the find node returns `"choices": [...]` and a gate (`choose`, with `"multi": true` for several) shows them. Skip the gate when Arjun named the exact thing. Use the exact answer, not memory of the page.
4. **Add.** Put it in the cart, basket, seat selection or ticket selection. Inspect before retrying so nothing is added twice.
5. **Check.** A `test` node: the right items and quantity are in the cart. Read the total. `on_fail` goes back to the find node.
6. **Stop.** The last node is the engine-owned gate `pay`, on the review page before payment. Question: `<shop> cart: <items>, <total>. Stop here before payment?` The engine appends the check result to the question. Yes or no both end the run with "stopped before payment".

Price check: find -> check (test: a price was read for each item) -> pay (gate: "<item>: <price>. Add to cart?"). Nothing is added.
Cart read: read -> check -> pay (gate: "<n> items, <total>. Anything else?"). Nothing is changed.

## Safety
- Never pay. Never open the payment or details step. Never type card data or personal data (name, address, phone, email). Never solve human verification.
- Sign-in asked: do not enter credentials. Call `task.handOff()`, report, wait.
- Guest checkout only up to the review page.
- Never remove items that were in the cart before this run. Undo removes only this run's additions.
- Never answer a gate yourself. A yes never allows checkout.

## DAG samples
`dag.buy.json`: find -> choose gate -> add -> check test -> pay gate. `dag.price.json`: price check.
Dated tickets: after the `pay` gate yes, add the tentative hold from `skills/calendar.md`.
