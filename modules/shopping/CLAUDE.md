# Shopping

One module for any shop: groceries (Tesco), products (Amazon), tickets (Cineworld), price checks. Extends `../_base/CLAUDE.md`. Browser: ego-browser only. One pi session, no subagents.

## Files
- `skills/shopping/SKILL.md`: the general process (understand, find, choose, add, check, stop) and the safety rules. Read it first.
- `skills/shopping/dag.buy.json`, `dag.price.json`: sample plans. Copy one into `tasks/<id>/dag.json` and fit it to the request.
- `skills/sites/<shop>.md`: page steps for one shop (`tesco`, `cineworld`, `amazon`).
- `skills/ego-browser/SKILL.md`: how to drive ego-browser.
- `skills/calendar.md`: tentative Google Calendar hold, only for tickets with a date.

## Pick the site note
Match the shop in the request to `skills/sites/<shop>.md`. If Arjun named no shop, pick a sensible one. If there is no note, follow the process and write one at the end (you may write in `skills/sites/`).

## Rules
- Never pay. Never open the payment or details step. Never type card or personal data (name, address, phone, email).
- Sign-in: do not enter credentials. `task.handOff()` and report.
- Guest checkout only up to the review page.
- Never remove items that were in the cart before. Undo removes only this run's additions.
- The last node is the engine-owned gate `pay`, on the review page. Its question: `<shop> cart: <items>, <total>. Stop here before payment?` The check node puts the observed items and total in its result; the engine appends it. Never answer a gate yourself. Yes still means stopped before payment.
- Price check and cart read change nothing.
- Temporary files go in `tasks/<id>/tmp/`.
