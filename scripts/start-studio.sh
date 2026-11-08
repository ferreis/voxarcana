#!/usr/bin/env bash
set -euo pipefail
VOXARCANA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$VOXARCANA_ROOT/backend"
if [ ! -x .venv-br/bin/python ] || [ ! -f ../frontend/dist/index.html ]; then
  echo "Prepare o estúdio primeiro: bash scripts/setup-br.sh"
  exit 1
fi
export VOXARCANA_ENGINE=chatterbox-br
exec .venv-br/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
