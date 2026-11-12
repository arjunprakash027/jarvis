import json
from pathlib import Path

import pytest

from jarvis import router
from jarvis.router import Judgments, Route, decide

MODULES = {
    "shopping": "Buy groceries on Tesco",
    "movies": "Book cinema tickets at Cineworld Dublin",
    "builder": "Build a new tool or a new Jarvis module",
}
CASES = json.loads((Path(__file__).parent / "router_cases.json").read_text())


def j(top="shopping", top_p=0.95, fits=0.95, detail=0.95, long=0.1):
    rest = (1 - top_p) / 2
    probs = {m: (top_p if m == top else rest) for m in MODULES}
    return Judgments(module_probs=probs, fits=fits, detail=detail, long=long)


def test_state_is_request_and_modules():
    assert router.build_state("hi", MODULES) == {"request": "hi", "modules": MODULES}


def test_clear_request_goes_to_module():
    assert decide(j()) == Route(module="shopping")


def test_long_task_flag():
    assert decide(j(top="builder", long=0.9)).long_task is True
    assert decide(j(top="builder", long=0.5)).long_task is False


def test_no_fit():
    assert decide(j(fits=0.1)).kind == "no_fit"


def test_unsettled_fit_asks_which():
    assert decide(j(fits=0.5)).kind == "which"


def test_close_modules_ask_which():
    r = decide(j(top_p=0.5))
    assert r.kind == "which" and "shopping" in r.question


def test_missing_detail_asks_detail():
    assert decide(j(detail=0.1)).kind == "detail"
    assert decide(j(detail=0.5)).kind == "detail"


def test_no_fit_beats_missing_detail():
    assert decide(j(fits=0.1, detail=0.1)).kind == "no_fit"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(router, "ENV_FILE", Path("/nonexistent/.env"))
    with pytest.raises(RuntimeError):
        router.judge("hi", MODULES)


def test_live_cases():
    if not router._api_key():
        pytest.fail("TYPESAFE_API_KEY missing")
    right, wrong = 0, []
    for c in CASES:
        r = router.route(c["request"], MODULES)
        got = r.module or r.kind
        if got == c["expect"]:
            right += 1
        else:
            wrong.append((c["request"], c["expect"], got))
    print(f"router score {right}/{len(CASES)}", wrong)
    assert right >= 13, wrong
