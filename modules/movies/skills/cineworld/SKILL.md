---
name: cineworld
description: Choose Cineworld Dublin showings and two seats with ego-browser, stop before personal details/payment, and add a tentative Google Calendar event through pi Composio tools.
---

# Cineworld Dublin

Load the installed ego-browser skill and run `ego-browser skill` before browser work. One TaskSpace per run; reuse it. Follow current snapshots, not old refs. Use observable waits after every selection: DOM updates are asynchronous and immediate second clicks can be lost.

## Observed path (12 November 2026)

1. Open https://www.cineworld.ie. If the Didomi consent dialog appears, choose **Disagree and close**. Click **quick buy**; wait for its panel (it can appear after an immediate snapshot).
2. **PICK** opens a month calendar. Select the requested Saturday; check the panel's full date. Open film buttons to inspect that day's actual showing links. Use full-page snapshots for content below the viewport. Collect a small list of evening film/time options and runtime; do not invent availability.
3. The engine's `choose_showing` gate asks Arjun to pick a film/time, confirms two standard adult tickets (or his stated ticket types), and permission to add one tentative calendar hold. Do not navigate to a showing until its answer identifies the choice. Ambiguous/negative answers are blockers, not approval of a default.
4. Showtime links lead to `https://web.cineworld.ie/order/showtimes/<id>/seats`. Sign-in may appear; **Continue as guest** is approved. Do not enter credentials, personal data or human verification. Stop if any is required.
5. **Choose your seats** shows Dublin, screen, showing and runtime. The seat SVGs have `role="button"`, `aria-label="Normal seat C6"`, `aria-disabled` and `aria-pressed`. Snapshots may omit their individual roles; bounded `page.evaluate()` can inspect those DOM attributes. Click actual available normal seats using their CSS aria labels, not JS dispatch. Avoid wheelchair/companion seats unless requested.
6. A fixed footer can intercept clicks on seats/ticket quantities near the viewport bottom. Inspect state, then wheel-scroll over the main content to move the target above the footer; do not force-click. Select each seat separately and wait for its `aria-pressed="true"` before selecting the next. Count all pressed seat SVGs, not just the two intended labels.
7. The site rejects an isolated single-seat gap at an aisle. In exploration C5+C6 failed; C6+C7 passed. These are examples, not fixed seat preferences. On rejection, inspect the message, deselect only this run's seats and choose a compliant adjacent pair. Never assume equal consecutive labels mean physically adjacent across an aisle.
8. **Select tickets** navigates to `/tickets` (**Choose your tickets**). Confirm the summary still lists two seats. Select two Adult tickets (or gate-approved types) with scoped quantity buttons/fresh refs. Wait for each quantity update and take a fresh snapshot between repeated ref clicks. Verify **2 of 2**, selected types/counts and live total.
9. This ticket page is the approved review boundary: it shows film, screen, date/time, seats, counts, total and included booking fee. **Do not click Your details.** It leads beyond our approved scope. No personal details, payment pages, voucher/card entry or payment actions. At this point the engine test verifies evidence and the final gate asks whether to end the demo here. A yes ends browser work with **stopped before payment**; a no also never permits payment.
10. Finish the TaskSpace after saving non-sensitive evidence in the task folder. If stopped for user control/authentication, hand off instead. Seat holds expire (about five minutes observed); never imply a booking is complete, and re-check if the run has expired before verification.

Exploration example only: I Play Rocky, Saturday 14 November 2026, 19:30, Dublin Screen 15, runtime 2h 8m, C6+C7, two Adults, €35.98 including €2 booking fee. These values must be re-read live, never substituted for a real run.

## Calendar (pi Composio tools)

The global pi-composio extension is available even when global skills are disabled. Use `composio_search` for Google Calendar event tools and check googlecalendar's active connection. If not connected use `composio_connect` with toolkits `["googlecalendar"]`, report its link to the supervisor for Arjun, and leave Calendar pending. Never enter credentials or create an event before active connection confirmation. No MCP configuration is needed. Cinema-only verification can proceed while Calendar is pending, but is not full acceptance.

Use `composio_get_schema` before each discovered tool, then `composio_execute` with its actual schema. Tools discovered during prep: GOOGLECALENDAR_EVENTS_LIST, GOOGLECALENDAR_CREATE_EVENT; discover a single-event read tool for verification too. For creation explicitly set `create_meeting_room=false`, `exclude_organizer=true`, `attendees=[]`, `send_updates="none"`, `calendar_id="primary"`, and `timezone="Europe/Dublin"`. Do not accept the create tool's default Meet link or invite/notification behavior. Use real ISO timestamps and confirm schemas in the executing session; never guess field names for other tools.

After the final gate, if the choice gate explicitly authorized the calendar hold, create exactly one event on the intended/default calendar. Use the selected showing's real date/start, Europe/Dublin timezone, and observed runtime for the end; disclose that runtime excludes unverified trailers. Title: `Tentative — <film> at Cineworld Dublin (not booked)`. Description states two tickets were only selected; no purchase occurred and the seats are not guaranteed. No invitees or notifications.

Before creation, look for an event matching this task/showing and check the task's recorded event ID, so retries do not duplicate it. Record the returned ID immediately and read the event back. On an ambiguous create timeout, search before retrying; if uncertain, stop rather than create another. If authorization was refused, do not create and report incomplete acceptance. Never call a calendar event proof of a cinema booking.
