#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
MODEL_DIR="$BACKEND_DIR/models/Qwen3-TTS-12Hz-1.7B-VoiceDesign"

cd "$BACKEND_DIR"

if [ ! -d .venv ]; then
  echo "Ambiente virtual não encontrado. Execute ./scripts/setup-dev.sh primeiro."
  exit 1
fi

source .venv/bin/activate

# O modelo é público. Ignora tokens Hugging Face quebrados/expirados
# que poderiam ser enviados implicitamente em requisições de leitura.
unset HF_TOKEN || true
unset HUGGING_FACE_HUB_TOKEN || true
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1

mkdir -p "$MODEL_DIR"

hf download Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign   --local-dir "$MODEL_DIR"

echo
echo "Modelo baixado em:"
echo "  $MODEL_DIR"
echo
echo "Configure backend/.env com:"
echo "  VOXARCANA_MODEL=./models/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
