# Tesco verification record

## Phase A
Manually explored search, add, review and empty-basket confirmation using ego-browser. This was site exploration, not an engine run.

## Phase B: one real typed run
After merging the harness and results-flow fixes, ran from the p6-shopping worktree root:

```sh
uv run jarvis up --text
```

Submitted once: `add milk, eggs and bread to my tesco basket`.
Module session: `jarvis-shopping`, model `openai/gpt-6.1-sol`.
Task ID: `69b22d037cb04e8ab09db441283eaa1e`.
Runtime DAG, node results, session and task log remain in ignored `tasks/`, not git.

DAG validation:

```text
uv run jarvis dag check modules/shopping/tasks/69b22d037cb04e8ab09db441283eaa1e/dag.json
OK
```

Actual engine output:

```text
shopping: done.
search: ok
basket: ok
verify: passed
pay: waits at gate [runtime awakeable id omitted]
pay: gate yes
compact: ok
```

The test returned `ok: true` and began: "Basket verified: estimated EUR 9.35, three items." It verified exactly one each of Tesco Fresh Milk1ltr (EUR 1.15), Tesco Free Range Eggs Medium Box Of 12 (EUR 4.35) and Tesco Medium Sliced White Bread 800g (EUR 0.85). Items 3, guide price EUR 6.35, minimum-basket charge EUR 3.00, estimated total EUR 9.35. No delivery slot selected; not a final delivered total.

The last node was the engine-owned `pay` gate with `needs: ["verify"]`; the engine appended the verify output, including the real total, to the question. It ended the demo on the basket review page, before checkout/payment. All four nodes completed. No card data entered, no payment/order, no slot booked. Compaction was confirmed by the harness; this run alone does not prove a smaller next provider prompt.

### Gate and cleanup deviation
The plan was to type `no, undo`. Instead the popup resolved **yes** before the implementer typed any answer. The engine ended successfully without dispatching undo. We did not resubmit the request or fabricate a declined/undo result.

The implementer then manually cleaned up the same ego-browser TaskSpace (17): confirmed the trolley still held just these three additions, clicked Empty Basket, confirmed Empty basket, waited for the empty message and reloaded. Confirmed Items 0 and Guide price EUR 0.00. Tesco still showed a EUR 3.00 minimum charge/estimate on the empty trolley; this was not a leftover item. Finished the TaskSpace with no pages kept.

Stopped jarvis up with Ctrl-C, confirmed exit 0, then removed the shared live-run lock. **Engine-driven `no, undo` cleanup is not verified by this run; actual manual cleanup is verified.**
