"""Local microphone input, whisper.cpp transcription and macOS speech."""

from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import wave

import sounddevice as sd

MODEL_PATH = Path.home() / ".cache/jarvis/models/ggml-base.en.bin"
SAMPLE_RATE = 16000


def transcribe(wav_path: str | Path) -> str:
    """Transcribe a 16 kHz mono PCM WAV with the selected local model."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Missing whisper model: {MODEL_PATH}; see docs/voice.md")
    with tempfile.TemporaryDirectory(prefix="jarvis-transcribe-") as directory:
        output = Path(directory) / "transcript"
        subprocess.run(
            [
                "whisper-cli", "-m", str(MODEL_PATH), "-f", str(wav_path),
                "-l", "en", "-nt", "-otxt", "-of", str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return output.with_suffix(".txt").read_text().strip()


def _record_here() -> bytes:
    """Record in this process until Enter. Used by the child recorder and by tests."""
    frames = bytearray()
    errors: list[str] = []

    def capture(data, frame_count, time_info, status):
        if status:
            errors.append(str(status))
        frames.extend(data)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=capture,
    ):
        input("Recording — press Enter to stop. ")
    if errors:
        raise RuntimeError(f"Microphone recording failed: {'; '.join(errors)}")
    return bytes(frames)


def _record_in_child() -> bytes:
    """Record in a child process and kill it on Enter.

    Stopping a CoreAudio stream inside the busy `jarvis up` process can deadlock
    (seen on 12 Nov 2026). A child that is killed never needs a clean stop.
    """
    child = subprocess.Popen([sys.executable, "-m", "jarvis.voice"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    chunks: list[bytes] = []
    reader = threading.Thread(target=lambda: chunks.extend(iter(lambda: child.stdout.read(3200), b"")), daemon=True)
    reader.start()
    try:
        input("Recording — press Enter to stop. ")
    finally:
        child.kill()
        child.wait()
        reader.join(timeout=2)
    return b"".join(chunks)


RECORDER = _record_in_child


def listen() -> str:
    """Press Enter to start, speak, then press Enter to stop; return the text."""
    input("Press Enter to start recording. ")
    frames = RECORDER()
    if not frames:
        raise RuntimeError("The microphone recorded no audio.")
    with tempfile.TemporaryDirectory(prefix="jarvis-recording-") as directory:
        wav_path = Path(directory) / "request.wav"
        with wave.open(str(wav_path), "wb") as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(SAMPLE_RATE)
            recording.writeframes(frames)
        return transcribe(wav_path)


def speak(text: str) -> None:
    """Speak literal text synchronously, without shell or option interpretation."""
    subprocess.run(["say"], input=text, text=True, check=True)


if __name__ == "__main__":
    # Child recorder: stream raw 16 kHz mono PCM to stdout until the parent kills us.
    out = sys.stdout.buffer

    def _send(data, frame_count, time_info, status):
        out.write(bytes(data))
        out.flush()

    with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=_send):
        threading.Event().wait()
