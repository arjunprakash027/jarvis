"""Gate popup helpers. No real popup is opened here."""

from unittest.mock import patch

from jarvis import gate

FILMS = ["I Play Rocky 19:30", "Dune 20:00", "Up 18:00", "Heat 21:00"]


def test_choose_command_single_and_multi():
    single = gate.choose_command("Movies", "Which film?", FILMS[:2])
    assert single[0] == "osascript" and "--" in single
    assert single[single.index("--") + 1:] == ["Movies", "Which film?", "0", FILMS[0], FILMS[1], "Other…"]
    assert any("choose from list" in a for a in single)
    multi = gate.choose_command("Movies", "Which?", FILMS[:2], multi=True)
    assert multi[multi.index("--") + 3] == "1"


def run_popup(output, **kw):
    with patch.object(gate, "_run", return_value=output) as run:
        return gate.ask_popup("g1", "Movies", "Which?", FILMS[:2], **kw), run


def test_picking_returns_exact_text():
    answer, _ = run_popup("yes\nDune 20:00")
    assert answer == {"answer": "yes", "text": "Dune 20:00"}
    answer, _ = run_popup("yes\nDune 20:00\nHeat 21:00", multi=True)
    assert answer == {"answer": "yes", "text": "Dune 20:00, Heat 21:00"}


def test_cancel_is_no_and_closed_is_none():
    assert run_popup("no")[0] == {"answer": "no", "text": ""}
    assert run_popup(None)[0] is None


def test_other_opens_text_dialog():
    with patch.object(gate, "_run", side_effect=["yes\nOther…", "Yes|something else"]) as run:
        answer = gate.ask_popup("g1", "Movies", "Which?", FILMS[:2])
    assert answer == {"answer": "yes", "text": "something else"}
    assert run.call_count == 2


def test_no_choices_uses_text_dialog_only():
    with patch.object(gate, "_run", return_value="No|") as run:
        assert gate.ask_popup("g1", "t", "q") == {"answer": "no", "text": ""}
    assert "choose from list" not in " ".join(run.call_args[0][1])


def test_pick_choices_by_number_and_name():
    assert gate.pick_choices("2", FILMS) == [FILMS[1]]
    assert gate.pick_choices("Two.", FILMS) == [FILMS[1]]
    assert gate.pick_choices("the dune 20:00 one", FILMS) == [FILMS[1]]
    assert gate.pick_choices("1 and 3", FILMS) == [FILMS[0]]
    assert gate.pick_choices("1 and 3", FILMS, multi=True) == [FILMS[0], FILMS[2]]
    assert gate.pick_choices("9", FILMS) == [] and gate.pick_choices("yes", FILMS) == []


def test_spoken_is_short_and_lists_choices_only_if_they_fit():
    assert gate.spoken("Movies", "Pick?", ["Rocky", "Dune"]) == "Movies. Pick? 1. Rocky 2. Dune"
    long = gate.spoken("Cineworld Dublin", "choose one of the live Saturday film and time options from find showings", FILMS)
    assert long.endswith("Pick one in the popup.") and len(long.split()) <= 18
    assert gate.spoken("t", "q") == "t. q"


def test_open_gate_passes_choices_only_when_present():
    got = []
    gate.open_gate("g", "t", "q", ["a", "b"], True, popup=lambda *a: got.append(a), say=lambda *a: got.append(a),
                   resolve=lambda *a: None)
    assert ("g", "t", "q", ["a", "b"], True) in got and ("t", "q", ["a", "b"]) in got
