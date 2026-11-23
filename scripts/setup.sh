#!/usr/bin/env bash
# Check or install the parts of the specialist scout plugin that need downloads.
# The embedding model is sentence-transformers/all-MiniLM-L6-v2 (Apache-2.0), ONNX file from its own repository.
#   setup.sh status       read-only: what is installed (default)
#   setup.sh roster       clone the agency-agents roster into the plugin data folder
#   setup.sh embeddings   create the virtualenv, download the pinned model, verify checksums
#   setup.sh all          roster, then embeddings
# Nothing here runs unless the user has asked for it (see commands/setup.md).
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.cache/specialist-scout}"
ROSTER_REPO="${AGENCY_ROSTER_REPO:-https://github.com/msitarzewski/agency-agents.git}"
MODEL_REVISION="1110a243fdf4706b3f48f1d95db1a4f5529b4d41"   # sentence-transformers/all-MiniLM-L6-v2 commit (Apache-2.0)
MODEL_BASE="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/${MODEL_REVISION}"
# local file name -> path in the upstream repository
declare -A REMOTE=(
  [model.onnx]="onnx/model.onnx"
  [tokenizer.json]="tokenizer.json"
)
declare -A SHA=(
  [model.onnx]="6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452"
  [tokenizer.json]="be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037"
)

existing_roster() {
  if [ -n "${AGENCY_AGENTS_DIR:-}" ] && [ -f "$AGENCY_AGENTS_DIR/divisions.json" ]; then
    echo "$AGENCY_AGENTS_DIR"; return
  fi
  for c in "$DATA/agency-agents" "$HOME/.agency-agents"; do
    if [ -f "$c/divisions.json" ]; then echo "$c"; return; fi
  done
}

sha_of() { shasum -a 256 "$1" | cut -d' ' -f1; }

# The pinned onnxruntime has wheels for specific Python versions only (no 3.15 wheel at this pin),
# so prefer a supported interpreter. Override with PYTHON=/path/to/python.
pick_python() {
  if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
  for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then echo "$candidate"; return; fi
  done
  echo "no python3 found; install Python 3.14 or set PYTHON" >&2
  return 1
}

model_ok() {
  for name in "${!SHA[@]}"; do
    [ -f "$DATA/model/$name" ] && [ "$(sha_of "$DATA/model/$name")" = "${SHA[$name]}" ] || return 1
  done
}

status() {
  echo "data folder: $DATA"
  if r="$(existing_roster)" && [ -n "$r" ]; then echo "roster:      installed at $r"; else echo "roster:      not installed"; fi
  if [ -x "$DATA/.venv/bin/python" ] && "$DATA/.venv/bin/python" -c "import onnxruntime, tokenizers, numpy" 2>/dev/null; then
    echo "packages:    installed ($DATA/.venv)"
  else
    echo "packages:    not installed"
  fi
  if model_ok 2>/dev/null; then echo "model:       installed and verified (revision ${MODEL_REVISION:0:12})"; else echo "model:       not installed"; fi
}

install_roster() {
  if r="$(existing_roster)" && [ -n "$r" ]; then
    echo "roster already available at $r; nothing to do"; return
  fi
  command -v git >/dev/null || { echo "git is required to install the roster" >&2; exit 1; }
  mkdir -p "$DATA"
  echo "cloning the roster into $DATA/agency-agents"
  git clone --depth 1 --quiet "$ROSTER_REPO" "$DATA/agency-agents"
  echo "roster installed"
}

install_embeddings() {
  mkdir -p "$DATA"
  if [ ! -x "$DATA/.venv/bin/python" ]; then
    py="$(pick_python)"
    echo "creating virtualenv with $("$py" -V) in $DATA/.venv"
    "$py" -m venv "$DATA/.venv"
  fi
  echo "installing pinned packages"
  if ! "$DATA/.venv/bin/python" -m pip install --quiet -r "$PLUGIN_ROOT/scripts/requirements.txt"; then
    rm -rf "$DATA/.venv"
    echo "package install failed; removed the partial virtualenv. Retry with PYTHON=python3.14 scripts/setup.sh embeddings" >&2
    exit 1
  fi

  mkdir -p "$DATA/model"
  for name in "${!SHA[@]}"; do
    if [ -f "$DATA/model/$name" ] && [ "$(sha_of "$DATA/model/$name")" = "${SHA[$name]}" ]; then
      echo "ok        $name"; continue
    fi
    echo "download  $name"
    curl -sSL --fail --max-time 600 -o "$DATA/model/$name.part" "$MODEL_BASE/${REMOTE[$name]}"
    if [ "$(sha_of "$DATA/model/$name.part")" != "${SHA[$name]}" ]; then
      rm -f "$DATA/model/$name.part"
      echo "checksum mismatch for $name; not installed" >&2
      exit 1
    fi
    mv "$DATA/model/$name.part" "$DATA/model/$name"
  done
  echo "$MODEL_REVISION" > "$DATA/model/REVISION"
  "$DATA/.venv/bin/python" "$PLUGIN_ROOT/scripts/roster.py" verify-model
}

case "${1:-status}" in
  status)     status ;;
  roster)     install_roster ;;
  embeddings) install_embeddings ;;
  all)        install_roster; install_embeddings ;;
  *) echo "usage: setup.sh status|roster|embeddings|all" >&2; exit 2 ;;
esac
