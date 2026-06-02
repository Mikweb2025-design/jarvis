#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ ! -d "$DIR/venv" ]; then
  echo "  ⚠  venv non trovato — esegui prima: bash setup.sh"
  exit 1
fi

source "$DIR/venv/bin/activate"

PORT=${JARVIS_PORT:-9999}
echo ""
echo "  J.A.R.V.I.S v8.0 Server → http://localhost:$PORT"
echo "  OCR • RAG • Computer Use • Playwright • Approval"
echo "  Ctrl+C per fermare"
echo ""

# crea data dir se non esiste
mkdir -p "$DIR/data/documents"

# avvia browser dopo 1.5s
(sleep 1.5 && open "http://localhost:$PORT") &

python3 "$DIR/jarvis_server.py"
