# Full Test by Voice (`p9-test`)

Date: 2026-11-12
Branch: `p9-test`

## Step 1: Preflight

All preflight checks passed (read-only, no changes made to browser or calendar state):

- **Pytest (`uv run pytest -q`)**: Passed (`91 passed in 18.47s`).
- **Modules (`uv run jarvis modules`)**: Listed `builder`, `movies`, `shopping` only (`clean-space` was NOT present on `main`).
  - `builder: Build, make or create new software: a new tool or a new Jarvis module, even one for a task another module does`
  - `movies: Choose a film, time and two seats at Cineworld Dublin; stop before payment and add a tentative Google Calendar event.`
  - `shopping: Buy groceries on Tesco`
- **Whisper model (`~/.cache/jarvis/models/ggml-base.en.bin`)**: Present (`141.1M`).
- **Restate (`restate-server`)**: Installed at `/opt/homebrew/bin/restate-server` (`restate-server 1.8.1`).
- **Live sessions and lock (`hc ls`, `/private/tmp/jarvis-live.lock`)**: No other `jarvis up` terminal or process running; `/private/tmp/jarvis-live.lock` was free.
- **ego-browser — Tesco (`https://www.tesco.ie/shop/en-IE/trolley`)**: Signed in (`My orders`, `My account`, `Sign out` present in Global Header) and starting basket empty (`Your basket is empty`, `Items: 0`, `Guide price: €0.00`).
- **ego-browser — Cineworld (`https://www.cineworld.ie`)**: Accessible (`quick buy` ready; guest checkout path verified in `modules/movies/skills/cineworld/SKILL.md`).
- **Composio Google Calendar**: Connected (`toolkit: "googlecalendar"`, `has_active_connection: true`, `status: "ACTIVE"`, `timeZone: "Europe/Dublin"`, `accessRole: "owner"`).

## Step 2: Voice Run

### Startup & Voice Hang Fix (PR #12)
- **Restate node-name reset**: On initial `jarvis up`, `restate-server` exited with `[RT0002]` because `~/.local/share/jarvis/restate/restate-data` held data from hostname `Arjuns-MacBook-Air.local` while the current hostname was `MacBookAir`. Moving the stale `restate-data` directory aside allowed `jarvis-restate` to start cleanly.
- **Voice hang and fix (PR #12)**: In the first `jarvis-up` terminal (`t140`), pressing Enter after speaking hung inside `Recording — press Enter to stop.`. This was fixed in PR #12, after which `jarvis-up` was restarted (`t144`) and push-to-talk recording and transcription worked immediately.

### Example 1: Shopping (Tesco) — PASS (by voice)
- **Exact Whisper transcript**: `Can you buy me eggs and bread in Tesco?` _(Oddity: Whisper transcribed "eggs and bread" and dropped "milk".)_
- **Route**: `shopping` (`task_id`: `ca4959ad3c544bf6afef577f57ebb72a`, terminal `jarvis-shopping` / `t146`)
- **Wall-clock time**: ~6m 11s (`21:25:39Z` to `21:31:50Z`, running concurrently with `movies`)
- **Node results**:
  - `plan` (`7e5c5ba54c374e59b55cc2143c5abd0a.json`): `ok: true` — `"Plan written for eggs and bread in Tesco. DAG includes search, basket, verify (test), and pay (gate) nodes."`
  - `search` (`816688fe023344b7aca5b31304654f15.json`): `ok: true` — `"Basket empty; selected Tesco eggs (EUR 4.35) and bread (EUR 0.85). Starting trolley verified empty (0 items, EUR 0.00 guide price) in TaskSpace 20. Selected defaults: 1) Tesco Free Range Eggs Medium Box Of 12 (product 260300754, EUR 4.35), 2) Tesco Medium Sliced White Bread 800g (product 306278295, EUR 0.85)."`
  - `basket` (`ea53828767f74aa6a6163078ff19d199.json`): `ok: true` — `"Added eggs and bread; guide price EUR 5.20, 2 items. Added 1x Tesco Medium Sliced White Bread 800g (EUR 0.85) and 1x Tesco Free Range Eggs Medium Box Of 12 (EUR 4.35) in TaskSpace 20, waiting for saved quantities and basket summary updates after each click."`
  - `verify` (`9176ca0b1bef44c9a75c1e64409d7bb1.json`, `test` node): `ok: true` (`passed`) — `"Basket total EUR 8.20, 2 items. Observed products on trolley review page: 1) Tesco Free Range Eggs Medium Box Of 12 (quantity 1, EUR 4.35), 2) Tesco Medium Sliced White Bread 800g (quantity 1, EUR 0.85). Basket Summary: Items = 2, Guide price = EUR 5.20, Minimum basket charge = EUR 3.00 (baskets under EUR 45.00), Total (estimated) = EUR 8.20. Caveat: no delivery or collection slot is selected, so this is an estimated total only."`
- **Gate (`pay`, `sign_15RQVl4oSiGH2CcALJrgjqQ80HyTKDotOAAAAEQ`)**:
  - Question: `"Tesco basket review: the verification result below states the 2 items, observed estimated total and charges; delivery is not selected. End the demo here, stopped before payment? For demo cleanup answer no, undo. Never click Checkout or open payment."` + `verify` result output.
  - Answer: Arjun answered `yes` in popup (`pay: gate yes`).
- **Compaction & completion**: `compact: ok`, `shopping: done.`
- **Post-run cleanup**: Because Arjun answered `yes` at the gate (which still stops before payment per module contract), the 2 test items remained in the Tesco trolley and were emptied afterward via `ego-browser` (`Empty Basket` -> confirmed `Your basket is empty`, `Items: 0`, `Guide price: €0.00`).
- **Result**: **PASS** by voice.

### Example 2: Movies (Cineworld Dublin) — NOT PASSED by voice (passed in `p7-movies` typed run)
- **Attempt 2a (Failed Route — Whisper transcription error)**:
  - **Exact Whisper transcript**: `Can you unbook my tickets for a movie this Saturday at seven?`
  - **Route**: `no_fit` -> Jarvis replied: `No module can do that yet.`
  - **Reason**: Whisper misheard `"book"` as `"unbook"`; the router properly returned `no_fit`.
- **Attempt 2b (Concurrent Popup Mixup -> Clean Module Block & Stop)**:
  - **Exact Whisper transcript**: `Can you book me tickets for a movie this Saturday at 7?`
  - **Route**: `movies` (`task_id`: `af46072879f94ed4a212edecfc5b6145`, terminal `jarvis-movies` / `t147`)
  - **Wall-clock time**: ~9m 15s (`21:26:11Z` to `21:35:26Z`, including waiting at recovery gate)
  - **Node results & gates**:
    - `plan` (`2dfc54ed09d54829bd0f973ffee1148a.json`): `ok: true` — `"DAG plan written for Saturday 7 PM Cineworld Dublin."`
    - `find_showings` (`e871a7d82eca4e85841bd82baac23d8f.json`): `ok: true` — `"Saturday 14 Nov 7 PM options found at Cineworld Dublin. Options around 19:00 (Europe/Dublin): 1) Ebenezer (1h 56m) at 18:40 or 19:30; 2) Fjord (2h 26m) at 18:45; 3) I Play Rocky (2h 8m) at 19:30 (also 17:30, 20:20); 4) Resident Evil (1h 37m) at 19:30 (also 17:00); 5) Prima Facie (1h 46m) at 19:40 (also 17:00); 6) Primetime (1h 49m) at 19:50 (also 17:00); 7) Clayface (1h 49m) at 20:00 (also 17:25)."`
    - `choose_showing` gate (`sign_1RZsThH0PULi3scNh_NR5PLHdyDFYDMWGAAAAEQ`): Question asked Arjun to choose one of the Saturday 14 Nov ~19:00 showings. Because the `shopping` `pay` popup and `movies` `choose_showing` popup were open concurrently, Arjun typed `"finsih the demo"` (intended for the shopping popup) and clicked Yes (`Arjun answered yes: finsih the demo`).
    - `select_seats` (`1bfc88056dfd47ae820d305c60c6ed28.json`, tries 1 and 2): `ok: false` — `"Blocked: choose_showing answer is ambiguous, no film or time specified. Gate reply 'finsih the demo' did not identify any Saturday 14 November film/time from the live Cineworld Dublin options..."`
    - Recovery gate (`sign_1RZsThH0PULi3scNh_NR5PLHdyDFYDMWGAAAAEg`): Arjun answered `stop` (`select_seats: gate answer: stop`).
    - Compaction & completion: `compact: ok`, `movies: stopped. stopped at step 'select_seats'`.
- **Result**: **NOT PASSED by voice** (operator popup mixup when two gate popups were open simultaneously; the module itself behaved according to contract by blocking on an ambiguous showing choice rather than guessing a film, and `p7-movies` already passed its full end-to-end typed run including seat selection, ticket summary stop-before-payment, and Composio Google Calendar hold creation/deletion in PR #10).

### Examples 3 & 4: Builder (`clean-space`) and Running `clean-space` — NOT RUN by voice (passed in `p8-builder` typed runs)
- **Status**: **NOT RUN by voice** during `p9-test`.
- **Prior verification**: Both building `modules/clean-space/` (`builder` long-task spec + DAG + `approve-plan` gate + pytest verification) and executing `clean-space` (`scan` -> `verify` test -> `confirm` gate declined so nothing is deleted) passed in real end-to-end typed runs in `p8-builder` (PR #8).

## Decision and Follow-Up Fixes

- **Arjun's decision (21:35Z)**: Arjun accepted the test run as sufficient (`"i am ok with this, finish the test everything seems to be working"`) after verifying voice push-to-talk, routing, concurrent Restate DAG execution, gate popups, `shopping` end-to-end completion, and `movies` showtime discovery + safety gating.
- **Follow-up PRs merged from `p9-test` observations**:
  - **PR #12**: Fixed the voice recording / Enter handling hang observed on initial `jarvis up`.
  - **PR #13**: Added the module-path extension so module sessions stay anchored to their target paths.
  - **PR #14**: Added choice popups so multi-option gates (such as `choose_showing`) present selectable choices instead of relying on free-text entry across concurrent popups.
  - **PR #15**: Switched module sessions to faster Flash models to reduce per-node latency during the live Loom demo.
