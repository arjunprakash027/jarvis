# Interactive pi compaction

Compaction: `hc keys jarvis-<module> / c o m p a c t enter` sends the native `/compact` command to the running interactive pi editor. Wait for a new `compaction` entry in that session's JSONL file; do not rely on `hc wait` alone for slash commands.

Tested on 12 November 2026 with pi 1.4.0 and hc 0.1.20 in throwaway interactive terminals, using antigravity/gemini-3-8-flash. No print mode or RPC session was used.

## What happened

- `hc send <terminal> /compact` did **not** invoke the command. hc wrapped it in `<hc from=...>` and the model answered it as an ordinary message.
- `hc keys <terminal> / c o m p a c t enter` invoked the built-in command. Pi showed “Compacting context” and persisted a `compaction` entry with `tokensBefore`, summary and `firstKeptEntryId`.
- The first session recorded compactions at 15,368, 16,642 and 24,126 tokens. The following model input sizes were 15,759, 16,859 and 24,517 tokens respectively: **not smaller**.
- A second throwaway session used project `compaction.keepRecentTokens=1000`. Compactions at 19,697 and 26,479 tokens were followed by model input sizes of 20,088 and 26,870. Again **not smaller**. A too-small session also reported “Nothing to compact”.

## Larger-context OpenAI check

The installed catalog did not include `openai/gpt-6.1-mini`. The supervisor approved `openai/gpt-5.4-mini`, but that model returned HTTP 400 (unsupported with this ChatGPT account). The supervisor then approved `openai/gpt-6-luna`.

In throwaway terminal `jv-openai-compact`, pi read eight 100-line text files (5,000 random words each). Its last assistant usage recorded **47,000 input tokens**. Native `/compact` persisted `tokensBefore=47005` and a 1,768-character summary. After sending “Reply only ok”, the next assistant usage recorded **1,353 input tokens**. This proves external compaction with a smaller actual provider prompt on this model. Project `keepRecentTokens` was 1,000 in the throwaway directory; this is a local test setting, not a change to the person's global settings.

A persisted compaction event alone is not evidence of a smaller provider prompt: the earlier antigravity tests did not shrink. The harness confirms the persisted event; intended module models still need their own before/after check.

## End-to-end module runs

A throwaway local module then ran twice through real `jarvis up --text`, Jev, Restate and the same interactive `jarvis-p5live` terminal on `openai/gpt-6-luna`. Each task read eight large files in separate step nodes, passed a test and resolved its native gate. With ordinary recent-context retention, the first run compacted **60,560 → 24,415** tokens and the second **75,072 → 25,315** (the next provider input after each persisted compaction). Both engine traces reported `compact: ok`.

A supplementary gate-first task was declined by a typed `no` sent to `jarvis up --text`, targeting its own awakeable id. It had executed no agent nodes, so pi reported “Already compacted”. Like “Nothing to compact”, that is a no-op, not evidence of a new reduction. The harness logs either condition rather than failing an otherwise completed run.

Pi's installed `docs/slash-commands.md` documents `/compact`; `docs/compaction.md` documents summary + retained recent messages and the `tokensBefore` field. Compaction does not shrink the JSONL file itself: it appends a summary and selects a retained boundary.
