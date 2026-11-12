"""Local microphone input, whisper.cpp transcription and macOS speech."""

from pathlib import Path
import subprocess
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


def listen() -> str:
    """Press Enter to start, speak, then press Enter to stop; return the text."""
    frames = bytearray()

    def capture(data, frame_count, time_info, status):
        if status:
            errors.append(str(status))
        frames.extend(data)

    errors: list[str] = []
    input("Press Enter to start recording. ")
    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=capture,
    ):
        input("Recording — press Enter to stop. ")
    if errors:
        raise RuntimeError(f"Microphone recording failed: {'; '.join(errors)}")
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
