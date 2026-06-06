#!/usr/bin/env python3
"""jarvis_computer_use.py — controllo nativo mouse, tastiera, screenshot, drag v1.0
Ispirato a Jarvey (novynlabs) e OpenAI computer use pattern"""
import subprocess, os, time, json
from pathlib import Path

def _run(cmd, timeout=10):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()

def mouse_move(x, y):
    """Muove il mouse a coordinate assolute"""
    script = f'''
    tell application "System Events"
        set mousePosition to {{{x}, {y}}}
        do shell script "python3 -c 'import Quartz; Quartz.CGWarpMouseCursorPosition(({x}, {y}))'"
    end tell
    '''
    # Fallback: usa cliclick se disponibile
    rc, _ = _run(f"cliclick m:{x},{y} 2>/dev/null")
    if rc != 0:
        # Python Quartz fallback
        try:
            import Quartz
            Quartz.CGWarpMouseCursorPosition((x, y))
            return f"✅ Mouse mosso a ({x}, {y})"
        except:
            return "⚠ Installa cliclick: brew install cliclick"
    return f"✅ Mouse mosso a ({x}, {y})"

def mouse_click(x=None, y=None, button="left", clicks=1):
    """Click del mouse — sinistro, destro, o doppio"""
    if x is not None and y is not None:
        mouse_move(x, y)
        time.sleep(0.1)
    
    if button == "right":
        script = '''
        tell application "System Events"
            click at current location with right button
        end tell
        '''
        # Fallback cliclick
        rc, _ = _run("cliclick rc:.")
        return "✅ Click destro" if rc == 0 else "⚠ Serve cliclick: brew install cliclick"
    elif clicks == 2:
        rc, _ = _run("cliclick dc:.")
        return "✅ Doppio click" if rc == 0 else "⚠ Serve cliclick"
    else:
        rc, _ = _run("cliclick c:.")
        return "✅ Click sinistro" if rc == 0 else "⚠ Serve cliclick: brew install cliclick"

def mouse_drag(from_x, from_y, to_x, to_y):
    """Drag del mouse da punto A a punto B"""
    rc, _ = _run(f"cliclick m:{from_x},{from_y} dd:{to_x},{to_y} du:.")
    if rc == 0:
        return f"✅ Drag da ({from_x},{from_y}) a ({to_x},{to_y})"
    return "⚠ Serve cliclick: brew install cliclick"

def mouse_scroll(direction="down", amount=300):
    """Scroll del mouse"""
    directions = {
        "down": f"cliclick ds:0,0 dd:0,-{amount} du:.",
        "up": f"cliclick ds:0,0 dd:0,{amount} du:.",
        "left": f"cliclick ds:0,0 dd:-{amount},0 du:.",
        "right": f"cliclick ds:0,0 dd:{amount},0 du:."
    }
    cmd = directions.get(direction, directions["down"])
    rc, _ = _run(cmd)
    return f"✅ Scroll {direction}" if rc == 0 else "⚠ Serve cliclick"

def keyboard_type(text):
    """Digita testo come se fosse da tastiera"""
    # Escape caratteri speciali per AppleScript
    escaped = text.replace('"', '\\"').replace('\\', '\\\\')
    script = f'''
    tell application "System Events"
        keystroke "{escaped}"
    end tell
    '''
    rc, _ = _run(f"osascript -e '{script}'")
    if rc == 0:
        return f"✅ Digitato: {text[:50]}..."
    
    # Fallback: cliclick
    rc, _ = _run(f"cliclick t:'{text}'")
    return f"✅ Digitato: {text[:50]}" if rc == 0 else "⚠ Digitazione fallita"

def keyboard_press(key, modifiers=None):
    """Premi un tasto specifico (enter, tab, escape, etc)"""
    key_map = {
        "enter": "return",
        "tab": "tab",
        "escape": "escape",
        "esc": "escape",
        "delete": "delete",
        "backspace": "delete",
        "space": "space",
        "up": "up arrow",
        "down": "down arrow",
        "left": "left arrow",
        "right": "right arrow",
        "home": "home",
        "end": "end",
        "page_up": "page up",
        "page_down": "page down",
    }
    apple_key = key_map.get(key.lower(), key.lower())
    
    mod_str = ""
    if modifiers:
        mods = []
        if "command" in modifiers or "cmd" in modifiers:
            mods.append("command down")
        if "control" in modifiers or "ctrl" in modifiers:
            mods.append("control down")
        if "option" in modifiers or "alt" in modifiers:
            mods.append("option down")
        if "shift" in modifiers:
            mods.append("shift down")
        mod_str = " using {" + ", ".join(mods) + "}"
    
    script = f'''
    tell application "System Events"
        keystroke "{apple_key}"{mod_str}
    end tell
    '''
    rc, _ = _run(f"osascript -e '{script}'")
    return f"✅ Tasto {key} premuto" if rc == 0 else f"⚠ Tasto {key} fallito"

def keyboard_shortcut(keys):
    """Esegue scorciatoia tastiera (es: cmd+c, cmd+a)"""
    parts = keys.lower().split("+")
    modifiers = [p for p in parts[:-1]]
    key = parts[-1]
    return keyboard_press(key, modifiers)

def get_mouse_position():
    """Ritorna posizione corrente del mouse"""
    try:
        import Quartz
        loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return {"x": int(loc.x), "y": int(loc.y)}
    except:
        rc, out = _run("cliclick p")
        if rc == 0 and "," in out:
            x, y = out.strip().split(",")
            return {"x": int(x), "y": int(y)}
        return {"x": 0, "y": 0}

def get_screen_resolution():
    """Ritorna risoluzione dello schermo principale"""
    script = '''
    tell application "System Events"
        set screenSize to size of window 1 of first application process whose background only is false
        return (item 1 of screenSize) & "x" & (item 2 of screenSize)
    end tell
    '''
    rc, result = _run(f"osascript -e '{script}'")
    if rc == 0:
        parts = result.split("x")
        return {"width": int(parts[0]), "height": int(parts[1])}
    
    # Fallback
    rc, out = _run("system_profiler SPDisplaysDataType | grep 'Resolution' | head -1")
    if out:
        import re
        nums = re.findall(r'\d+', out.split(":")[-1])
        if len(nums) >= 2:
            return {"width": int(nums[0]), "height": int(nums[1])}
    return {"width": 1920, "height": 1080}

def screenshot_and_analyze(save_path=None):
    """Screenshot + analisi base del contenuto"""
    from jarvis_screen import take_screenshot, ocr_screenshot
    
    result = take_screenshot(save_path=save_path)
    if result["status"] != "ok":
        return result
    
    ocr_text = ocr_screenshot(result["path"])
    return {
        "status": "ok",
        "screenshot_path": result["path"],
        "ocr_text": ocr_text[:1000] if isinstance(ocr_text, str) else "",
        "message": "Screenshot catturato e analizzato"
    }

def computer_use_action(action, **kwargs):
    """Dispatcher per azioni computer use"""
    actions = {
        "mouse_move": lambda: mouse_move(kwargs.get("x", 0), kwargs.get("y", 0)),
        "mouse_click": lambda: mouse_click(kwargs.get("x"), kwargs.get("y"), kwargs.get("button", "left"), kwargs.get("clicks", 1)),
        "mouse_drag": lambda: mouse_drag(kwargs.get("from_x", 0), kwargs.get("from_y", 0), kwargs.get("to_x", 0), kwargs.get("to_y", 0)),
        "mouse_scroll": lambda: mouse_scroll(kwargs.get("direction", "down"), kwargs.get("amount", 300)),
        "keyboard_type": lambda: keyboard_type(kwargs.get("text", "")),
        "keyboard_press": lambda: keyboard_press(kwargs.get("key", "enter"), kwargs.get("modifiers")),
        "keyboard_shortcut": lambda: keyboard_shortcut(kwargs.get("keys", "cmd+c")),
        "get_mouse_pos": lambda: get_mouse_position(),
        "get_resolution": lambda: get_screen_resolution(),
        "list_windows": lambda: _osa('tell application "System Events" to set winList to name of every process whose background only is false\nset output to ""\nrepeat with proc in winList\n\ttell application "System Events" to tell process proc to set wins to (title of every window)\n\trepeat with w in wins\n\t\tset output to output & proc & ": " & w & linefeed\n\tend repeat\nend repeat\nreturn output'),
        "screenshot_analyze": lambda: screenshot_and_analyze(),
    }
    
    handler = actions.get(action)
    if handler:
        return handler()
    return f"⚠ Azione computer use sconosciuta: {action}"
