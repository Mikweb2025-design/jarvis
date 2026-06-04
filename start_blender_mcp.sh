#!/bin/bash
# start_blender_mcp.sh — Avvia Blender con UI + addon MCP attivo
# Uso: ./start_blender_mcp.sh
# Blender si apre normalmente e il server MCP parte automaticamente in background.

BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
ADDON="$HOME/Library/Application Support/Blender/5.1/scripts/addons/blender_mcp_addon.py"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTOSTART="$SCRIPT_DIR/blender_mcp_enable.py"

# Script inline per abilitare l'addon e avviare il server all'apertura
cat > /tmp/blender_mcp_enable.py << 'PYEOF'
import bpy, time

def enable_mcp():
    addon_name = "blender_mcp_addon"
    prefs = bpy.context.preferences

    # Abilita addon se non attivo
    if addon_name not in prefs.addons:
        try:
            bpy.ops.preferences.addon_enable(module=addon_name)
            bpy.ops.wm.save_userpref()
            print(f"[MCP] Addon '{addon_name}' abilitato")
        except Exception as e:
            print(f"[MCP] WARN: {e}")
    else:
        print(f"[MCP] Addon già attivo")

    # Avvia server con piccolo delay
    def start():
        try:
            bpy.ops.blendermcp.start_server()
            print("[MCP] Server avviato su localhost:9876 ✓")
        except Exception as e:
            print(f"[MCP] ERR start: {e}")
        return None  # non ripetere

    bpy.app.timers.register(start, first_interval=1.5)
    return None

bpy.app.timers.register(enable_mcp, first_interval=0.5)
PYEOF

echo "🟢 Avvio Blender 5.1.1 con MCP addon..."
echo "   Server socket → localhost:9876"
echo "   Chiudi questa finestra per fermare."
echo ""

"$BLENDER" --python /tmp/blender_mcp_enable.py "$@"
