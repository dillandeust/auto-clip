#!/usr/bin/env bash
# Lance le dashboard Vite en pointant le proxy /api vers le backend local
# (sinon il cible http://backend:8000, le nom de service docker, injoignable sur l'hôte).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/_ref_openshorts/dashboard"
export VITE_PROXY_TARGET="${VITE_PROXY_TARGET:-http://localhost:8000}"
export VITE_RENDER_TARGET="${VITE_RENDER_TARGET:-http://localhost:3100}"
exec npm run dev -- --port 5173 --strictPort
