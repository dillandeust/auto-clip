#!/usr/bin/env bash
# Lance le backend OpenShorts avec le LD_LIBRARY_PATH requis pour que
# ctranslate2 (faster-whisper) trouve cuDNN/cuBLAS et utilise le GPU.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
NVDIR="$ROOT/.venv/lib/python3.12/site-packages/nvidia"
export LD_LIBRARY_PATH="$NVDIR/cudnn/lib:$NVDIR/cublas/lib:${LD_LIBRARY_PATH:-}"
cd "$ROOT/_ref_openshorts"
exec "$ROOT/.venv/bin/uvicorn" app:app --host 127.0.0.1 --port 8000 "$@"
