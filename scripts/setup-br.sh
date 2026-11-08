#!/usr/bin/env bash
set -euo pipefail
VOXARCANA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HOME/.cache/voxarcana-tmp"
export TMPDIR="$HOME/.cache/voxarcana-tmp"
python3 -m venv "$VOXARCANA_ROOT/backend/.venv-br"
VOXARCANA_PYTHON="$VOXARCANA_ROOT/backend/.venv-br/bin/python"
"$VOXARCANA_PYTHON" -m pip install --upgrade pip
"$VOXARCANA_PYTHON" -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
"$VOXARCANA_PYTHON" -m pip install -r "$VOXARCANA_ROOT/backend/requirements-br.txt"
"$VOXARCANA_PYTHON" "$VOXARCANA_ROOT/scripts/download-br.py"
npm --prefix "$VOXARCANA_ROOT/frontend" ci
npm --prefix "$VOXARCANA_ROOT/frontend" run build
printf '\nPronto. Inicie com: bash scripts/start-studio.sh\n'
