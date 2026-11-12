"""One real whisper.cpp transcription; microphone/speaker tests use fakes."""

from pathlib import Path
import string
import subprocess
import wave

import pytest

from jarvis import voice

FIXTURE = Path(__file__).parent / "fixtures/request.wav"
REQUEST = "Please add milk, eggs, and bread to my shopping basket for tomorrow morning."


def test_transcribe_recorded_request():
    with wave.open(str(FIXTURE)) as recording:
        assert recording.getparams()[:3] == (1, 2, 16000)
        assert recording.getnframes() / recording.getframerate() == 5
    text = voice.transcribe(FIXTURE)
    normalize = lambda value: value.lower().translate(str.maketrans("", "", string.punctuation)).split()
    assert normalize(text) == normalize(REQUEST)


def test_missing_model(monkeypatch, tmp_path):
    monkeypatch.setattr(voice, "MODEL_PATH", tmp_path / "missing.bin")
    with pytest.raises(FileNotFoundError, match="Missing whisper model"):
        voice.transcribe(FIXTURE)


def test_transcription_failure_is_not_returned_as_text(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="invalid audio")

    monkeypatch.setattr(voice.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        voice.transcribe(FIXTURE)


def test_listen_records_then_transcribes_and_removes_audio(monkeypatch):
    prompts = []
    paths = []
    closed = []

    class Stream:
        def __init__(self, **kwargs):
            assert kwargs["samplerate"] == 16000
            assert kwargs["channels"] == 1
            assert kwargs["dtype"] == "int16"
            self.callback = kwargs["callback"]

        def __enter__(self):
            self.callback(b"\0\0" * 16000, 16000, None, None)

        def __exit__(self, *args):
            closed.append(True)

    def transcribe(path):
        assert closed
        with wave.open(str(path)) as recording:
            assert recording.getnframes() == 16000
        paths.append(path)
        return REQUEST

    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt))
    monkeypatch.setattr(voice.sd, "RawInputStream", Stream)
    monkeypatch.setattr(voice, "transcribe", transcribe)
    assert voice.listen() == REQUEST
    assert len(prompts) == 2
    assert not paths[0].exists()


@pytest.mark.parametrize("status", [None, "input overflow"])
def test_listen_rejects_empty_or_damaged_recording(monkeypatch, status):
    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]

        def __enter__(self):
            self.callback(b"", 0, None, status)

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("builtins.input", lambda prompt: None)
    monkeypatch.setattr(voice.sd, "RawInputStream", Stream)
    with pytest.raises(RuntimeError, match="recording failed|no audio"):
        voice.listen()


def test_listen_closes_microphone_on_eof(monkeypatch):
    closed = []
    prompts = iter([None, EOFError()])

    class Stream:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            pass

        def __exit__(self, *args):
            closed.append(True)

    def enter(prompt):
        result = next(prompts)
        if isinstance(result, EOFError):
            raise result

    monkeypatch.setattr("builtins.input", enter)
    monkeypatch.setattr(voice.sd, "RawInputStream", Stream)
    with pytest.raises(EOFError):
        voice.listen()
    assert closed == [True]


def test_speak_sends_literal_text_on_stdin(monkeypatch):
    calls = []
    monkeypatch.setattr(voice.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    text = "-o do-not-create-a-file; $(echo not-a-command)"
    voice.speak(text)
    assert calls == [((["say"],), {"input": text, "text": True, "check": True})]
