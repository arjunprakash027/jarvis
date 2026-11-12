# Local voice

`jarvis.voice.listen() -> str` waits for Enter, records the default microphone,
then stops on a second Enter and returns `transcribe()`'s text. This is the
brief's permitted terminal push-to-talk fallback: terminals do not reliably
report key-up, so holding Space would need another input mechanism or global
key permissions. There is no wake word or background recording.

`speak(text) -> None` blocks until macOS `say` finishes. Text goes through stdin,
not a shell or command-line options. `transcribe(wav_path) -> str` calls
`whisper-cli` with English, no timestamps and a temporary text output file.
It expects a mono, 16 kHz, signed 16-bit PCM WAV. Recording and transcript
scratch files are deleted on success or failure. Errors propagate to the caller.

## Setup (macOS)

```sh
brew install whisper-cpp
mkdir -p ~/.cache/jarvis/models
for model in base.en small.en; do
  curl -fL --retry 3 -o "$HOME/.cache/jarvis/models/ggml-$model.bin" \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$model.bin"
done
uv sync
```

Homebrew resolves `whisper-cpp` to the `whisper.cpp` formula. Models stay outside
the repository. The Python `sounddevice` dependency supplies PortAudio on macOS.
Grant Microphone access to the hosting terminal when macOS asks (Herdr Core for
an `hc` terminal). No Accessibility or Input Monitoring permission is needed.
A missing microphone, denied permission or audio overflow raises an error rather
than passing damaged input to the router. Ctrl-C/EOF while recording closes the
stream and propagates the interruption.

```sh
uv run python -c 'from jarvis.voice import listen, speak; text = listen(); print(text); speak(text)'
```

The caller should show the returned text on screen; `listen()` does not route
it or manage gates. `p5-up` connects these functions to the main loop. A gate
caller sends the returned text to its waiting gate, not to the router.

## Model and measurement

Selected model: **ggml-base.en.bin** (`~/.cache/jarvis/models/ggml-base.en.bin`).

Latency (s): 1.29

Measured on this Apple M1, 8 GB Mac with Homebrew whisper.cpp 1.9.5, default
Metal acceleration and default four CPU threads. The latency above is the median
of five wall-clock calls to the actual `transcribe()` function, including process
startup, model load, decoding and output-file reading; it excludes recording and
speech playback. The five calls took 1.228, 1.290, 1.007, 1.320 and 1.342 seconds.
All five returned the exact request words.

Before choosing, both models transcribed the same five-second WAV using
`whisper-cli -m MODEL -f tests/fixtures/request.wav -l en -nt`:

| Model | First call (s) | Next two calls (s) | Words |
| --- | ---: | --- | --- |
| base.en | 12.990 | 0.841, 0.480 | All correct |
| small.en | 1.956 | 1.525, 1.128 | All correct |

Base was faster on subsequent calls with equal correctness, so it is selected.
**The very first base call took 12.990 seconds**, before the other measurements;
the under-two-second signal is met after initialization, not guaranteed on first
use. The initial slowdown may include Metal initialization/compilation; its
cause was not isolated. Do one transcription before a demo. These are local
measurements under the current workload, not guarantees for live speech.
Arjun's microphone/voice and audible playback still need the `p9-test` live check;
tests deliberately do not record a microphone or play speech.

## Test audio and verification

`tests/fixtures/request.wav` is synthetic, non-personal audio made by macOS `say`:

> Please add milk, eggs, and bread to my shopping basket for tomorrow morning.

It is mono PCM, 16 kHz, 16-bit, exactly 5.000 seconds and 160,044 bytes (under
200 KB). The spoken audio is 4.526 seconds; trailing silence pads it to five.
To regenerate it:

```sh
say -v Samantha -o tests/fixtures/request.wav --data-format=LEI16@16000 \
  'Please add milk, eggs, and bread to my shopping basket for tomorrow morning.'
uv run python - <<'PY'
import wave
path = 'tests/fixtures/request.wav'
with wave.open(path, 'rb') as recording:
    frames = recording.readframes(recording.getnframes())
assert len(frames) <= 160000
with wave.open(path, 'wb') as recording:
    recording.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
    recording.writeframes(frames + b'\0' * (160000 - len(frames)))
PY
uv run pytest tests/test_voice.py -q
grep -qE 'Latency \(s\): [0-9.]+' docs/voice.md
```

The real integration test requires `whisper-cli` and the selected model; it does
not silently skip if they are missing. Other tests fake audio hardware and `say`
to check recording, cleanup, failures and literal-text speech invocation.
