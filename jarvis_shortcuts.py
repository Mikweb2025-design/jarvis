#!/usr/bin/env python3
"""jarvis_shortcuts.py — Shortcuts macOS automation"""
import subprocess

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.returncode, r.stdout.strip() or r.stderr.strip()

def run_shortcut(name, input_text=""):
    """Esegue uno Shortcut macOS"""
    if input_text:
        script = f'''
        tell application "Shortcuts Events"
            run the shortcut "{name}" with input "{input_text}"
        end tell
        '''
    else:
        script = f'''
        tell application "Shortcuts Events"
            run the shortcut "{name}"
        end tell
        '''
    rc, result = _osa(script)
    if rc == 0:
        return f"✅ Shortcut eseguito: {name}"
    # Fallback con shortcuts CLI (macOS 13+)
    rc2, result2 = _osa(f'do shell script "shortcuts run \\"{name}\\""')
    if rc2 == 0:
        return f"✅ Shortcut eseguito: {name}"
    return f"⚠ Shortcut '{name}' non trovato o errore: {result}"

def list_shortcuts():
    """Elenca gli Shortcut disponibili"""
    rc, result = _osa('do shell script "shortcuts list --show-identifiers 2>/dev/null || echo NO_SHORTCUTS"')
    if result == "NO_SHORTCUTS":
        return "Nessuno Shortcut trovato (richiede macOS 13+)"
    shortcuts = [s.strip() for s in result.strip().split("\n") if s.strip()]
    if not shortcuts:
        return "Nessuno Shortcut configurato"
    return f"📋 Shortcut disponibili:\n" + "\n".join(f"  • {s}" for s in shortcuts[:30])

def get_shortcut_info(name):
    """Info su uno Shortcut specifico"""
    rc, result = _osa(f'do shell script "shortcuts view \\"{name}\\"" 2>/dev/null || echo NOT_FOUND')
    if result == "NOT_FOUND":
        return f"⚠ Shortcut '{name}' non trovato"
    return f"📋 {name}:\n{result[:500]}"
