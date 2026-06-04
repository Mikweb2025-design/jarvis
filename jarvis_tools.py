#!/usr/bin/env python3
"""jarvis_tools.py — tutti i tools macOS unificati v5.1 — +OCR, Playwright, Computer Use, RAG, Approval, Blender"""
import subprocess, os, re, json, urllib.parse
from pathlib import Path
from datetime import datetime

# ── import moduli base ──
from jarvis_memory import JarvisMemory
from jarvis_calendar import get_today_events, get_upcoming_events, create_event, get_calendars, open_calendar_app
from jarvis_mail import get_unread_count, get_recent_emails, search_emails
from jarvis_notes import create_note, search_notes, list_notes, read_note
from jarvis_screen import (take_screenshot, get_screen_description, get_frontmost_window_info,
    get_display_info, capture_region, ocr_screenshot, get_selected_text, screen_awareness_summary)
from jarvis_browser import (open_url, search_web, get_page_content_js, get_browser_tabs,
    click_element, fill_form, scroll_page, playwright_navigate, playwright_click,
    playwright_fill, playwright_extract, playwright_screenshot)
from jarvis_files import (list_directory, create_file, create_directory, rename_file,
    delete_file, copy_file, move_file, read_file, search_files, get_file_info, organize_downloads)
from jarvis_shortcuts import run_shortcut, list_shortcuts
from jarvis_planner import (create_plan, get_active_plans, complete_step,
    delete_plan, get_plan_detail)
from jarvis_git import git_status, git_branches, git_log, git_execute, git_diff, git_create_branch, git_commit

# ── nuovi moduli v8.0 ──
from jarvis_computer_use import (mouse_move, mouse_click, mouse_drag, mouse_scroll,
    keyboard_type, keyboard_press, keyboard_shortcut, get_mouse_position,
    get_screen_resolution, computer_use_action)
from jarvis_rag import rag
from jarvis_approval import approval, check_and_approve
# ── Blender MCP (opzionale — non blocca se Blender è chiuso) ──
try:
    from jarvis_blender import (
        blender_status, blender_get_scene, blender_get_object, blender_execute,
        blender_create_object, blender_delete_object, blender_set_material,
        blender_move_object, blender_screenshot, blender_render,
        blender_setup_avatar, blender_focus_view,
        blender_polyhaven_search, blender_polyhaven_download,
        blender_sketchfab_search, blender_sketchfab_download,
    )
    _BLENDER_OK = True
except ImportError:
    _BLENDER_OK = False

memory = JarvisMemory()

def web_search_ddg(query, max_results=8):
    """Cerca su DuckDuckGo (no API key necessaria)"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"🔍 Nessun risultato per: {query}"
        output = [f"🔍 Risultati per '{query}':"]
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r.get('title','')}\n   {r.get('href','')}\n   {r.get('body','')[:120]}")
        return "\n\n".join(output)
    except ImportError:
        # Fallback: usa Google
        import urllib.parse
        return f"⚠ duckduckgo_search non installato. pip install duckduckgo-search. Ricerca Google: https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
    except Exception as e:
        return f"⚠ Errore ricerca: {e}"

TOOLS_SCHEMA = [
    {"type":"function","function":{"name":"open_app","description":"Apre un'app macOS","parameters":{"type":"object","properties":{"app_name":{"type":"string"}},"required":["app_name"]}}},
    {"type":"function","function":{"name":"open_url","description":"Apre un URL nel browser","parameters":{"type":"object","properties":{"url":{"type":"string"},"browser":{"type":"string","default":""}},"required":["url"]}}},
    {"type":"function","function":{"name":"web_search","description":"Cerca su Google","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"system_volume","description":"Controlla volume macOS","parameters":{"type":"object","properties":{"action":{"type":"string","enum":["set","mute","unmute","get"]},"level":{"type":"integer"}},"required":["action"]}}},
    {"type":"function","function":{"name":"take_screenshot","description":"Screenshot schermo","parameters":{"type":"object","properties":{"mode":{"type":"string","enum":["full","window","selection"],"default":"full"}}}}},
    {"type":"function","function":{"name":"get_system_info","description":"Info sistema: battery, cpu, ram, disk, ip, uptime","parameters":{"type":"object","properties":{"info_type":{"type":"string","enum":["battery","cpu","ram","disk","ip","uptime","all"]}},"required":["info_type"]}}},
    {"type":"function","function":{"name":"clipboard_action","description":"Leggi o scrivi clipboard","parameters":{"type":"object","properties":{"action":{"type":"string","enum":["read","write"]},"text":{"type":"string","default":""}},"required":["action"]}}},
    {"type":"function","function":{"name":"send_notification","description":"Mostra notifica macOS","parameters":{"type":"object","properties":{"title":{"type":"string"},"message":{"type":"string"}},"required":["title","message"]}}},
    {"type":"function","function":{"name":"set_reminder","description":"Crea promemoria","parameters":{"type":"object","properties":{"title":{"type":"string"},"minutes_from_now":{"type":"integer","default":0}},"required":["title"]}}},
    {"type":"function","function":{"name":"play_music","description":"Controlla Music/Spotify","parameters":{"type":"object","properties":{"action":{"type":"string","enum":["play","pause","next","previous","stop"]},"app":{"type":"string","enum":["Music","Spotify"],"default":"Music"}},"required":["action"]}}},
    {"type":"function","function":{"name":"quit_app","description":"Chiude un'app","parameters":{"type":"object","properties":{"app_name":{"type":"string"}},"required":["app_name"]}}},
    {"type":"function","function":{"name":"lock_screen","description":"Blocca schermo","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"show_desktop","description":"Mostra desktop","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"set_brightness","description":"Luminosità 0-100","parameters":{"type":"object","properties":{"level":{"type":"integer"}},"required":["level"]}}},
    {"type":"function","function":{"name":"run_terminal_command","description":"Esegue comando bash","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
    # Calendar
    {"type":"function","function":{"name":"calendar_today","description":"Eventi di oggi","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"calendar_upcoming","description":"Prossimi eventi","parameters":{"type":"object","properties":{"days":{"type":"integer","default":7}}}}},
    {"type":"function","function":{"name":"calendar_create","description":"Crea evento calendario","parameters":{"type":"object","properties":{"title":{"type":"string"},"start_date":{"type":"string"},"duration_minutes":{"type":"integer","default":60}},"required":["title"]}}},
    {"type":"function","function":{"name":"calendar_list","description":"Lista calendari","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"calendar_open","description":"Apre app Calendario","parameters":{"type":"object","properties":{}}}},
    # Mail
    {"type":"function","function":{"name":"mail_unread","description":"Email non lette","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"mail_recent","description":"Email recenti","parameters":{"type":"object","properties":{"limit":{"type":"integer","default":5}}}}},
    {"type":"function","function":{"name":"mail_search","description":"Cerca email","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"mail_read_aloud","description":"Legge email non lette ad alta voce","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"mail_send","description":"Invia email con Apple Mail","parameters":{"type":"object","properties":{
        "to":{"type":"string","description":"Destinatario (email o nome <email>)"},
        "subject":{"type":"string","description":"Oggetto dell'email"},
        "body":{"type":"string","description":"Corpo del messaggio"},
        "cc":{"type":"string","description":"CC opzionale","default":""},
        "bcc":{"type":"string","description":"BCC opzionale","default":""}
    },"required":["to","subject","body"]}}},
    # Notes
    {"type":"function","function":{"name":"notes_create","description":"Crea nota","parameters":{"type":"object","properties":{"title":{"type":"string"},"body":{"type":"string","default":""}},"required":["title"]}}},
    {"type":"function","function":{"name":"notes_search","description":"Cerca note","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"notes_list","description":"Lista note recenti","parameters":{"type":"object","properties":{"limit":{"type":"integer","default":10}}}}},
    # Screen
    {"type":"function","function":{"name":"screen_info","description":"Info schermo e app visibili","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"screen_frontmost","description":"App e finestra in primo piano","parameters":{"type":"object","properties":{}}}},
    # Browser
    {"type":"function","function":{"name":"browser_tabs","description":"Tab Chrome aperti","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"browser_current","description":"Pagina Chrome attiva","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"browser_scroll","description":"Scroll pagina","parameters":{"type":"object","properties":{"direction":{"type":"string","enum":["up","down","top","bottom"]}},"required":["direction"]}}},
    # Files
    {"type":"function","function":{"name":"files_list","description":"Lista directory","parameters":{"type":"object","properties":{"path":{"type":"string","default":"~/Desktop"}}}}},
    {"type":"function","function":{"name":"files_read","description":"Leggi file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"files_create","description":"Crea file","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string","default":""}},"required":["path"]}}},
    {"type":"function","function":{"name":"files_search","description":"Cerca file","parameters":{"type":"object","properties":{"query":{"type":"string"},"path":{"type":"string","default":"~"}},"required":["query"]}}},
    {"type":"function","function":{"name":"files_info","description":"Info file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"files_organize","description":"Organizza Downloads","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"files_delete","description":"Elimina file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    # Memory
    {"type":"function","function":{"name":"memory_remember","description":"Ricorda un fatto","parameters":{"type":"object","properties":{"content":{"type":"string"},"category":{"type":"string","default":"fact"},"tags":{"type":"string","default":""}},"required":["content"]}}},
    {"type":"function","function":{"name":"memory_search","description":"Cerca nei ricordi","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"memory_preferences","description":"Mostra preferenze salvate","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"memory_stats","description":"Statistiche memoria","parameters":{"type":"object","properties":{}}}},
    # Shortcuts
    {"type":"function","function":{"name":"shortcuts_run","description":"Esegue Shortcut","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"shortcuts_list","description":"Lista Shortcut","parameters":{"type":"object","properties":{}}}},
    # Planner
    {"type":"function","function":{"name":"planner_create","description":"Crea piano multi-step","parameters":{"type":"object","properties":{"title":{"type":"string"},"steps":{"type":"array","items":{"type":"string"}},"priority":{"type":"string","default":"medium"}},"required":["title","steps"]}}},
    {"type":"function","function":{"name":"planner_list","description":"Piani attivi","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"planner_complete","description":"Completa step","parameters":{"type":"object","properties":{"plan_id":{"type":"integer"},"step":{"type":"integer"}},"required":["plan_id","step"]}}},
    {"type":"function","function":{"name":"planner_detail","description":"Dettaglio piano","parameters":{"type":"object","properties":{"plan_id":{"type":"integer"}},"required":["plan_id"]}}},
    # Web Search
    {"type":"function","function":{"name":"web_search_ddg","description":"Cerca su DuckDuckGo con risultati","parameters":{"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":8}},"required":["query"]}}},
    # Git
    {"type":"function","function":{"name":"git_status","description":"Stato repository git","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"git_log","description":"Log commit git","parameters":{"type":"object","properties":{"count":{"type":"integer","default":10}}}}},
    {"type":"function","function":{"name":"git_branches","description":"Lista branch git","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"git_diff","description":"Diff modifiche git","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"git_commit","description":"Commit git","parameters":{"type":"object","properties":{"message":{"type":"string"}},"required":["message"]}}},
    {"type":"function","function":{"name":"git_create_branch","description":"Crea branch git","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"git_command","description":"Esegue comando git","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
    # OCR + Screen Awareness
    {"type":"function","function":{"name":"screen_ocr","description":"OCR su screenshot — legge testo dallo schermo","parameters":{"type":"object","properties":{"image_path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"screen_summary","description":"Riassunto completo stato schermo (app, finestre, contesto)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"screen_selected_text","description":"Estrae testo selezionato nell'app attiva","parameters":{"type":"object","properties":{}}}},
    # Browser Automation Playwright
    {"type":"function","function":{"name":"browser_navigate","description":"Naviga URL con Playwright e estrae contenuto","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{"name":"browser_extract","description":"Estrae contenuto da pagina web con selettore","parameters":{"type":"object","properties":{"url":{"type":"string"},"selector":{"type":"string","default":"body"}},"required":["url"]}}},
    {"type":"function","function":{"name":"browser_playwright_click","description":"Click elemento con Playwright","parameters":{"type":"object","properties":{"selector":{"type":"string"},"url":{"type":"string","default":""}},"required":["selector"]}}},
    {"type":"function","function":{"name":"browser_playwright_fill","description":"Compila form con Playwright","parameters":{"type":"object","properties":{"selector":{"type":"string"},"text":{"type":"string"},"url":{"type":"string","default":""}},"required":["selector","text"]}}},
    {"type":"function","function":{"name":"browser_screenshot","description":"Screenshot pagina web con Playwright","parameters":{"type":"object","properties":{"url":{"type":"string"},"save_path":{"type":"string","default":""}},"required":["url"]}}},
    # Computer Use
    {"type":"function","function":{"name":"computer_mouse_move","description":"Muove mouse a coordinate","parameters":{"type":"object","properties":{"x":{"type":"integer"},"y":{"type":"integer"}},"required":["x","y"]}}},
    {"type":"function","function":{"name":"computer_mouse_click","description":"Click mouse (sinistro, destro, doppio)","parameters":{"type":"object","properties":{"x":{"type":"integer"},"y":{"type":"integer"},"button":{"type":"string","enum":["left","right"],"default":"left"},"clicks":{"type":"integer","default":1}}}}},
    {"type":"function","function":{"name":"computer_mouse_drag","description":"Drag mouse da A a B","parameters":{"type":"object","properties":{"from_x":{"type":"integer"},"from_y":{"type":"integer"},"to_x":{"type":"integer"},"to_y":{"type":"integer"}},"required":["from_x","from_y","to_x","to_y"]}}},
    {"type":"function","function":{"name":"computer_keyboard_type","description":"Digita testo come tastiera","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}},
    {"type":"function","function":{"name":"computer_keyboard_press","description":"Premi tasto specifico","parameters":{"type":"object","properties":{"key":{"type":"string"},"modifiers":{"type":"string","default":""}},"required":["key"]}}},
    {"type":"function","function":{"name":"computer_keyboard_shortcut","description":"Scorciatoia tastiera (es: cmd+c)","parameters":{"type":"object","properties":{"keys":{"type":"string"}},"required":["keys"]}}},
    {"type":"function","function":{"name":"computer_mouse_position","description":"Posizione corrente mouse","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"computer_resolution","description":"Risoluzione schermo","parameters":{"type":"object","properties":{}}}},
    # RAG
    {"type":"function","function":{"name":"rag_add_document","description":"Aggiungi documento al database RAG","parameters":{"type":"object","properties":{"title":{"type":"string"},"content":{"type":"string"},"source":{"type":"string","default":""}},"required":["title","content"]}}},
    {"type":"function","function":{"name":"rag_add_file","description":"Aggiungi file al database RAG","parameters":{"type":"object","properties":{"file_path":{"type":"string"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"rag_search","description":"Cerca documenti nel database RAG","parameters":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"rag_list","description":"Lista documenti nel database RAG","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"rag_stats","description":"Statistiche database RAG","parameters":{"type":"object","properties":{}}}},
    # Approval
    {"type":"function","function":{"name":"approval_pending","description":"Lista richieste approvazione pending","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"approval_approve","description":"Approva richiesta","parameters":{"type":"object","properties":{"request_id":{"type":"string"},"auto_future":{"type":"boolean","default":False}},"required":["request_id"]}}},
    {"type":"function","function":{"name":"approval_deny","description":"Nega richiesta","parameters":{"type":"object","properties":{"request_id":{"type":"string"}},"required":["request_id"]}}},
]

def _run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()

# ── SYSTEM ──
def open_app(app_name="", **_):
    aliases = {"chrome":"Google Chrome","vscode":"Visual Studio Code","vs code":"Visual Studio Code",
               "iterm":"iTerm","iterm2":"iTerm","terminale":"Terminal","note":"Notes",
               "appunti":"Notes","promemoria":"Reminders","calendario":"Calendar","foto":"Photos",
               "musica":"Music","anteprima":"Preview","posta":"Mail","attività":"Activity Monitor",
               "preferenze":"System Preferences","impostazioni":"System Preferences",
               "calcolatrice":"Calculator","calc":"Calculator","whatsapp":"WhatsApp",
               "xcode":"Xcode","docker":"Docker","figma":"Figma","slack":"Slack"}
    name = aliases.get(app_name.lower(), app_name)
    rc, _ = _run(f'open -a "{name}"')
    return f"✅ {name} aperta" if rc==0 else f"⚠ App '{name}' non trovata"

def web_search(query="", **_):
    q = urllib.parse.quote_plus(query)
    _run(f'open "https://www.google.com/search?q={q}"')
    return f"✅ Ricerca Google: '{query}'"

def system_volume(action="", level=None, **_):
    if action=="set" and level is not None:
        _osa(f"set volume output volume {level}"); return f"✅ Volume → {level}%"
    elif action=="mute":
        _osa("set volume with output muted"); return "✅ Muto"
    elif action=="unmute":
        _osa("set volume without output muted"); return "✅ Audio attivo"
    elif action=="get":
        v = _osa("output volume of (get volume settings)"); return f"Volume: {v}%"
    return "⚠ Azione non valida"

def get_system_info(info_type="all", **_):
    r = {}
    if info_type in ("battery","all"): r["battery"] = _run("pmset -g batt | grep -o '[0-9]*%' | head -1")[1] or "N/A"
    if info_type in ("cpu","all"):     r["cpu"]     = _run("top -l 1 -n 0 | grep 'CPU usage' | awk '{print $3}'")[1] or "N/A"
    if info_type in ("ram","all"):     r["ram"]     = _run("memory_pressure | grep 'System-wide memory free percentage'")[1] or "N/A"
    if info_type in ("disk","all"):    r["disk"]    = _run("df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}' ")[1] or "N/A"
    if info_type in ("ip","all"):      r["ip"]      = _run("ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1")[1] or "N/A"
    if info_type in ("uptime","all"):  r["uptime"]  = _run("uptime | awk -F'up ' '{print $2}' | awk -F',' '{print $1}'")[1] or "N/A"
    if len(r)==1: return list(r.values())[0]
    return " | ".join(f"{k}:{v}" for k,v in r.items())

def clipboard_action(action="", text="", **_):
    if action=="read":
        _, out = _run("pbpaste"); return f"📋 {out[:300]}" if out else "📋 Clipboard vuota"
    elif action=="write":
        subprocess.run("pbcopy", input=text.encode(), check=True); return f"✅ Copiato: {text[:80]}"
    return "⚠ Azione non valida"

def send_notification(title="", message="", subtitle="", **_):
    sub = f'subtitle "{subtitle}"' if subtitle else ""
    _osa(f'display notification "{message}" with title "{title}" {sub}')
    return f"✅ Notifica: {title}"

def set_reminder(title="", notes="", minutes_from_now=0, **_):
    if minutes_from_now>0:
        script = f'tell application "Reminders" to make new reminder with properties {{name:"{title}",body:"{notes}",remind me date:(current date) + {minutes_from_now*60}}}'
    else:
        script = f'tell application "Reminders" to make new reminder with properties {{name:"{title}",body:"{notes}"}}'
    _osa(script)
    t = f" tra {minutes_from_now} min" if minutes_from_now else ""
    return f"✅ Promemoria: '{title}'{t}"

def play_music(action="", app="Music", **_):
    cmds = {"play":f'tell application "{app}" to play',"pause":f'tell application "{app}" to pause',
            "stop":f'tell application "{app}" to stop',"next":f'tell application "{app}" to next track',
            "previous":f'tell application "{app}" to previous track'}
    s = cmds.get(action)
    if not s: return f"⚠ Azione non valida: {action}"
    _osa(s); return f"✅ {app}: {action}"

def quit_app(app_name="", **_):
    _osa(f'tell application "{app_name}" to quit'); return f"✅ {app_name} chiusa"

def lock_screen(**_):
    _run('"/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession" -suspend')
    return "✅ Schermo bloccato"

def show_desktop(**_):
    _osa('tell application "System Events" to key code 103 using {command down}')
    return "✅ Desktop mostrato"

def set_brightness(level=100, **_):
    level = max(0, min(100, int(level)))
    rc, _ = _run(f'brightness {level/100:.2f} 2>/dev/null || echo "N/A"')
    return f"✅ Luminosità → {level}%" if rc==0 else "⚠ Installa: brew install brightness"

def run_terminal_command(command="", **_):
    BLOCKED = ["rm -rf /","sudo rm -rf","mkfs","dd if=/dev","fork bomb",":(){"]
    for b in BLOCKED:
        if b in command: return f"⛔ Comando bloccato: '{b}'"
    rc, out = _run(command)
    return f"{'✅' if rc==0 else '⚠'} {out[:400] or '(ok)'}"

# ── CALENDAR ──
def calendar_today(**_): return get_today_events()
def calendar_upcoming(days=7, **_): return get_upcoming_events(days)
def calendar_create(title="", start_date="", duration_minutes=60, **_):
    return create_event(title, start_date, duration_minutes)
def calendar_list(**_): return get_calendars()
def calendar_open(**_): return open_calendar_app()

# ── MAIL ──
def mail_unread(**_): return get_unread_count()
def mail_recent(limit=5, **_): return get_recent_emails(limit)
def mail_search(query="", **_): return search_emails(query)
def mail_read_aloud(**_):
    """Recupera email non lette e le restituisce per lettura vocale"""
    from jarvis_mail import parse_unread_count, format_emails_for_speech
    count = get_unread_count()
    if "Nessuna" in count:
        return count
    emails_data = get_recent_emails(limit=5)
    speech = format_emails_for_speech(emails_data)
    return speech

def mail_send(to="", subject="", body="", cc="", bcc="", **_):
    """Invia email tramite Apple Mail con AppleScript"""
    if not to or not subject or not body:
        return "⚠ Servono destinatario, oggetto e corpo."
    import subprocess, re as _re
    def esc(s):
        return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')
    # Se "to" sembra un nome (no @), usa {name} invece di {address}
    if '@' in to:
        to_props = '{{address:"{0}"}}'.format(esc(to))
    else:
        to_props = '{{name:"{0}"}}'.format(esc(to))
    script = f'''
    tell application "Mail"
        set newMsg to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
        tell newMsg
            make new to recipient at end of to recipients with properties {to_props}
    '''
    def _p(s):
        return '{{name:"{0}"}}'.format(esc(s)) if '@' not in s else '{{address:"{0}"}}'.format(esc(s))
    if cc:
        script += f'''
            make new cc recipient at end of cc recipients with properties {_p(cc)}
    '''
    if bcc:
        script += f'''
            make new bcc recipient at end of bcc recipients with properties {_p(bcc)}
    '''
    script += '''
            send
        end tell
    end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        return f"✅ Email inviata a {to} con oggetto \"{subject}\""
    err = (r.stderr or r.stdout or '').strip()
    return f"⚠ Errore invio email: {err}"

# ── NOTES ──
def notes_create(title="", body="", **_): return create_note(title, body)
def notes_search(query="", **_): return search_notes(query)
def notes_list(limit=10, **_): return list_notes(limit)

# ── SCREEN ──
def screen_info(**_):
    apps = get_screen_description()
    disp = get_display_info()
    return f"🖥 App visibili: {apps}\n{disp}"
def screen_frontmost(**_):
    info = get_frontmost_window_info()
    return f"🖥 App: {info['app']} | Finestra: {info['window']}"

# ── BROWSER ──
def browser_tabs(**_):
    tabs = get_browser_tabs()
    if isinstance(tabs, list):
        return "\n".join(f"🌐 {t['title']}\n   {t['url']}" for t in tabs[:10])
    return str(tabs)
def browser_current(**_):
    info = get_page_content_js()
    return f"🌐 {info['title']}\n   {info['url']}"
def browser_scroll(direction="down", **_): return scroll_page(direction)

# ── FILES ──
def files_list(path="~/Desktop", **_): return list_directory(path)
def files_read(path="", **_): return read_file(path)
def files_create(path="", content="", **_): return create_file(path, content)
def files_search(query="", path="~", **_): return search_files(query, path)
def files_info(path="", **_): return get_file_info(path)
def files_organize(**_): return organize_downloads()
def files_delete(path="", **_): return delete_file(path)

# ── MEMORY ──
def memory_remember(content="", category="fact", tags="", **_):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    return memory.remember(content, category, tag_list)
def memory_search(query="", **_):
    results = memory.search(query)
    return "\n".join(f"🧠 [{r.get('category','')}] {r['content']}" for r in results)
def memory_preferences(**_):
    prefs = memory.get_all_preferences()
    if not prefs: return "Nessuna preferenza salvata"
    return "\n".join(f"⚙ {k}: {v}" for k, v in prefs.items())
def memory_stats(**_):
    s = memory.stats()
    return f"🧠 Memorie: {s['total_memories']} | Categorie: {s['by_category']} | Conversazioni: {s['conversation_entries']}"

# ── SHORTCUTS ──
def shortcuts_run(name="", **_): return run_shortcut(name)
def shortcuts_list(**_): return list_shortcuts()

# ── PLANNER ──
def planner_create(title="", steps=None, priority="medium", **_):
    if isinstance(steps, str):
        steps = [s.strip() for s in steps.split(",")]
    return create_plan(title, steps or [], priority)
def planner_list(**_): return get_active_plans()
def planner_complete(plan_id=0, step=0, **_): return complete_step(plan_id, step)
def planner_detail(plan_id=0, **_): return get_plan_detail(plan_id)

# ── WEB SEARCH ──
def web_search_ddg_tool(query="", max_results=8, **_): return web_search_ddg(query, max_results)

# ── GIT ──
def git_status_tool(**_): return git_status()
def git_log_tool(count=10, **_): return git_log(count=count)
def git_branches_tool(**_): return git_branches()
def git_diff_tool(**_): return git_diff()
def git_commit_tool(message="", **_): return git_commit(message)
def git_create_branch_tool(name="", **_): return git_create_branch(name)
def git_command_tool(command="", **_): return git_execute(command)

# ── OCR + SCREEN AWARENESS ──
def screen_ocr_tool(image_path="", **_):
    return ocr_screenshot(image_path if image_path else None)
def screen_summary_tool(**_): return screen_awareness_summary()
def screen_selected_text_tool(**_): return get_selected_text()

# ── BROWSER PLAYWRIGHT ──
def browser_navigate_tool(url="", **_): return playwright_navigate(url)
def browser_extract_tool(url="", selector="body", **_): return playwright_extract(url, selector)
def browser_playwright_click_tool(selector="", url="", **_): return playwright_click(selector, url if url else None)
def browser_playwright_fill_tool(selector="", text="", url="", **_): return playwright_fill(selector, text, url if url else None)
def browser_screenshot_tool(url="", save_path="", **_): return playwright_screenshot(url, save_path if save_path else None)

# ── COMPUTER USE ──
def computer_mouse_move_tool(x=0, y=0, **_): return mouse_move(x, y)
def computer_mouse_click_tool(x=None, y=None, button="left", clicks=1, **_):
    return mouse_click(x, y, button, clicks)
def computer_mouse_drag_tool(from_x=0, from_y=0, to_x=0, to_y=0, **_):
    return mouse_drag(from_x, from_y, to_x, to_y)
def computer_keyboard_type_tool(text="", **_): return keyboard_type(text)
def computer_keyboard_press_tool(key="", modifiers="", **_):
    mods = [m.strip() for m in modifiers.split(",")] if modifiers else None
    return keyboard_press(key, mods)
def computer_keyboard_shortcut_tool(keys="", **_): return keyboard_shortcut(keys)
def computer_mouse_position_tool(**_): return get_mouse_position()
def computer_resolution_tool(**_): return get_screen_resolution()

# ── RAG ──
def rag_add_document_tool(title="", content="", source="", **_):
    return rag.add_document(title, content, source)
def rag_add_file_tool(file_path="", **_): return rag.add_file(file_path)
def rag_search_tool(query="", limit=5, **_): return rag.search(query, limit)
def rag_list_tool(**_): return rag.list_documents()
def rag_stats_tool(**_): return rag.stats()

# ── APPROVAL ──
def approval_pending_tool(**_): return approval.get_pending()
def approval_approve_tool(request_id="", auto_future=False, **_):
    return approval.approve(request_id, auto_future)
def approval_deny_tool(request_id="", **_): return approval.deny(request_id)

# ── DISPATCH ──
HANDLERS = {
    "open_app":open_app,"open_url":open_url,"web_search":web_search,
    "system_volume":system_volume,"take_screenshot":take_screenshot,
    "get_system_info":get_system_info,"clipboard_action":clipboard_action,
    "send_notification":send_notification,"set_reminder":set_reminder,
    "play_music":play_music,"quit_app":quit_app,"lock_screen":lock_screen,
    "show_desktop":show_desktop,"set_brightness":set_brightness,
    "run_terminal_command":run_terminal_command,
    "calendar_today":calendar_today,"calendar_upcoming":calendar_upcoming,
    "calendar_create":calendar_create,"calendar_list":calendar_list,"calendar_open":calendar_open,
    "mail_unread":mail_unread,"mail_recent":mail_recent,"mail_search":mail_search,"mail_read_aloud":mail_read_aloud,
    "mail_send":mail_send,
    "notes_create":notes_create,"notes_search":notes_search,"notes_list":notes_list,
    "screen_info":screen_info,"screen_frontmost":screen_frontmost,
    "browser_tabs":browser_tabs,"browser_current":browser_current,"browser_scroll":browser_scroll,
    "files_list":files_list,"files_read":files_read,"files_create":files_create,
    "files_search":files_search,"files_info":files_info,"files_organize":files_organize,
    "files_delete":files_delete,
    "memory_remember":memory_remember,"memory_search":memory_search,
    "memory_preferences":memory_preferences,"memory_stats":memory_stats,
    "shortcuts_run":shortcuts_run,"shortcuts_list":shortcuts_list,
    "planner_create":planner_create,"planner_list":planner_list,
    "planner_complete":planner_complete,"planner_detail":planner_detail,
    "web_search_ddg":web_search_ddg_tool,
    "git_status":git_status_tool,"git_log":git_log_tool,"git_branches":git_branches_tool,
    "git_diff":git_diff_tool,"git_commit":git_commit_tool,
    "git_create_branch":git_create_branch_tool,"git_command":git_command_tool,
    # OCR + Screen
    "screen_ocr":screen_ocr_tool,"screen_summary":screen_summary_tool,"screen_selected_text":screen_selected_text_tool,
    # Browser Playwright
    "browser_navigate":browser_navigate_tool,"browser_extract":browser_extract_tool,
    "browser_playwright_click":browser_playwright_click_tool,"browser_playwright_fill":browser_playwright_fill_tool,
    "browser_screenshot":browser_screenshot_tool,
    # Computer Use
    "computer_mouse_move":computer_mouse_move_tool,"computer_mouse_click":computer_mouse_click_tool,
    "computer_mouse_drag":computer_mouse_drag_tool,"computer_keyboard_type":computer_keyboard_type_tool,
    "computer_keyboard_press":computer_keyboard_press_tool,"computer_keyboard_shortcut":computer_keyboard_shortcut_tool,
    "computer_mouse_position":computer_mouse_position_tool,"computer_resolution":computer_resolution_tool,
    # RAG
    "rag_add_document":rag_add_document_tool,"rag_add_file":rag_add_file_tool,
    "rag_search":rag_search_tool,"rag_list":rag_list_tool,"rag_stats":rag_stats_tool,
    # Approval
    "approval_pending":approval_pending_tool,"approval_approve":approval_approve_tool,"approval_deny":approval_deny_tool,
}

# ── Blender tools (aggiunti a runtime se modulo disponibile) ──────────────
if _BLENDER_OK:
    def _b(fn): return lambda **kw: fn(**kw)
    HANDLERS.update({
        # Stato e scene
        "blender_status":     lambda **_: blender_status(),
        "blender_scene":      lambda **_: blender_get_scene(),
        "blender_object":     lambda name="", **_: blender_get_object(name),
        # Esecuzione codice Python in Blender
        "blender_execute":    lambda code="", **_: blender_execute(code),
        # Creazione / modifica oggetti
        "blender_create":     lambda object_type="cube", name=None, location=None,
                                     scale=None, size=1.0, **_:
                              blender_create_object(object_type, name, location, scale, size),
        "blender_delete":     lambda name="", **_: blender_delete_object(name),
        "blender_material":   lambda object_name="", color=None, material_name=None,
                                     metallic=0.0, roughness=0.5, **_:
                              blender_set_material(object_name, color, material_name, metallic, roughness),
        "blender_move":       lambda name="", location=None, rotation=None, scale=None, **_:
                              blender_move_object(name, location, rotation, scale),
        # Render e screenshot
        "blender_screenshot": lambda save_path=None, **_: blender_screenshot(save_path),
        "blender_render":     lambda output_path="/tmp/blender_render.png", frame=None, engine="EEVEE", **_:
                              blender_render(output_path, frame, engine),
        "blender_setup_avatar": lambda glb_path=None, **_:
                              blender_setup_avatar(glb_path),
        "blender_focus_view": lambda **_: blender_focus_view(),
        # PolyHaven
        "blender_polyhaven_search":    lambda query="", asset_type="hdris", **_:
                                       blender_polyhaven_search(query, asset_type),
        "blender_polyhaven_download":  lambda asset_id="", asset_type="textures", resolution="2k", **_:
                                       blender_polyhaven_download(asset_id, asset_type, resolution),
        # Sketchfab
        "blender_sketchfab_search":    lambda query="", count=10, **_:
                                       blender_sketchfab_search(query, count),
        "blender_sketchfab_download":  lambda model_id="", **_:
                                       blender_sketchfab_download(model_id),
    })

def execute_tool(name, arguments):
    h = HANDLERS.get(name)
    if not h: return f"⚠ Tool '{name}' non trovato"
    try: return h(**arguments)
    except Exception as e: return f"⚠ Errore {name}: {e}"
