---
name: sys-widget
description: Query current macOS RAM and SSD space consumption, format taskbar and tooltip widget text, and report metrics.
---

# sys-widget

Inherit base rules in `modules/_base/CLAUDE.md`. Use only the predefined session. The engine dispatches nodes and owns gates. All inspection commands are read-only; never modify system configurations, kill processes, or mutate disk partitions.

## Runtime DAG contract

For every task run, the session writes `tasks/<id>/dag.json` before execution. Validate with `check_dag(dag, [])`:

```json
{
  "task": "Show current RAM and SSD consumption in a taskbar widget",
  "nodes": [
    {"id": "query", "type": "step", "do": "Execute scripts/widget.sh --json to query current RAM and SSD space metrics.", "needs": []},
    {"id": "format", "type": "step", "do": "Format the metrics into taskbar status line and detailed tooltip text.", "needs": ["query"]},
    {"id": "verify", "type": "test", "do": "Verify that reported RAM and SSD metrics are non-empty, within machine limits, and properly structured.", "needs": ["format"], "on_fail": "query"}
  ]
}
```

If `verify` fails, the engine retries up to twice before presenting the recovery gate.

## Querying RAM and SSD

The module provides an executable helper script at `scripts/widget.sh` (or `modules/sys-widget/scripts/widget.sh` from the repo root).

### 1. Widget script modes

- **Full output (default)**: prints the taskbar line, separator, and tooltip detail:
  ```sh
  ./scripts/widget.sh
  ```
- **Taskbar only**:
  ```sh
  ./scripts/widget.sh --taskbar
  ```
  Example output:
  `RAM: 6.3G/8.0G (78%) | SSD: 18Gi/228Gi (45%)`

- **Tooltip only**:
  ```sh
  ./scripts/widget.sh --tooltip
  ```

- **JSON format**:
  ```sh
  ./scripts/widget.sh --json
  ```
  Outputs structured JSON with `ram` and `ssd` objects containing numeric values in GiB and percentages.

### 2. Direct system commands

- Total RAM: `sysctl -n hw.memsize`
- Memory statistics: `vm_stat`
  - Used RAM = `(Pages active + Pages wired down + Pages occupied by compressor) * page_size`
  - Free RAM = `(Pages free + Pages speculative) * page_size`
- SSD space: `df -h /`
  - Reports Size, Used, Available, Capacity percentage on root mount `/`.

## Output conventions

- **Spoken / First Sentence**: Must be 10 words or less, starting with key facts:
  `RAM: 6.3 GB used (78%), SSD: 18 GB used (45%).`
- **Taskbar text**: Single compact line:
  `RAM: <used>G/<total>G (<pct>%) | SSD: <used>/<total> (<pct>%)`
- **Tooltip text**: Multiline breakdown with active, wired, and compressed memory, plus filesystem mount details.

## Verification

The test node `verify` confirms:
1. Output is non-empty and formatted according to contract.
2. RAM used percentage is a valid number between 0% and 100%.
3. Total RAM matches physical hardware (`hw.memsize`).
4. SSD size and used capacity are non-zero.
