"""
blender_mcp_autostart.py — Eseguito da Blender all'avvio per:
  1. Abilitare l'addon blender_mcp_addon
  2. Avviare il server MCP sulla porta 9876
Uso: /Applications/Blender.app/Contents/MacOS/Blender --background --python blender_mcp_autostart.py
"""
import bpy, sys, time

print("[Jarvis-Blender] Avvio MCP autostart...")

# Abilita l'addon se non già attivo
addon_name = "blender_mcp_addon"
if addon_name not in bpy.context.preferences.addons:
    try:
        bpy.ops.preferences.addon_enable(module=addon_name)
        bpy.ops.wm.save_userpref()
        print(f"[Jarvis-Blender] Addon '{addon_name}' abilitato e salvato")
    except Exception as e:
        print(f"[Jarvis-Blender] WARN addon enable: {e}")
else:
    print(f"[Jarvis-Blender] Addon '{addon_name}' già attivo")

# Avvia il server MCP
time.sleep(0.5)
try:
    bpy.ops.blendermcp.start_server()
    print("[Jarvis-Blender] Server MCP avviato su localhost:9876")
except Exception as e:
    print(f"[Jarvis-Blender] ERR start_server: {e}")

# Mantieni vivo il processo (necessario in background mode)
print("[Jarvis-Blender] Server in esecuzione. Ctrl+C per fermare.")
try:
    while True:
        time.sleep(2)
        # Aggiorna i timer di Blender (necessario per il server socket)
        bpy.app.timers.register(lambda: None, first_interval=0.1)
except KeyboardInterrupt:
    print("[Jarvis-Blender] Stop.")
    try:
        bpy.ops.blendermcp.stop_server()
    except:
        pass
