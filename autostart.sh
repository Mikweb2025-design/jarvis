#!/bin/bash
# autostart.sh — installa LaunchAgent (avvio automatico al login)
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/info.mikweb.jarvis.plist"
LOG="$HOME/Library/Logs/jarvis.log"
PYTHON="${DIR}/venv/bin/python3"

# Crea wrapper che kill la porta prima di partire
WRAPPER="$DIR/launcher.sh"
cat > "$WRAPPER" << 'EOW'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${DIR}/venv/bin/python3"
/usr/sbin/lsof -ti:9999 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1
cd "$DIR"
exec "$PYTHON" "$DIR/jarvis_server.py"
EOW
chmod +x "$WRAPPER"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>info.mikweb.jarvis</string>
    <key>ProgramArguments</key>
    <array>
        <string>${WRAPPER}</string>
    </array>
    <key>WorkingDirectory</key><string>${DIR}</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
    <key>StandardOutPath</key><string>${LOG}</string>
    <key>StandardErrorPath</key><string>${LOG}</string>
    <key>ThrottleInterval</key><integer>10</integer>
    <key>SessionCreate</key><true/>
    <key>AbandonProcessGroup</key><true/>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "  ✅ Jarvis si avvierà automaticamente ad ogni login"
echo "  Log: ${LOG}"
echo "  Comandi:"
echo "    launchctl start info.mikweb.jarvis   # avvia ora"
echo "    launchctl stop  info.mikweb.jarvis   # ferma"
echo "    tail -f ${LOG}                       # log live"
echo ""
