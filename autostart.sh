#!/bin/bash
# autostart.sh — installa LaunchAgent (avvio automatico al login)
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/info.mikweb.jarvis.plist"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>info.mikweb.jarvis</string>
    <key>ProgramArguments</key>
    <array><string>/bin/bash</string><string>${DIR}/run.sh</string></array>
    <key>WorkingDirectory</key><string>${DIR}</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
    <key>StandardOutPath</key><string>${DIR}/jarvis.log</string>
    <key>StandardErrorPath</key><string>${DIR}/jarvis.log</string>
    <key>ThrottleInterval</key><integer>10</integer>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "  ✅ Jarvis si avvierà automaticamente ad ogni login"
echo "  Comandi:"
echo "    launchctl start info.mikweb.jarvis   # avvia ora"
echo "    launchctl stop  info.mikweb.jarvis   # ferma"
echo "    tail -f ${DIR}/jarvis.log            # log live"
echo ""
