#!/bin/bash
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${DIR}/venv/bin/python3"
/usr/sbin/lsof -ti:9999 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1
cd "$DIR"
exec "$PYTHON" "$DIR/jarvis_server_fastapi.py"
