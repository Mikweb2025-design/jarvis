#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${DIR}/venv/bin/python3"
/usr/sbin/lsof -ti:9999 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1
cd "$DIR"
exec "$PYTHON" "$DIR/jarvis_server.py"
