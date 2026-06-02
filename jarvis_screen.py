#!/usr/bin/env python3
"""jarvis_screen.py — screen awareness con OCR, analisi app, contesto visivo v2.0"""
import subprocess, os, tempfile, json
from pathlib import Path
from datetime import datetime

def _run(cmd, timeout=10):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()

def take_screenshot(mode="full", save_path=None):
    p = save_path or os.path.expanduser("~/Desktop/jarvis_screen.png")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not p.endswith(".png"):
        p = p + f"_{ts}.png"
    flags = {"full": "", "window": "-w", "selection": "-s"}
    rc, _ = _run(f"screencapture {flags.get(mode, '')} '{p}'")
    if rc == 0:
        return {"status": "ok", "path": p, "message": f"Screenshot salvato: {p}"}
    return {"status": "error", "message": "Screenshot fallito"}

def ocr_screenshot(image_path=None, lang="ita+eng"):
    """OCR su screenshot usando Apple Vision framework o Tesseract"""
    if image_path is None:
        result = take_screenshot()
        if result["status"] != "ok":
            return "Errore screenshot"
        image_path = result["path"]
    
    # Metodo 1: Apple Shortcuts con OCR nativo (più veloce, no dipendenze)
    text = _ocr_apple_vision(image_path)
    if text:
        return text
    
    # Metodo 2: Tesseract fallback
    return _ocr_tesseract(image_path, lang)

def _ocr_apple_vision(image_path):
    """OCR usando macOS Shortcuts o osascript con Vision framework"""
    script = f'''
    use framework "Foundation"
    use framework "AppKit"
    use framework "Vision"
    
    set theImage to current application's NSImage's alloc()'s initWithContentsOfFile:"{image_path}"
    if theImage is missing value then return "ERROR"
    
    set cgImage to theImage's CGImageForProposedRect:(missing value) context:(missing value) hints:(missing value)
    set request to current application's VNRecognizeTextRequest's alloc()'s init()
    request's setRecognitionLevel:(current application's VNRequestRecognitionLevelAccurate)
    request's setUsesLanguageCorrection:true
    
    set handler to current application's VNImageRequestHandler's alloc()'s initWithCGImage:cgImage options:{{}}
    handler's performRequests:{{request}} error:(missing value)
    
    set observations to request's results()
    set textList to current application's NSMutableArray's array()
    
    repeat with obs in observations
        set topCandidates to obs's topCandidates:1
        if topCandidates's |count|() > 0 then
            set txt to (topCandidates's objectAtIndex:0)'s string()
            if txt's |length|() > 0 then
                textList's addObject:txt
            end if
        end if
    end repeat
    
    return (textList's componentsJoinedByString:"\\n") as text
    '''
    rc, result = _run(f"osascript -l JavaScript -e '{script}'")
    if rc == 0 and result and result != "ERROR":
        return result
    return None

def _ocr_tesseract(image_path, lang="ita+eng"):
    """Fallback OCR con Tesseract"""
    try:
        rc, text = _run(f"tesseract '{image_path}' - -l {lang} --psm 6")
        if rc == 0 and text.strip():
            return text.strip()
    except:
        pass
    
    # Ultimo fallback: pytesseract Python
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip()
    except:
        return "OCR non disponibile — installa: brew install tesseract tesseract-lang"

def get_screen_description():
    """Descrive cosa c'è sullo schermo (app visibili + titolo finestre)"""
    script = '''
    set appList to ""
    tell application "System Events"
        repeat with p in (application processes whose background only is false)
            set appName to name of p
            set winList to ""
            repeat with w in (windows of p)
                set winList to winList & (name of w) & "; "
            end repeat
            if winList is not "" then
                set appList to appList & appName & ": " & winList & "\\n"
            else
                set appList to appList & appName & "\\n"
            end if
        end repeat
    end tell
    return appList
    '''
    rc, apps = _run(f"osascript -e '{script}'")
    return apps if apps else "Nessuna app visibile"

def get_frontmost_window_info():
    """Info sulla finestra in primo piano"""
    script = '''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        set appName to name of frontApp
        set winCount to count of windows of frontApp
        if winCount > 0 then
            set w to window 1 of frontApp
            set winTitle to name of w
            set winPos to position of w
            set winSize to size of w
            return appName & "|" & winTitle & "|" & (item 1 of winPos) & "," & (item 2 of winPos) & "|" & (item 1 of winSize) & "," & (item 2 of winSize)
        else
            return appName & "|(nessuna finestra)|0,0|0,0"
        end if
    end tell
    '''
    result = _osa(script)
    if result:
        parts = result.split("|")
        return {
            "app": parts[0],
            "window": parts[1] if len(parts) > 1 else "",
            "position": parts[2] if len(parts) > 2 else "0,0",
            "size": parts[3] if len(parts) > 3 else "0,0"
        }
    return {"app": "sconosciuto", "window": "", "position": "0,0", "size": "0,0"}

def get_display_info():
    """Info sui display collegati"""
    rc, out = _run("system_profiler SPDisplaysDataType | grep -E 'Resolution|Main|Retina|Display Type' | head -10")
    return out if out else "Info display non disponibili"

def capture_region(x=0, y=0, width=500, height=500, save_path=None):
    """Cattura una regione specifica dello schermo"""
    p = save_path or os.path.expanduser("~/Desktop/jarvis_region.png")
    rc, _ = _run(f"screencapture -R{x},{y},{width},{height} '{p}'")
    if rc == 0:
        return {"status": "ok", "path": p}
    return {"status": "error", "message": "Cattura regione fallita"}

def get_selected_text():
    """Estrae il testo selezionato sullo schermo (copia da app attiva)"""
    script = '''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        set appName to name of frontApp
    end tell
    tell application appName to activate
    delay 0.1
    tell application "System Events"
        keystroke "c" using command down
    end tell
    delay 0.2
    return the clipboard as text
    '''
    try:
        text = _osa(script)
        return text if text else "Nessun testo selezionato"
    except:
        return "Impossibile estrarre testo selezionato"

def screen_awareness_summary():
    """Riassunto completo dello stato dello schermo per il contesto LLM"""
    apps = get_screen_description()
    front = get_frontmost_window_info()
    return f"""STATO SCHERMO:
- App aperte: {apps.strip()}
- App attiva: {front['app']}
- Finestra: {front['window']}
- Posizione: {front['position']}
- Dimensione: {front['size']}"""
