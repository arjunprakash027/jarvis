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


OTHER = "Other…"
_CHOOSE = [
    "on run argv",
    "set multi to (item 3 of argv is \"1\")",
    "set r to choose from list (items 4 thru -1 of argv) with title (item 1 of argv) with prompt (item 2 of argv) "
    "multiple selections allowed multi OK button name \"Choose\" cancel button name \"No\"",
    'if r is false then return "no"',
    "set AppleScript's text item delimiters to linefeed",
    'return "yes" & linefeed & (r as text)',
    "end run",
]


def choose_command(task: str, question: str, choices: list[str], multi: bool = False) -> list[str]:
    """The osascript command for a choose-from-list popup. The last entry is Other…."""
    items = [c.replace("\n", " ") for c in choices] + [OTHER]
    return ["osascript"] + [a for line in _CHOOSE for a in ("-e", line)] + ["--", task, question, "1" if multi else "0", *items]


def _run(gate_id: str, cmd: list[str]) -> str | None:
    """Run a popup process. Return its output, or None if it was closed or failed."""
    PID_DIR.mkdir(exist_ok=True)
    pid_file = PID_DIR / f"{gate_id}.pid"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    pid_file.write_text(str(proc.pid))
    try:
        out, _ = proc.communicate()
    finally:
        pid_file.unlink(missing_ok=True)
    return out.strip() if proc.returncode == 0 else None


def ask_text(gate_id: str, task: str, question: str) -> dict | None:
    cmd = ["osascript"] + [a for line in _APPLESCRIPT for a in ("-e", line)] + ["--", task, question]
    out = _run(gate_id, cmd)
    if out is None or "|" not in out:
        return None
    button, text = out.split("|", 1)
    return {"answer": button.lower(), "text": text}


def ask_popup(gate_id: str, task: str, question: str, choices: list[str] | None = None, multi: bool = False) -> dict | None:
    """Show the native dialog. Return {"answer": "yes"|"no", "text": str}, or None if closed.

    With choices it is a list to pick from (Other… opens the text dialog). Cancel is no.
    """
    if not choices:
        return ask_text(gate_id, task, question)
    out = _run(gate_id, choose_command(task, question, choices, multi))
    if out is None:
        return None
    first, *picked = out.split("\n")
    if first != "yes":
        return {"answer": "no", "text": ""}
    if OTHER in picked:
        return ask_text(gate_id, task, question)
    return {"answer": "yes", "text": ", ".join(picked)}


SPOKEN_WORDS = 18  # Arjun: what Jarvis says must be very short; the popup shows the full text


def brief(text: str, words: int = SPOKEN_WORDS) -> str:
    """The short form that Jarvis speaks: at most `words` words."""
    parts = text.split()
    return " ".join(parts[:words]) if len(parts) > words else text


def spoken(task: str, question: str, choices: list[str] | None = None) -> str:
    """What Jarvis says: at most 18 words. Up to 3 choices if they fit, else a pointer to the popup."""
    base = f"{task}. {question}"
    if not choices:
        return brief(base)
    listed = " ".join(f"{i}. {c}" for i, c in enumerate(choices[:3], 1))
    if len(f"{base} {listed}".split()) <= SPOKEN_WORDS:
        return f"{base} {listed}"
    return brief(base, SPOKEN_WORDS - 5) + " Pick one in the popup."


def speak(task: str, question: str, choices: list[str] | None = None) -> None:
    subprocess.run(["say", spoken(task, question, choices)], check=False)


NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}


def pick_choices(text: str, choices: list[str], multi: bool = False) -> list[str]:
    """Choices that a typed or spoken answer names: by number ("2", "two") or by name. [] if none."""
    low = text.lower()
    named = [c for c in choices if c.lower() in low]
    if named:
        return named if multi else named[:1]
    tokens = [t for t in low.replace(",", " ").replace(".", " ").split() if t not in ("number", "option")]
    # "one" is also a pronoun ("the dune one"), so it counts only as the first word.
    picked = [choices[n - 1] for i, t in enumerate(tokens)
              if 1 <= (n := int(t) if t.isdigit() else NUMBERS.get(t, 0) if t != "one" or i == 0 else 0) <= len(choices)]
    return picked if multi else picked[:1]


def open_gate(
    gate_id: str,
    task: str,
    question: str,
    choices: list[str] | None = None,
    multi: bool = False,
    *,
    popup: Callable[..., dict | None] = ask_popup,
    say: Callable[..., None] = speak,
    resolve: Callable[[str, dict], None] = resolve_gate,
) -> None:
    """Speak the question and show the popup. Return after the first answer is sent."""
    done = threading.Event()
    extra = (choices, multi) if choices else ()

    def talk() -> None:
        say(task, question, *((choices,) if choices else ()))

    def ask() -> None:
        answer = popup(gate_id, task, question, *extra)
        if answer is not None and not done.is_set():
            done.set()
            resolve(gate_id, answer)

    threads = [threading.Thread(target=talk), threading.Thread(target=ask)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def spawn_gate(gate_id: str, task: str, question: str, choices: list[str] | None = None, multi: bool = False) -> None:
    """Start the popup in a separate process and return at once. This is the engine default."""
    extra = [json.dumps(choices), "1" if multi else "0"] if choices else []
    subprocess.Popen(
        [sys.executable, "-m", "jarvis.gate", gate_id, task, question, *extra],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    open_gate(*args[:3], *((json.loads(args[3]), args[4] == "1") if len(args) > 4 else ()))
