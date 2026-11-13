"""Fly-in progress HUD: a small floating window with the live DAG and the latest log lines.

The window is a Swift AppKit program (hud_app.swift) compiled to bin/jarvis-hud. Python keeps
the task state here and sends it as one JSON line on the program's stdin after each change.
Closing stdin tells the window to fade out. Set JARVIS_NO_HUD=1 to never open a window;
under pytest no window opens either. The state functions work the same without a window.
"""

import json
import os
import queue
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

from . import log

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("hud_app.swift")
BINARY = ROOT / "bin/jarvis-hud"
LOG_LINES = 8
ICONS = {"done": "✓", "running": "●", "waiting": "○", "failed": "✗", "gate": "?"}

_state = {"module": "", "task_id": "", "request": "", "nodes": [], "log": deque(maxlen=LOG_LINES)}
_lock = threading.Lock()
_proc = None
_queue: queue.Queue = queue.Queue()
_writer = None


def enabled() -> bool:
    """True when a window should open: macOS, not JARVIS_NO_HUD, not inside pytest."""
    return sys.platform == "darwin" and os.environ.get("JARVIS_NO_HUD", "") != "1" and "pytest" not in sys.modules


def snapshot() -> dict:
    """The state the window shows, as sent on its stdin."""
    with _lock:
        return {"module": _state["module"], "task_id": _state["task_id"], "request": _state["request"],
                "nodes": [dict(n) for n in _state["nodes"]], "log": list(_state["log"])}


def render() -> str:
    """The same state as plain text, one line per node and per log entry (used by tests and `jarvis hud`)."""
    s = snapshot()
    lines = [f"{s['module']}: {s['request']}".strip(": ")]
    lines += [f"{ICONS[n['status']]} {n['id']}" + (f" · {n['note']}" if n.get("note") else "") for n in s["nodes"]]
    lines += [f"  {entry}" for entry in s["log"]]
    return "\n".join(lines)


def node_change(kind: str, text: str) -> tuple[str, str, str] | None:
    """Read a `node` or `gate` event. Return (node id, new status, note), or None if it is no change."""
    if kind not in ("node", "gate") or ": " not in text:
        return None
    node_id, _, what = text.partition(": ")
    note = what.split(" · ", 1)[1].strip('"') if " · " in what else ""
    if kind == "gate":
        return node_id, ("gate" if what.startswith("waiting") else "done"), what if what.startswith("waiting") else ""
    if what.startswith("ok"):
        return node_id, "done", note
    if what.startswith("failed"):
        return node_id, "failed", note or what
    if what.startswith(("running", "retrying", "still running")):
        return node_id, "running", what if what.startswith("still") else ""
    return None


def start(module: str, task_id: str, request: str) -> None:
    """Begin showing a task. Opens the window when enabled; the DAG arrives with update_dag."""
    global _proc
    with _lock:
        _state.update(module=module, task_id=task_id, request=request, nodes=[])
        _state["log"].clear()
    if _listener not in log.listeners:
        log.listeners.append(_listener)
    if enabled() and (_proc is None or _proc.poll() is not None):
        _proc = _spawn()
    _send()


def update_dag(nodes: list[dict]) -> None:
    """Show these DAG nodes (dag.json `nodes`); each starts as waiting."""
    with _lock:
        _state["nodes"] = [{"id": n["id"], "type": n.get("type", "step"), "status": "waiting", "note": ""} for n in nodes]
    _send()


def add_log(kind: str, text: str) -> None:
    """Append a log line and move the node it names, if any."""
    with _lock:
        _state["log"].append(f"{kind} {text}".strip())
        change = node_change(kind, text)
        if change:
            node_id, status, note = change
            for n in _state["nodes"]:
                if n["id"] == node_id:
                    n.update(status=status, note=note)
    _send()


def stop() -> None:
    """The task ended: send the final state and let the window fade out."""
    global _proc
    _send()
    if _proc is not None:
        _queue.put((_proc, None))
        _proc = None


def _listener(kind: str, text: str) -> None:
    if _state["module"]:
        add_log(kind, text)


def _send() -> None:
    if _proc is not None:
        _queue.put((_proc, json.dumps(snapshot()) + "\n"))


def _spawn():
    """Start bin/jarvis-hud, compiling it from hud_app.swift first when it is missing."""
    global _writer
    if BINARY.is_file():
        cmd = [str(BINARY)]
    else:
        BINARY.parent.mkdir(exist_ok=True)
        cmd = ["sh", "-c", f'swiftc -O -o "$1" "$2" 2>/dev/null && exec "$1"', "hud", str(BINARY), str(SOURCE)]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    except OSError:
        return None
    if _writer is None or not _writer.is_alive():
        _writer = threading.Thread(target=_drain, daemon=True)
        _writer.start()
    return proc


def _drain() -> None:
    """A slow or dead window must never stall the task: writes happen on this thread."""
    while True:
        proc, item = _queue.get()
        try:
            if item is None:
                proc.stdin.close()
            else:
                proc.stdin.write(item)
                proc.stdin.flush()
        except (OSError, ValueError):
            pass
