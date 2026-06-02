#!/bin/bash
# JARVIS Server Watchdog v2 — Riavvia automaticamente se crasha
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "🤖 JARVIS Watchdog v2 avviato"
echo "📍 Directory: $(pwd)"
echo "🔍 Controllo ogni 3 secondi..."
echo "📝 Log: /tmp/jarvis_watchdog.log"

while true; do
    if ! curl -s --connect-timeout 2 --max-time 3 http://localhost:9999/api/status > /dev/null 2>&1; then
        echo "⚠️  [$(date '+%H:%M:%S')] Server offline - Riavvio..."
        pkill -9 -f "python3.*jarvis_server" 2>/dev/null
        sleep 2
        python3 -u jarvis_server.py >> /tmp/jarvis_watchdog.log 2>&1 &
        SERVER_PID=$!
        echo "✅ Server riavviato con PID $SERVER_PID"
        sleep 5
        # Verify it actually started
        if curl -s --connect-timeout 2 http://localhost:9999/api/status > /dev/null 2>&1; then
            echo "✅ Server verificato online"
        else
            echo "❌ Server non risponde dopo il riavvio, riprovo..."
            sleep 3
            python3 -u jarvis_server.py >> /tmp/jarvis_watchdog.log 2>&1 &
            sleep 5
        fi
    fi
    sleep 3
done
