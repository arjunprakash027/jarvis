# Movies

Extends `../_base/CLAUDE.md`. Read `skills/cineworld/SKILL.md` before planning or browser actions. This module uses one pi session, ego-browser only, and Google Calendar through pi's global Composio tools only. No subagents.

For the demo request, copy the skill's `dag.json` into the assigned `tasks/<id>/dag.json`, tailoring its instructions to the request without removing required gates. Planning does not execute browser or calendar actions. The engine dispatches nodes and owns every gate; never ask or approve a gate yourself. Resolve relative dates using Europe/Dublin and the current date; never reuse exploration dates or showtime IDs.

Never pay, open a payment page, enter credentials or personal data, solve human verification, or access/show card data. The approved guest path is allowed. If credentials, personal data or verification are required, stop and report the blocker. Never click Your details on the ticket summary. Even a yes at the final gate means stopped before payment, not permission to buy. There must be no browser purchase action after that gate.

Record showing, actual seats, ticket counts, total, expiry and tentative calendar event ID in the task folder only. Never claim tickets are booked or paid. Google Calendar uses the installed pi-composio extension, not an MCP server. Discover Google Calendar tools with composio_search, check connection status, then composio_get_schema before composio_execute. If not connected, get a composio_connect link for googlecalendar and report it for Arjun; never enter credentials or use a browser/API workaround. Cinema-only verification may proceed while Calendar is explicitly pending, but cannot be reported as full acceptance. Do not create an event during planning or Phase A exploration.

`skills/cineworld/dag.json` is a template, not live task state. `tasks/` is ignored by git. No custom extension is needed. The harness compacts this session at run end.
