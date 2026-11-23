#!/usr/bin/env bash
# Check or install the parts of the Agency plugin that need downloads.
#   setup.sh status       read-only: what is installed (default)
#   setup.sh roster       clone the agency-agents roster into the plugin data folder
#   setup.sh embeddings   create the virtualenv, download the pinned model, verify checksums
#   setup.sh all          roster, then embeddings
# Nothing here runs unless the user has asked for it (see commands/setup.md).
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.cache/agency-skill}"
ROSTER_REPO="${AGENCY_ROSTER_REPO:-https://github.com/msitarzewski/agency-agents.git}"
MODEL_REVISION="75251058ddd779e3a744f87fdf63fb39681aec16"   # onnx-models/all-MiniLM-L6-v2-onnx commit
MODEL_BASE="https://huggingface.co/onnx-models/all-MiniLM-L6-v2-onnx/resolve/${MODEL_REVISION}"
declare -A SHA=(
  [model.onnx]="994a58868f7abacacbf2192aa0aae8f56da8c4505dbde2740c861b24426ede6b"
  [tokenizer.json]="da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0"
  [vocab.txt]="07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3"
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

model_ok() {
  for name in "${!SHA[@]}"; do
    [ -f "$DATA/model/$name" ] && [ "$(sha_of "$DATA/model/$name")" = "${SHA[$name]}" ] || return 1
  done
}

status() {
  echo "data folder: $DATA"
  if r="$(existing_roster)" && [ -n "$r" ]; then echo "roster:      installed at $r"; else echo "roster:      not installed"; fi
  if [ -x "$DATA/.venv/bin/python" ]; then echo "packages:    installed ($DATA/.venv)"; else echo "packages:    not installed"; fi
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
    echo "creating virtualenv in $DATA/.venv"
    "${PYTHON:-python3}" -m venv "$DATA/.venv"
  fi
  echo "installing pinned packages"
  "$DATA/.venv/bin/python" -m pip install --quiet -r "$PLUGIN_ROOT/scripts/requirements.txt"

  mkdir -p "$DATA/model"
  for name in "${!SHA[@]}"; do
    if [ -f "$DATA/model/$name" ] && [ "$(sha_of "$DATA/model/$name")" = "${SHA[$name]}" ]; then
      echo "ok        $name"; continue
    fi
    echo "download  $name"
    curl -sSL --fail --max-time 600 -o "$DATA/model/$name.part" "$MODEL_BASE/$name"
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
