"""One timestamped line per event: printed in the terminal and appended to a log file."""

import os
import threading
import time
from pathlib import Path

listeners = []  # the voice piece can append fn(kind, text); keep them quick
_lock = threading.Lock()


def log_path() -> Path:
    return Path(os.environ.get("JARVIS_LOG") or Path.home() / ".local/share/jarvis/jarvis.log")


def headline(text, limit: int = 80) -> str:
    """The first sentence of a node output, at most `limit` characters."""
    first = " ".join(str(text).split()).split(". ")[0].rstrip(".")
    return first if len(first) <= limit else first[: limit - 1] + "…"


def event(kind: str, text: str = "") -> None:
    line = f"{time.strftime('%H:%M:%S')} {kind:<8} {text}".rstrip()
    with _lock:
        print(line, flush=True)
        try:
            path = log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass  # a full disk must not stop a task
    for listener in list(listeners):
        try:
            listener(kind, text)
        except Exception:
            pass


def follow(stream=None, *, lines: int = 50, poll: float = 0.5, stop=lambda: False) -> None:
    """Print the last `lines` lines of the log, then new ones as they arrive (tail -f)."""
    import sys
    out = stream or sys.stdout
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    with open(path) as f:
        for line in f.read().splitlines()[-lines:]:
            print(line, file=out, flush=True)
        while not stop():
            line = f.readline()
            if line:
                print(line.rstrip("\n"), file=out, flush=True)
            else:
                time.sleep(poll)
