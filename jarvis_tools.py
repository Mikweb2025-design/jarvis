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
# ── nuovi moduli v9.0 ──
from jarvis_goals import (create_goal, list_goals, update_key_result, add_key_result,
    get_goal_detail, delete_goal, archive_goal)
from jarvis_providers import (list_providers, set_provider, set_provider_model,
    switch_active, get_active_provider, chat_completion, estimate_cost)
from jarvis_network import (public_ip, ip_geolocation, ping_test, dns_lookup,
    port_check, bandwidth_speedtest, connectivity_summary)
from jarvis_mcp import (list_servers, enable_server, disable_server, add_server,
    remove_server, call_tool, list_tools)
from jarvis_homeassistant import (ha_get_config, ha_get_states, ha_get_state,
    ha_call_service, ha_fire_event, ha_get_services, ha_get_history, ha_get_logbook,
    ha_dashboard_url)
# ── Trend Monitoring v9.3 ──
from jarvis_trends import trends_search as _trends_search, trending_now as _trending_now
# ── Telegram v9.3 ──
from jarvis_telegram import send as _telegram_send, status as _telegram_status
# ── Self-Evolution Engine v11.0 ──
from jarvis_evolution import evol
# ── Vision Engine v11.0 ──
from jarvis_vision import vision
from jarvis_docs import docgen
# ── Voice Engine v11.0 ──
from jarvis_voice import voice
# ── macOS Native Control v11.0 ──
from jarvis_os_control import os_control
# ── Security Chain v11.0 ──
from jarvis_security import security
# ── Multi-Agent Pantheon v11.0 ──
from jarvis_pantheon import pantheon
# ── Plugin Store v11.0 ──
from jarvis_plugins import plugins
from jarvis_skills import skills
# ── World News v10.0 ──
from jarvis_worldnews import fetch_world_news as _fetch_world_news
# ── Image Generation v12.0 ──
from jarvis_imagegen import generate_image as _generate_image, list_models as _list_image_models
# ── Music Generation v12.0 (ACE-Step) ──
from jarvis_musicgen import generate_music as _generate_music, list_genres as _list_music_genres, get_status as _music_status
# ── WhatsApp v1.0 (OpenWA) ──
try:
    from jarvis_whatsapp_openwa import send_message as _wa_send_msg, send_image as _wa_send_img, send_audio as _wa_send_audio, get_status as _wa_status, ensure_session as _wa_ensure
    _WA_OK = True
except ImportError:
    _WA_OK = False
# ── Knowledge Graph v12.0 (GitNexus) ──
from jarvis_gitnexus import (analyze_repo as _kg_analyze, build_knowledge_graph as _kg_graph,
    get_symbols as _kg_symbols, search_code as _kg_search, get_status as _kg_status)
# ── Blender MCP (opzionale — non blocca se Blender è chiuso) ──
try:
    from jarvis_blender import (
        blender_status, blender_get_scene, blender_get_object, blender_execute,
        blender_create_object, blender_delete_object, blender_set_material,
        blender_move_object, blender_screenshot, blender_render,
        blender_setup_avatar, blender_focus_view,
        blender_enable_hyper3d, blender_generate_hyper3d,
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
    {"type":"function","function":{"name":"files_copy","description":"Copia file","parameters":{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]}}},
    {"type":"function","function":{"name":"files_move","description":"Sposta/rinomina file","parameters":{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]}}},
    {"type":"function","function":{"name":"files_rename","description":"Rinomina file","parameters":{"type":"object","properties":{"path":{"type":"string"},"new_name":{"type":"string"}},"required":["path","new_name"]}}},
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
    {"type":"function","function":{"name":"rag_add_folder","description":"Indicizza tutti i file in una cartella nel database RAG","parameters":{"type":"object","properties":{"folder_path":{"type":"string"},"recursive":{"type":"boolean","default":True}},"required":["folder_path"]}}},
    {"type":"function","function":{"name":"rag_search","description":"Cerca documenti nel database RAG (ricerca ibrida FTS + semantica)","parameters":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"rag_semantic_search","description":"Cerca documenti con sola similarità semantica (cosine similarity)","parameters":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"rag_list","description":"Lista documenti nel database RAG","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"rag_stats","description":"Statistiche database RAG","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"rag_delete","description":"Elimina un documento dal database RAG","parameters":{"type":"object","properties":{"doc_id":{"type":"integer"}},"required":["doc_id"]}}},
    {"type":"function","function":{"name":"rag_delete_all","description":"Elimina TUTTI i documenti dal database RAG","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"rag_get_document","description":"Recupera documento completo con chunk dal database RAG","parameters":{"type":"object","properties":{"doc_id":{"type":"integer"}},"required":["doc_id"]}}},
    {"type":"function","function":{"name":"rag_update_document","description":"Aggiorna titolo/contenuto/source di un documento RAG","parameters":{"type":"object","properties":{"doc_id":{"type":"integer"},"title":{"type":"string"},"content":{"type":"string"},"source":{"type":"string"}},"required":["doc_id"]}}},
    {"type":"function","function":{"name":"rag_reembed","description":"Rigenera tutti gli embedding del database RAG (dopo cambio modello)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"rag_search_by_source","description":"Cerca documenti RAG per percorso sorgente","parameters":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer","default":50}},"required":["query"]}}},
    {"type":"function","function":{"name":"rag_export","description":"Esporta intero database RAG in formato JSON","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"rag_dedup","description":"Trova e rimuove documenti duplicati dal database RAG","parameters":{"type":"object","properties":{"threshold":{"type":"number","default":0.95,"description":"Soglia similarità (0-1)"}}}}},
    # Approval
    {"type":"function","function":{"name":"approval_pending","description":"Lista richieste approvazione pending","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"approval_approve","description":"Approva richiesta","parameters":{"type":"object","properties":{"request_id":{"type":"string"},"auto_future":{"type":"boolean","default":False}},"required":["request_id"]}}},
    {"type":"function","function":{"name":"approval_deny","description":"Nega richiesta","parameters":{"type":"object","properties":{"request_id":{"type":"string"}},"required":["request_id"]}}},
    # Blender 3D (via MCP)
    {"type":"function","function":{"name":"blender_status","description":"Verifica se Blender è connesso e gli addon attivi","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"blender_scene","description":"Info sulla scena Blender: oggetti, frame, render engine","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"blender_execute","description":"Esegue codice Python bpy arbitrario in Blender. Usalo per creare/modificare QUALSIASI cosa: oggetti, materiali, modificatori, ecc.","parameters":{"type":"object","properties":{"code":{"type":"string","description":"Codice Python con bpy"}},"required":["code"]}}},
    {"type":"function","function":{"name":"blender_create","description":"Crea una primitiva 3D in Blender","parameters":{"type":"object","properties":{"object_type":{"type":"string","enum":["cube","sphere","cylinder","plane","torus","monkey","cone","light","camera"]},"name":{"type":"string"}},"required":["object_type"]}}},
    {"type":"function","function":{"name":"blender_delete","description":"Elimina un oggetto Blender per nome","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"blender_material","description":"Applica un materiale colorato a un oggetto","parameters":{"type":"object","properties":{"object_name":{"type":"string"},"color":{"type":"array","items":{"type":"number"},"description":"[R,G,B] 0-1"},"metallic":{"type":"number","default":0.0},"roughness":{"type":"number","default":0.5}},"required":["object_name"]}}},
    {"type":"function","function":{"name":"blender_render","description":"Renderizza la scena Blender e salva PNG","parameters":{"type":"object","properties":{"output_path":{"type":"string","default":"/tmp/blender_render.png"}}}}},
    {"type":"function","function":{"name":"blender_screenshot","description":"Cattura screenshot del viewport 3D","parameters":{"type":"object","properties":{"save_path":{"type":"string","default":"/tmp/blender_viewport.png"}}}}},
    {"type":"function","function":{"name":"blender_focus_view","description":"Material preview + inquadra tutti gli oggetti nel viewport","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"blender_setup_avatar","description":"Importa l'avatar RPM con luci e camera ritratto","parameters":{"type":"object","properties":{}}}},
    # ── Goals/OKR v9.0 ──
    {"type":"function","function":{"name":"goals_create","description":"Crea un obiettivo con Key Results misurabili (OKR)","parameters":{"type":"object","properties":{"title":{"type":"string"},"description":{"type":"string","default":""},"key_results":{"type":"array","items":{"type":"string"},"description":"Lista di key results misurabili"},"priority":{"type":"string","enum":["low","medium","high"],"default":"medium"}},"required":["title"]}}},
    {"type":"function","function":{"name":"goals_list","description":"Elenca obiettivi attivi, completati o archiviati","parameters":{"type":"object","properties":{"status":{"type":"string","enum":["active","completed","archived"],"default":""}}}}},
    {"type":"function","function":{"name":"goals_detail","description":"Dettaglio obiettivo con progresso key results","parameters":{"type":"object","properties":{"goal_id":{"type":"integer"}},"required":["goal_id"]}}},
    {"type":"function","function":{"name":"goals_update_kr","description":"Aggiorna progresso di un Key Result","parameters":{"type":"object","properties":{"goal_id":{"type":"integer"},"kr_id":{"type":"integer"},"current":{"type":"integer"}},"required":["goal_id","kr_id","current"]}}},
    {"type":"function","function":{"name":"goals_add_kr","description":"Aggiunge un Key Result a un obiettivo","parameters":{"type":"object","properties":{"goal_id":{"type":"integer"},"description":{"type":"string"},"target":{"type":"integer","default":100}},"required":["goal_id","description"]}}},
    {"type":"function","function":{"name":"goals_delete","description":"Elimina un obiettivo","parameters":{"type":"object","properties":{"goal_id":{"type":"integer"}},"required":["goal_id"]}}},
    {"type":"function","function":{"name":"goals_archive","description":"Archivia un obiettivo completato","parameters":{"type":"object","properties":{"goal_id":{"type":"integer"}},"required":["goal_id"]}}},
    # ── Providers v9.0 (Multi-LLM Switchboard) ──
    {"type":"function","function":{"name":"providers_list","description":"Elenca provider LLM e loro stato","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"providers_switch","description":"Cambia provider LLM attivo (groq, ollama, openai, gemini, anthropic)","parameters":{"type":"object","properties":{"provider":{"type":"string","enum":["groq","ollama","openai","gemini","anthropic"]}},"required":["provider"]}}},
    {"type":"function","function":{"name":"providers_set_model","description":"Cambia modello per un provider","parameters":{"type":"object","properties":{"provider":{"type":"string"},"model":{"type":"string"}},"required":["provider","model"]}}},
    # ── Network v9.0 ──
    {"type":"function","function":{"name":"network_public_ip","description":"Mostra IP pubblico e geolocalizzazione","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"network_ping","description":"Test ping verso un host","parameters":{"type":"object","properties":{"host":{"type":"string","default":"8.8.8.8"}}}}},
    {"type":"function","function":{"name":"network_dns","description":"Lookup DNS per un dominio","parameters":{"type":"object","properties":{"domain":{"type":"string","default":"google.com"}}}}},
    {"type":"function","function":{"name":"network_speedtest","description":"Test velocità connessione","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"network_connectivity","description":"Report completo connettività internet","parameters":{"type":"object","properties":{}}}},
    # ── World Map ──
    {"type":"function","function":{"name":"open_world_map","description":"Griglia webcam mondo: Milano, Venezia, Tokyo, Berlino, New York, Sydney","parameters":{"type":"object","properties":{}}}},
    # ── MCP v9.0 ──
    {"type":"function","function":{"name":"mcp_list","description":"Elenca server MCP configurati","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"mcp_enable","description":"Attiva un server MCP (github, slack, filesystem, ecc.)","parameters":{"type":"object","properties":{"name":{"type":"string"},"env":{"type":"object"}},"required":["name"]}}},
    {"type":"function","function":{"name":"mcp_disable","description":"Disattiva un server MCP","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"mcp_tools","description":"Elenca tools disponibili su un server MCP","parameters":{"type":"object","properties":{"server":{"type":"string"}},"required":["server"]}}},
    {"type":"function","function":{"name":"mcp_call","description":"Chiama un tool su un server MCP","parameters":{"type":"object","properties":{"server":{"type":"string"},"tool":{"type":"string"},"args":{"type":"object"}},"required":["server","tool"]}}},
    # ── Home Assistant v9.0 ──
    {"type":"function","function":{"name":"ha_config","description":"Mostra configurazione Home Assistant (versione, nome, unità, fuso orario)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"ha_states","description":"Elenca tutte le entità Home Assistant con il loro stato attuale, raggruppate per dominio","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"ha_state","description":"Ottiene lo stato di una specifica entità Home Assistant","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"ID entità (es. light.soggiorno, sensor.temperatura)"}},"required":["entity_id"]}}},
    {"type":"function","function":{"name":"ha_service","description":"Chiama un servizio Home Assistant (es. accendi/spegni luci, imposta termostato). Se non specifici entity_id, agisce su TUTTE le luci accese/spente.","parameters":{"type":"object","properties":{"domain":{"type":"string","description":"Dominio del servizio (es. light, switch, climate, media_player)"},"service":{"type":"string","description":"Nome servizio (es. turn_on, turn_off, set_temperature)"},"entity_id":{"type":"string","description":"ID entità da controllare (es. light.soggiorno, light.lampe1, switch.ventilatore). Opzionale: se omesso agisce su tutte le luci."},"data":{"type":"object","description":"Parametri aggiuntivi (es. brightness, temperature, rgb_color)"}},"required":["domain","service"]}}},
    {"type":"function","function":{"name":"ha_dashboard","description":"Apre la dashboard di Home Assistant nel browser","parameters":{"type":"object","properties":{}}}},
    # ── Trends v9.3 ──
    {"type":"function","function":{"name":"trends_search","description":"Cerca tendenze/trend attuali in una categoria (technology, ai, social, startup, opensource, german, italian)","parameters":{"type":"object","properties":{"category":{"type":"string","default":"technology"},"region":{"type":"string","default":"wt"},"max_results":{"type":"integer","default":10}},"required":["category"]}}},
    {"type":"function","function":{"name":"trending_now","description":"Trend del momento — scorciatoia rapida per cosa sta trendendo ora","parameters":{"type":"object","properties":{"region":{"type":"string","default":"it"}}}}},
    # ── Telegram v9.3 ──
    {"type":"function","function":{"name":"telegram_send","description":"Invia un messaggio Telegram. chat_id opzionale (default: usa config.json)","parameters":{"type":"object","properties":{"message":{"type":"string"},"chat_id":{"type":"integer","default":0}},"required":["message"]}}},
    # ── World News v10.0 ──
    {"type":"function","function":{"name":"world_news","description":"Notizie dal mondo geo-localizzate su mappa interattiva. Mostra news da BBC, NYT, ANSA, Tagesschau con posizione geografica.","parameters":{"type":"object","properties":{"max_items":{"type":"integer","default":30}},"required":[]}}},
    # Self-Evolution Engine v11.0
    {"type":"function","function":{"name":"evolution_status","description":"Stato del Self-Evolution Engine: salute, errori, healing, skills generate, pattern","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"evolution_daily_report","description":"Report giornaliero performance: errori oggi, risolti, healing, health score","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"evolution_weekly_report","description":"Report settimanale: errori irrisolti, auto-fix, categorie errori","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"evolution_heal","description":"Esegue auto-healing: verifica servizi (Blender MCP, Ollama, disco) e ripara automaticamente","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"evolution_audit","description":"Dawn Audit completo: check di tutti i servizi e sistema","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"evolution_analyze","description":"Analisi pattern conversazione: topic frequenti, tool più usati, comportamenti","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"evolution_skills","description":"Lista skills generate automaticamente dall'Evolution Engine","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"evolution_generate_skill","description":"Genera una nuova skill Python automaticamente. nome e descrizione obbligatori.","parameters":{"type":"object","properties":{"name":{"type":"string"},"description":{"type":"string"}},"required":["name","description"]}}},
    # Vision Engine v11.0
    {"type":"function","function":{"name":"vision_analyze","description":"Analisi completa screenshot: oggetti, testo, QR, volti, colori dominanti","parameters":{"type":"object","properties":{"image_path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"vision_read_text","description":"Legge testo da immagine usando Apple Vision + Tesseract OCR","parameters":{"type":"object","properties":{"image_path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"vision_detect_qr","description":"Rileva codici QR e barcode in uno screenshot","parameters":{"type":"object","properties":{"image_path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"vision_describe","description":"Descrive un'immagine usando AI vision (Ollama llava)","parameters":{"type":"object","properties":{"image_path":{"type":"string"}},"required":["image_path"]}}},
    {"type":"function","function":{"name":"vision_analyze_region","description":"Cattura e analizza una regione specifica dello schermo","parameters":{"type":"object","properties":{"x":{"type":"integer"},"y":{"type":"integer"},"w":{"type":"integer"},"h":{"type":"integer"}},"required":["x","y","w","h"]}}},
    {"type":"function","function":{"name":"vision_detect_faces","description":"Rileva volti in uno screenshot o immagine","parameters":{"type":"object","properties":{"image_path":{"type":"string","default":""}}}}},
    # Voice Engine v11.0
    {"type":"function","function":{"name":"voice_say","description":"Parla ad alta voce con sintesi vocale (PlayAI o macOS say)","parameters":{"type":"object","properties":{"text":{"type":"string"},"voice":{"type":"string","default":""},"speed":{"type":"number","default":1.0}},"required":["text"]}}},
    {"type":"function","function":{"name":"voice_listen","description":"Ascolta microfono e trascrive in testo (STT)","parameters":{"type":"object","properties":{"timeout":{"type":"integer","default":5},"language":{"type":"string","default":"it-IT"}}}}},
    {"type":"function","function":{"name":"voice_list","description":"Elenca tutte le voci PlayAI disponibili","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"voice_set","description":"Cambia voce attiva per sintesi vocale","parameters":{"type":"object","properties":{"voice":{"type":"string"}},"required":["voice"]}}},
    # macOS Native Control v11.0
    {"type":"function","function":{"name":"os_list_windows","description":"Elenca tutte le finestre aperte con posizione e dimensione","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_focus_window","description":"Porta in primo piano una finestra per titolo o nome app","parameters":{"type":"object","properties":{"title":{"type":"string"}},"required":["title"]}}},
    {"type":"function","function":{"name":"os_move_window","description":"Sposta e ridimensiona una finestra","parameters":{"type":"object","properties":{"title":{"type":"string"},"x":{"type":"integer"},"y":{"type":"integer"},"width":{"type":"integer","default":0},"height":{"type":"integer","default":0}},"required":["title"]}}},
    {"type":"function","function":{"name":"os_minimize_window","description":"Minimizza una finestra","parameters":{"type":"object","properties":{"title":{"type":"string"}},"required":["title"]}}},
    {"type":"function","function":{"name":"os_maximize_window","description":"Massimizza una finestra","parameters":{"type":"object","properties":{"title":{"type":"string"}},"required":["title"]}}},
    {"type":"function","function":{"name":"os_list_apps","description":"Elenca tutte le app in esecuzione","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_app_info","description":"Info dettagliate su un'app in esecuzione","parameters":{"type":"object","properties":{"app_name":{"type":"string"}},"required":["app_name"]}}},
    {"type":"function","function":{"name":"os_tile_window_left","description":"Affianca finestra a sinistra (metà schermo)","parameters":{"type":"object","properties":{"title":{"type":"string"}},"required":["title"]}}},
    {"type":"function","function":{"name":"os_tile_window_right","description":"Affianca finestra a destra (metà schermo)","parameters":{"type":"object","properties":{"title":{"type":"string"}},"required":["title"]}}},
    {"type":"function","function":{"name":"os_arrange_grid","description":"Disponi finestre in griglia 2x2","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_open_pref_pane","description":"Apri pannello preferenze di sistema","parameters":{"type":"object","properties":{"pane":{"type":"string","description":"display, sound, keyboard, mouse, trackpad, bluetooth, network, battery, security, dock"}},"required":["pane"]}}},
    {"type":"function","function":{"name":"os_toggle_dark_mode","description":"Attiva/disattiva modalità scura","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_screensaver","description":"Avvia screensaver","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_empty_trash","description":"Svuota il cestino","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_sleep_display","description":"Mette in sleep il display","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_set_wallpaper","description":"Cambia sfondo desktop","parameters":{"type":"object","properties":{"image_path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"os_dock_autohide","description":"Nasconde/mostra automaticamente il Dock","parameters":{"type":"object","properties":{"enabled":{"type":"boolean","default":True}}}}},
    {"type":"function","function":{"name":"os_dock_position","description":"Cambia posizione Dock (left, bottom, right)","parameters":{"type":"object","properties":{"position":{"type":"string","enum":["left","bottom","right"]}},"required":["position"]}}},
    {"type":"function","function":{"name":"os_next_space","description":"Vai al workspace successivo (Mission Control)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_prev_space","description":"Vai al workspace precedente","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_show_desktop","description":"Mostra desktop (nasconde tutte le finestre)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"os_system_profiler","description":"Info hardware dettagliate","parameters":{"type":"object","properties":{"category":{"type":"string","default":"SPHardwareDataType"}}}}},
    {"type":"function","function":{"name":"os_list_processes","description":"Elenco processi in esecuzione","parameters":{"type":"object","properties":{"count":{"type":"integer","default":20}}}}},
    # Security Chain v11.0
    {"type":"function","function":{"name":"security_check_command","description":"Verifica se un comando è sicuro da eseguire","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
    {"type":"function","function":{"name":"security_trust_score","description":"Mostra trust score di un'entità (tool, utente)","parameters":{"type":"object","properties":{"entity":{"type":"string"}},"required":["entity"]}}},
    {"type":"function","function":{"name":"security_audit_log","description":"Mostra log di audit della sicurezza (ultime azioni)","parameters":{"type":"object","properties":{"limit":{"type":"integer","default":20}}}}},
    {"type":"function","function":{"name":"security_activity_report","description":"Report completo attività di sicurezza","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"security_add_rule","description":"Aggiungi regola di permesso","parameters":{"type":"object","properties":{"pattern":{"type":"string"},"level":{"type":"string","enum":["read","write","admin","deny"]},"category":{"type":"string","default":"command"}},"required":["pattern","level"]}}},
    {"type":"function","function":{"name":"security_list_rules","description":"Elenca regole di permesso attive","parameters":{"type":"object","properties":{}}}},
    # Pantheon Multi-Agent v11.0
    {"type":"function","function":{"name":"pantheon_list_agents","description":"Elenca agenti registrati nel Pantheon","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"pantheon_agent_info","description":"Info dettagliate su un agente","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"pantheon_register","description":"Registra un nuovo agente","parameters":{"type":"object","properties":{"name":{"type":"string"},"capabilities":{"type":"string","default":""},"endpoint":{"type":"string","default":""}},"required":["name"]}}},
    {"type":"function","function":{"name":"pantheon_delegate","description":"Delega un task a un agente (o auto-seleziona il migliore)","parameters":{"type":"object","properties":{"description":{"type":"string"},"agent":{"type":"string","default":""},"priority":{"type":"integer","default":0}},"required":["description"]}}},
    {"type":"function","function":{"name":"pantheon_task_status","description":"Stato di un task delegato","parameters":{"type":"object","properties":{"task_id":{"type":"string"}},"required":["task_id"]}}},
    {"type":"function","function":{"name":"pantheon_list_tasks","description":"Elenca task in sospeso","parameters":{"type":"object","properties":{"limit":{"type":"integer","default":10}}}}},
    {"type":"function","function":{"name":"pantheon_send_message","description":"Invia messaggio a un agente","parameters":{"type":"object","properties":{"to_agent":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string","default":""}},"required":["to_agent","subject"]}}},
    {"type":"function","function":{"name":"pantheon_read_messages","description":"Leggi messaggi ricevuti","parameters":{"type":"object","properties":{"unread_only":{"type":"boolean","default":True}}}}},
    {"type":"function","function":{"name":"pantheon_broadcast","description":"Invia messaggio a tutti gli agenti","parameters":{"type":"object","properties":{"subject":{"type":"string"},"body":{"type":"string","default":""}},"required":["subject"]}}},
    {"type":"function","function":{"name":"pantheon_economy","description":"Report economia agenti (crediti, transazioni)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"pantheon_transfer","description":"Trasferisci crediti tra agenti","parameters":{"type":"object","properties":{"from_agent":{"type":"string"},"to_agent":{"type":"string"},"amount":{"type":"number"},"reason":{"type":"string","default":""}},"required":["from_agent","to_agent","amount"]}}},
    {"type":"function","function":{"name":"pantheon_balance","description":"Mostra saldo crediti di un agente","parameters":{"type":"object","properties":{"agent_name":{"type":"string"}},"required":["agent_name"]}}},
    {"type":"function","function":{"name":"pantheon_orchestrate","description":"Scompone un task complesso e lo delega a più agenti","parameters":{"type":"object","properties":{"task_description":{"type":"string"}},"required":["task_description"]}}},
    # Plugin Store v11.0
    {"type":"function","function":{"name":"plugins_list","description":"Elenca plugin installati","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"plugins_install","description":"Installa un plugin dal marketplace, URL o file","parameters":{"type":"object","properties":{"source":{"type":"string","description":"Nome plugin, URL, o path file"},"name":{"type":"string","default":""}},"required":["source"]}}},
    {"type":"function","function":{"name":"plugins_uninstall","description":"Disinstalla un plugin","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"plugins_enable","description":"Attiva un plugin","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"plugins_disable","description":"Disattiva un plugin","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"plugins_marketplace","description":"Esplora catalogo plugin disponibili nel marketplace","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"plugins_info","description":"Info dettagliate su un plugin","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"plugins_health","description":"Stato salute di tutti i plugin","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"plugins_check_updates","description":"Controlla aggiornamenti disponibili per i plugin installati","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"plugins_update_all","description":"Aggiorna tutti i plugin all'ultima versione","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"plugins_rate","description":"Valuta un plugin (1-5 stelle)","parameters":{"type":"object","properties":{"name":{"type":"string"},"rating":{"type":"integer","description":"1-5 stelle"},"review":{"type":"string","default":""}},"required":["name","rating"]}}},
    {"type":"function","function":{"name":"plugins_reviews","description":"Mostra recensioni di un plugin","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"plugins_search","description":"Cerca plugin nel marketplace per nome o descrizione","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"plugins_run","description":"Esegue una funzione di un plugin installato","parameters":{"type":"object","properties":{"name":{"type":"string"},"function":{"type":"string","default":""}},"required":["name"]}}},
    # Self-Learning Skills System v1.0
    {"type":"function","function":{"name":"skills_list","description":"Elenca tutte le skills auto-generate con statistiche d'uso","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"skills_create","description":"Genera una NUOVA skill con AI: descrivi cosa deve fare e l'AI genera il codice. Es: 'skills_create cerca su Google e salva risultati in un file'","parameters":{"type":"object","properties":{"name":{"type":"string","description":"Nome breve in snake_case (es: google_search_save)"},"description":{"type":"string","description":"Descrizione dettagliata di cosa deve fare la skill"},"category":{"type":"string","default":"general"}},"required":["name","description"]}}},
    {"type":"function","function":{"name":"skills_improve","description":"Migliora una skill esistente con feedback su cosa non funziona o cosa aggiungere","parameters":{"type":"object","properties":{"name":{"type":"string"},"feedback":{"type":"string","description":"Cosa migliorare o aggiungere"}},"required":["name","feedback"]}}},
    {"type":"function","function":{"name":"skills_run","description":"Esegue una skill per nome","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"skills_info","description":"Info dettagliate su una skill","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"skills_delete","description":"Elimina una skill","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"skills_stats","description":"Statistiche del Self-Learning Skills System","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"skills_suggestions","description":"Mostra suggerimenti di skill da generare basati sui tuoi pattern d'uso","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"skills_toggle","description":"Attiva o disattiva una skill","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    # Video Analytics v1.0
    {"type":"function","function":{"name":"video_analytics_start","description":"Avvia analisi video su uno stream (webcam o URL). Rileva auto, persone, stima velocità","parameters":{"type":"object","properties":{"stream_url":{"type":"string","description":"URL stream RTSP/HTTP/IP webcam, oppure '0' per webcam locale"}},"required":["stream_url"]}}},
    {"type":"function","function":{"name":"video_analytics_stop","description":"Ferma l'analisi video in corso","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"video_analytics_counts","description":"Quante auto/persone sono passate nelle ultime N ore","parameters":{"type":"object","properties":{"hours":{"type":"integer","description":"Numero di ore (default 1)","default":1}},"required":[]}}},
    {"type":"function","function":{"name":"video_analytics_status","description":"Stato dell'analisi video: FPS, frame processati, conteggi sessione, modello usato","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"video_analytics_set_line","description":"Imposta la linea virtuale di rilevamento (percentuale dall'alto, default 70%)","parameters":{"type":"object","properties":{"y_pct":{"type":"number","description":"Percentuale dall'alto (0-1), es: 0.7 = 70%","default":0.7}},"required":[]}}},
    {"type":"function","function":{"name":"video_analytics_reset","description":"Azzera tutto lo storico: conteggi sessioni, sample velocità e database","parameters":{"type":"object","properties":{}}}},
    # Document Generator v1.0
    {"type":"function","function":{"name":"doc_make_docx","description":"Crea documento Word con titolo, testo, tabella. Input: JSON con headers, rows, title, text oppure dict list","parameters":{"type":"object","properties":{"data":{"type":"string","description":"JSON: {\"title\":\"...\",\"text\":\"...\",\"headers\":[\"A\",\"B\"],\"rows\":[[1,2],[3,4]]} oppure lista di dict"},"output":{"type":"string","description":"Percorso file output (opzionale)","default":""}}}}},
    {"type":"function","function":{"name":"doc_make_docx_from_text","description":"Crea documento Word da testo semplice (multi-linea)","parameters":{"type":"object","properties":{"text":{"type":"string","description":"Testo del documento, usa \\n per newline"},"title":{"type":"string","description":"Titolo del documento","default":"Documento"}}}}},
    {"type":"function","function":{"name":"doc_make_xlsx","description":"Crea foglio Excel con tabelle formattate, filtri, colonne auto-size. Input: JSON con headers, rows, title","parameters":{"type":"object","properties":{"data":{"type":"string","description":"JSON: {\"title\":\"...\",\"headers\":[\"A\",\"B\"],\"rows\":[[1,2],[3,4]]}"},"output":{"type":"string","description":"Percorso file output (opzionale)","default":""}}}}},
    {"type":"function","function":{"name":"doc_make_pptx","description":"Crea presentazione PowerPoint con slide multiple, testo, tabelle. Input: JSON array slide con title, content, table","parameters":{"type":"object","properties":{"data":{"type":"string","description":"JSON con title/text oppure slides array: [{\"title\":\"Slide 1\",\"content\":\"testo\",\"table\":{\"headers\":[],\"rows\":[]}}]"},"slides_data":{"type":"string","description":"JSON array slide: [{\"title\":\"...\",\"content\":\"...\",\"table\":{\"headers\":[],\"rows\":[]}}] (opzionale)","default":""}}}}},
    {"type":"function","function":{"name":"doc_make_pdf","description":"Crea PDF con titolo, testo, tabelle formattate, colori","parameters":{"type":"object","properties":{"data":{"type":"string","description":"JSON: {\"title\":\"...\",\"text\":\"...\",\"headers\":[\"A\",\"B\"],\"rows\":[[1,2]]}"}}}}},
    {"type":"function","function":{"name":"doc_make_html_presentation","description":"Crea presentazione HTML interattiva con stile sentry, navigazione tastiera, grafici canvas. Supporta: title, section, content, two_column, table, chart(bar/pie/line), image, thank_you. Temi: corporate, dark, nature, sunset. Singolo file HTML autoportante (no npm/build richiesti). Input: JSON con title, theme, author, slides array","parameters":{"type":"object","properties":{"data":{"type":"string","description":"JSON con title, theme, slides array. Ogni slide: type, title, subtitle, content, items[], headers[], rows[][], chart_type, image, columns[][]"}}}}},
    {"type":"function","function":{"name":"doc_auto_presentation","description":"Crea presentazione AUTOMATICA con LLM: basta dare un tema/argomento, l'IA genera i contenuti delle slide da sola. Supporta PowerPoint (pptx) e HTML interattivo.","parameters":{"type":"object","properties":{"topic":{"type":"string","description":"Tema della presentazione (es: 'Intelligenza Artificiale', 'Report vendite Q1 2024', 'Strategia di marketing')"},"format":{"type":"string","enum":["pptx","html"],"description":"Formato: pptx (PowerPoint) o html (presentazione web interattiva)","default":"pptx"},"theme":{"type":"string","enum":["corporate","dark","nature","sunset"],"description":"Tema visivo","default":"corporate"}},"required":["topic"]}}},
    # ── Image Generation v12.0 (IONOS Hub) ──
    {"type":"function","function":{"name":"image_generate","description":"Genera immagini con AI. IMPORTANTE: passa come prompt la DESCRIZIONE COMPLETA e DETTAGLIATA che l'utente ha fornito, senza riassumere o tagliare. Includi soggetto, azione, colore, sfondo, stile — tutto. Più dettagliato è il prompt, migliore è il risultato.", "parameters":{"type":"object","properties":{"prompt":{"type":"string","description":"Descrizione COMPLETA e DETTAGLIATA dell'immagine (copia fedelmente la richiesta dell'utente, non riassumere)"},"model":{"type":"string","description":"Modello disponibile: black-forest-labs/FLUX.1-schnell (solo questo supportato)","default":"black-forest-labs/FLUX.1-schnell"},"size":{"type":"string","description":"Dimensione: 1024x1024, 1024x1792, 1792x1024","default":"1024x1024"},"n":{"type":"integer","description":"Numero di immagini da generare","default":1}},"required":["prompt"]}}},
    {"type":"function","function":{"name":"image_list_models","description":"Elenca i modelli di image generation disponibili (FLUX, SD3.5)","parameters":{"type":"object","properties":{}}}},
    # ── Music Generation v12.0 (ACE-Step) ──
    {"type":"function","function":{"name":"music_generate","description":"Genera musica con AI via ACE-Step 1.5 (funziona offline su GPU locale). Crea tracce musicali da prompt testuale o preimpostazioni di genere.","parameters":{"type":"object","properties":{"prompt":{"type":"string","description":"Descrizione della musica da generare (opzionale se usi un genere preimpostato)","default":""},"genre":{"type":"string","description":"Genere: electronic, ambient, cinematic, lo-fi, synthwave, jazz, classical","default":"electronic"},"duration":{"type":"integer","description":"Durata in secondi (max 240)","default":30},"temperature":{"type":"number","description":"Creatività (0.0-2.0)","default":1.0}},"required":[]}}},
    {"type":"function","function":{"name":"music_list_genres","description":"Elenca i generi musicali disponibili per la generazione","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"music_status","description":"Stato del music generator (ACE-Step disponibile, cartella output)","parameters":{"type":"object","properties":{}}}},
    # ── WhatsApp v1.0 (OpenWA) ──
    {"type":"function","function":{"name":"whatsapp_send","description":"Invia un messaggio WhatsApp a un contatto o numero. Usa OpenWA (gateway self-hosted).","parameters":{"type":"object","properties":{"to":{"type":"string","description":"Numero o contatto WhatsApp (es. 393401234567 o 'Mario Rossi')"},"text":{"type":"string","description":"Testo del messaggio"}},"required":["to","text"]}}},
    {"type":"function","function":{"name":"whatsapp_status","description":"Stato della connessione WhatsApp: sessione attiva, OpenWA raggiungibile","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"whatsapp_ensure","description":"Attiva/crea la sessione WhatsApp e mostra QR code se non ancora connessa","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"whatsapp_send_image","description":"Invia un'immagine via WhatsApp. Usa l'URL ottenuto da image_generate (anche URL locale /api/image?file=... funziona, viene convertito in base64).","parameters":{"type":"object","properties":{"to":{"type":"string","description":"Numero o gruppo WhatsApp (es. 120363407071302556@g.us per gruppo Jarvis)"},"url":{"type":"string","description":"URL dell'immagine (anche locale /api/image?file=...)"},"caption":{"type":"string","description":"Didascalia opzionale","default":""}},"required":["to","url"]}}},
    {"type":"function","function":{"name":"whatsapp_send_file","description":"Invia un file/documento via WhatsApp da un URL pubblico.","parameters":{"type":"object","properties":{"to":{"type":"string","description":"Numero o gruppo WhatsApp"},"url":{"type":"string","description":"URL pubblico del file"},"filename":{"type":"string","description":"Nome del file","default":""},"caption":{"type":"string","description":"Didascalia opzionale","default":""}},"required":["to","url"]}}},
    # ── Knowledge Graph v12.0 (GitNexus) ──
    {"type":"function","function":{"name":"kg_analyze","description":"Analizza la struttura del repository: file, linguaggi, statistiche. Usa GitNexus se disponibile, altrimenti fallback file tree.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Percorso del repository (default: repo corrente)","default":""}}}}},
    {"type":"function","function":{"name":"kg_graph","description":"Costruisce il grafo della conoscenza del repository: entità, relazioni, dipendenze tra file. Richiede GitNexus.","parameters":{"type":"object","properties":{"path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"kg_symbols","description":"Estrae simboli dal repository: funzioni, classi, import. Analisi statica del codice.","parameters":{"type":"object","properties":{"path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"kg_search","description":"Cerca nel codice del repository per una query testuale. Trova funzioni, classi, riferimenti.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Testo da cercare nel codice"},"path":{"type":"string","default":""}},"required":["query"]}}},
    {"type":"function","function":{"name":"kg_status","description":"Stato del knowledge graph: GitNexus disponibile, repo percorso, info","parameters":{"type":"object","properties":{}}}},
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
def files_copy(src="", dst="", **_): return copy_file(src, dst)
def files_move(src="", dst="", **_): return move_file(src, dst)
def files_rename(path="", new_name="", **_): return rename_file(path, new_name)

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
def rag_add_folder_tool(folder_path="", recursive=True, **_):
    return rag.add_folder(folder_path, recursive)
def rag_search_tool(query="", limit=5, **_): return rag.search(query, limit)
def rag_semantic_search_tool(query="", limit=5, **_): return rag.semantic_search(query, limit)
def rag_list_tool(**_): return rag.list_documents()
def rag_stats_tool(**_): return rag.stats()
def rag_delete_tool(doc_id=0, **_): return rag.delete_document(doc_id)
def rag_delete_all_tool(**_): return rag.delete_all()
def rag_get_document_tool(doc_id=0, **_): return rag.get_document(doc_id)
def rag_update_document_tool(doc_id=0, title="", content="", source="", **_):
    return rag.update_document(doc_id, title=title or None, content=content or None, source=source or None)
def rag_reembed_all_tool(**_): return rag.reembed_all()
def rag_search_by_source_tool(query="", limit=50, **_): return rag.search_by_source(query, limit)
def rag_export_tool(**_): return rag.export_json()
def rag_dedup_tool(threshold=0.95, **_): return rag.deduplicate(threshold)

# ── GOALS / OKR v9.0 ──
def goals_create_tool(title="", description="", key_results=None, priority="medium", **_):
    return create_goal(title, description, key_results or [], priority=priority)
def goals_list_tool(status="", **_):
    return list_goals(status if status else None)
def goals_detail_tool(goal_id=0, **_): return get_goal_detail(goal_id)
def goals_update_kr_tool(goal_id=0, kr_id=0, current=0, **_):
    return update_key_result(goal_id, kr_id, current)
def goals_add_kr_tool(goal_id=0, description="", target=100, **_):
    return add_key_result(goal_id, description, target)
def goals_delete_tool(goal_id=0, **_): return delete_goal(goal_id)
def goals_archive_tool(goal_id=0, **_): return archive_goal(goal_id)

# ── PROVIDERS v9.0 ──
def providers_list_tool(**_): return list_providers()
def providers_switch_tool(provider="", **_): return switch_active(provider)
def providers_set_model_tool(provider="", model="", **_): return set_provider_model(provider, model)

# ── NETWORK v9.0 ──
def network_public_ip_tool(**_):
    ip = public_ip()
    geo = ip_geolocation(ip)
    return f"🌐 IP Pubblico: {ip}\n📍 Localizzazione: {geo}"
def network_ping_tool(host="8.8.8.8", **_): return ping_test(host)
def network_dns_tool(domain="google.com", **_): return dns_lookup(domain)
def network_speedtest_tool(**_): return bandwidth_speedtest()
def network_connectivity_tool(**_): return connectivity_summary()

# ── HOME ASSISTANT v9.0 ──
def ha_states_tool(**_):
    data = ha_get_states()
    if isinstance(data, dict) and "error" in data:
        return f"⚠ Home Assistant: {data['error']}"
    lines = [f"🏠 Home Assistant — {len(data)} entità disponibili:"]
    domains = {}
    for e in data:
        domain = e["entity_id"].split(".")[0]
        domains.setdefault(domain, []).append(e)
    for domain, entities in sorted(domains.items()):
        lines.append(f"\n  📂 {domain} ({len(entities)}):")
        for e in entities[:3]:
            state = e.get("state", "")
            name = e["attributes"].get("friendly_name", e["entity_id"])
            lines.append(f"    • {name} → {state}")
        if len(entities) > 3:
            lines.append(f"    ... e altri {len(entities)-3}")
    return "\n".join(lines)
def ha_state_tool(entity_id="", **_):
    if not entity_id:
        return "⚠ Specifica entity_id (es. light.soggiorno)"
    data = ha_get_state(entity_id)
    if isinstance(data, dict) and "error" in data:
        return f"⚠ {data['error']}"
    attrs = data.get("attributes", {})
    return (
        f"🏠 {data['entity_id']}\n"
        f"  Stato: {data['state']}\n"
        f"  Nome: {attrs.get('friendly_name', '—')}\n"
        f"  Ultimo cambio: {data.get('last_changed', '—')}"
    )
def ha_service_tool(domain="", service="", entity_id="", data=None, **_):
    if not domain or not service:
        return "⚠ Specifica domain e service"
    payload = dict(data or {})

    # Se entity_id non specificato ma domain/servizio è generico (es. spegni tutte le luci)
    if not entity_id and not payload.get("entity_id"):
        if domain == "light" and service in ("turn_off", "turn_on"):
            all_states = ha_get_states()
            if isinstance(all_states, dict) and "error" in all_states:
                return f"⚠ {all_states['error']}"
            targets = [s["entity_id"] for s in all_states
                       if s["entity_id"].startswith("light.") and s["state"] == ("on" if service == "turn_off" else "off")]
            if not targets:
                return "⚠ Nessuna luce da " + ("spegnere" if service == "turn_off" else "accendere")
            done = 0
            for eid in targets:
                ha_call_service(domain, service, {"entity_id": eid})
                done += 1
            return f"✅ {done} luci " + ("spente" if service == "turn_off" else "accese")
        return "⚠ Specifica entity_id (es. light.lampe1)"

    if entity_id and "entity_id" not in payload:
        payload["entity_id"] = entity_id
    if not payload.get("entity_id"):
        return "⚠ Specifica l'entità da controllare (entity_id)"

    result = ha_call_service(domain, service, payload)
    if isinstance(result, dict) and "error" in result:
        return f"⚠ {result['error']}"
    state = ha_get_state(payload["entity_id"])
    if isinstance(state, dict) and "error" not in state:
        return f"✅ {payload['entity_id']} → {state['state']}"
    return "✅ fatto"
def ha_config_tool(**_):
    cfg = ha_get_config()
    if isinstance(cfg, dict) and "error" in cfg:
        return f"⚠ {cfg['error']}"
    return (
        f"🏠 Configurazione Home Assistant:\n"
        f"  Versione: {cfg.get('version', '—')}\n"
        f"  Nome installazione: {cfg.get('location_name', '—')}\n"
        f"  Unità: {cfg.get('unit_system', {}).get('length', '—')}\n"
        f"  Fuso orario: {cfg.get('time_zone', '—')}\n"
        f"  Modalità: {'Modifica' if cfg.get('config_source') == 'storage' else 'YAML'}"
    )
def ha_dashboard_tool(**_):
    return "✅ Aperta dashboard Home Assistant"

# ── WORLD MAP v9.0 ──
def open_world_map(**_):
    """Cerca webcam live YouTube per 5 città e restituisce dati per la griglia"""
    import requests as _req, urllib.parse as _up, re as _re
    # Known working 24/7 webcam YouTube IDs per città (fallback se YouTube search fallisce)
    KNOWN_CAMS = {
        "Milano": "28BXLXTP63E",
        "Venezia": "CMn6xQXuSjI",
        "Tokyo": "8H3nRCFVR6Y",
        "Berlino": "iaTAp8FxtHw",
        "New York": "VGnFLdQW39A",
        "Sydney": "DkY66Fy4r4M",
    }
    cities = [
        {"name": "Milano", "lat": 45.4642, "lon": 9.1900},
        {"name": "Venezia", "lat": 45.4408, "lon": 12.3155},
        {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
        {"name": "Berlino", "lat": 52.5200, "lon": 13.4050},
        {"name": "New York", "lat": 40.7128, "lon": -74.0060},
        {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    ]
    webcams = []
    for c in cities:
        # Usa known cam (testato funzionante) se disponibile
        video_id = KNOWN_CAMS.get(c["name"])
        # Se non c'è known cam, cerca su YouTube
        if not video_id:
            try:
                q = _up.quote(f'{c["name"]} webcam diretta 4K')
                yt_r = _req.get(f'https://www.youtube.com/results?search_query={q}',
                    timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
                ids = _re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', yt_r.text)
                if ids:
                    video_id = ids[0]
            except Exception:
                pass
        webcams.append({"name": c["name"], "lat": c["lat"], "lon": c["lon"], "video_id": video_id})
    return webcams  # lista di dict per WEBCAM_GRID

# ── MCP v9.0 ──
def mcp_list_tool(**_): return list_servers()
def mcp_enable_tool(name="", env=None, **_): return enable_server(name, env)
def mcp_disable_tool(name="", **_): return disable_server(name)
def mcp_tools_tool(server="", **_): return list_tools(server)
def mcp_call_tool(server="", tool="", args=None, **_): return call_tool(server, tool, args)

# ── APPROVAL ──
def approval_pending_tool(**_): return approval.get_pending()
def approval_approve_tool(request_id="", auto_future=False, **_):
    return approval.approve(request_id, auto_future)
def approval_deny_tool(request_id="", **_): return approval.deny(request_id)

# ── WORLD NEWS v10.0 ──
def world_news_tool(max_items=30, **_):
    data = _fetch_world_news(max_items)
    return json.dumps(data, ensure_ascii=False)

# ── TRENDS v9.3 ──
def trends_search_tool(category="technology", region="wt", max_results=10, **_):
    result = _trends_search(category, region, max_results)
    if result["status"] != "ok":
        return f"⚠ {result.get('message', 'errore')}"
    items = result["results"]
    if not items:
        return "🔍 Nessun trend trovato per questa categoria."
    lines = [f"📊 TREND — {category.upper()} ({region}):"]
    for i, r in enumerate(items[:max_results], 1):
        lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet'][:120]}")
    return "\n\n".join(lines)

def trending_now_tool(region="it", **_):
    result = _trending_now(region)
    if result["status"] != "ok":
        return f"⚠ {result.get('message', 'errore')}"
    items = result["results"]
    if not items:
        return "🔍 Nessun trend trovato."
    lines = [f"⚡ TRENDING ORA ({region.upper()}) — {len(items)} risultati:"]
    for i, r in enumerate(items[:10], 1):
        lines.append(f"{i}. {r['title']}\n   {r['snippet'][:120]}")
    return "\n\n".join(lines)

# ── TELEGRAM v9.3 ──
def telegram_send_tool(message="", chat_id=0, **_):
    if not message:
        return "⚠ Inserisci un messaggio da inviare."
    return _telegram_send(chat_id if chat_id else None, message)

# ── SELF-EVOLUTION ENGINE v11.0 ──
def evolution_status(**_):
    try: return evol.get_status_summary()
    except Exception as e: return f"⚠ Evolution Engine: {e}"

def evolution_daily_report(**_):
    try:
        r = evol.generate_daily_report()
        return (f"📊 Report Giornaliero ({r['date']})\n"
                f"  ❌ Errori: {r['errors_today']}\n"
                f"  ✅ Risolti: {r['fixed_today']}\n"
                f"  🔧 Healing: {r['healing_actions']}\n"
                f"  🏥 Salute: {r['health_score']}/100")
    except Exception as e: return f"⚠ Report giornaliero: {e}"

def evolution_weekly_report(**_):
    try:
        r = evol.generate_weekly_report()
        lines = [f"📊 Report Settimanale ({r['period']})"]
        lines.append(f"  ❌ Errori irrisolti: {r['unresolved_errors']}")
        lines.append(f"  🔧 Auto-fix: {r['auto_fixes']}")
        for cat in r["error_categories"][:3]:
            lines.append(f"  • {cat['category']}: {cat['cnt']}")
        return "\n".join(lines)
    except Exception as e: return f"⚠ Report settimanale: {e}"

def evolution_heal(**_):
    try:
        results = evol.run_healing_check()
        fixed = sum(1 for r in results if r["status"] == "applied")
        lines = [f"🔧 Healing check: {fixed} fix applicati"]
        for r in results:
            icon = "✅" if r["status"] == "healthy" else "🔄" if r["status"] == "applied" else "❌"
            lines.append(f"  {icon} {r['description']}: {r['status']}")
        return "\n".join(lines)
    except Exception as e: return f"⚠ Healing: {e}"

def evolution_audit(**_):
    try:
        r = evol.run_dawn_audit()
        healthy = sum(1 for c in r["checks"] if c["status"] == "healthy")
        fixed = sum(1 for c in r["checks"] if c["status"] == "applied")
        return (f"🔍 Dawn Audit\n"
                f"  ✅ Sani: {healthy}\n"
                f"  🔧 Riparati: {fixed}\n"
                f"  📊 Errori da mezzanotte: {r['errors_since_midnight']}")
    except Exception as e: return f"⚠ Audit: {e}"

def evolution_analyze(**_):
    try:
        r = evol.analyze_patterns()
        if r["status"] == "no_data":
            return "📊 Ancora pochi dati per analisi pattern"
        lines = ["📊 Pattern Analysis"]
        if r.get("topics"):
            lines.append("  🏷 Topic frequenti:")
            for t in r["topics"][:5]:
                lines.append(f"    • {t['key']}: {t['count']}x")
        if r.get("tools"):
            lines.append("  🛠 Tool più usati:")
            for t in r["tools"][:5]:
                lines.append(f"    • {t['key']}: {t['count']}x")
        return "\n".join(lines)
    except Exception as e: return f"⚠ Analyzer: {e}"

def evolution_skills(**_):
    try:
        skills = evol.get_auto_skills()
        if not skills:
            return "🧬 Nessuna skill auto-generata ancora"
        lines = ["🧬 Auto-Skills generate:"]
        for s in skills:
            lines.append(f"  • {s['name']}: {s['description'][:60]} (usata {s['usage_count']}x)")
        return "\n".join(lines)
    except Exception as e: return f"⚠ Skills: {e}"

def evolution_generate_skill(name="", description="", **_):
    if not name or not description:
        return "⚠ Serve nome e descrizione per generare skill"
    try:
        return evol.generate_skill(name, description)
    except Exception as e:
        return f"⚠ Generazione skill: {e}"

# ── VISION ENGINE v11.0 ──
def vision_analyze_tool(image_path="", **_):
    try:
        result = vision.analyze_screenshot(image_path or None)
        return json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else str(result)
    except Exception as e: return f"⚠ Vision: {e}"

def vision_read_text_tool(image_path="", **_):
    try: text = vision.read_text(image_path if image_path else None); return f"📝 Testo rilevato:\n{text[:2000]}" if text else "Nessun testo trovato nell'immagine"
    except Exception as e: return f"⚠ OCR: {e}"

def vision_detect_qr_tool(image_path="", **_):
    try: codes = vision.detect_qr(image_path if image_path else None); return "\n".join(f"📱 QR/Barcode: {c.get('type','')} — {c.get('data','')[:200]}" for c in codes) if codes else "Nessun QR/barcode rilevato"
    except Exception as e: return f"⚠ QR: {e}"

def vision_describe_tool(image_path="", **_):
    try: return vision.describe_image(image_path) if image_path else "Specifica image_path"
    except Exception as e: return f"⚠ Describe: {e}"

def vision_analyze_region_tool(x=0, y=0, w=0, h=0, **_):
    try: return json.dumps(vision.analyze_region(x, y, w, h), indent=2, ensure_ascii=False)
    except Exception as e: return f"⚠ Region: {e}"

def vision_detect_faces_tool(image_path="", **_):
    try: count = vision.detect_faces(image_path if image_path else None); return f"🙂 {count} volti rilevati" if count else "Nessun volto rilevato"
    except Exception as e: return f"⚠ Faces: {e}"

# ── VOICE ENGINE v11.0 ──
def voice_say_tool(text="", speed=1.0, **kw):
    _voice = kw.get('voice', '')
    try: return voice.say(text, _voice if _voice else None, speed)
    except Exception as e: return f"⚠ Voice: {e}"

def voice_listen_tool(timeout=5, language="it-IT", **_):
    try: text = voice.listen(timeout, language); return f"🎤 Riconosciuto: {text[:500]}" if text else "Nessun input vocale rilevato"
    except Exception as e: return f"⚠ STT: {e}"

def voice_list_tool(**_):
    try: return voice.list_voices()
    except Exception as e: return f"⚠ Voice list: {e}"

def voice_set_tool(**kw):
    _voice = kw.get('voice', '')
    try: return voice.set_voice(_voice)
    except Exception as e: return f"⚠ Voice set: {e}"

# ── macOS NATIVE CONTROL v11.0 ──
def os_list_windows_tool(**_):
    try: windows = os_control.list_windows(); return "\n".join(f"🪟 {w['app']} — {w['title'][:40]} [{w['position']}] {w['size']}" for w in windows[:20]) if windows else "Nessuna finestra visibile"
    except Exception as e: return f"⚠ Windows: {e}"

def os_focus_window_tool(title="", **_):
    try: return os_control.focus_window(title)
    except Exception as e: return f"⚠ Focus: {e}"

def os_move_window_tool(title="", x=0, y=0, width=0, height=0, **_):
    try: return os_control.move_window(title, x, y, width or None, height or None)
    except Exception as e: return f"⚠ Move: {e}"

def os_minimize_window_tool(title="", **_):
    try: return os_control.minimize_window(title)
    except Exception as e: return f"⚠ Minimize: {e}"

def os_maximize_window_tool(title="", **_):
    try: return os_control.maximize_window(title)
    except Exception as e: return f"⚠ Maximize: {e}"

def os_list_apps_tool(**_):
    try: apps = os_control.list_apps(); return f"📱 App in esecuzione ({len(apps)}): " + ", ".join(apps[:20])
    except Exception as e: return f"⚠ Apps: {e}"

def os_app_info_tool(app_name="", **_):
    try: return os_control.app_info(app_name)
    except Exception as e: return f"⚠ App info: {e}"

def os_tile_window_left_tool(title="", **_):
    try: return os_control.tile_window_left(title) or f"✅ {title} affiancata a sinistra"
    except Exception as e: return f"⚠ Tile: {e}"

def os_tile_window_right_tool(title="", **_):
    try: return os_control.tile_window_right(title) or f"✅ {title} affiancata a destra"
    except Exception as e: return f"⚠ Tile: {e}"

def os_arrange_grid_tool(**_):
    try: os_control.arrange_windows_grid(); return "✅ Finestre disposte in griglia 2x2"
    except Exception as e: return f"⚠ Grid: {e}"

def os_open_pref_pane_tool(pane="", **_):
    try: return os_control.open_pref_pane(pane)
    except Exception as e: return f"⚠ Pref pane: {e}"

def os_toggle_dark_mode_tool(**_):
    try: return os_control.toggle_dark_mode()
    except Exception as e: return f"⚠ Dark mode: {e}"

def os_screensaver_tool(**_):
    try: os_control.screensaver(); return "🖼 Screensaver avviato"
    except Exception as e: return f"⚠ Screensaver: {e}"

def os_empty_trash_tool(**_):
    try: return os_control.empty_trash()
    except Exception as e: return f"⚠ Trash: {e}"

def os_sleep_display_tool(**_):
    try: os_control.sleep_display(); return "💤 Display in sleep"
    except Exception as e: return f"⚠ Sleep: {e}"

def os_set_wallpaper_tool(image_path="", **_):
    try: return os_control.set_wallpaper(image_path if image_path else None)
    except Exception as e: return f"⚠ Wallpaper: {e}"

def os_dock_autohide_tool(enabled=True, **_):
    try: return os_control.dock_autohide(enabled)
    except Exception as e: return f"⚠ Dock: {e}"

def os_dock_position_tool(position="bottom", **_):
    try: return os_control.dock_position(position)
    except Exception as e: return f"⚠ Dock: {e}"

def os_next_space_tool(**_):
    try: os_control.next_space(); return "➡ Workspace successivo"
    except Exception as e: return f"⚠ Space: {e}"

def os_prev_space_tool(**_):
    try: os_control.prev_space(); return "⬅ Workspace precedente"
    except Exception as e: return f"⚠ Space: {e}"

def os_show_desktop_tool(**_):
    try: return os_control.show_desktop()
    except Exception as e: return f"⚠ Desktop: {e}"

def os_system_profiler_tool(category="SPHardwareDataType", **_):
    try: return os_control.system_profiler(category)
    except Exception as e: return f"⚠ Profiler: {e}"

def os_list_processes_tool(count=20, **_):
    try: return os_control.list_processes(count)
    except Exception as e: return f"⚠ Processes: {e}"

# ── SECURITY CHAIN v11.0 ──
def security_check_command_tool(command="", **_):
    try:
        safe, reason, risk = security.check_command_safety(command)
        return f"{'✅ Sicuro' if safe else '⛔ Pericoloso'}: {reason} (risk: {risk})"
    except Exception as e: return f"⚠ Security: {e}"

def security_trust_score_tool(entity="", **_):
    try: return json.dumps(security.check_trust(entity), ensure_ascii=False)
    except Exception as e: return f"⚠ Trust: {e}"

def security_audit_log_tool(limit=20, **_):
    try:
        log = security.db.get_audit_log(limit)
        return "\n".join(f"{'✅' if a['allowed'] else '⛔'} {a['action']} — {a['entity']} ({a['timestamp']})" for a in log) if log else "Nessun audit log"
    except Exception as e: return f"⚠ Audit: {e}"

def security_activity_report_tool(**_):
    try: return json.dumps(security.get_activity_report(), indent=2, ensure_ascii=False)
    except Exception as e: return f"⚠ Report: {e}"

def security_add_rule_tool(pattern="", level="read", category="command", **_):
    try: return security.add_permission_rule(pattern, level, category)
    except Exception as e: return f"⚠ Rule: {e}"

def security_list_rules_tool(**_):
    try:
        rules = security.list_rules()
        return "\n".join(f"  {r['level']:6s} {r['pattern']} ({r['category']})" for r in rules) if rules else "Nessuna regola"
    except Exception as e: return f"⚠ Rules: {e}"

# ── PANTHEON MULTI-AGENT v11.0 ──
def pantheon_list_agents_tool(**_):
    try: return pantheon.list_agents()
    except Exception as e: return f"⚠ Pantheon: {e}"

def pantheon_agent_info_tool(name="", **_):
    try: return pantheon.agent_info(name)
    except Exception as e: return f"⚠ Agent: {e}"

def pantheon_register_tool(name="", capabilities="", endpoint="", **_):
    try: caps = [c.strip() for c in capabilities.split(",")] if capabilities else ["general"]; return json.dumps(pantheon.register_agent(name, caps, endpoint), ensure_ascii=False)
    except Exception as e: return f"⚠ Register: {e}"

def pantheon_delegate_tool(description="", agent="", priority=0, **_):
    try: return json.dumps(pantheon.delegate(description, agent if agent else None, priority), ensure_ascii=False)
    except Exception as e: return f"⚠ Delegate: {e}"

def pantheon_task_status_tool(task_id="", **_):
    try: return pantheon.task_status(task_id)
    except Exception as e: return f"⚠ Task: {e}"

def pantheon_list_tasks_tool(limit=10, **_):
    try: return pantheon.list_tasks(limit=limit)
    except Exception as e: return f"⚠ Tasks: {e}"

def pantheon_send_message_tool(to_agent="", subject="", body="", **_):
    try: return pantheon.send_message(to_agent, subject, body)
    except Exception as e: return f"⚠ Message: {e}"

def pantheon_read_messages_tool(unread_only=True, **_):
    try: return pantheon.read_messages("jarvis", unread_only=unread_only)
    except Exception as e: return f"⚠ Messages: {e}"

def pantheon_broadcast_tool(subject="", body="", **_):
    try: return pantheon.broadcast(subject, body)
    except Exception as e: return f"⚠ Broadcast: {e}"

def pantheon_economy_tool(**_):
    try: return pantheon.economy_report()
    except Exception as e: return f"⚠ Economy: {e}"

def pantheon_transfer_tool(from_agent="", to_agent="", amount=0, reason="", **_):
    try: return pantheon.transfer_credits(from_agent, to_agent, amount, reason)
    except Exception as e: return f"⚠ Transfer: {e}"

def pantheon_balance_tool(agent_name="", **_):
    try: return pantheon.get_balance(agent_name)
    except Exception as e: return f"⚠ Balance: {e}"

def pantheon_orchestrate_tool(task_description="", **_):
    try: return pantheon.orchestrate(task_description)
    except Exception as e: return f"⚠ Orchestrate: {e}"

# ── PLUGIN STORE v11.0 ──
def plugins_list_tool(**_):
    try: return plugins.list_plugins()
    except Exception as e: return f"⚠ Plugins: {e}"

def plugins_install_tool(source="", name="", **_):
    try: return plugins.install(source, name if name else None)
    except Exception as e: return f"⚠ Install: {e}"

def plugins_uninstall_tool(name="", **_):
    try: return plugins.uninstall(name)
    except Exception as e: return f"⚠ Uninstall: {e}"

def plugins_enable_tool(name="", **_):
    try: return plugins.enable(name)
    except Exception as e: return f"⚠ Enable: {e}"

def plugins_disable_tool(name="", **_):
    try: return plugins.disable(name)
    except Exception as e: return f"⚠ Disable: {e}"

def plugins_marketplace_tool(**_):
    try: return plugins.marketplace_catalog()
    except Exception as e: return f"⚠ Marketplace: {e}"

def plugins_info_tool(name="", **_):
    try: return plugins.get_plugin_info(name)
    except Exception as e: return f"⚠ Plugin info: {e}"

def plugins_health_tool(**_):
    try: return plugins.plugins_health()
    except Exception as e: return f"⚠ Health: {e}"

def plugins_check_updates_tool(**_):
    try: return plugins.check_updates()
    except Exception as e: return f"⚠ Updates: {e}"

def plugins_update_all_tool(**_):
    try: return plugins.update_all()
    except Exception as e: return f"⚠ Update all: {e}"

def plugins_rate_tool(name="", rating=0, review="", **_):
    try: return plugins.rate_plugin(name, rating, review)
    except Exception as e: return f"⚠ Rate: {e}"

def plugins_reviews_tool(name="", **_):
    try: return plugins.get_reviews(name)
    except Exception as e: return f"⚠ Reviews: {e}"

def plugins_search_tool(query="", **_):
    try:
        results = plugins.search_marketplace(query)
        if not results:
            return f"Nessun plugin trovato per '{query}'"
        lines = [f"🔍 Risultati per '{query}':"]
        for p in results:
            installed = "📥" if p.get("_installed") else "  "
            rating = f" ⭐{p.get('rating', 0):.1f}" if p.get("rating") else ""
            lines.append(f"  {installed} {p['name']} v{p.get('version','1.0')}{rating}")
            lines.append(f"     {p.get('description','')[:70]}")
        return "\n".join(lines)
    except Exception as e: return f"⚠ Search: {e}"

def plugins_run_tool(name="", function="", **_):
    try: return plugins.run_plugin(name, function if function else None)
    except Exception as e: return f"⚠ Run: {e}"

# ── SELF-LEARNING SKILLS ──
def skills_list_tool(**_):
    try: return skills.list_skills()
    except Exception as e: return f"⚠ Skills list: {e}"

def skills_create_tool(name="", description="", category="general", **_):
    try: return skills.create_skill(name, description, category)
    except Exception as e: return f"⚠ Skills create: {e}"

def skills_improve_tool(name="", feedback="", **_):
    try: return skills.improve_skill(name, feedback)
    except Exception as e: return f"⚠ Skills improve: {e}"

def skills_run_tool(name="", **_):
    try:
        return skills.run_skill(name, **_)
    except Exception as e: return f"⚠ Skills run: {e}"

def skills_info_tool(name="", **_):
    try: return skills.get_skill_info(name)
    except Exception as e: return f"⚠ Skills info: {e}"

def skills_delete_tool(name="", **_):
    try: return skills.delete_skill(name)
    except Exception as e: return f"⚠ Skills delete: {e}"

def skills_stats_tool(**_):
    try:
        s = skills.get_stats()
        return (f"🧠 Self-Learning Skills Stats:\n"
                f"  Totali: {s['total']} | Attive: {s['active']}\n"
                f"  Usi totali: {s['total_uses']}\n"
                f"  Successi: {s['total_success']} | Fallimenti: {s['total_failures']}")
    except Exception as e: return f"⚠ Skills stats: {e}"

def skills_suggestions_tool(**_):
    try: return skills.get_suggestions()
    except Exception as e: return f"⚠ Skills suggestions: {e}"

def skills_toggle_tool(name="", **_):
    try: return skills.toggle_skill(name)
    except Exception as e: return f"⚠ Skills toggle: {e}"

# ── Video Analytics v1.0 ──
_VA_OK = False
try:
    from jarvis_video_analytics import start_analytics, stop_analytics, get_counts, get_status, set_detection_line, reset_history
    _VA_OK = True
except Exception:
    pass

def video_analytics_start_tool(stream_url="0", **_):
    if not _VA_OK: return "⚠ Video Analytics non disponibile (openCV?)"
    try: return start_analytics(stream_url)
    except Exception as e: return f"⚠ Video start: {e}"

def video_analytics_stop_tool(**_):
    if not _VA_OK: return "⚠ Video Analytics non disponibile"
    try: return stop_analytics()
    except Exception as e: return f"⚠ Video stop: {e}"

def video_analytics_counts_tool(hours=1, **_):
    if not _VA_OK: return "⚠ Video Analytics non disponibile"
    try:
        c = get_counts(hours)
        if "error" in c: return f"⚠ {c['error']}"
        return f"📊 Ultime {hours}h: {c['cars']} auto 🚗 | {c['people']} persone 🧑 | media {c['avg_speed_kmh']} km/h"
    except Exception as e: return f"⚠ Video counts: {e}"

def video_analytics_status_tool(**_):
    if not _VA_OK: return "⚠ Video Analytics non disponibile"
    try:
        s = get_status()
        if not s.get("running"): return "⏹ Analisi video non attiva"
        return (f"📹 Analisi in corso: {s['stream_url']}\n"
                f"   FPS: {s['fps']} | Frame: {s['frames_processed']}\n"
                f"   Sessione: {s['car_count_session']} auto 🚗 | {s['people_count_session']} persone 🧑\n"
                f"   Modello: {s['model']}")
    except Exception as e: return f"⚠ Video status: {e}"

def video_analytics_set_line_tool(y_pct=0.7, **_):
    if not _VA_OK: return "⚠ Video Analytics non disponibile"
    try: return set_detection_line(y_pct)
    except Exception as e: return f"⚠ Video line: {e}"

def video_analytics_reset_tool(**_):
    if not _VA_OK: return "⚠ Video Analytics non disponibile"
    try: return reset_history()
    except Exception as e: return f"⚠ Video reset: {e}"

# ── DOCUMENT GENERATOR v2.5 ──
def doc_make_docx_tool(data="", output="", **_):
    try:
        d = json.loads(data) if isinstance(data, str) else data
        path, url = docgen.make_docx(d, output if output else None)
        return f"✅ [Word creato]({url}) — {path}"
    except Exception as e:
        return f"⚠ docx: {e}"

def doc_make_docx_from_text_tool(text="", title="Documento", **_):
    try:
        path, url = docgen.make_docx_from_text(text, title)
        return f"✅ [Word creato]({url}) — {path}"
    except Exception as e:
        return f"⚠ docx: {e}"

def doc_make_xlsx_tool(data="", output="", **_):
    try:
        d = json.loads(data) if isinstance(data, str) else data
        path, url = docgen.make_xlsx(d, output if output else None)
        return f"✅ [Excel creato]({url}) — {path}"
    except Exception as e:
        return f"⚠ xlsx: {e}"

def doc_make_pptx_tool(data="", slides_data="", **_):
    try:
        d = json.loads(data) if isinstance(data, str) else data
        s = json.loads(slides_data) if isinstance(slides_data, str) and slides_data else None
        path, url = docgen.make_pptx(d, s)
        return f"✅ [📊 Presentazione creata]({url}) — {path}"
    except Exception as e:
        return f"⚠ pptx: {e}"

def doc_make_pdf_tool(data="", **_):
    try:
        d = json.loads(data) if isinstance(data, str) else data
        path, url = docgen.make_pdf(d)
        return f"✅ [PDF creato]({url}) — {path}"
    except Exception as e:
        return f"⚠ pdf: {e}"

def doc_make_html_presentation_tool(data="", **_):
    try:
        d = json.loads(data) if isinstance(data, str) else data
        slides = d.pop("slides", []) if isinstance(d, dict) else []
        path, url = docgen.make_html_presentation(d, slides)
        return f"✅ [📊 Presentazione HTML creata]({url}) — {path}"
    except Exception as e:
        return f"⚠ html_presentation: {e}"

def doc_auto_presentation_tool(topic="", format="pptx", theme="corporate", **_):
    """Genera automaticamente una presentazione usando LLM per creare i contenuti delle slide."""
    try:
        if not topic:
            return "⚠ Specifica un tema per la presentazione"
        format = format or "pptx"
        theme = theme or "corporate"

        import re as _re_json
        from jarvis_providers import get_active_provider, chat_completion as _pc

        slides_data = None
        sys_prompt = """Sei un creatore di presentazioni professionista. Dato un tema, genera un JSON array di slide.
Ogni slide ha: type (title/section/content/two_column/table/chart/thank_you), title, subtitle,
items (array di stringhe per type=content), headers/rows (array per type=table),
chart_type (per type=chart), image (per type=image),
columns (array di 2 array di stringhe per type=two_column), col1_title, col2_title.
Rispondi SOLO con il JSON, nient'altro.
Esempio: [{"type":"title","title":"Titolo","subtitle":"Sottotitolo"},{"type":"content","title":"Sezione","items":["Punto 1","Punto 2"]}]"""

        user_prompt = f"Crea una presentazione su: {topic}. Almeno 4 slide, massimo 10. Usa type vari (title, section, content, two_column, chart, thank_you) per varietà."

        # 1. Prova provider attivo (via chat_completion)
        try:
            text = _pc([
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ])
            if text and not text.startswith("Errore"):
                jm = _re_json.search(r'```(?:json)?\s*([\s\S]*?)```', text)
                if jm: text = jm.group(1).strip()
                slides_data = json.loads(text)
                if not isinstance(slides_data, list):
                    slides_data = [slides_data]
        except: pass

        # 2. Fallback: Groq diretto
        if not slides_data:
            try:
                cfg_path = Path(__file__).parent / "config.json"
                cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
                groq_key = cfg.get("groq", {}).get("api_key", "")
                if groq_key:
                    import requests as _req
                    groq_model = cfg.get("groq", {}).get("model", "llama-3.3-70b-versatile")
                    resp = _req.post("https://api.groq.com/openai/v1/chat/completions",
                        json={"model": groq_model, "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_prompt}
                        ], "temperature": 0.5, "max_tokens": 4096},
                        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                        timeout=60)
                    if resp.ok:
                        text = resp.json()["choices"][0]["message"]["content"].strip()
                        jm = _re_json.search(r'```(?:json)?\s*([\s\S]*?)```', text)
                        if jm: text = jm.group(1).strip()
                        slides_data = json.loads(text)
                        if not isinstance(slides_data, list):
                            slides_data = [slides_data]
            except: pass

        # 3. Fallback: Ollama locale
        if not slides_data:
            try:
                import requests as _req
                resp = _req.post("http://localhost:11434/api/chat",
                    json={"model": "llama3.2", "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": topic}
                    ], "stream": False}, timeout=15)
                if resp.ok:
                    text = resp.json()["message"]["content"].strip()
                    jm = _re_json.search(r'```(?:json)?\s*([\s\S]*?)```', text)
                    if jm: text = jm.group(1).strip()
                    slides_data = json.loads(text)
                    if not isinstance(slides_data, list):
                        slides_data = [slides_data]
            except: pass

        if not slides_data:
            words = topic.split()[:8]
            short = ' '.join(words)
            slides_data = [
                {"type": "title", "title": topic[:60], "subtitle": f"Generata da J.A.R.V.I.S — {short}"},
                {"type": "section", "title": "Introduzione", "subtitle": short},
                {"type": "content", "title": "Punti Chiave", "items": [
                    f"{topic} — analisi approfondita",
                    "Dati e statistiche rilevanti",
                    "Tendenze e sviluppi recenti",
                    "Impatto e implicazioni",
                    "Prospettive future"
                ]},
                {"type": "thank_you", "title": "Grazie!", "subtitle": "Domande?"}
            ]

        data = {"title": topic[:60], "theme": theme, "author": "J.A.R.V.I.S"}
        if format == "html":
            path, url = docgen.make_html_presentation(data, slides_data)
            return f"✅ [Presentazione HTML creata]({url}) — {path}"
        else:
            path, url = docgen.make_pptx(data, slides_data)
            return f"✅ [Presentazione PowerPoint creata]({url}) — {path}"
    except Exception as e:
        traceback.print_exc()
        return f"⚠ auto_presentation: {e}"
# ── IMAGE GENERATION v12.0 ──
def image_generate_tool(prompt="", model="black-forest-labs/FLUX.1-schnell", size="1024x1024", n=1, **_):
    try:
        if not prompt or not prompt.strip():
            return "⚠ Prompt vuoto! Devi specificare cosa generare. Rileggi la richiesta dell'utente ed estrai SOLO il soggetto visivo."
        # Coercizione tipi: l'LLM a volte passa n come stringa
        try:
            n = int(n)
        except (ValueError, TypeError):
            n = 1
        # Pulizia prompt: rimuove il framing della richiesta WhatsApp
        import re as _re
        _clean = prompt.strip()
        _framing = [
            r'(?i)^mandami\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)^mandaci\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)^manda\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)^inviaci\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)^invia\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)^fammi\s+(vedere|una|un\s+)?foto\s+(di|con)\s+',
            r'(?i)^mostrami\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)^genera\s+(una\s+)?immagine\s+(di|con)\s+',
            r'(?i)^crea\s+(una\s+)?immagine\s+(di|con)\s+',
            r'(?i)^cerco\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)^vorrei\s+(una\s+)?foto\s+(di|con)\s+',
            r'(?i)\s*(sul\s+)?gruppo\s+whatsapp.*$',
            r'(?i)\s*(su|nel|sul|sull[oaie])\s+gruppo\s+\w+.*$',
            r'(?i)\s*(per|via)\s+(whatsapp|whats?ap).*$',
            r'(?i)^per\s+favore[\s,]+',
            r'(?i)^grazie[\s,!]+',
            r'(?i)^\[whatsapp[^\]]*\]\s*',
        ]
        for _pat in _framing:
            _clean = _re.sub(_pat, '', _clean).strip()
        # Se la pulizia ha rimosso tutto, usa il prompt originale
        _prompt_used = _clean if _clean else prompt

        print(f"  [ImageGen] prompt originale: {prompt!r}")
        print(f"  [ImageGen] prompt pulito:   {_prompt_used!r}")

        res = _generate_image(_prompt_used, model, size, n)
        if isinstance(res, dict) and "images" in res and res["images"]:
            url = res["images"][0].get("url", "")
            _revised = res.get("revised_prompt", "")
            _detail = f" | revised: {_revised[:80]}" if _revised and _revised != _prompt_used else ""
            return f"✅ Immagine generata! URL={url} — prompt: {_prompt_used[:120]}{_detail}"
        return str(res)[:300]
    except Exception as e:
        return f"⚠ Image gen: {e}"

def image_list_models_tool(**_):
    try: return _list_image_models()
    except Exception as e: return f"⚠ Image models: {e}"

# ── MUSIC GENERATION v12.0 ──
def music_generate_tool(prompt="", genre="electronic", duration=30, temperature=1.0, **_):
    try: return _generate_music(prompt, duration, genre, temperature)
    except Exception as e: return f"⚠ Music gen: {e}"

def music_list_genres_tool(**_):
    try: return _list_music_genres()
    except Exception as e: return f"⚠ Music genres: {e}"

def music_status_tool(**_):
    try: return _music_status()
    except Exception as e: return f"⚠ Music status: {e}"

# ── WHATSAPP v1.0 (OpenWA) ──
def whatsapp_send_tool(to="", text="", **_):
    if not _WA_OK:
        return "⚠ OpenWA non disponibile (installa openwa.github.io)"
    try:
        if not to or not text:
            return "⚠ Specifica destinatario (numero o contatto) e testo"
        res = _wa_send_msg(to, text)
        if isinstance(res, dict) and res.get("ok"):
            return f"✅ Messaggio inviato con successo a {to}"
        err = res.get("error") or str(res.get("data", {}))[:200]
        return f"⚠ Invio messaggio fallito: {err}"
    except Exception as e:
        return f"⚠ WA send: {e}"

def whatsapp_status_tool(**_):
    if not _WA_OK:
        return {"openwa_available": False, "error": "OpenWA not imported"}
    try:
        return _wa_status()
    except Exception as e:
        return f"⚠ WA status: {e}"

def whatsapp_ensure_tool(**_):
    if not _WA_OK:
        return {"ok": False, "error": "OpenWA not imported"}
    try:
        return _wa_ensure()
    except Exception as e:
        return f"⚠ WA session: {e}"

def whatsapp_send_image_tool(to="", url="", caption="", **_):
    """Invia un'immagine via WhatsApp da un URL pubblico."""
    if not _WA_OK:
        return "⚠ OpenWA non disponibile"
    if not to or not url:
        return "⚠ Specifica destinatario e URL dell'immagine"
    try:
        res = _wa_send_img(to, url, caption)
        if isinstance(res, dict) and res.get("ok"):
            mid = res.get("data", {}).get("messageId", "")
            return f"✅ OK: immagine già inviata a {to}. NON chiamare di nuovo questo tool. messageId={mid[:30]}"
        err = res.get("error") or str(res.get("data", {}))[:200]
        return f"⚠ Invio immagine fallito: {err}"
    except Exception as e:
        return f"⚠ WA send image: {e}"

def whatsapp_send_file_tool(to="", url="", filename="", caption="", **_):
    """Invia un file/documento via WhatsApp da un URL pubblico."""
    if not _WA_OK:
        return "⚠ OpenWA non disponibile"
    if not to or not url:
        return "⚠ Specifica destinatario e URL del file"
    try:
        return _wa_send(to, f"📎 {filename or 'File'}: {url}\n{caption or ''}")
    except Exception as e:
        return f"⚠ WA send file: {e}"

# ── KNOWLEDGE GRAPH v12.0 ──
def kg_analyze_tool(path="", **_):
    try: return _kg_analyze(path if path else None)
    except Exception as e: return f"⚠ KG analyze: {e}"

def kg_graph_tool(path="", **_):
    try: return _kg_graph(path if path else None)
    except Exception as e: return f"⚠ KG graph: {e}"

def kg_symbols_tool(path="", **_):
    try: return _kg_symbols(path if path else None)
    except Exception as e: return f"⚠ KG symbols: {e}"

def kg_search_tool(query="", path="", **_):
    try: return _kg_search(query, path if path else None)
    except Exception as e: return f"⚠ KG search: {e}"

def kg_status_tool(**_):
    try: return _kg_status()
    except Exception as e: return f"⚠ KG status: {e}"

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
    "files_copy":files_copy,
    "files_move":files_move,
    "files_rename":files_rename,
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
    "computer_use_action":computer_use_action,
    "computer_mouse_move":computer_mouse_move_tool,"computer_mouse_click":computer_mouse_click_tool,
    "computer_mouse_drag":computer_mouse_drag_tool,"computer_keyboard_type":computer_keyboard_type_tool,
    "computer_keyboard_press":computer_keyboard_press_tool,"computer_keyboard_shortcut":computer_keyboard_shortcut_tool,
    "computer_mouse_position":computer_mouse_position_tool,"computer_resolution":computer_resolution_tool,
    # RAG
    "rag_add_document":rag_add_document_tool,"rag_add_file":rag_add_file_tool,
    "rag_add_folder":rag_add_folder_tool,
    "rag_search":rag_search_tool,"rag_semantic_search":rag_semantic_search_tool,
    "rag_list":rag_list_tool,"rag_stats":rag_stats_tool,
    "rag_delete":rag_delete_tool,"rag_delete_all":rag_delete_all_tool,
    "rag_get_document":rag_get_document_tool,"rag_update_document":rag_update_document_tool,
    "rag_reembed":rag_reembed_all_tool,"rag_search_by_source":rag_search_by_source_tool,
    "rag_export":rag_export_tool,"rag_dedup":rag_dedup_tool,
    # Approval
    "approval_pending":approval_pending_tool,"approval_approve":approval_approve_tool,"approval_deny":approval_deny_tool,
    # Goals v9.0
    "goals_create":goals_create_tool,"goals_list":goals_list_tool,"goals_detail":goals_detail_tool,
    "goals_update_kr":goals_update_kr_tool,"goals_add_kr":goals_add_kr_tool,
    "goals_delete":goals_delete_tool,"goals_archive":goals_archive_tool,
    # Providers v9.0
    "providers_list":providers_list_tool,"providers_switch":providers_switch_tool,
    "providers_set_model":providers_set_model_tool,
    # Network v9.0
    "network_public_ip":network_public_ip_tool,"network_ping":network_ping_tool,
    "network_dns":network_dns_tool,"network_speedtest":network_speedtest_tool,
    "network_connectivity":network_connectivity_tool,
    # MCP v9.0
    "mcp_list":mcp_list_tool,"mcp_enable":mcp_enable_tool,"mcp_disable":mcp_disable_tool,
    "mcp_tools":mcp_tools_tool,    "mcp_call":mcp_call_tool,
    # Home Assistant v9.0
    "ha_config":ha_config_tool,"ha_states":ha_states_tool,
    "ha_state":ha_state_tool,"ha_service":ha_service_tool,
    "ha_dashboard":ha_dashboard_tool,
    # World Map
    "open_world_map":open_world_map,
    # Trends v9.3
    "trends_search":trends_search_tool,
    "trending_now":trending_now_tool,
    # Telegram v9.3
    "telegram_send":telegram_send_tool,
    # World News v10.0
    "world_news":world_news_tool,
    # Self-Evolution Engine v11.0
    "evolution_status":evolution_status,
    "evolution_daily_report":evolution_daily_report,
    "evolution_weekly_report":evolution_weekly_report,
    "evolution_heal":evolution_heal,
    "evolution_audit":evolution_audit,
    "evolution_analyze":evolution_analyze,
    "evolution_skills":evolution_skills,
    "evolution_generate_skill":evolution_generate_skill,
    # Vision Engine v11.0
    "vision_analyze":vision_analyze_tool,
    "vision_read_text":vision_read_text_tool,
    "vision_detect_qr":vision_detect_qr_tool,
    "vision_describe":vision_describe_tool,
    "vision_analyze_region":vision_analyze_region_tool,
    "vision_detect_faces":vision_detect_faces_tool,
    # Voice Engine v11.0
    "voice_say":voice_say_tool,
    "voice_listen":voice_listen_tool,
    "voice_list":voice_list_tool,
    "voice_set":voice_set_tool,
    # macOS Native Control v11.0
    "os_list_windows":os_list_windows_tool,
    "os_focus_window":os_focus_window_tool,
    "os_move_window":os_move_window_tool,
    "os_minimize_window":os_minimize_window_tool,
    "os_maximize_window":os_maximize_window_tool,
    "os_list_apps":os_list_apps_tool,
    "os_app_info":os_app_info_tool,
    "os_tile_window_left":os_tile_window_left_tool,
    "os_tile_window_right":os_tile_window_right_tool,
    "os_arrange_grid":os_arrange_grid_tool,
    "os_open_pref_pane":os_open_pref_pane_tool,
    "os_toggle_dark_mode":os_toggle_dark_mode_tool,
    "os_screensaver":os_screensaver_tool,
    "os_empty_trash":os_empty_trash_tool,
    "os_sleep_display":os_sleep_display_tool,
    "os_set_wallpaper":os_set_wallpaper_tool,
    "os_dock_autohide":os_dock_autohide_tool,
    "os_dock_position":os_dock_position_tool,
    "os_next_space":os_next_space_tool,
    "os_prev_space":os_prev_space_tool,
    "os_show_desktop":os_show_desktop_tool,
    "os_system_profiler":os_system_profiler_tool,
    "os_list_processes":os_list_processes_tool,
    # Security Chain v11.0
    "security_check_command":security_check_command_tool,
    "security_trust_score":security_trust_score_tool,
    "security_audit_log":security_audit_log_tool,
    "security_activity_report":security_activity_report_tool,
    "security_add_rule":security_add_rule_tool,
    "security_list_rules":security_list_rules_tool,
    # Pantheon Multi-Agent v11.0
    "pantheon_list_agents":pantheon_list_agents_tool,
    "pantheon_agent_info":pantheon_agent_info_tool,
    "pantheon_register":pantheon_register_tool,
    "pantheon_delegate":pantheon_delegate_tool,
    "pantheon_task_status":pantheon_task_status_tool,
    "pantheon_list_tasks":pantheon_list_tasks_tool,
    "pantheon_send_message":pantheon_send_message_tool,
    "pantheon_read_messages":pantheon_read_messages_tool,
    "pantheon_broadcast":pantheon_broadcast_tool,
    "pantheon_economy":pantheon_economy_tool,
    "pantheon_transfer":pantheon_transfer_tool,
    "pantheon_balance":pantheon_balance_tool,
    "pantheon_orchestrate":pantheon_orchestrate_tool,
    # Plugin Store v11.0
    "plugins_list":plugins_list_tool,
    "plugins_install":plugins_install_tool,
    "plugins_uninstall":plugins_uninstall_tool,
    "plugins_enable":plugins_enable_tool,
    "plugins_disable":plugins_disable_tool,
    "plugins_marketplace":plugins_marketplace_tool,
    "plugins_info":plugins_info_tool,
    "plugins_health":plugins_health_tool,
    "plugins_check_updates":plugins_check_updates_tool,
    "plugins_update_all":plugins_update_all_tool,
    "plugins_rate":plugins_rate_tool,
    "plugins_reviews":plugins_reviews_tool,
    "plugins_search":plugins_search_tool,
    "plugins_run":plugins_run_tool,
    # Self-Learning Skills
    "skills_list":skills_list_tool,
    "skills_create":skills_create_tool,
    "skills_improve":skills_improve_tool,
    "skills_run":skills_run_tool,
    "skills_info":skills_info_tool,
    "skills_delete":skills_delete_tool,
    "skills_stats":skills_stats_tool,
    "skills_suggestions":skills_suggestions_tool,
    "skills_toggle":skills_toggle_tool,
    "video_analytics_start":video_analytics_start_tool,
    "video_analytics_stop":video_analytics_stop_tool,
    "video_analytics_counts":video_analytics_counts_tool,
    "video_analytics_status":video_analytics_status_tool,
    "video_analytics_set_line":video_analytics_set_line_tool,
    "video_analytics_reset":video_analytics_reset_tool,
    # Document Generator v1.0
    "doc_make_docx":doc_make_docx_tool,
    "doc_make_docx_from_text":doc_make_docx_from_text_tool,
    "doc_make_xlsx":doc_make_xlsx_tool,
    "doc_make_pptx":doc_make_pptx_tool,
    "doc_make_pdf":doc_make_pdf_tool,
    "doc_make_html_presentation":doc_make_html_presentation_tool,
    "doc_auto_presentation":doc_auto_presentation_tool,
    # ── Image Generation v12.0 ──
    "image_generate":image_generate_tool,
    "image_list_models":image_list_models_tool,
    # ── Music Generation v12.0 ──
    "music_generate":music_generate_tool,
    "music_list_genres":music_list_genres_tool,
    "music_status":music_status_tool,
    # ── WhatsApp v1.0 ──
    "whatsapp_send":whatsapp_send_tool,
    "whatsapp_send_image":whatsapp_send_image_tool,
    "whatsapp_send_file":whatsapp_send_file_tool,
    "whatsapp_status":whatsapp_status_tool,
    "whatsapp_ensure":whatsapp_ensure_tool,
    # ── Knowledge Graph v12.0 ──
    "kg_analyze":kg_analyze_tool,
    "kg_graph":kg_graph_tool,
    "kg_symbols":kg_symbols_tool,
    "kg_search":kg_search_tool,
    "kg_status":kg_status_tool,
}

# Registra automaticamente le skill come tool (runtime)
skills.register_as_tools(TOOLS_SCHEMA, HANDLERS)

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
        "blender_enable_hyper3d": lambda api_key="vibecoding", **_: blender_enable_hyper3d(api_key),
        "blender_generate_hyper3d": lambda prompt="", **_: blender_generate_hyper3d(prompt)[1],
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
    if not isinstance(arguments, dict):
        arguments = {}
    try: return h(**arguments)
    except Exception as e: return f"⚠ Errore {name}: {e}"
