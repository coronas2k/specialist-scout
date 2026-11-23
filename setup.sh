#!/usr/bin/env bash
# Set up the optional embedding search for the agency skill.
# Keyword search works without this script. Re-running is safe: finished steps are skipped.
set -euo pipefail
cd "$(dirname "$0")"

REVISION="75251058ddd779e3a744f87fdf63fb39681aec16"   # onnx-models/all-MiniLM-L6-v2-onnx commit
BASE="https://huggingface.co/onnx-models/all-MiniLM-L6-v2-onnx/resolve/${REVISION}"
declare -A SHA=(
  [model.onnx]="994a58868f7abacacbf2192aa0aae8f56da8c4505dbde2740c861b24426ede6b"
  [tokenizer.json]="da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0"
  [vocab.txt]="07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3"
)

echo "== virtualenv"
if [ ! -x .venv/bin/python ]; then
  "${PYTHON:-python3}" -m venv .venv
fi
.venv/bin/python -m pip install --quiet -r requirements.txt
echo "installed: $(.venv/bin/python -m pip freeze | grep -E '^(onnxruntime|tokenizers|numpy)==' | tr '\n' ' ')"

echo "== model (${REVISION:0:12})"
mkdir -p model
for name in "${!SHA[@]}"; do
  want="${SHA[$name]}"
  if [ -f "model/$name" ] && [ "$(shasum -a 256 "model/$name" | cut -d' ' -f1)" = "$want" ]; then
    echo "ok       $name"
    continue
  fi
  echo "download $name"
  curl -sSL --fail --max-time 600 -o "model/$name.part" "$BASE/$name"
  got="$(shasum -a 256 "model/$name.part" | cut -d' ' -f1)"
  if [ "$got" != "$want" ]; then
    rm -f "model/$name.part"
    echo "checksum mismatch for $name (got $got)" >&2
    exit 1
  fi
  mv "model/$name.part" "model/$name"
done
echo "$REVISION" > model/REVISION

echo "== check"
.venv/bin/python roster.py verify-model
.venv/bin/python roster.py search "landing page load faster" --limit 3
