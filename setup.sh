#!/bin/bash
# ─────────────────────────────────────────────────────────────
# setup.sh — installa tutto da zero v8.0
# Uso: bash setup.sh
# ─────────────────────────────────────────────────────────────
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "════════════════════════════════════════════════════"
echo "  J.A.R.V.I.S v8.0 — Setup (Apple Silicon)"
echo "════════════════════════════════════════════════════"
echo ""

# Homebrew
if ! command -v brew &>/dev/null; then
  warn "Installazione Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi
ok "Homebrew"

# portaudio
brew list portaudio &>/dev/null 2>&1 || brew install portaudio
ok "portaudio"

# brightness CLI
brew list brightness &>/dev/null 2>&1 || brew install brightness
ok "brightness"

# cliclick (computer use)
brew list cliclick &>/dev/null 2>&1 || brew install cliclick
ok "cliclick"

# tesseract (OCR fallback)
brew list tesseract &>/dev/null 2>&1 || brew install tesseract tesseract-lang
ok "tesseract"

# data dir
mkdir -p "$DIR/data/documents"
ok "data directory"

# venv
if [ ! -d "$DIR/venv" ]; then
  python3 -m venv "$DIR/venv"
  ok "virtual environment creato"
else
  ok "virtual environment già esistente"
fi

source "$DIR/venv/bin/activate"
pip install --upgrade pip -q

# core deps
pip install requests numpy -q
ok "core dependencies"

# speech recognition (wake word + STT)
pip install SpeechRecognition -q 2>/dev/null && ok "SpeechRecognition" || warn "SpeechRecognition non installato"

# pyaudio (wake word)
PORTAUDIO_PREFIX=$(brew --prefix portaudio)
pip install --global-option='build_ext' \
  --global-option="-I${PORTAUDIO_PREFIX}/include" \
  --global-option="-L${PORTAUDIO_PREFIX}/lib" \
  pyaudio -q 2>/dev/null && ok "pyaudio" || warn "pyaudio non installato (wake word disabilitato)"

# playwright (browser automation)
pip install playwright -q 2>/dev/null && ok "playwright" || warn "playwright non installato"
playwright install chromium 2>/dev/null && ok "chromium installato" || warn "chromium non installato"

# OCR deps
pip install pytesseract pillow -q 2>/dev/null && ok "OCR deps" || warn "OCR deps non installati"

# RAG deps (opzionali)
pip install sentence-transformers -q 2>/dev/null && ok "sentence-transformers" || warn "sentence-transformers non installato (RAG base attivo)"

# config.json
if [ ! -f "$DIR/config.json" ]; then
  python3 -c "from jarvis import load_config; load_config()" 2>/dev/null || true
  ok "config.json creato"
else
  ok "config.json già esistente"
fi

echo ""
echo "════════════════════════════════════════════════════"
echo "  ✅  Setup v8.0 completato!"
echo ""
echo "  PROSSIMI PASSI:"
echo "  1. Inserisci la Groq API key in config.json"
echo "     nano $DIR/config.json"
echo ""
echo "  2. Avvia il server:"
echo "     ./run.sh"
echo ""
echo "  3. Apri il browser su:"
echo "     http://localhost:9999"
echo ""
echo "  NUOVE FEATURE v8.0:"
echo "  🔊 Wake Word sempre attivo (VAD + hotkey)"
echo "  👁️  Screen OCR (Apple Vision + Tesseract)"
echo "  🌐 Browser Automation (Playwright)"
echo "  🖱️  Computer Use (mouse, keyboard, drag)"
echo "  📚 RAG Vector Embeddings (ricerca semantica)"
echo "  🔒 Approval Flow (azioni sensibili)"
echo "  📅 Calendar, 📧 Mail, 📝 Notes"
echo "  🧠 Memoria persistente (SQLite FTS5)"
echo "  🎯 80+ tools disponibili"
echo "════════════════════════════════════════════════════"
echo ""
