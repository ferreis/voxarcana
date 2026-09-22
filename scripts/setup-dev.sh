#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 não encontrado."
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(
        f"VoxArcana requer Python >= 3.10; encontrado "
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
print(
    f"Usando Python "
    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
)
PY

cd "$BACKEND_DIR"

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install -U pip
python -m pip install -e .

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo
echo "Ambiente pronto."
echo "Para iniciar o protótipo:"
echo "  cd $BACKEND_DIR"
echo "  source .venv/bin/activate"
echo "  python -m uvicorn app.main:app --host 127.0.0.1 --port 8765"
