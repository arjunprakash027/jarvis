"""Gates: a macOS popup plus speech. The first answer wins.

A gate id is a Restate awakeable id. `resolve_gate` answers that id only.
The popup runs in its own process, so it survives a restart of the engine service.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

DEFAULT_INGRESS = "http://127.0.0.1:8080"
PID_DIR = Path(tempfile.gettempdir()) / "jarvis-gates"

_APPLESCRIPT = [
    "on run argv",
    'set r to display dialog (item 2 of argv) with title (item 1 of argv) default answer "" '
    'buttons {"No", "Yes"} default button "Yes" giving up after 86400',
    '(button returned of r) & "|" & (text returned of r)',
    "end run",
]


def ingress_url() -> str:
    return os.environ.get("JARVIS_RESTATE_INGRESS", DEFAULT_INGRESS).rstrip("/")


def resolve_gate(gate_id: str, answer: dict, ingress: str | None = None) -> None:
    """Send the answer to the gate with this id, then close its popup."""
    req = urllib.request.Request(
        f"{ingress or ingress_url()}/restate/awakeables/{gate_id}/resolve",
        data=json.dumps(answer).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10).close()
    close_popup(gate_id)


def close_popup(gate_id: str) -> None:
    pid_file = PID_DIR / f"{gate_id}.pid"
    try:
        os.kill(int(pid_file.read_text()), signal.SIGTERM)
    except (OSError, ValueError):
        pass


def ask_popup(gate_id: str, task: str, question: str) -> dict | None:
    """Show the native dialog. Return {"answer": "yes"|"no", "text": str}, or None if closed."""
    PID_DIR.mkdir(exist_ok=True)
    pid_file = PID_DIR / f"{gate_id}.pid"
    cmd = ["osascript"] + [a for line in _APPLESCRIPT for a in ("-e", line)] + ["--", task, question]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    pid_file.write_text(str(proc.pid))
    try:
        out, _ = proc.communicate()
    finally:
        pid_file.unlink(missing_ok=True)
    if proc.returncode != 0 or "|" not in out:
        return None
    button, text = out.strip().split("|", 1)
    return {"answer": button.lower(), "text": text}


def speak(task: str, question: str) -> None:
    subprocess.run(["say", f"{task}. {question}"], check=False)


def open_gate(
    gate_id: str,
    task: str,
    question: str,
    *,
    popup: Callable[[str, str, str], dict | None] = ask_popup,
    say: Callable[[str, str], None] = speak,
    resolve: Callable[[str, dict], None] = resolve_gate,
) -> None:
    """Speak the question and show the popup. Return after the first answer is sent."""
    done = threading.Event()

    def talk() -> None:
        say(task, question)

    def ask() -> None:
        answer = popup(gate_id, task, question)
        if answer is not None and not done.is_set():
            done.set()
            resolve(gate_id, answer)

    threads = [threading.Thread(target=talk), threading.Thread(target=ask)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def spawn_gate(gate_id: str, task: str, question: str) -> None:
    """Start the popup in a separate process and return at once. This is the engine default."""
    subprocess.Popen(
        [sys.executable, "-m", "jarvis.gate", gate_id, task, question],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    open_gate(*sys.argv[1:4])
