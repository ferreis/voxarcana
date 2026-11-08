#!/usr/bin/env bash
set -euo pipefail
VOXARCANA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$VOXARCANA_ROOT"
if [ ! -x backend/.venv-br/bin/python ]; then
  echo "Prepare o ambiente primeiro: bash scripts/setup-br.sh" >&2
  exit 1
fi
if ! command -v ollama >/dev/null; then
  echo "O Ollama não está instalado. Consulte o README para preparar o analisador." >&2
  exit 1
fi
if [ ! -d frontend/node_modules ]; then
  npm --prefix frontend ci
fi
# Compile before stopping services: a failed build leaves the current studio up.
npm --prefix frontend run build
exec backend/.venv-br/bin/python scripts/restart-studio.py
