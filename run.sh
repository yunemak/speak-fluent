#!/usr/bin/env bash
set -Eeuo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

[[ -x .venv/bin/python ]] || fail 'Run the one-time setup in README.md first (missing .venv).'
command -v npm >/dev/null || fail 'Install Node.js 22.12+ and npm first.'
command -v setsid >/dev/null || fail 'Install util-linux (setsid) first.'
[[ -x frontend/node_modules/.bin/vite ]] || fail 'Run: npm --prefix frontend ci'
.venv/bin/python -c 'import uvicorn' 2>/dev/null || fail 'Run: .venv/bin/python -m pip install -r backend/requirements.txt'

# Each service gets its own process group so npm's child processes stop too.
pids=()
cleanup() {
    trap '' INT TERM
    if ((${#pids[@]})); then
        printf '\nStopping Speak Fluent...\n'
        for pid in "${pids[@]}"; do
            kill -TERM -- "-$pid" 2>/dev/null || true
        done
        wait "${pids[@]}" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start() {
    setsid "$@" &
    pids+=("$!")
}

export SPEAK_FLUENT_OLLAMA_URL="${SPEAK_FLUENT_OLLAMA_URL:-http://127.0.0.1:11434}"
ollama_ready() {
    .venv/bin/python - <<'PY'
import json
import os
import sys
import urllib.request

try:
    url = os.environ['SPEAK_FLUENT_OLLAMA_URL'].rstrip('/') + '/api/tags'
    with urllib.request.urlopen(url, timeout=1) as response:
        assert isinstance(json.load(response)['models'], list)
except Exception:
    sys.exit(1)
PY
}

if ollama_ready; then
    printf 'Using Ollama at %s\n' "$SPEAK_FLUENT_OLLAMA_URL"
else
    ollama_pid=''
    # An existing Ollama may already be listening while it discovers GPUs.
    if .venv/bin/python - <<'PY'
import os
import socket
import sys
from urllib.parse import urlsplit

url = urlsplit(os.environ['SPEAK_FLUENT_OLLAMA_URL'])
try:
    with socket.create_connection((url.hostname, url.port or (443 if url.scheme == 'https' else 80)), timeout=1):
        pass
except OSError:
    sys.exit(1)
PY
    then
        printf 'Waiting for Ollama at %s...\n' "$SPEAK_FLUENT_OLLAMA_URL"
    else
        [[ "${SPEAK_FLUENT_OLLAMA_URL%/}" == 'http://127.0.0.1:11434' ]] || \
            fail "Cannot reach Ollama at $SPEAK_FLUENT_OLLAMA_URL. Start that server first."
        if [[ -x .tools/ollama/bin/ollama ]]; then
            ollama="$PWD/.tools/ollama/bin/ollama"
        else
            ollama="$(command -v ollama)" || fail 'Install Ollama and download the models described in README.md.'
        fi
        printf 'Starting Ollama...\n'
        start env OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 "$ollama" serve
        ollama_pid="${pids[0]}"
    fi
    ready=false
    for ((attempt = 0; attempt < 30; attempt++)); do
        if [[ -n "$ollama_pid" ]]; then
            kill -0 "$ollama_pid" 2>/dev/null || fail 'Ollama exited during startup. See its output above.'
        fi
        if ollama_ready; then
            ready=true
            break
        fi
        sleep 1
    done
    "$ready" || fail 'Ollama did not become ready. See its output above.'
fi

printf 'Starting backend and frontend...\n'
start .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
start npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
printf '\nOpen http://127.0.0.1:5173 once the servers are ready. Press Ctrl+C to stop.\n\n'

# A failed service should not leave the other services running unnoticed.
status=0
wait -n "${pids[@]}" || status=$?
printf '\nA service exited; shutting down Speak Fluent.\n' >&2
((status != 0)) || status=1
exit "$status"
