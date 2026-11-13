#!/usr/bin/env bash
# Set up Jarvis on a Mac.
#
#   scripts/install.sh           install what is missing, then check
#   scripts/install.sh --check   check only, change nothing
#   scripts/install.sh --test    install, then also run the tests
#
# The script is safe to run again. It never overwrites .env, never prints a key,
# and never signs in to an account for you.

set -euo pipefail

MODE="install"
RUN_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --test) RUN_TESTS=1 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (use --check, --test or --help)" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="$HOME/.cache/jarvis/models"
MODEL="$MODEL_DIR/ggml-base.en.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"

if [ -t 1 ]; then
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
else
  GREEN=""; YELLOW=""; RED=""; BOLD=""; OFF=""
fi
MISSING=0   # a required part is absent
TODO=()     # steps only the person can do

ok()    { printf '%s  ok   %s %s\n' "$GREEN" "$OFF" "$1"; }
warn()  { printf '%s  note %s %s\n' "$YELLOW" "$OFF" "$1"; }
bad()   { printf '%s  miss %s %s\n' "$RED" "$OFF" "$1"; MISSING=1; }
step()  { printf '\n%s%s%s\n' "$BOLD" "$1" "$OFF"; }
have()  { command -v "$1" >/dev/null 2>&1; }

# brew_tool <command> <formula> <what it is for>
brew_tool() {
  local cmd="$1" formula="$2" why="$3"
  if have "$cmd"; then
    ok "$cmd ($why)"
  elif [ "$MODE" = "check" ]; then
    bad "$cmd is missing ($why). Install: brew install $formula"
  else
    echo "  Installing $formula ..."
    brew install "$formula"
    ok "$cmd installed ($why)"
  fi
}

step "1. System"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "Jarvis runs on macOS only: it uses say, osascript and AppKit." >&2
  exit 1
fi
ok "macOS $(sw_vers -productVersion)"
if ! have brew; then
  echo "Homebrew is missing. Install it from https://brew.sh, then run this script again." >&2
  exit 1
fi
ok "Homebrew"

step "2. Tools from Homebrew"
brew_tool uv uv "Python and the package"
brew_tool whisper-cli whisper-cpp "local speech to text"
brew_tool restate-server restatedev/tap/restate-server "the task engine"
brew_tool restate restatedev/tap/restate "the task engine command line"
brew_tool pi pi-coding-agent "the agent in each module session"

step "3. Tools this script does not install"
if have hc; then
  ok "hc (Herdr Core: keeps each agent session alive in a terminal)"
else
  bad "hc is missing. Install Herdr Core, then run this script again."
fi
if have swiftc; then
  ok "swiftc (builds the progress window on first use)"
else
  warn "swiftc is missing. The progress window and the hotkey stay off. Install: xcode-select --install"
fi

step "4. Speech model"
if [ -s "$MODEL" ]; then
  ok "$MODEL"
elif [ "$MODE" = "check" ]; then
  bad "Speech model is missing: $MODEL"
else
  echo "  Downloading ggml-base.en.bin (about 140 MB) ..."
  mkdir -p "$MODEL_DIR"
  curl -fL --retry 3 --progress-bar -o "$MODEL.part" "$MODEL_URL"
  mv "$MODEL.part" "$MODEL"
  ok "$MODEL"
fi

step "5. Python package"
if [ "$MODE" = "check" ]; then
  if [ -d "$ROOT/.venv" ]; then ok ".venv exists"; else bad ".venv is missing. Run: uv sync"; fi
else
  (cd "$ROOT" && uv sync --quiet)
  ok "uv sync"
fi

step "6. TypeSafe key"
ENV_FILE="$ROOT/.env"
if [ -n "${TYPESAFE_API_KEY:-}" ]; then
  ok "TYPESAFE_API_KEY is set in the environment"
elif [ -f "$ENV_FILE" ] && grep -Eq '^[[:space:]]*TYPESAFE_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]' "$ENV_FILE"; then
  ok "TYPESAFE_API_KEY is set in .env"
else
  if [ "$MODE" = "install" ] && [ ! -f "$ENV_FILE" ]; then
    (umask 077 && printf 'TYPESAFE_API_KEY=\n' > "$ENV_FILE")
    warn "Made an empty .env (git ignores it)."
  fi
  TODO+=("Put your TypeSafe key in $ENV_FILE as TYPESAFE_API_KEY=... The router needs it.")
fi

step "7. Check"
if [ -d "$ROOT/.venv" ] && have uv; then
  if modules="$(cd "$ROOT" && uv run --quiet jarvis modules 2>&1)"; then
    ok "jarvis modules:"
    printf '%s\n' "$modules" | sed 's/^/         /'
  else
    bad "jarvis modules failed:"
    printf '%s\n' "$modules" | sed 's/^/         /'
  fi
  if [ "$RUN_TESTS" = "1" ]; then
    (cd "$ROOT" && uv run pytest -q)
  fi
fi

TODO+=("Sign in to a model provider in pi (run: pi). Then set that model in each modules/<name>/module.toml.")
TODO+=("Start Jarvis: uv run jarvis up   (or: uv run jarvis up --text  to type and use no microphone)")

step "Left for you"
for item in "${TODO[@]}"; do
  printf '  - %s\n' "$item"
done

if [ "$MISSING" = "1" ]; then
  printf '\n%sSome required parts are missing. See the "miss" lines above.%s\n' "$RED" "$OFF"
  exit 1
fi
printf '\n%sSetup is complete.%s\n' "$GREEN" "$OFF"
