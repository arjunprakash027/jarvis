# Restate proof

Date: 12 November 2026. Machine: the M1 Mac. Time used: under 10 minutes.

## What I tried

- Installed `restate-server` 1.8.1 and the `restate` CLI with `brew install restatedev/tap/restate-server restatedev/tap/restate`.
- Added the Python library with `uv add "restate-sdk[serve]"` (restate-sdk 1.5.1). The `serve` extra brings uvicorn, which `python -m restate serve module:app` needs.
- Wrote a small service. It has one Virtual Object named `module`. Its handler runs a stored step, makes an awakeable (the gate), waits for it, and runs a second stored step. Each step writes a line to a log file when it really runs.
- Started the server, started the service, and registered it with `restate deployments register http://localhost:9080`.

## What I saw

1. One Virtual Object for each module. I sent request A and request B to the key `shopping`, and request C to the key `movies`. A started and stopped at its gate. B did not start. C started at once, because it has a different key. After I answered A, B started.
2. A gate that waits. The awakeable id went to the log. The handler slept on it. The ingress call `POST /restate/awakeables/<id>/resolve` woke it.
3. A restart at the gate. I killed the Python service with `kill -9` while A and C waited. I started it again. Restate called the handler again and replayed the journal. The step `step1` did not run a second time. I resolved the awakeable of A. A ran `step2` once and ended. B then started. A has one `EXEC step1` line and one `EXEC step2` line in the log.

## Notes for the engine

- Restate retries a stored step that raises an error, without a limit. The engine must catch each error inside the step and return it as data.
- The code of the handler runs again after a restart. Only the stored steps are skipped. The walk must use only stored results, so it takes the same path again.
- The awakeable id is the gate id. Any program can resolve it with an HTTP call. The popup can be a separate process that survives a restart of the service.

Result: pass. A Virtual Object for each module, a waiting gate and a restart at the gate all work on this Mac, and done steps do not run again.
