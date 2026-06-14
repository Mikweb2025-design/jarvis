#!/usr/bin/env python3
"""jarvis_server.py — server HTTP locale porta 9999 v8.0 — ULTRA-LOW LATENCY + TTS STREAMING"""
import sys, json, time, os, traceback, threading, re
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from io import BytesIO
import socket

sys.path.insert(0, str(Path(__file__).parent))

from jarvis import load_config, KNOWN_VOICES, KokoroTTS
from jarvis_agent import JarvisAgent
from jarvis_tools import execute_tool, TOOLS_SCHEMA, memory
from jarvis_screen import ocr_screenshot, screen_awareness_summary, get_selected_text
from jarvis_browser import playwright_navigate, playwright_extract, playwright_screenshot
from jarvis_computer_use import computer_use_action, get_mouse_position, get_screen_resolution
from jarvis_rag import rag
from jarvis_approval import approval
from jarvis_wake import JarvisWake
from jarvis_trends import trends_search, trending_now
from jarvis_telegram import start as telegram_start, send as telegram_send, status as telegram_status
from jarvis_evolution import evol
from jarvis_vision import vision
from jarvis_voice import voice
from jarvis_os_control import os_control
from jarvis_security import security
from jarvis_pantheon import pantheon
from jarvis_plugins import plugins
_HAVE_DEEP = False
try:
    from deep_translator import GoogleTranslator as _GTrans
    _GTrans(source='en', target='it').translate('test')
    _HAVE_DEEP = True
except:
    pass
if not _HAVE_DEEP:
    try:
        import requests as _gtr
        def _GTrans(source='en', target='it'):
            class _GT:
                def translate(self, txt):
                    r = _gtr.post('https://translate.googleapis.com/translate_a/single', params={
                        'client': 'gtx', 'sl': source, 'tl': target, 'dt': 't', 'q': txt[:2000]
                    }, timeout=8)
                    return r.json()[0][0][0] if r.ok else txt
            return _GT()
        _HAVE_DEEP = True
    except:
        pass

# Abilita WAL mode per SQLite (concorrenza migliorata)
memory.db.execute("PRAGMA journal_mode=WAL")
memory.db.execute("PRAGMA busy_timeout=5000")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Server multi-thread stabile con timeout e gestione errori"""
    daemon_threads = True
    allow_reuse_address = True
    allow_reuse_port = True
    timeout = 30  # Timeout per le connessioni idle

cfg   = load_config()
agent = JarvisAgent(cfg)
tts_engine = KokoroTTS(cfg)

# ── WAKE WORD + DICTATION (disattivato) ──
_wake = None

# ── QWEN3-TTS: Worker dedicato con modello in RAM ──
# MLX non è thread-safe: il modello deve essere usato solo nel thread che l'ha caricato
print("  [TTS] Inizializzazione Qwen3-TTS worker...")
_tts_model = None
_tts_queue = None
_tts_result = {}
_tts_lock = threading.Lock()
_tts_event = threading.Event()
_tts_ready = threading.Event()
_tts_stop = threading.Event()

def _tts_worker():
    """Worker dedicato: carica il modello MLX e lo usa esclusivamente in questo thread"""
    global _tts_model
    
    # Carica modello nel worker thread
    try:
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        model_name = cfg["tts"].get("qwen3_model", "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit")
        print(f"  [TTS] Worker: caricamento {model_name}...")
        t0 = time.time()
        _tts_model = load_model(model_name)
        elapsed = time.time() - t0
        print(f"  [TTS] ✅ Qwen3-TTS caricato in RAM (worker thread) in {elapsed:.1f}s")
        _tts_ready.set()
    except Exception as e:
        print(f"  [TTS] ❌ Errore caricamento Qwen3-TTS: {e}")
        print(f"  [TTS] Fallback a Edge TTS")
        _tts_model = None
        _tts_ready.set()
        return
    
    # Loop principale: processa richieste TTS
    import tempfile, numpy as np, soundfile as sf
    while not _tts_stop.is_set():
        _tts_event.wait(timeout=1.0)
        if _tts_stop.is_set():
            break
        _tts_event.clear()
        
        with _tts_lock:
            task_id = _tts_queue
            task = _tts_result.get(task_id, {}).get("task")
        
        if task is None:
            continue
        
        try:
            text = task["text"]
            spk = task["speaker"]
            lang = task["language"]
            inst = task["instruct"]
            print(f"  [TTS Qwen3] Worker: Voce={spk}, Lingua={lang}, Testo={len(text)} chars")
            
            results = list(_tts_model.generate_custom_voice(
                text=text, speaker=spk, language=lang, instruct=inst
            ))
            audio = results[0].audio
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_path = f.name
            sf.write(output_path, np.array(audio), 24000)
            with open(output_path, "rb") as f:
                data = f.read()
            os.unlink(output_path)
            
            with _tts_lock:
                _tts_result[task_id] = {"data": data, "content_type": "audio/wav", "error": None}
            print(f"  [TTS Qwen3] ✅ Generato {len(data)} bytes")
        except Exception as e:
            print(f"  [TTS Qwen3 Worker] fallito: {e}")
            with _tts_lock:
                _tts_result[task_id] = {"data": None, "content_type": None, "error": str(e)}
        _tts_event.clear()

def load_qwen3_model():
    """Avvia il worker TTS che caricherà il modello nel suo thread"""
    global _tts_worker_thread
    _tts_worker_thread = threading.Thread(target=_tts_worker, daemon=True, name="qwen3-tts-worker")
    _tts_worker_thread.start()
    # Attendi che il worker sia pronto (max 60s per download modello)
    if _tts_ready.wait(timeout=60):
        return _tts_model is not None
    print("  [TTS] ⚠ Timeout caricamento modello")
    return False

def _qwen3_generate(text, voice="vivian", language="italian"):
    """Invia richiesta TTS al worker dedicato e attende il risultato"""
    global _tts_queue, _tts_result
    
    # Per testi lunghi, usa Edge TTS direttamente (più veloce)
    if len(text) > 150:
        return None, None, "text too long for Qwen3, use Edge TTS"
    
    lang_config = cfg["tts"].get("qwen3_languages", {})
    if language and language.lower() in lang_config:
        lc = lang_config[language.lower()]
        spk = voice if voice else lc.get("voice", "vivian")
        lang = lc.get("language", "Italian")
        inst = lc.get("instruct", "Clear, professional tone")
    else:
        spk = voice or "vivian"
        lang = language or "Italian"
        inst = "Clear, professional tone"
    
    task_id = f"task_{time.time()}_{id(threading.current_thread())}"
    
    with _tts_lock:
        _tts_queue = task_id
        _tts_result[task_id] = {"task": {"text": text, "speaker": spk, "language": lang, "instruct": inst}}
    
    _tts_event.set()
    
    # Attendi risultato (max 20s)
    for _ in range(200):
        time.sleep(0.1)
        with _tts_lock:
            result = _tts_result.get(task_id)
        if result and "data" in result:
            return result["data"], result["content_type"], result["error"]
    
    return None, None, "timeout"

# Avvia worker TTS all'avvio del server (solo se abilitato)
if cfg["tts"].get("qwen3_enabled", True):
    load_qwen3_model()
else:
    print("  [TTS] Qwen3-TTS disabilitato da config.json, uso Edge TTS")
    _tts_ready.set()

# Auto-ingest documenti all'avvio
try:
    _rag_docs_dir = Path(__file__).parent / "data" / "documents"
    if _rag_docs_dir.exists():
        any_files = any(_rag_docs_dir.iterdir())
        if any_files:
            rag_st = rag.stats()
            if rag_st["documents"] == 0:
                print(f"  [RAG] Auto-ingest {_rag_docs_dir} ...")
                result = rag.add_folder(str(_rag_docs_dir), recursive=True)
                print(f"  [RAG] ✅ Indicizzati {result.get('indexed', 0)} file")
except Exception as e:
    print(f"  [RAG] Auto-ingest skip: {e}")

# Lock per proteggere stato condiviso tra thread
state_lock = threading.Lock()
tts_lock = threading.Lock()

# Cache per sysinfo (evita chiamate troppo frequenti)
_sysinfo_cache = {"data": None, "time": 0}
_sysinfo_lock = threading.Lock()

# Modello Qwen3-TTS precaricato all'avvio

def _generate_tts_chunk(text, voice="vivian", language="italian", speed=1.0):
    """Genera audio TTS per un chunk di testo. Ritorna (audio_bytes, content_type)"""
    import tempfile, subprocess, numpy as np
    
    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    clean = re.sub(r'\*(.+?)\*', r'\1', clean)
    clean = re.sub(r'`(.+?)`', r'\1', clean)
    clean = re.sub(r'#{1,6}\s*', '', clean)
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean).strip()
    if not clean:
        return None, None
    
    # Qwen3-TTS: generazione singola ottimizzata
    try:
        if _tts_model is None:
            raise Exception("Modello Qwen3-TTS non disponibile")
        
        import tempfile, numpy as np, soundfile as sf
        
        data, ct, err = _qwen3_generate(clean, voice=voice, language=language)
        if data is not None:
            return data, ct
        
        raise Exception(err or "Qwen3-TTS returned no data")
        
    except Exception as e:
        print(f"  [TTS Qwen3] fallito: {e}")
        # Fallback: Edge TTS con voce corretta
        try:
            import asyncio, edge_tts
            
            voice_map = {
                "vivian": "it-IT-ElsaNeural",
                "serena": "it-IT-ElsaNeural",
                "aiden": "it-IT-DiegoNeural",
                "ryan": "de-DE-KatjaNeural",
                "eric": "de-DE-ConradNeural",
                "dylan": "de-DE-ConradNeural",
            }
            tts_voice = voice_map.get(voice, "it-IT-ElsaNeural")
            
            rate = f"+{int((speed-1)*100)}%"
            async def _gen():
                comm = edge_tts.Communicate(clean, tts_voice, rate=rate)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    p = f.name
                await comm.save(p)
                return p
            p = asyncio.run(_gen())
            with open(p, "rb") as f:
                data = f.read()
            os.unlink(p)
            print(f"  [TTS Edge] Voce: {tts_voice}")
            return data, "audio/mpeg"
        except Exception as e:
            print(f"  [TTS Edge] fallito: {e}")
            return None, None

def _split_into_sentences(text):
    """Split text in frasi complete per TTS streaming"""
    # Match frasi che terminano con . ! ? o newline
    sentences = re.split(r'(?<=[.!?])\s+|(?<=\n)\n+', text)
    return [s.strip() for s in sentences if s.strip()]

def _run(cmd, timeout=5):
    import subprocess
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception:
        return "error"

def sysinfo():
    return {
        "battery": _run("pmset -g batt | grep -o '[0-9]*%' | head -1", 3) or "N/A",
        "cpu":     _run("top -l 1 -n 0 | grep 'CPU usage' | awk '{print $3}'", 3) or "N/A",
        "ram":     _run("memory_pressure | grep 'System-wide memory free percentage'", 3) or "N/A",
        "disk":    _run("df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'", 3) or "N/A",
        "ip":      _run("ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1", 3) or "N/A",
        "uptime":  _run("uptime | awk -F'up ' '{print $2}' | awk -F',' '{print $1}'", 3) or "N/A",
        "hostname":_run("hostname", 3) or "N/A",
        "model":   _run("sysctl -n hw.model", 3) or "N/A",
    }

def sysinfo_detailed():
    """Info dettagliate con cache (5 secondi)"""
    now = time.time()
    with _sysinfo_lock:
        if _sysinfo_cache["data"] and (now - _sysinfo_cache["time"]) < 5:
            return _sysinfo_cache["data"]
        
        r = {}
        try:
            r["cpu_usage"] = _run("top -l 1 -n 0 | grep 'CPU usage' | awk '{print $3}'", 3) or "0%"
            r["cpu_cores"] = _run("sysctl -n hw.ncpu", 3) or "0"
            r["ram_total"] = _run("sysctl -n hw.memsize | awk '{printf \"%.1f GB\", $1/1073741824}'", 3) or "0 GB"
            r["ram_free"] = _run("memory_pressure | grep 'System-wide memory free percentage' | awk '{print $5}'", 3) or "0%"
            r["disk_total"] = _run("df -h / | tail -1 | awk '{print $2}'", 3) or "0"
            r["disk_used"] = _run("df -h / | tail -1 | awk '{print $3}'", 3) or "0"
            r["disk_pct"] = _run("df -h / | tail -1 | awk '{print $5}'", 3) or "0%"
            r["battery"] = _run("pmset -g batt | grep -o '[0-9]*%' | head -1", 3) or "N/A"
            r["uptime"] = _run("uptime | awk -F'up ' '{print $2}' | awk -F',' '{print $1}'", 3) or "N/A"
            r["load_avg"] = _run("sysctl -n vm.loadavg | awk '{print $2, $3, $4}'", 3) or "0 0 0"
            r["processes"] = _run("ps aux | wc -l | tr -d ' '", 3) or "0"
        except Exception:
            pass
        
        _sysinfo_cache["data"] = r
        _sysinfo_cache["time"] = now
        return r

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    
    def log_message(self, fmt, *a):
        try:
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] {fmt%a}")
        except:
            pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")

    def _json(self, code, data):
        try:
            b = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Connection", "close")
            self._cors()
            self.end_headers()
            self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # Client disconnected, ignore

    def _sse_event(self, data):
        """Invia un evento SSE"""
        try:
            msg = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            self.wfile.write(msg.encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_OPTIONS(self):
        try:
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
        except:
            pass

    def do_GET(self):
        try:
            # Path senza query string (così "/?fresh=123" matcha come "/")
            _path_only = self.path.split("?", 1)[0]

            # Serve static assets
            if _path_only.startswith("/assets/"):
                asset_path = Path(__file__).parent / _path_only.lstrip("/")
                if asset_path.exists() and asset_path.is_file():
                    ext_map = {".css":"text/css", ".js":"application/javascript", ".html":"text/html"}
                    b = asset_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", ext_map.get(asset_path.suffix, "application/octet-stream"))
                    self.send_header("Content-Length", str(len(b)))
                    self.send_header("Cache-Control", "no-cache")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b)
                    return
                self._json(404, {"error": f"Asset not found: {_path_only}"})
                return

            # Serve page fragments
            if _path_only.startswith("/pages/"):
                page_path = Path(__file__).parent / _path_only.lstrip("/")
                if page_path.exists() and page_path.is_file():
                    b = page_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(b)))
                    self.send_header("Cache-Control", "no-cache")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b)
                    return
                self._json(404, {"error": f"Page not found: {_path_only}"})
                return

            if _path_only in ("/", "/index.html"):
                # Try new SPA first, fallback to old monolith
                p = Path(__file__).parent / "index.html"
                if not p.exists():
                    p = Path(__file__).parent / "jarvis_app.html"
                if p.exists():
                    b = p.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type","text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(b)))
                    self.send_header("Connection", "close")
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b)
                else:
                    self._json(404,{"error":"index.html / jarvis_app.html non trovato"})

            elif self.path.startswith("/holographic_avatar.png"):
                p = Path(__file__).parent / "holographic_avatar.png"
                if p.exists():
                    b = p.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(b)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b)
                else:
                    self._json(404, {"error": "avatar not found"})

            elif self.path.startswith("/holographic_avatar_animated.mp4"):
                p = Path(__file__).parent / "holographic_avatar_animated.mp4"
                if p.exists():
                    b = p.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(len(b)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b)
                else:
                    self._json(404, {"error": "animated avatar not found"})

            elif self.path.startswith("/waiting_neurons.mp4"):
                p = Path(__file__).parent / "waiting_neurons.mp4"
                if p.exists():
                    b = p.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(len(b)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b)
                else:
                    self._json(404, {"error": "waiting video not found"})

            elif self.path.startswith("/assets/avatar.glb"):
                p = Path(__file__).parent / "assets" / "avatar.glb"
                if p.exists():
                    b = p.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "model/gltf-binary")
                    self.send_header("Content-Length", str(len(b)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b)
                else:
                    self._json(404, {"error": "avatar.glb not found"})

            elif self.path.startswith("/api/image"):
                # Serve immagini da /tmp/ o dalla cartella output del progetto
                # Sicurezza: solo estensioni immagine, solo percorsi whitelist
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                file_param = qs.get("file", [""])[0]
                if not file_param:
                    self._json(400, {"error": "Parametro 'file' mancante"}); return
                # Normalizza il percorso
                import posixpath
                file_param = posixpath.basename(file_param)  # solo nome file, no path traversal
                # Cerca prima in /tmp/, poi nella cartella output del progetto
                ALLOWED_DIRS = [
                    Path("/tmp"),
                    Path(__file__).parent / "output",
                ]
                ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
                p = None
                for d in ALLOWED_DIRS:
                    candidate = d / file_param
                    if candidate.exists() and candidate.suffix.lower() in ALLOWED_EXT:
                        p = candidate; break
                if not p:
                    self._json(404, {"error": f"Immagine non trovata: {file_param}"}); return
                ext_mime = {".png":"image/png", ".jpg":"image/jpeg", ".jpeg":"image/jpeg",
                            ".gif":"image/gif", ".webp":"image/webp"}
                mime = ext_mime.get(p.suffix.lower(), "image/png")
                b = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-cache")
                self._cors()
                self.end_headers()
                self.wfile.write(b)

            elif self.path=="/api/status":
                rag_st = rag.stats()
                self._json(200,{"status":"online","model":cfg["groq"]["model"],
                    "voice":cfg["tts"].get("qwen3_voice", cfg["tts"].get("voice", "vivian")),"version":"11.0",
                    "rag":{"docs":rag_st["documents"],"chunks":rag_st["chunks"],"model":rag_st["model"]},
                    "time":datetime.now().isoformat()})

            elif self.path=="/api/sysinfo":
                self._json(200, sysinfo())

            elif self.path=="/api/sysinfo/detailed":
                self._json(200, sysinfo_detailed())

            elif self.path=="/api/models":
                self._json(200,{"models":["llama-3.3-70b-versatile","llama-3.1-8b-instant",
                    "llama3-70b-8192","mixtral-8x7b-32768","gemma2-9b-it"]})

            elif self.path=="/api/tools":
                self._json(200,{"tools":[t["function"]["name"] for t in TOOLS_SCHEMA],
                    "count":len(TOOLS_SCHEMA)})

            elif self.path=="/api/memory/stats":
                self._json(200, memory.stats())

            elif self.path=="/api/memory/preferences":
                self._json(200, memory.get_all_preferences())

            elif self.path=="/api/memory/recent":
                self._json(200, {"conversations": memory.get_recent_conversations(10)})

            elif self.path.startswith("/api/memory/all"):
                items = memory.get_all(limit=200)
                self._json(200, {"memories": items, "total": len(items)})

            elif self.path=="/api/calendar/today":
                from jarvis_calendar import get_today_events
                self._json(200, {"events": get_today_events()})

            elif self.path=="/api/mail/unread":
                from jarvis_mail import get_unread_count, parse_unread_count
                count_text = get_unread_count()
                count_num = parse_unread_count(count_text)
                self._json(200, {"unread": count_text, "count": count_num})

            elif self.path=="/api/mail/recent":
                from jarvis_mail import get_recent_emails, format_emails_for_speech
                emails_data = get_recent_emails()
                speech_text = format_emails_for_speech(emails_data)
                self._json(200, {"emails": emails_data, "emails_text": speech_text})

            elif self.path=="/api/plans":
                from jarvis_planner import get_active_plans
                self._json(200, {"plans": get_active_plans()})

            elif self.path=="/api/conversations":
                convs = memory.get_all(limit=50)
                self._json(200, {"conversations": convs})

            elif self.path=="/api/git/status":
                from jarvis_git import git_status
                self._json(200, {"result": git_status()})

            elif self.path=="/api/git/branches":
                from jarvis_git import git_branches
                self._json(200, {"result": git_branches()})

            elif self.path=="/api/git/log":
                from jarvis_git import git_log
                self._json(200, {"result": git_log()})

            elif self.path=="/api/screen/summary":
                self._json(200, {"summary": screen_awareness_summary()})

            elif self.path=="/api/screen/selected":
                self._json(200, {"text": get_selected_text()})

            elif self.path=="/api/rag/list":
                self._json(200, {"documents": rag.list_documents()})

            elif self.path=="/api/rag/stats":
                self._json(200, rag.stats())

            elif self.path.startswith("/api/rag/document?"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                doc_id = int(qs.get("id", [0])[0])
                if not doc_id:
                    self._json(400, {"error": "Parametro 'id' mancante"})
                else:
                    self._json(200, rag.get_document(doc_id))

            elif self.path=="/api/approval/pending":
                self._json(200, {"pending": approval.get_pending()})

            elif self.path=="/api/approval/all":
                self._json(200, {"requests": approval.get_all_requests()})

            elif self.path=="/api/computer/mouse":
                self._json(200, {"position": get_mouse_position(), "resolution": get_screen_resolution()})

            elif self.path=="/api/wake/status":
                self._json(200, {"wake": False})

            elif self.path=="/api/memory/graph":
                if agent:
                    self._json(200, agent.graph.get_stats())
                else:
                    self._json(200, {"entities": 0, "relations": 0})

            elif _path_only == "/api/trends":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                cat = qs.get("category", ["technology"])[0]
                region = qs.get("region", ["wt"])[0]
                max_r = int(qs.get("max_results", [10])[0])
                result = trends_search(cat, region, max_r)
                self._json(200, result)

            elif self.path == "/api/telegram/status":
                self._json(200, telegram_status())

            elif self.path.startswith("/api/worldnews"):
                from jarvis_worldnews import fetch_world_news
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                max_items = min(int(qs.get("max", [30])[0]), 60)
                data = fetch_world_news(max_items)
                self._json(200, data)

            elif self.path == "/api/evolution/status":
                try: self._json(200, {"status": evol.get_status_summary(), "daily": evol.generate_daily_report(), "patterns": evol.analyze_patterns()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif self.path == "/api/evolution/heal":
                try: self._json(200, {"results": evol.run_healing_check()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif self.path == "/api/evolution/report/daily":
                try: self._json(200, evol.generate_daily_report())
                except Exception as e: self._json(500, {"error": str(e)})

            elif self.path == "/api/evolution/report/weekly":
                try: self._json(200, evol.generate_weekly_report())
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/vision/analyze":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                img = qs.get("image_path", [""])[0]
                try: self._json(200, vision.analyze_screenshot(img if img else None))
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/vision/ocr":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                img = qs.get("image_path", [""])[0]
                try: self._json(200, {"text": vision.read_text(img if img else None)})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/voice/list":
                try: self._json(200, {"voices": voice.list_voices()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/voice/status":
                try: self._json(200, {"current_voice": voice.current_voice, "available": list(voice.PLAYAI_VOICES.keys())})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/os/windows":
                try: self._json(200, {"windows": os_control.list_windows()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/os/apps":
                try: self._json(200, {"apps": os_control.list_apps()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/os/system":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                cat = qs.get("category", ["SPHardwareDataType"])[0]
                try: self._json(200, {"info": os_control.system_profiler(cat)})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/security/status":
                try: self._json(200, security.get_activity_report())
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/security/rules":
                try: self._json(200, {"rules": security.list_rules()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/security/audit":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                limit = int(qs.get("limit", [20])[0])
                try: self._json(200, {"audit": security.db.get_audit_log(limit)})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/pantheon/agents":
                try: self._json(200, {"agents": pantheon.db.list_agents()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/pantheon/tasks":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                limit = int(qs.get("limit", [10])[0])
                try: self._json(200, {"tasks": pantheon.db.get_pending_tasks(limit=limit)})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/pantheon/economy":
                try: self._json(200, {"economy": pantheon.economy_report()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/plugins/list":
                try: self._json(200, {"plugins": plugins.list_plugins()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/plugins/marketplace":
                try: self._json(200, {"marketplace": plugins.marketplace_catalog()})
                except Exception as e: self._json(500, {"error": str(e)})

            elif _path_only == "/api/plugins/health":
                try: self._json(200, {"health": plugins.plugins_health()})
                except Exception as e: self._json(500, {"error": str(e)})

            else:
                self._json(404,{"error":f"Non trovato: {self.path}"})
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        except Exception as e:
            try:
                self._json(500,{"error":str(e)})
            except:
                pass

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length",0))
            try: body = json.loads(self.rfile.read(n)) if n else {}
            except: self._json(400,{"error":"JSON non valido"}); return

            # ── STREAMING CHAT CON VOCE (SSE + TTS STREAMING SIMULTANEO) ──
            if self.path=="/api/chat/voice":
                msg = body.get("message","").strip()
                if not msg: self._json(400,{"error":"Messaggio vuoto"}); return
                
                voice = body.get("voice", cfg["tts"].get("qwen3_voice", "vivian"))
                language = body.get("language", "italian")
                speed = body.get("speed", cfg["tts"].get("speed", 1.0))
                
                with state_lock:
                    if "model" in body:
                        cfg["groq"]["model"] = body["model"]
                        agent.cfg["groq"]["model"] = body["model"]
                    if "temperature" in body:
                        cfg["groq"]["temperature"] = float(body["temperature"])

                self.send_response(200)
                self.send_header("Content-Type","text/event-stream")
                self.send_header("Cache-Control","no-cache")
                self.send_header("Connection","keep-alive")
                self._cors(); self.end_headers()

                try:
                    # actions first — se trovate, esegui e torna SUBITO senza LLM
                    actions = agent._detect_direct_actions(msg)
                    if actions:
                        self._sse_event({"type":"actions","data":actions})
                        # Estrai SPEECH se presente, generane TTS, chiudi senza LLM
                        speech = next((a[7:] for a in actions if a.startswith('SPEECH:')), None)
                        if speech:
                            try:
                                import asyncio, edge_tts, tempfile, base64
                                voice_map = {"vivian":"it-IT-ElsaNeural","serena":"it-IT-ElsaNeural",
                                    "aiden":"it-IT-DiegoNeural","ryan":"de-DE-KatjaNeural",
                                    "eric":"de-DE-ConradNeural","dylan":"de-DE-ConradNeural"}
                                tts_v = voice_map.get(voice, "it-IT-ElsaNeural")
                                async def _qk():
                                    comm = edge_tts.Communicate(speech, tts_v)
                                    with tempfile.NamedTemporaryFile(suffix=".mp3",delete=False) as f: p=f.name
                                    await comm.save(p); return p
                                p = asyncio.run(_qk())
                                with open(p,"rb") as f: aud=f.read()
                                os.unlink(p)
                                self._sse_event({"type":"audio_chunk","data":base64.b64encode(aud).decode(),"format":"mp3"})
                            except Exception as _e:
                                print(f"[TTS quick] {_e}")
                        memory.log_conversation("user", msg)
                        memory.log_conversation("assistant", speech or "✅")
                        self._sse_event({"type":"reply","data":speech or "","elapsed":0,"model":"direct"})
                        self._sse_event({"type":"done"})
                        return  # ← NESSUN LLM, nessun riassunto

                    # Nessuna action diretta → chiamata LLM streaming
                    import requests as req_lib
                    from jarvis_agent import LLM_URL as GROQ_URL, SYSTEM_PROMPT

                    memory_context = memory.get_context_for_prompt(msg, max_items=3)
                    # RAG context
                    rag_context = ""
                    if len(msg.split()) >= 3:
                        try:
                            rag_context = rag.query_context(msg, max_chunks=5)
                        except Exception as e:
                            print(f"[RAG] stream error: {e}")
                    memory.log_conversation("user", msg)
                    agent.history.append({"role": "user", "content": msg})
                    if len(agent.history) > 40:
                        agent.history = agent.history[-40:]

                    system_parts = [SYSTEM_PROMPT]
                    if rag_context:
                        system_parts.append(rag_context)
                    system_parts.append(memory_context)
                    system_msg = "\n\n".join(system_parts)
                    messages = [{"role": "system", "content": system_msg}] + agent.history
                    
                    headers = {
                        "Authorization": f"Bearer {cfg['groq']['api_key']}",
                        "Content-Type": "application/json"
                    }
                    
                    from jarvis_agent import _detect_complexity, FAST_MODEL
                    chosen_model = _detect_complexity(msg) or cfg["groq"]["model"]
                    payload = {
                        "model": chosen_model,
                        "messages": messages,
                        "temperature": float(cfg["groq"]["temperature"]),
                        "max_tokens": 2048,
                        "stream": True
                    }
                    # Notifica UI il tier usato
                    self._sse_event({"type":"tier","model":chosen_model,"fast":chosen_model==FAST_MODEL})

                    t0 = time.time()
                    full_reply = ""
                    first_token_time = None
                    buffer = ""
                    tts_pending = False
                    
                    # Mappa voci per Edge TTS (streaming veloce)
                    voice_map = {
                        "vivian": "it-IT-ElsaNeural",
                        "serena": "it-IT-ElsaNeural",
                        "aiden": "it-IT-DiegoNeural",
                        "ryan": "de-DE-KatjaNeural",
                        "eric": "de-DE-ConradNeural",
                        "dylan": "de-DE-ConradNeural",
                    }
                    tts_voice = voice_map.get(voice, "it-IT-ElsaNeural")
                    rate = f"+{int((speed-1)*100)}%"
                    
                    resp = req_lib.post(GROQ_URL, json=payload, headers=headers, timeout=60, stream=True)
                    
                    for line in resp.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            if line.startswith('data: '):
                                data = line[6:]
                                if data == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        if first_token_time is None:
                                            first_token_time = time.time() - t0
                                            self._sse_event({"type":"first_token","elapsed":round(first_token_time, 3)})
                                        
                                        full_reply += content
                                        buffer += content
                                        
                                        # Invia chunk di testo per UI
                                        self._sse_event({"type":"text_chunk","data":content})
                                        
                                        # Controlla se abbiamo una frase completa per TTS streaming
                                        sentence_match = re.search(r'(.+?[.!?])\s*', buffer)
                                        if sentence_match and len(buffer) > 20:
                                            sentence = sentence_match.group(1).strip()
                                            if len(sentence) > 8:
                                                # Genera TTS per questa frase (Edge TTS per velocità)
                                                try:
                                                    import asyncio, edge_tts, tempfile
                                                    async def _gen():
                                                        comm = edge_tts.Communicate(sentence, tts_voice, rate=rate)
                                                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                                                            p = f.name
                                                        await comm.save(p)
                                                        return p
                                                    p = asyncio.run(_gen())
                                                    with open(p, "rb") as f:
                                                        audio_data = f.read()
                                                    os.unlink(p)
                                                    import base64
                                                    self._sse_event({
                                                        "type": "audio_chunk",
                                                        "data": base64.b64encode(audio_data).decode(),
                                                        "format": "mp3"
                                                    })
                                                except Exception as e:
                                                    print(f"  [Stream TTS] Error: {e}")
                                                buffer = buffer[sentence_match.end():]
                                except:
                                    pass
                    
                    # Invia l'ultimo buffer come frase
                    if buffer.strip():
                        try:
                            import asyncio, edge_tts, tempfile
                            async def _gen():
                                comm = edge_tts.Communicate(buffer.strip(), tts_voice, rate=rate)
                                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                                    p = f.name
                                await comm.save(p)
                                return p
                            p = asyncio.run(_gen())
                            with open(p, "rb") as f:
                                audio_data = f.read()
                            os.unlink(p)
                            import base64
                            self._sse_event({
                                "type": "audio_chunk",
                                "data": base64.b64encode(audio_data).decode(),
                                "format": "mp3"
                            })
                        except Exception as e:
                            print(f"  [Stream TTS final] Error: {e}")
                    
                    elapsed = round(time.time() - t0, 2)
                    agent.history.append({"role": "assistant", "content": full_reply})
                    memory.log_conversation("assistant", full_reply)
                    
                    self._sse_event({"type":"reply","data":full_reply,"elapsed":elapsed,"model":cfg["groq"]["model"]})
                    self._sse_event({"type":"done"})
                    
                except Exception as e:
                    self._sse_event({"type":"error","data":str(e)})
                    traceback.print_exc()

            # ── STREAMING CHAT (SSE) ──
            elif self.path=="/api/chat/stream":
                msg = body.get("message","").strip()
                if not msg: self._json(400,{"error":"Messaggio vuoto"}); return
                with state_lock:
                    if "model" in body:
                        cfg["groq"]["model"] = body["model"]
                        agent.cfg["groq"]["model"] = body["model"]
                    if "temperature" in body:
                        cfg["groq"]["temperature"] = float(body["temperature"])

                self.send_response(200)
                self.send_header("Content-Type","text/event-stream")
                self.send_header("Cache-Control","no-cache")
                self.send_header("Connection","keep-alive")
                self._cors(); self.end_headers()

                try:
                    # actions first — se trovate, torna SUBITO senza LLM
                    actions = agent._detect_direct_actions(msg)
                    if actions:
                        self._sse_event({"type":"actions","data":actions})
                        speech = next((a[7:] for a in actions if a.startswith('SPEECH:')), None)
                        memory.log_conversation("user", msg)
                        memory.log_conversation("assistant", speech or "✅")
                        self._sse_event({"type":"reply","data":speech or "","elapsed":0,"model":"direct"})
                        self._sse_event({"type":"done"})
                        return  # ← NESSUN LLM

                    # streaming reply (solo se nessuna action diretta)
                    reply, elapsed = agent.chat_stream(msg)
                    self._sse_event({"type":"reply","data":reply,"elapsed":elapsed,"model":cfg["groq"]["model"]})
                    self._sse_event({"type":"done"})
                except Exception as e:
                    self._sse_event({"type":"error","data":str(e)})
                    traceback.print_exc()

            elif self.path=="/api/chat":
                msg = body.get("message","").strip()
                if not msg: self._json(400,{"error":"Messaggio vuoto"}); return
                with state_lock:
                    if "model" in body:
                        cfg["groq"]["model"] = body["model"]
                        agent.cfg["groq"]["model"] = body["model"]
                    if "temperature" in body:
                        cfg["groq"]["temperature"] = float(body["temperature"])
                t0 = time.time()
                try:
                    from jarvis_agent import _detect_complexity, FAST_MODEL
                    chosen = _detect_complexity(msg) or cfg["groq"]["model"]
                    reply, actions = agent.chat(msg)
                    self._json(200,{"reply":reply,"actions":actions,
                        "elapsed":round(time.time()-t0,2),
                        "model":chosen,"fast":chosen==FAST_MODEL})
                except Exception as e:
                    traceback.print_exc()
                    self._json(500,{"error":str(e)})

            elif self.path=="/api/tool":
                name = body.get("name","")
                args = body.get("args",{})
                if not name: self._json(400,{"error":"Nome tool mancante"}); return
                self._json(200,{"result":execute_tool(name,args),"tool":name})

            elif self.path=="/api/translate":
                text = body.get("text","")
                target = body.get("target","italian")
                source = body.get("source","english")
                if not text: self._json(400,{"error":"Testo vuoto"}); return
                t0 = time.time()
                translated = None
                lang_map = {"italian":"it","english":"en","french":"fr","german":"de","spanish":"es"}
                src_lang = lang_map.get(source,"en")
                tgt_lang = lang_map.get(target,"it")
                try:
                    if _HAVE_DEEP:
                        r = _GTrans(source=src_lang, target=tgt_lang).translate(text[:500])
                        if r and r.strip() and r.strip() != text[:2000]:
                            translated = r.strip()
                except Exception as _te:
                    print(f"[TRANS] deep error: {_te}")
                if not translated:
                    try:
                        from jarvis_agent import LLM_URL as GROQ_URL
                        import requests as req_lib
                        payload = {"model": cfg["groq"]["model"], "messages": [
                            {"role":"system","content":f"Sei un traduttore professionista. Traduci il seguente testo da {source} a {target}. Restituisci SOLO la traduzione, nient'altro."},
                            {"role":"user","content": text[:2000]}
                        ], "temperature": 0.1, "max_tokens": 2048}
                        headers = {"Authorization": f"Bearer {cfg['groq']['api_key']}", "Content-Type": "application/json"}
                        resp = req_lib.post(GROQ_URL, json=payload, headers=headers, timeout=10)
                        r = resp.json()["choices"][0]["message"]["content"].strip()
                        if r: translated = r
                    except:
                        pass
                if translated:
                    self._json(200, {"translated":translated, "elapsed":round(time.time()-t0,2)})
                else:
                    self._json(200, {"translated":text, "note":"traduzione non disponibile"})

            elif self.path=="/api/tts":
                text  = body.get("text","")
                voice = body.get("voice", cfg["tts"].get("qwen3_voice", "vivian"))
                language = body.get("language", "italian")
                speed = body.get("speed", cfg["tts"].get("speed",1.0))
                if not text: self._json(400,{"error":"Testo vuoto"}); return
                
                t0 = time.time()
                data, content_type = _generate_tts_chunk(text, voice=voice, language=language, speed=speed)
                
                if data is None:
                    # Last fallback: macOS say
                    try:
                        import subprocess
                        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                        clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                        clean = re.sub(r'`(.+?)`', r'\1', clean)
                        clean = re.sub(r'#{1,6}\s*', '', clean)
                        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean).strip()
                        subprocess.run(["say", "-v", "Alice", clean[:200]], capture_output=True)
                        self._json(200,{"status":"played_via_say","warning":"TTS fallback, usato macOS say"})
                        return
                    except Exception as e:
                        self._json(500,{"error":f"TTS tutti i fallback falliti: {e}"})
                        return
                
                ct = "audio/wav" if content_type == "audio/wav" else "audio/mpeg"
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self._cors(); self.end_headers(); self.wfile.write(data)
                print(f"  [TTS] Generato in {time.time()-t0:.2f}s ({len(data)} bytes)")

            elif self.path=="/api/wav2lip":
                text  = body.get("text","")
                voice = body.get("voice", cfg["tts"].get("qwen3_voice", "vivian"))
                language = body.get("language", "italian")
                if not text: self._json(400,{"error":"Testo vuoto"}); return

                t0 = time.time()
                tts_data, _ = _generate_tts_chunk(text, voice=voice, language=language, speed=1.0)
                if tts_data is None:
                    self._json(500,{"error":"TTS fallito"}); return

                audio_path = "/tmp/wav2lip_input.wav"
                with open(audio_path, "wb") as f: f.write(tts_data)

                out_path = f"/tmp/wav2lip_{int(time.time())}.mp4"
                try:
                    from wav2lip_run import run as wav2lip_run
                    face_path = os.path.join(os.path.dirname(__file__), "holographic_avatar.png")
                    wav2lip_run(face_path, audio_path, out_path, fps=20)
                except Exception as e:
                    self._json(500,{"error":f"Wav2Lip: {e}"}); return

                with open(out_path, "rb") as f: video_data = f.read()
                os.unlink(out_path)
                os.unlink(audio_path)
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(video_data)))
                self.send_header("Connection", "close")
                self._cors(); self.end_headers(); self.wfile.write(video_data)
                print(f"  [Wav2Lip] video in {time.time()-t0:.2f}s ({len(video_data)} bytes)")

            elif self.path=="/api/config/update":
                with state_lock:
                    for k,v in body.items():
                        if k=="model": cfg["groq"]["model"]=v; agent.cfg["groq"]["model"]=v
                        elif k=="voice": cfg["tts"]["voice"]=v; cfg["tts"]["qwen3_voice"]=v
                        elif k=="temperature": cfg["groq"]["temperature"]=float(v)
                        elif k=="speed": cfg["tts"]["speed"]=float(v)
                        elif k=="qwen3_voice": cfg["tts"]["qwen3_voice"]=v; cfg["tts"]["voice"]=v
                        elif k=="qwen3_language": cfg["tts"]["qwen3_language"]=v
                        elif k=="wake": pass  # wake word disattivato
                self._json(200,{"status":"ok"})

            elif self.path=="/api/wake/toggle":
                self._json(200,{"wake": False, "message": "Wake word disattivato"})

            elif self.path=="/api/memory/remember":
                content = body.get("content","")
                category = body.get("category","fact")
                tags = body.get("tags",[])
                if not content: self._json(400,{"error":"Contenuto mancante"}); return
                result = memory.remember(content, category, tags)
                self._json(200,{"result":result})

            elif self.path=="/api/memory/search":
                query = body.get("query","")
                if not query: self._json(400,{"error":"Query mancante"}); return
                results = memory.search(query)
                self._json(200,{"results":results})

            elif self.path=="/api/memory/preference":
                key = body.get("key","")
                value = body.get("value","")
                if not key: self._json(400,{"error":"Key mancante"}); return
                result = memory.set_preference(key, value)
                self._json(200,{"result":result})

            elif self.path=="/api/memory/delete":
                mid = body.get("id")
                if mid is None: self._json(400,{"error":"ID mancante"}); return
                result = memory.delete_memory(int(mid))
                self._json(200,{"result":result})

            elif self.path=="/api/memory/update":
                mid = body.get("id")
                content = body.get("content","").strip()
                if mid is None or not content: self._json(400,{"error":"ID e content richiesti"}); return
                c = memory.db.cursor()
                c.execute("UPDATE memories SET content=?, updated_at=datetime('now') WHERE id=?", (content, int(mid)))
                memory.db.commit()
                self._json(200,{"result":f"Memoria {mid} aggiornata"})

            elif self.path=="/api/calendar/create":
                title = body.get("title","")
                start = body.get("start_date","")
                duration = body.get("duration_minutes", 60)
                if not title: self._json(400,{"error":"Titolo mancante"}); return
                from jarvis_calendar import create_event
                result = create_event(title, start, duration)
                self._json(200,{"result":result})

            elif self.path=="/api/notes/create":
                title = body.get("title","")
                b = body.get("body","")
                if not title: self._json(400,{"error":"Titolo mancante"}); return
                from jarvis_notes import create_note
                result = create_note(title, b)
                self._json(200,{"result":result})

            elif self.path=="/api/plan/create":
                title = body.get("title","")
                steps = body.get("steps",[])
                priority = body.get("priority","medium")
                if not title: self._json(400,{"error":"Titolo mancante"}); return
                from jarvis_planner import create_plan
                result = create_plan(title, steps, priority)
                self._json(200,{"result":result})

            elif self.path=="/api/git/command":
                cmd = body.get("command","")
                if not cmd: self._json(400,{"error":"Command mancante"}); return
                from jarvis_git import git_execute
                result = git_execute(cmd)
                self._json(200,{"result":result})

            elif self.path=="/api/web/search":
                query = body.get("query","")
                if not query: self._json(400,{"error":"Query mancante"}); return
                from jarvis_tools import web_search_ddg
                results = web_search_ddg(query)
                self._json(200,{"results":results})

            elif self.path=="/api/screen/ocr":
                image_path = body.get("image_path","")
                result = ocr_screenshot(image_path if image_path else None)
                self._json(200,{"result":result})

            elif self.path=="/api/browser/navigate":
                url = body.get("url","")
                if not url: self._json(400,{"error":"URL mancante"}); return
                result = playwright_navigate(url)
                self._json(200,{"result":result})

            elif self.path=="/api/browser/extract":
                url = body.get("url","")
                selector = body.get("selector","body")
                if not url: self._json(400,{"error":"URL mancante"}); return
                result = playwright_extract(url, selector)
                self._json(200,{"result":result})

            elif self.path=="/api/browser/screenshot":
                url = body.get("url","")
                save_path = body.get("save_path","")
                if not url: self._json(400,{"error":"URL mancante"}); return
                result = playwright_screenshot(url, save_path if save_path else None)
                self._json(200,{"result":result})

            elif self.path=="/api/computer/action":
                action = body.get("action","")
                if not action: self._json(400,{"error":"Azione mancante"}); return
                params = {k:v for k,v in body.items() if k != "action"}
                result = computer_use_action(action, **params)
                self._json(200,{"result":result})

            elif self.path=="/api/rag/add":
                title = body.get("title","")
                content = body.get("content","")
                source = body.get("source","")
                if not title or not content: self._json(400,{"error":"Title e content richiesti"}); return
                result = rag.add_document(title, content, source)
                self._json(200,{"result":result})

            elif self.path=="/api/rag/add_file":
                file_path = body.get("file_path","")
                if not file_path: self._json(400,{"error":"File path mancante"}); return
                result = rag.add_file(file_path)
                self._json(200,{"result":result})

            elif self.path=="/api/rag/search":
                query = body.get("query","")
                limit = body.get("limit",5)
                if not query: self._json(400,{"error":"Query mancante"}); return
                results = rag.search(query, limit)
                self._json(200,{"results":results})

            elif self.path=="/api/rag/semantic_search":
                query = body.get("query","")
                limit = body.get("limit",5)
                if not query: self._json(400,{"error":"Query mancante"}); return
                results = rag.semantic_search(query, limit)
                self._json(200,{"results":results})

            elif self.path=="/api/rag/delete":
                doc_id = body.get("doc_id",0)
                if not doc_id: self._json(400,{"error":"Doc ID mancante"}); return
                result = rag.delete_document(doc_id)
                self._json(200,{"result":result})

            elif self.path=="/api/rag/delete_all":
                result = rag.delete_all()
                self._json(200,{"result":result})

            elif self.path=="/api/rag/add_folder":
                folder = body.get("folder_path","")
                recursive = body.get("recursive", True)
                if not folder: self._json(400,{"error":"folder_path mancante"}); return
                result = rag.add_folder(folder, recursive)
                self._json(200,{"result":result})

            elif self.path=="/api/rag/add_folder_stream":
                """SSE streaming: indicizza cartella con progress bar"""
                folder = body.get("folder_path","")
                recursive = body.get("recursive", True)
                if not folder: self._json(400,{"error":"folder_path mancante"}); return

                self.send_response(200)
                self.send_header("Content-Type","text/event-stream")
                self.send_header("Cache-Control","no-cache")
                self.send_header("Connection","keep-alive")
                self._cors(); self.end_headers()

                def on_progress(current, total, file_name, status):
                    try:
                        pct = round(current / total * 100, 1) if total > 0 else 0
                        self._sse_event({
                            "type": "progress",
                            "current": current,
                            "total": total,
                            "percent": pct,
                            "file": file_name,
                            "status": status
                        })
                    except:
                        pass

                result = rag.add_folder(folder, recursive, progress_callback=on_progress)
                self._sse_event({"type": "complete", "result": result})

            elif self.path=="/api/rag/ingest":
                """Indicizza la cartella data/documents/ e data/"""
                from jarvis_rag import DOCS_DIR
                results = []
                for folder in [str(DOCS_DIR), str(Path(__file__).parent / "data")]:
                    if Path(folder).exists():
                        r = rag.add_folder(folder, recursive=True)
                        results.append({"folder": folder, **r})
                self._json(200,{"results": results})

            elif self.path=="/api/rag/update":
                doc_id = body.get("doc_id", 0)
                if not doc_id: self._json(400, {"error": "doc_id mancante"}); return
                result = rag.update_document(
                    doc_id,
                    title=body.get("title"),
                    content=body.get("content"),
                    source=body.get("source"),
                    metadata=body.get("metadata")
                )
                self._json(200, {"result": result})

            elif self.path=="/api/rag/reembed":
                """Rigenera tutti gli embedding"""
                self.send_response(200)
                self.send_header("Content-Type","text/event-stream")
                self.send_header("Cache-Control","no-cache")
                self.send_header("Connection","keep-alive")
                self._cors(); self.end_headers()

                def on_progress(current, total, label, status):
                    try:
                        pct = round(current / total * 100, 1) if total > 0 else 0
                        self._sse_event({
                            "type": "progress",
                            "current": current,
                            "total": total,
                            "percent": pct,
                            "label": label,
                            "status": status
                        })
                    except:
                        pass

                result = rag.reembed_all(progress_callback=on_progress)
                self._sse_event({"type": "complete", "result": result})

            elif self.path=="/api/rag/search_by_source":
                query = body.get("query", "")
                limit = body.get("limit", 50)
                if not query: self._json(400, {"error": "query mancante"}); return
                self._json(200, {"documents": rag.search_by_source(query, limit)})

            elif self.path=="/api/rag/export":
                self._json(200, rag.export_json())

            elif self.path=="/api/rag/dedup":
                threshold = body.get("threshold", 0.95)
                result = rag.deduplicate(threshold)
                self._json(200, {"result": result})

            elif self.path=="/api/approval/approve":
                request_id = body.get("request_id","")
                auto_future = body.get("auto_future",False)
                if not request_id: self._json(400,{"error":"Request ID mancante"}); return
                result = approval.approve(request_id, auto_future)
                self._json(200,{"approved":result,"request_id":request_id})

            elif self.path=="/api/approval/deny":
                request_id = body.get("request_id","")
                if not request_id: self._json(400,{"error":"Request ID mancante"}); return
                result = approval.deny(request_id)
                self._json(200,{"denied":result,"request_id":request_id})

            elif self.path=="/api/reset":
                with state_lock:
                    agent.reset()
                self._json(200,{"status":"ok"})

            elif self.path == "/api/trends/search":
                query = body.get("query", "")
                region = body.get("region", "wt")
                max_r = body.get("max_results", 15)
                if query:
                    result = trends_search(query, region, max_r)
                else:
                    result = trending_now(region)
                self._json(200, result)

            elif self.path == "/api/telegram/send":
                message = body.get("message", "")
                chat_id = body.get("chat_id", 0)
                if not message:
                    self._json(400, {"error": "Messaggio vuoto"})
                    return
                result = telegram_send(chat_id if chat_id else None, message)
                self._json(200, {"result": result})

            elif self.path == "/api/vision/analyze":
                img = body.get("image_path", "")
                self._json(200, vision.analyze_screenshot(img if img else None))

            elif self.path == "/api/vision/ocr":
                img = body.get("image_path", "")
                self._json(200, {"text": vision.read_text(img if img else None)})

            elif self.path == "/api/vision/qr":
                img = body.get("image_path", "")
                self._json(200, {"codes": vision.detect_qr(img if img else None)})

            elif self.path == "/api/vision/describe":
                img = body.get("image_path", "")
                if not img: self._json(400, {"error": "image_path required"}); return
                self._json(200, {"description": vision.describe_image(img)})

            elif self.path == "/api/vision/region":
                x = body.get("x", 0); y = body.get("y", 0); w = body.get("w", 0); h = body.get("h", 0)
                self._json(200, vision.analyze_region(x, y, w, h))

            elif self.path == "/api/voice/say":
                text = body.get("text", "")
                if not text: self._json(400, {"error": "Text required"}); return
                v = body.get("voice", voice.current_voice)
                speed = body.get("speed", 1.0)
                self._json(200, {"result": voice.say(text, v, speed)})

            elif self.path == "/api/voice/set":
                v = body.get("voice", "")
                if not v: self._json(400, {"error": "Voice required"}); return
                self._json(200, {"result": voice.set_voice(v)})

            elif self.path == "/api/os/focus":
                title = body.get("title", "")
                if not title: self._json(400, {"error": "Title required"}); return
                self._json(200, {"result": os_control.focus_window(title)})

            elif self.path == "/api/os/move":
                title = body.get("title", "")
                x = body.get("x", 0); y = body.get("y", 0)
                w = body.get("width"); h = body.get("height")
                self._json(200, {"result": os_control.move_window(title, x, y, w, h)})

            elif self.path == "/api/os/minimize":
                title = body.get("title", "")
                if not title: self._json(400, {"error": "Title required"}); return
                self._json(200, {"result": os_control.minimize_window(title)})

            elif self.path == "/api/os/maximize":
                title = body.get("title", "")
                if not title: self._json(400, {"error": "Title required"}); return
                self._json(200, {"result": os_control.maximize_window(title)})

            elif self.path == "/api/os/dock":
                action = body.get("action", "")
                if action == "autohide":
                    self._json(200, {"result": os_control.dock_autohide(body.get("enabled", True))})
                elif action == "position":
                    self._json(200, {"result": os_control.dock_position(body.get("position", "bottom"))})
                else:
                    self._json(400, {"error": "Invalid dock action"})

            elif self.path == "/api/os/wallpaper":
                img = body.get("image_path", "")
                self._json(200, {"result": os_control.set_wallpaper(img if img else None)})

            elif self.path == "/api/os/screensaver":
                os_control.screensaver()
                self._json(200, {"result": "Screensaver started"})

            elif self.path == "/api/os/empty_trash":
                self._json(200, {"result": os_control.empty_trash()})

            elif self.path == "/api/os/dark_mode":
                self._json(200, {"result": os_control.toggle_dark_mode()})

            elif self.path == "/api/os/pref_pane":
                pane = body.get("pane", "")
                if not pane: self._json(400, {"error": "Pane required"}); return
                self._json(200, {"result": os_control.open_pref_pane(pane)})

            elif self.path == "/api/security/check":
                cmd = body.get("command", "")
                if not cmd: self._json(400, {"error": "Command required"}); return
                safe, reason, risk = security.check_command_safety(cmd)
                self._json(200, {"safe": safe, "reason": reason, "risk": risk})

            elif self.path == "/api/security/rule":
                action = body.get("action", "add")
                pattern = body.get("pattern", "")
                level = body.get("level", "read")
                if action == "add":
                    self._json(200, {"result": security.add_permission_rule(pattern, level)})
                elif action == "remove":
                    self._json(200, {"result": security.remove_permission_rule(pattern)})
                else:
                    self._json(400, {"error": "Invalid action"})

            elif self.path == "/api/pantheon/register":
                name = body.get("name", "")
                caps = body.get("capabilities", "")
                endpoint = body.get("endpoint", "")
                if not name: self._json(400, {"error": "Name required"}); return
                cl = [c.strip() for c in caps.split(",")] if caps else ["general"]
                self._json(200, pantheon.register_agent(name, cl, endpoint))

            elif self.path == "/api/pantheon/delegate":
                desc = body.get("description", "")
                agent_name = body.get("agent", "")
                if not desc: self._json(400, {"error": "Description required"}); return
                self._json(200, pantheon.delegate(desc, agent_name if agent_name else None))

            elif self.path == "/api/pantheon/transfer":
                frm = body.get("from_agent", "")
                to = body.get("to_agent", "")
                amount = body.get("amount", 0)
                reason = body.get("reason", "")
                if not frm or not to: self._json(400, {"error": "from_agent and to_agent required"}); return
                ok, msg = pantheon.db.transfer_credits(frm, to, amount, reason)
                self._json(200, {"success": ok, "message": msg})

            elif self.path == "/api/pantheon/message":
                to = body.get("to_agent", "")
                subject = body.get("subject", "")
                msg_body = body.get("body", "")
                if not to or not subject: self._json(400, {"error": "to_agent and subject required"}); return
                self._json(200, {"result": pantheon.send_message(to, subject, msg_body)})

            elif self.path == "/api/pantheon/broadcast":
                subject = body.get("subject", "")
                msg_body = body.get("body", "")
                if not subject: self._json(400, {"error": "Subject required"}); return
                self._json(200, {"result": pantheon.broadcast(subject, msg_body)})

            elif self.path == "/api/pantheon/task/complete":
                task_id = body.get("task_id", "")
                result = body.get("result", "")
                error = body.get("error", "")
                if not task_id: self._json(400, {"error": "task_id required"}); return
                self._json(200, {"result": pantheon.complete_task(task_id, result, error)})

            elif self.path == "/api/plugins/install":
                source = body.get("source", "")
                name = body.get("name", "")
                if not source: self._json(400, {"error": "Source required"}); return
                self._json(200, {"result": plugins.install(source, name if name else None)})

            elif self.path == "/api/plugins/uninstall":
                name = body.get("name", "")
                if not name: self._json(400, {"error": "Name required"}); return
                self._json(200, {"result": plugins.uninstall(name)})

            elif self.path == "/api/plugins/toggle":
                name = body.get("name", "")
                enable = body.get("enable", True)
                if not name: self._json(400, {"error": "Name required"}); return
                if enable:
                    self._json(200, {"result": plugins.enable(name)})
                else:
                    self._json(200, {"result": plugins.disable(name)})

            elif self.path == "/api/export":
                fmt = body.get("format","json")
                convos = memory.get_recent_conversations(100)
                if fmt == "markdown":
                    md = "# J.A.R.V.I.S Conversation Export\n\n"
                    for c in convos:
                        role = "👤 Tu" if c["role"]=="user" else "🤖 JARVIS"
                        md += f"### {role} — {c['timestamp']}\n\n{c['content']}\n\n---\n\n"
                    self.send_response(200)
                    self.send_header("Content-Type","text/markdown")
                    self.send_header("Content-Disposition",'attachment; filename="jarvis_export.md"')
                    self.send_header("Connection", "close")
                    self._cors(); self.end_headers(); self.wfile.write(md.encode())
                else:
                    self._json(200,{"conversations":convos})
            else:
                self._json(404,{"error":f"POST non trovato: {self.path}"})
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        except Exception as e:
            try:
                self._json(500,{"error":str(e)})
            except:
                pass

PORT = int(os.environ.get("JARVIS_PORT",9999))

if __name__=="__main__":
    print()
    print("═"*52)
    print("  J.A.R.V.I.S  SERVER  v9.0 — CYBERPUNK EDITION")
    print("═"*52)
    print(f"  URL  →  http://localhost:{PORT}")
    print(f"  LLM  →  {cfg['groq']['model']}")
    print(f"  TTS  →  Qwen3-TTS (MLX) + Streaming + Edge")
    print(f"  Voce →  {cfg['tts'].get('qwen3_voice', 'vivian')} ({cfg['tts'].get('qwen3_language', 'Italian')})")
    print(f"  Tool →  {len(TOOLS_SCHEMA)} disponibili")
    print(f"  OCR  →  Apple Vision + Tesseract")
    print(f"  RAG  →  Vector embeddings + FTS5")
    print(f"  Computer Use → Mouse + Keyboard + Drag")
    print(f"  Browser → Playwright automation + AppleScript")
    print(f"  Approval → Flow per azioni sensibili")
    print(f"  SSE  →  Streaming + TTS chunks abilitati")
    print(f"  SQLite → WAL mode + busy_timeout")
    print(f"  Wake →  disattivato")
    print(f"  HUD  →  Cyberpunk v11.0 — Vision + Voice + OS Control + Security + Pantheon + Plugins")
    print("─"*52)
    if cfg["groq"]["api_key"]=="YOUR_GROQ_API_KEY_HERE":
        print("  ⚠  Groq API key mancante in config.json!")
        print()
    print("  Ctrl+C per fermare")
    print("─"*52)
    print()
    sys.stdout.flush()
    # Precarica Wav2Lip (modello + face detection)
    try:
        from wav2lip_run import prepare_face
        face_path = os.path.join(os.path.dirname(__file__), "holographic_avatar.png")
        if os.path.exists(face_path):
            prepare_face(face_path)
            print(f"  Wav2Lip → Modello e face pre-caricati")
        else:
            print(f"  Wav2Lip → avatar non trovato, skip preload")
    except Exception as e:
        print(f"  Wav2Lip → preload skipped: {e}")

    # ── Telegram Bot (opzionale) ──
    if cfg.get("telegram", {}).get("enabled", False) and cfg.get("telegram", {}).get("bot_token", ""):
        try:
            telegram_start()
            print(f"  Telegram → bot attivo")
        except Exception as e:
            print(f"  Telegram → errore avvio: {e}")
    else:
        print(f"  Telegram → disattivato (configura telegram.bot_token in config.json)")

    # ── Wake Word disattivato ──
    print(f"  Wake → disattivato")

    try:
        HOST = os.environ.get("JARVIS_HOST", "127.0.0.1")
        server = ThreadedHTTPServer((HOST,PORT), H)
        print(f"  Host  →  {HOST}")
        server.allow_reuse_address = True
        server.daemon_threads = True
        print(f"  Server avviato su {PORT} (multi-thread, stabile)")
        sys.stdout.flush()
        server.serve_forever()
    except Exception as e:
        print(f"\n  ERRORE SERVER: {e}")
        traceback.print_exc()
        sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n  Fermo worker TTS...")
        _tts_stop.set()
        _tts_event.set()
        if _tts_worker_thread:
            _tts_worker_thread.join(timeout=3)
        if _wake:
            _wake.stop()
            print("  Wake word fermato.")
        else:
            print("  Wake word già fermo.")
        print("\n  Server fermato.\n")
