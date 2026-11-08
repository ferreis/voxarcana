#!/usr/bin/env bash
set -euo pipefail
VOXARCANA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v ollama >/dev/null 2>&1; then
  echo "Para interpretar personagens automaticamente, instale o Ollama: https://ollama.com/download"
  exit 1
fi
cd "$VOXARCANA_ROOT/backend"
.venv-br/bin/python - <<'PY'
from app.scene import get_reader
get_reader().prepare()
print('Interpretação de cenas instalada. O analisador usará CPU, preservando a VRAM para as vozes.')
PY
