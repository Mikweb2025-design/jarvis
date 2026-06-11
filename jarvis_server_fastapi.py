#!/usr/bin/env python3
"""jarvis_server_fastapi.py — J.A.R.V.I.S FastAPI v1.0 — Modern async backend"""
import sys, json, time, os, traceback, threading, re, base64, asyncio, logging
import numpy as np
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Query, Body
from fastapi.responses import JSONResponse, StreamingResponse, Response, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))

# ── Constants ──
VOICE_MAP = {"vivian": "it-IT-ElsaNeural", "serena": "it-IT-ElsaNeural",
             "aiden": "it-IT-DiegoNeural", "ryan": "de-DE-KatjaNeural",
             "eric": "de-DE-ConradNeural", "dylan": "de-DE-ConradNeural"}

logger = logging.getLogger("jarvis_fastapi")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

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
from jarvis_imagegen import generate_image as _gen_image, list_models as _list_img_models
from jarvis_musicgen import generate_music as _gen_music, list_genres as _list_music_g, get_status as _music_st
from jarvis_gitnexus import analyze_repo as _kg_repo, build_knowledge_graph as _kg_graph, get_symbols as _kg_syms, search_code as _kg_srch, get_status as _kg_st
from jarvis_telegram import start as telegram_start, send as telegram_send, status as telegram_status
from jarvis_evolution import evol
from jarvis_vision import vision
from jarvis_voice import voice
from jarvis_os_control import os_control
from jarvis_security import security
from jarvis_pantheon import pantheon
from jarvis_plugins import plugins
from jarvis_skills import skills
try:
    from jarvis_whatsapp_openwa import send_message as _wa_send, send_image as _wa_send_img, send_audio as _wa_send_audio, get_status as _wa_status, ensure_session as _wa_ensure, check_health as _wa_health, OPENWA_URL
except ImportError:
    _wa_send = _wa_send_img = _wa_send_audio = _wa_status = _wa_ensure = _wa_health = lambda *a, **kw: {"ok": False, "error": "OpenWA not available"}
    OPENWA_URL = "http://localhost:2785"

# ── Pydantic Models ──

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    model: Optional[str] = None
    temperature: Optional[float] = None

class ChatVoiceRequest(ChatRequest):
    voice: str = "vivian"
    language: str = "italian"
    speed: float = 1.0

class ToolRequest(BaseModel):
    name: str
    args: dict = {}

class TTSRequest(BaseModel):
    text: str
    voice: str = "vivian"
    language: str = "italian"
    speed: float = 1.0

class ConfigUpdate(BaseModel):
    model: Optional[str] = None
    voice: Optional[str] = None
    temperature: Optional[float] = None
    speed: Optional[float] = None
    qwen3_voice: Optional[str] = None
    qwen3_language: Optional[str] = None

class MemoryRequest(BaseModel):
    content: str
    category: str = "fact"
    tags: list = []

class MemoryUpdate(BaseModel):
    id: int
    content: str

class MemoryDelete(BaseModel):
    id: int

class MemorySearch(BaseModel):
    query: str

class PreferenceRequest(BaseModel):
    key: str
    value: str

class RAGAddRequest(BaseModel):
    title: str
    content: str
    source: str = ""

class RAGAddFile(BaseModel):
    file_path: str

class RAGSearch(BaseModel):
    query: str
    limit: int = 5

class RAGDelete(BaseModel):
    doc_id: int

class RAGAddFolder(BaseModel):
    folder_path: str
    recursive: bool = True

class TranslateRequest(BaseModel):
    text: str
    target: str = "italian"
    source: str = "english"

class PresentationCreate(BaseModel):
    data: Optional[dict] = None
    title: Optional[str] = None
    slides: list = []
    pptx: bool = False
    theme: str = "corporate"
    presenton: bool = False

class PresentationAuto(BaseModel):
    prompt: str
    format: str = "html"
    title: Optional[str] = None
    theme: str = "corporate"
    author: str = "J.A.R.V.I.S"
    language: str = "Italian"
    tone: str = "default"
    n_slides: int = 8
    instructions: str = ""

class WebSearch(BaseModel):
    query: str

class BrowserNavigate(BaseModel):
    url: str

class BrowserExtract(BaseModel):
    url: str
    selector: str = "body"

class BrowserScreenshot(BaseModel):
    url: str
    save_path: str = ""

class ComputerAction(BaseModel):
    action: str

class CalendarCreate(BaseModel):
    title: str
    start_date: str = ""
    duration_minutes: int = 60

class NotesCreate(BaseModel):
    title: str
    body: str = ""

class PlanCreate(BaseModel):
    title: str
    steps: list = []
    priority: str = "medium"

class GitCommand(BaseModel):
    command: str

class ApprovalAction(BaseModel):
    request_id: str
    auto_future: bool = False

class ApprovalDeny(BaseModel):
    request_id: str

class VisionAnalyze(BaseModel):
    image_path: str = ""

class VisionDescribe(BaseModel):
    image_path: str

class VisionRegion(BaseModel):
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

class VoiceSay(BaseModel):
    text: str
    voice: Optional[str] = None
    speed: float = 1.0

class VoiceSet(BaseModel):
    voice: str

class OSFocus(BaseModel):
    title: str

class OSMove(BaseModel):
    title: str
    x: int = 0
    y: int = 0
    width: Optional[int] = None
    height: Optional[int] = None

class OSMinMax(BaseModel):
    title: str

class OSDock(BaseModel):
    action: str
    enabled: Optional[bool] = None
    position: Optional[str] = None

class OSWallpaper(BaseModel):
    image_path: str = ""

class OSPrefPane(BaseModel):
    pane: str

class SecurityCheck(BaseModel):
    command: str

class SecurityRule(BaseModel):
    action: str = "add"
    pattern: str = ""
    level: str = "read"

class PantheonRegister(BaseModel):
    name: str
    capabilities: str = ""
    endpoint: str = ""

class PantheonDelegate(BaseModel):
    description: str
    agent: str = ""

class PantheonTransfer(BaseModel):
    from_agent: str
    to_agent: str
    amount: int = 0
    reason: str = ""

class PantheonMessage(BaseModel):
    to_agent: str
    subject: str
    body: str = ""

class PantheonBroadcast(BaseModel):
    subject: str
    body: str = ""

class PantheonTaskComplete(BaseModel):
    task_id: str
    result: str = ""
    error: str = ""

class PluginInstall(BaseModel):
    source: str
    name: Optional[str] = None

class PluginUninstall(BaseModel):
    name: str

class PluginToggle(BaseModel):
    name: str
    enable: bool = True

class PluginRate(BaseModel):
    name: str
    rating: int
    review: str = ""

class SkillCreate(BaseModel):
    name: str
    description: str
    category: str = "general"

class SkillRun(BaseModel):
    name: str
    args: dict = {}

class SkillImprove(BaseModel):
    name: str
    feedback: str

class SkillName(BaseModel):
    name: str

class GoalCreate(BaseModel):
    title: str
    description: str = ""

class GoalDelete(BaseModel):
    id: int

class GoalAddKR(BaseModel):
    goal_id: int
    title: str
    target: int = 100

class GoalUpdateKR(BaseModel):
    goal_id: int
    kr_id: int
    current: int = 0

class ExportRequest(BaseModel):
    format: str = "json"

class VideoAnalyticsStart(BaseModel):
    stream_url: str = "0"

class VideoAnalyticsAction(BaseModel):
    action: str = "status"

class VideoAnalyticsCalibrate(BaseModel):
    value: float = 1.0

class WhatsAppSendRequest(BaseModel):
    to: str
    text: str

class WhatsAppSendImageRequest(BaseModel):
    to: str
    url: str
    caption: Optional[str] = None

class RAGUpdate(BaseModel):
    doc_id: int
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[dict] = None

class RAGSearchBySource(BaseModel):
    query: str
    limit: int = 50

class RAGDedup(BaseModel):
    threshold: float = 0.95

class TrendsSearch(BaseModel):
    query: str = ""
    region: str = "wt"
    max_results: int = 15

class TelegramSend(BaseModel):
    message: str
    chat_id: int = 0

class ImageGenRequest(BaseModel):
    prompt: str
    model: str = "black-forest-labs/FLUX.1-schnell"
    size: str = "1024x1024"
    n: int = 1

class MusicGenRequest(BaseModel):
    prompt: str = ""
    genre: str = "electronic"
    duration: int = 30
    temperature: float = 1.0

class KGSearchRequest(BaseModel):
    query: str
    path: str = ""

class KGPathRequest(BaseModel):
    path: str = ""

# ── Globals ──

cfg = load_config()
agent = JarvisAgent(cfg)
tts_engine = KokoroTTS(cfg)

# ── Qwen3-TTS Worker ──
_tts_model = None
_tts_queue = None
_tts_result = {}
_tts_lock = threading.Lock()
_tts_event = threading.Event()
_tts_ready = threading.Event()
_tts_stop = threading.Event()
_tts_worker_thread = None

def _tts_worker():
    global _tts_model
    try:
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        model_name = cfg["tts"].get("qwen3_model", "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit")
        print(f"  [TTS] Worker: caricamento {model_name}...")
        t0 = time.time()
        _tts_model = load_model(model_name)
        elapsed = time.time() - t0
        print(f"  [TTS] OK Qwen3-TTS caricato in RAM in {elapsed:.1f}s")
        _tts_ready.set()
    except Exception as e:
        print(f"  [TTS] Errore caricamento Qwen3-TTS: {e}")
        _tts_model = None
        _tts_ready.set()
        return

    import tempfile, soundfile as sf
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
            text, spk, lang, inst = task["text"], task["speaker"], task["language"], task["instruct"]
            results = list(_tts_model.generate_custom_voice(text=text, speaker=spk, language=lang, instruct=inst))
            audio = results[0].audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_path = f.name
            sf.write(output_path, np.array(audio), 24000)
            with open(output_path, "rb") as f:
                data = f.read()
            os.unlink(output_path)
            with _tts_lock:
                done = _tts_result[task_id].pop("done", None)
                _tts_result[task_id] = {"data": data, "content_type": "audio/wav", "error": None}
        except Exception as e:
            print(f"  [TTS Qwen3 Worker] fallito: {e}")
            with _tts_lock:
                done = _tts_result[task_id].pop("done", None)
                _tts_result[task_id] = {"data": None, "content_type": None, "error": str(e)}
        if done:
            done.set()
        _tts_event.clear()

def load_qwen3_model_safe():
    global _tts_worker_thread
    _tts_worker_thread = threading.Thread(target=_tts_worker, daemon=True, name="qwen3-tts-worker")
    _tts_worker_thread.start()
    if _tts_ready.wait(timeout=60):
        return _tts_model is not None
    return False

def _qwen3_generate(text, voice="vivian", language="italian"):
    global _tts_queue, _tts_result
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
    done = threading.Event()
    with _tts_lock:
        _tts_queue = task_id
        _tts_result[task_id] = {"task": {"text": text, "speaker": spk, "language": lang, "instruct": inst}, "done": done}
    _tts_event.set()
    if done.wait(timeout=20):
        with _tts_lock:
            result = _tts_result.get(task_id)
        if result and "data" in result:
            return result["data"], result["content_type"], result["error"]
    return None, None, "timeout"

def _generate_tts_chunk(text, voice="vivian", language="italian", speed=1.0):
    import tempfile, subprocess
    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    clean = re.sub(r'\*(.+?)\*', r'\1', clean)
    clean = re.sub(r'`(.+?)`', r'\1', clean)
    clean = re.sub(r'#{1,6}\s*', '', clean)
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean).strip()
    if not clean:
        return None, None
    try:
        if _tts_model is None:
            raise Exception("Modello Qwen3-TTS non disponibile")
        import tempfile, soundfile as sf
        data, ct, err = _qwen3_generate(clean, voice=voice, language=language)
        if data is not None:
            return data, ct
        raise Exception(err or "Qwen3-TTS returned no data")
    except Exception as e:
        print(f"  [TTS Qwen3] fallito: {e}")
        try:
            import asyncio, edge_tts
            tts_voice = VOICE_MAP.get(voice, "it-IT-ElsaNeural")
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
            return data, "audio/mpeg"
        except Exception as e:
            print(f"  [TTS Edge] fallito: {e}")
            return None, None

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

memory.db.execute("PRAGMA journal_mode=WAL")
memory.db.execute("PRAGMA busy_timeout=5000")

# ── Lifespan ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    if cfg["tts"].get("qwen3_enabled", True):
        load_qwen3_model_safe()
    else:
        _tts_ready.set()
    _rag_docs_dir = Path(__file__).parent / "data" / "documents"
    if _rag_docs_dir.exists():
        any_files = any(_rag_docs_dir.iterdir())
        if any_files:
            rag_st = rag.stats()
            if rag_st["documents"] == 0:
                rag.add_folder(str(_rag_docs_dir), recursive=True)
    try:
        from wav2lip_run import prepare_face
        face_path = os.path.join(os.path.dirname(__file__), "holographic_avatar.png")
        if os.path.exists(face_path):
            prepare_face(face_path)
    except:
        pass
    if cfg.get("telegram", {}).get("enabled", False) and cfg.get("telegram", {}).get("bot_token", ""):
        try:
            telegram_start()
        except:
            pass
    try:
        from jarvis_video_analytics import start_analytics
        start_analytics()
    except:
        pass
    try:
        _ensure_wa_webhook()
    except:
        pass
    yield
    _tts_stop.set()
    _tts_event.set()
    if _tts_worker_thread:
        _tts_worker_thread.join(timeout=3)

app = FastAPI(
    title="J.A.R.V.I.S API",
    description="Just A Rather Very Intelligent System — Cyberpunk AI Assistant",
    version="11.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state_lock = threading.Lock()

# ── Helpers ──

def _run(cmd, timeout=5):
    import subprocess
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception:
        return "error"

_sysinfo_cache = {"data": None, "time": 0}
_sysinfo_lock = threading.Lock()

_sysinfo_brief_cache = {"data": None, "time": 0}

def sysinfo():
    now = time.time()
    if _sysinfo_brief_cache["data"] and (now - _sysinfo_brief_cache["time"]) < 5:
        return _sysinfo_brief_cache["data"]
    r = {
        "battery": _run("pmset -g batt | grep -o '[0-9]*%' | head -1", 3) or "N/A",
        "cpu":     _run("top -l 1 -n 0 | grep 'CPU usage' | awk '{print $3}'", 3) or "N/A",
        "ram":     _run("memory_pressure | grep 'System-wide memory free percentage'", 3) or "N/A",
        "disk":    _run("df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'", 3) or "N/A",
        "ip":      _run("ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1", 3) or "N/A",
        "uptime":  _run("uptime | awk -F'up ' '{print $2}' | awk -F',' '{print $1}'", 3) or "N/A",
        "hostname":_run("hostname", 3) or "N/A",
        "model":   _run("sysctl -n hw.model", 3) or "N/A",
    }
    _sysinfo_brief_cache["data"] = r
    _sysinfo_brief_cache["time"] = now
    return r

def sysinfo_detailed():
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
        except:
            pass
        _sysinfo_cache["data"] = r
        _sysinfo_cache["time"] = now
        return r

# ── Static Files ──

STATIC_DIR = Path(__file__).parent
FRONTEND_DIST = STATIC_DIR / "dist" / "frontend"

# Serve assets from project root (style.css, app.js, avatar3d.js, worldnews.js)
# Vite-built assets (index-xxxxx.js) are also served here since they land in dist/frontend/assets/
# and we copy them to the project assets dir on build
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
app.mount("/pages", StaticFiles(directory=str(STATIC_DIR / "pages")), name="pages")
app.mount("/data/downloads", StaticFiles(directory=str(STATIC_DIR / "data" / "downloads")), name="downloads")

# ── API Routes ──

# ── Status & System ──

@app.get("/api/status")
async def api_status():
    rag_st = rag.stats()
    return {
        "status": "online",
        "model": cfg["groq"]["model"],
        "voice": cfg["tts"].get("qwen3_voice", cfg["tts"].get("voice", "vivian")),
        "version": "11.0",
        "rag": {"docs": rag_st["documents"], "chunks": rag_st["chunks"], "model": rag_st["model"]},
        "time": datetime.now().isoformat(),
    }

@app.get("/api/sysinfo")
async def api_sysinfo():
    return sysinfo()

@app.get("/api/sysinfo/detailed")
async def api_sysinfo_detailed():
    return sysinfo_detailed()

@app.get("/api/models")
async def api_models():
    return {"models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                       "llama3-70b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"]}

@app.get("/api/tools")
async def api_tools():
    return {"tools": [t["function"]["name"] for t in TOOLS_SCHEMA], "count": len(TOOLS_SCHEMA)}

@app.post("/api/reset")
async def api_reset():
    with state_lock:
        agent.reset()
    return {"status": "ok"}

@app.post("/api/config/update")
async def api_config_update(body: ConfigUpdate):
    with state_lock:
        if body.model:
            cfg["groq"]["model"] = body.model
            agent.cfg["groq"]["model"] = body.model
        if body.voice:
            cfg["tts"]["voice"] = body.voice
            cfg["tts"]["qwen3_voice"] = body.voice
        if body.temperature is not None:
            cfg["groq"]["temperature"] = body.temperature
        if body.speed is not None:
            cfg["tts"]["speed"] = body.speed
        if body.qwen3_voice:
            cfg["tts"]["qwen3_voice"] = body.qwen3_voice
            cfg["tts"]["voice"] = body.qwen3_voice
        if body.qwen3_language:
            cfg["tts"]["qwen3_language"] = body.qwen3_language
    return {"status": "ok"}

# ── Chat ──

@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    msg = body.message.strip()
    if not msg:
        raise HTTPException(400, "Messaggio vuoto")
    with state_lock:
        if body.model:
            cfg["groq"]["model"] = body.model
            agent.cfg["groq"]["model"] = body.model
        if body.temperature is not None:
            cfg["groq"]["temperature"] = body.temperature
    t0 = time.time()
    try:
        from jarvis_agent import _detect_complexity, FAST_MODEL
        chosen = _detect_complexity(msg) or cfg["groq"]["model"]
        reply, actions = agent.chat(msg)
        return {
            "reply": reply, "actions": actions,
            "elapsed": round(time.time() - t0, 2),
            "model": chosen, "fast": chosen == FAST_MODEL,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

@app.post("/api/chat/stream")
async def api_chat_stream(body: ChatRequest):
    msg = body.message.strip()
    if not msg:
        raise HTTPException(400, "Messaggio vuoto")
    with state_lock:
        if body.model:
            cfg["groq"]["model"] = body.model
            agent.cfg["groq"]["model"] = body.model
        if body.temperature is not None:
            cfg["groq"]["temperature"] = body.temperature

    async def event_stream():
        try:
            actions = agent._detect_direct_actions(msg)
            if actions:
                yield f"data: {json.dumps({'type': 'actions', 'data': actions})}\n\n"
                speech = next((a[7:] for a in actions if a.startswith('SPEECH:')), None)
                memory.log_conversation("user", msg)
                memory.log_conversation("assistant", speech or "OK")
                yield f"data: {json.dumps({'type': 'reply', 'data': speech or '', 'elapsed': 0, 'model': 'direct'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            reply, elapsed = agent.chat_stream(msg)
            yield f"data: {json.dumps({'type': 'reply', 'data': reply, 'elapsed': elapsed, 'model': cfg['groq']['model']})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
            traceback.print_exc()

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

@app.post("/api/chat/voice")
async def api_chat_voice(body: ChatVoiceRequest):
    msg = body.message.strip()
    if not msg:
        raise HTTPException(400, "Messaggio vuoto")

    async def event_stream():
        try:
            actions = agent._detect_direct_actions(msg)
            if actions:
                yield f"data: {json.dumps({'type': 'actions', 'data': actions})}\n\n"
                speech = next((a[7:] for a in actions if a.startswith('SPEECH:')), None)
                if speech:
                    try:
                        import asyncio, edge_tts, tempfile
                        tts_v = VOICE_MAP.get(body.voice, "it-IT-ElsaNeural")
                        async def _qk():
                            comm = edge_tts.Communicate(speech, tts_v)
                            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                                p = f.name
                            await comm.save(p)
                            return p
                        p = await _qk()
                        with open(p, "rb") as f:
                            aud = f.read()
                        os.unlink(p)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'data': base64.b64encode(aud).decode(), 'format': 'mp3'})}\n\n"
                    except Exception as _e:
                        print(f"[TTS quick] {_e}")
                memory.log_conversation("user", msg)
                memory.log_conversation("assistant", speech or "OK")
                yield f"data: {json.dumps({'type': 'reply', 'data': speech or '', 'elapsed': 0, 'model': 'direct'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            t0 = time.time()
            reply, actions = agent.chat_stream(msg)
            elapsed = time.time() - t0
            yield f"data: {json.dumps({'type': 'reply', 'data': reply, 'elapsed': elapsed, 'model': 'agentic'})}\n\n"

            if reply and not reply.startswith("[Errore"):
                import asyncio, edge_tts, tempfile
                tts_voice = VOICE_MAP.get(body.voice, "it-IT-ElsaNeural")
                rate = f"+{int((body.speed-1)*100)}%"
                try:
                    comm = edge_tts.Communicate(reply[:500], tts_voice, rate=rate)
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        p = f.name
                    await comm.save(p)
                    with open(p, "rb") as f:
                        audio_data = f.read()
                    os.unlink(p)
                    yield f"data: {json.dumps({'type': 'audio_chunk', 'data': base64.b64encode(audio_data).decode(), 'format': 'mp3'})}\n\n"
                except Exception as e:
                    print(f"  [Voice TTS] Error: {e}")

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
            traceback.print_exc()

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

# ── Tool ──

@app.post("/api/tool")
async def api_tool(body: ToolRequest):
    if not body.name:
        raise HTTPException(400, "Nome tool mancante")
    return {"result": execute_tool(body.name, body.args), "tool": body.name}

# ── Translate ──

@app.post("/api/translate")
async def api_translate(body: TranslateRequest):
    if not body.text:
        raise HTTPException(400, "Testo vuoto")
    t0 = time.time()
    translated = None
    lang_map = {"italian": "it", "english": "en", "french": "fr", "german": "de", "spanish": "es"}
    src_lang = lang_map.get(body.source, "en")
    tgt_lang = lang_map.get(body.target, "it")
    try:
        if _HAVE_DEEP:
            r = _GTrans(source=src_lang, target=tgt_lang).translate(body.text[:500])
            if r and r.strip() and r.strip() != body.text[:2000]:
                translated = r.strip()
    except Exception:
        pass
    if not translated:
        try:
            from jarvis_agent import GROQ_URL
            import requests
            payload = {
                "model": cfg["groq"]["model"],
                "messages": [
                    {"role": "system", "content": f"Sei un traduttore professionista. Traduci il seguente testo da {body.source} a {body.target}. Restituisci SOLO la traduzione, nient'altro."},
                    {"role": "user", "content": body.text[:2000]},
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
            }
            headers = {"Authorization": f"Bearer {cfg['groq']['api_key']}", "Content-Type": "application/json"}
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=10)
            r = resp.json()["choices"][0]["message"]["content"].strip()
            if r:
                translated = r
        except:
            pass
    if translated:
        return {"translated": translated, "elapsed": round(time.time() - t0, 2)}
    return {"translated": body.text, "note": "traduzione non disponibile"}

# ── TTS ──

@app.post("/api/tts")
async def api_tts(body: TTSRequest):
    if not body.text:
        raise HTTPException(400, "Testo vuoto")
    t0 = time.time()
    data, content_type = _generate_tts_chunk(body.text, voice=body.voice, language=body.language, speed=body.speed)
    if data is None:
        try:
            import subprocess
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', body.text)
            clean = re.sub(r'\*(.+?)\*', r'\1', clean)
            clean = re.sub(r'`(.+?)`', r'\1', clean)
            clean = re.sub(r'#{1,6}\s*', '', clean)
            clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean).strip()
            subprocess.run(["say", "-v", "Alice", clean[:200]], capture_output=True)
            return {"status": "played_via_say", "warning": "TTS fallback, usato macOS say"}
        except Exception as e:
            raise HTTPException(500, f"TTS fallito: {e}")
    ct = "audio/wav" if content_type == "audio/wav" else "audio/mpeg"
    return Response(content=data, media_type=ct, headers={
        "Content-Disposition": "inline",
        "Content-Length": str(len(data)),
    })

@app.post("/api/wav2lip")
async def api_wav2lip(body: TTSRequest):
    if not body.text:
        raise HTTPException(400, "Testo vuoto")
    t0 = time.time()
    tts_data, _ = _generate_tts_chunk(body.text, voice=body.voice, language=body.language)
    if tts_data is None:
        raise HTTPException(500, "TTS fallito")
    audio_path = "/tmp/wav2lip_input.wav"
    with open(audio_path, "wb") as f:
        f.write(tts_data)
    out_path = f"/tmp/wav2lip_{int(time.time())}.mp4"
    try:
        from wav2lip_run import run as wav2lip_run
        face_path = os.path.join(os.path.dirname(__file__), "holographic_avatar.png")
        wav2lip_run(face_path, audio_path, out_path, fps=20)
    except Exception as e:
        os.unlink(audio_path)
        raise HTTPException(500, f"Wav2Lip: {e}")
    with open(out_path, "rb") as f:
        video_data = f.read()
    os.unlink(out_path)
    os.unlink(audio_path)
    return Response(content=video_data, media_type="video/mp4")

# ── Memory ──

@app.get("/api/memory/stats")
async def api_memory_stats():
    return memory.stats()

@app.get("/api/memory/preferences")
async def api_memory_preferences():
    return memory.get_all_preferences()

@app.get("/api/memory/recent")
async def api_memory_recent():
    return {"conversations": memory.get_recent_conversations(10)}

@app.get("/api/memory/all")
async def api_memory_all():
    items = memory.get_all(limit=200)
    return {"memories": items, "total": len(items)}

@app.post("/api/memory/remember")
async def api_memory_remember(body: MemoryRequest):
    if not body.content:
        raise HTTPException(400, "Contenuto mancante")
    result = memory.remember(body.content, body.category, body.tags)
    return {"result": result}

@app.post("/api/memory/search")
async def api_memory_search(body: MemorySearch):
    if not body.query:
        raise HTTPException(400, "Query mancante")
    results = memory.search(body.query)
    return {"results": results}

@app.post("/api/memory/preference")
async def api_memory_preference(body: PreferenceRequest):
    if not body.key:
        raise HTTPException(400, "Key mancante")
    result = memory.set_preference(body.key, body.value)
    return {"result": result}

@app.post("/api/memory/delete")
async def api_memory_delete(body: MemoryDelete):
    if body.id is None:
        raise HTTPException(400, "ID mancante")
    result = memory.delete_memory(int(body.id))
    return {"result": result}

@app.post("/api/memory/update")
async def api_memory_update(body: MemoryUpdate):
    if not body.content:
        raise HTTPException(400, "ID e content richiesti")
    c = memory.db.cursor()
    c.execute("UPDATE memories SET content=?, updated_at=datetime('now') WHERE id=?", (body.content, int(body.id)))
    memory.db.commit()
    return {"result": f"Memoria {body.id} aggiornata"}

@app.get("/api/memory/graph")
async def api_memory_graph():
    if agent:
        return agent.graph.get_stats()
    return {"entities": 0, "relations": 0}

# ── Calendar ──

@app.get("/api/calendar/today")
async def api_calendar_today():
    from jarvis_calendar import get_today_events
    return {"events": get_today_events()}

@app.post("/api/calendar/create")
async def api_calendar_create(body: CalendarCreate):
    if not body.title:
        raise HTTPException(400, "Titolo mancante")
    from jarvis_calendar import create_event
    result = create_event(body.title, body.start_date, body.duration_minutes)
    return {"result": result}

# ── Notes ──

@app.post("/api/notes/create")
async def api_notes_create(body: NotesCreate):
    if not body.title:
        raise HTTPException(400, "Titolo mancante")
    from jarvis_notes import create_note
    result = create_note(body.title, body.body)
    return {"result": result}

# ── Mail ──

@app.get("/api/mail/unread")
async def api_mail_unread():
    from jarvis_mail import get_unread_count, parse_unread_count
    count_text = get_unread_count()
    count_num = parse_unread_count(count_text)
    return {"unread": count_text, "count": count_num}

@app.get("/api/mail/recent")
async def api_mail_recent():
    from jarvis_mail import get_recent_emails, format_emails_for_speech
    emails_data = get_recent_emails()
    speech_text = format_emails_for_speech(emails_data)
    return {"emails": emails_data, "emails_text": speech_text}

# ── Planner ──

@app.get("/api/plans")
async def api_plans():
    from jarvis_planner import get_active_plans
    return {"plans": get_active_plans()}

@app.post("/api/plan/create")
async def api_plan_create(body: PlanCreate):
    if not body.title:
        raise HTTPException(400, "Titolo mancante")
    from jarvis_planner import create_plan
    result = create_plan(body.title, body.steps, body.priority)
    return {"result": result}

# ── Conversations ──

@app.get("/api/conversations")
async def api_conversations():
    convs = memory.get_all(limit=50)
    return {"conversations": convs}

# ── Git ──

@app.get("/api/git/status")
async def api_git_status():
    from jarvis_git import git_status
    return {"result": git_status()}

@app.get("/api/git/branches")
async def api_git_branches():
    from jarvis_git import git_branches
    return {"result": git_branches()}

@app.get("/api/git/log")
async def api_git_log():
    from jarvis_git import git_log
    return {"result": git_log()}

@app.post("/api/git/command")
async def api_git_command(body: GitCommand):
    if not body.command:
        raise HTTPException(400, "Command mancante")
    from jarvis_git import git_execute
    result = git_execute(body.command)
    return {"result": result}

# ── Screen ──

@app.get("/api/screen/summary")
async def api_screen_summary():
    return {"summary": screen_awareness_summary()}

@app.get("/api/screen/selected")
async def api_screen_selected():
    return {"text": get_selected_text()}

@app.post("/api/screen/ocr")
async def api_screen_ocr(body: VisionAnalyze):
    result = ocr_screenshot(body.image_path if body.image_path else None)
    return {"result": result}

# ── Browser ──

@app.post("/api/browser/navigate")
async def api_browser_navigate(body: BrowserNavigate):
    if not body.url:
        raise HTTPException(400, "URL mancante")
    result = playwright_navigate(body.url)
    return {"result": result}

@app.post("/api/browser/extract")
async def api_browser_extract(body: BrowserExtract):
    if not body.url:
        raise HTTPException(400, "URL mancante")
    result = playwright_extract(body.url, body.selector)
    return {"result": result}

@app.post("/api/browser/screenshot")
async def api_browser_screenshot(body: BrowserScreenshot):
    if not body.url:
        raise HTTPException(400, "URL mancante")
    result = playwright_screenshot(body.url, body.save_path if body.save_path else None)
    return {"result": result}

# ── Web Search ──

@app.post("/api/web/search")
async def api_web_search(body: WebSearch):
    if not body.query:
        raise HTTPException(400, "Query mancante")
    from jarvis_tools import web_search_ddg
    results = web_search_ddg(body.query)
    return {"results": results}

# ── Computer Use ──

@app.get("/api/computer/mouse")
async def api_computer_mouse():
    return {"position": get_mouse_position(), "resolution": get_screen_resolution()}

@app.post("/api/computer/action")
async def api_computer_action(body: ComputerAction):
    if not body.action:
        raise HTTPException(400, "Azione mancante")
    result = computer_use_action(body.action)
    return {"result": result}

# ── RAG ──

@app.get("/api/rag/list")
async def api_rag_list():
    return {"documents": rag.list_documents()}

@app.get("/api/rag/stats")
async def api_rag_stats():
    return rag.stats()

@app.get("/api/rag/document")
async def api_rag_document(id: int = Query(0)):
    if not id:
        raise HTTPException(400, "Parametro 'id' mancante")
    return rag.get_document(id)

@app.post("/api/rag/add")
async def api_rag_add(body: RAGAddRequest):
    if not body.title or not body.content:
        raise HTTPException(400, "Title e content richiesti")
    result = rag.add_document(body.title, body.content, body.source)
    return {"result": result}

@app.post("/api/rag/add_file")
async def api_rag_add_file(body: RAGAddFile):
    if not body.file_path:
        raise HTTPException(400, "File path mancante")
    result = rag.add_file(body.file_path)
    return {"result": result}

@app.post("/api/rag/search")
async def api_rag_search(body: RAGSearch):
    if not body.query:
        raise HTTPException(400, "Query mancante")
    results = rag.search(body.query, body.limit)
    return {"results": results}

@app.post("/api/rag/semantic_search")
async def api_rag_semantic_search(body: RAGSearch):
    if not body.query:
        raise HTTPException(400, "Query mancante")
    results = rag.semantic_search(body.query, body.limit)
    return {"results": results}

@app.post("/api/rag/delete")
async def api_rag_delete(body: RAGDelete):
    if not body.doc_id:
        raise HTTPException(400, "Doc ID mancante")
    result = rag.delete_document(body.doc_id)
    return {"result": result}

@app.post("/api/rag/delete_all")
async def api_rag_delete_all():
    result = rag.delete_all()
    return {"result": result}

@app.post("/api/rag/add_folder")
async def api_rag_add_folder(body: RAGAddFolder):
    if not body.folder_path:
        raise HTTPException(400, "folder_path mancante")
    result = rag.add_folder(body.folder_path, body.recursive)
    return {"result": result}

@app.post("/api/rag/add_folder_stream")
async def api_rag_add_folder_stream(body: RAGAddFolder):
    if not body.folder_path:
        raise HTTPException(400, "folder_path mancante")

    async def event_stream():
        def on_progress(current, total, file_name, status):
            pct = round(current / total * 100, 1) if total > 0 else 0
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                lambda: None  # We handle this via the synchronous generator
            )

        result = rag.add_folder(body.folder_path, body.recursive)
        yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/api/rag/ingest")
async def api_rag_ingest():
    from jarvis_rag import DOCS_DIR
    results = []
    for folder in [str(DOCS_DIR), str(Path(__file__).parent / "data")]:
        if Path(folder).exists():
            r = rag.add_folder(folder, recursive=True)
            results.append({"folder": folder, **r})
    return {"results": results}

@app.post("/api/rag/update")
async def api_rag_update(body: RAGUpdate):
    if not body.doc_id:
        raise HTTPException(400, "doc_id mancante")
    result = rag.update_document(
        body.doc_id,
        title=body.title,
        content=body.content,
        source=body.source,
        metadata=body.metadata,
    )
    return {"result": result}

@app.post("/api/rag/reembed")
async def api_rag_reembed():
    async def event_stream():
        result = rag.reembed_all()
        yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/api/rag/search_by_source")
async def api_rag_search_by_source(body: RAGSearchBySource):
    if not body.query:
        raise HTTPException(400, "query mancante")
    return {"documents": rag.search_by_source(body.query, body.limit)}

@app.get("/api/rag/export")
async def api_rag_export():
    return rag.export_json()

@app.post("/api/rag/dedup")
async def api_rag_dedup(body: RAGDedup):
    result = rag.deduplicate(body.threshold)
    return {"result": result}

# ── Approval ──

@app.get("/api/approval/pending")
async def api_approval_pending():
    return {"pending": approval.get_pending()}

@app.get("/api/approval/all")
async def api_approval_all():
    return {"requests": approval.get_all_requests()}

@app.post("/api/approval/approve")
async def api_approval_approve(body: ApprovalAction):
    if not body.request_id:
        raise HTTPException(400, "Request ID mancante")
    result = approval.approve(body.request_id, body.auto_future)
    return {"approved": result, "request_id": body.request_id}

@app.post("/api/approval/deny")
async def api_approval_deny(body: ApprovalDeny):
    if not body.request_id:
        raise HTTPException(400, "Request ID mancante")
    result = approval.deny(body.request_id)
    return {"denied": result, "request_id": body.request_id}

# ── Wake Word ──

@app.get("/api/wake/status")
async def api_wake_status():
    return {"wake": False}

@app.post("/api/wake/toggle")
async def api_wake_toggle():
    return {"wake": False, "message": "Wake word disattivato"}

# ── Trends ──

@app.get("/api/trends")
async def api_trends(category: str = "technology", region: str = "wt", max_results: int = 10):
    result = trends_search(category, region, max_results)
    return result

@app.post("/api/trends/search")
async def api_trends_search(body: TrendsSearch):
    if body.query:
        result = trends_search(body.query, body.region, body.max_results)
    else:
        result = trending_now(body.region)
    return result

# ── Telegram ──

@app.get("/api/telegram/status")
async def api_telegram_status():
    return telegram_status()

@app.post("/api/telegram/send")
async def api_telegram_send(body: TelegramSend):
    if not body.message:
        raise HTTPException(400, "Messaggio vuoto")
    result = telegram_send(body.chat_id if body.chat_id else None, body.message)
    return {"result": result}

# ── Image Generation (IONOS Hub) ──

@app.post("/api/imagegen/generate")
async def api_imagegen_generate(body: ImageGenRequest):
    if not body.prompt:
        raise HTTPException(400, "Prompt mancante")
    return _gen_image(body.prompt, body.model, body.size, body.n)

@app.get("/api/imagegen/models")
async def api_imagegen_models():
    return {"models": _list_img_models()}

# ── Music Generation (ACE-Step) ──

@app.post("/api/musicgen/generate")
async def api_musicgen_generate(body: MusicGenRequest):
    return _gen_music(body.prompt, body.duration, body.genre, body.temperature)

@app.get("/api/musicgen/genres")
async def api_musicgen_genres():
    return {"genres": _list_music_g()}

@app.get("/api/musicgen/status")
async def api_musicgen_status():
    return _music_st()

# ── Knowledge Graph (GitNexus) ──

@app.post("/api/kg/analyze")
async def api_kg_analyze(body: KGPathRequest):
    return _kg_repo(body.path if body.path else None)

@app.post("/api/kg/graph")
async def api_kg_graph(body: KGPathRequest):
    return _kg_graph(body.path if body.path else None)

@app.post("/api/kg/symbols")
async def api_kg_symbols(body: KGPathRequest):
    return _kg_syms(body.path if body.path else None)

@app.post("/api/kg/search")
async def api_kg_search(body: KGSearchRequest):
    if not body.query:
        raise HTTPException(400, "Query mancante")
    return _kg_srch(body.query, body.path if body.path else None)

@app.get("/api/kg/status")
async def api_kg_status():
    return _kg_st()

# ── World News ──

@app.get("/api/worldnews")
async def api_worldnews(max: int = Query(30, le=60)):
    from jarvis_worldnews import fetch_world_news
    data = fetch_world_news(max)
    return data

# ── Evolution ──

@app.get("/api/evolution/status")
async def api_evolution_status():
    try:
        return {"status": evol.get_status_summary(), "daily": evol.generate_daily_report(), "patterns": evol.analyze_patterns()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/evolution/heal")
async def api_evolution_heal():
    try:
        return {"results": evol.run_healing_check()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/evolution/report/daily")
async def api_evolution_daily():
    try:
        return evol.generate_daily_report()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/evolution/report/weekly")
async def api_evolution_weekly():
    try:
        return evol.generate_weekly_report()
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Vision ──

@app.get("/api/vision/analyze")
async def api_vision_analyze(image_path: str = ""):
    try:
        return vision.analyze_screenshot(image_path if image_path else None)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/vision/ocr")
async def api_vision_ocr(image_path: str = ""):
    try:
        return {"text": vision.read_text(image_path if image_path else None)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/vision/analyze")
async def api_vision_analyze_post(body: VisionAnalyze):
    return vision.analyze_screenshot(body.image_path if body.image_path else None)

@app.post("/api/vision/ocr")
async def api_vision_ocr_post(body: VisionAnalyze):
    return {"text": vision.read_text(body.image_path if body.image_path else None)}

@app.post("/api/vision/qr")
async def api_vision_qr(body: VisionAnalyze):
    return {"codes": vision.detect_qr(body.image_path if body.image_path else None)}

@app.post("/api/vision/describe")
async def api_vision_describe(body: VisionDescribe):
    if not body.image_path:
        raise HTTPException(400, "image_path required")
    return {"description": vision.describe_image(body.image_path)}

@app.post("/api/vision/region")
async def api_vision_region(body: VisionRegion):
    return vision.analyze_region(body.x, body.y, body.w, body.h)

# ── Voice ──

@app.get("/api/voice/list")
async def api_voice_list():
    try:
        return {"voices": voice.list_voices()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/voice/status")
async def api_voice_status():
    try:
        return {"current_voice": voice.current_voice, "available": list(voice.PLAYAI_VOICES.keys())}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/voice/say")
async def api_voice_say(body: VoiceSay):
    if not body.text:
        raise HTTPException(400, "Text required")
    v = body.voice or voice.current_voice
    return {"result": voice.say(body.text, v, body.speed)}

@app.post("/api/voice/set")
async def api_voice_set(body: VoiceSet):
    if not body.voice:
        raise HTTPException(400, "Voice required")
    return {"result": voice.set_voice(body.voice)}

# ── OS Control ──

@app.get("/api/os/windows")
async def api_os_windows():
    try:
        return {"windows": os_control.list_windows()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/os/apps")
async def api_os_apps():
    try:
        return {"apps": os_control.list_apps()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/os/system")
async def api_os_system(category: str = "SPHardwareDataType"):
    try:
        return {"info": os_control.system_profiler(category)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/os/focus")
async def api_os_focus(body: OSFocus):
    if not body.title:
        raise HTTPException(400, "Title required")
    return {"result": os_control.focus_window(body.title)}

@app.post("/api/os/move")
async def api_os_move(body: OSMove):
    return {"result": os_control.move_window(body.title, body.x, body.y, body.width, body.height)}

@app.post("/api/os/minimize")
async def api_os_minimize(body: OSMinMax):
    if not body.title:
        raise HTTPException(400, "Title required")
    return {"result": os_control.minimize_window(body.title)}

@app.post("/api/os/maximize")
async def api_os_maximize(body: OSMinMax):
    if not body.title:
        raise HTTPException(400, "Title required")
    return {"result": os_control.maximize_window(body.title)}

@app.post("/api/os/dock")
async def api_os_dock(body: OSDock):
    if body.action == "autohide":
        return {"result": os_control.dock_autohide(body.enabled if body.enabled is not None else True)}
    elif body.action == "position":
        return {"result": os_control.dock_position(body.position or "bottom")}
    raise HTTPException(400, "Invalid dock action")

@app.post("/api/os/wallpaper")
async def api_os_wallpaper(body: OSWallpaper):
    return {"result": os_control.set_wallpaper(body.image_path if body.image_path else None)}

@app.post("/api/os/screensaver")
async def api_os_screensaver():
    os_control.screensaver()
    return {"result": "Screensaver started"}

@app.post("/api/os/empty_trash")
async def api_os_empty_trash():
    return {"result": os_control.empty_trash()}

@app.post("/api/os/dark_mode")
async def api_os_dark_mode():
    return {"result": os_control.toggle_dark_mode()}

@app.post("/api/os/pref_pane")
async def api_os_pref_pane(body: OSPrefPane):
    if not body.pane:
        raise HTTPException(400, "Pane required")
    return {"result": os_control.open_pref_pane(body.pane)}

# ── Security ──

@app.get("/api/security/status")
async def api_security_status():
    try:
        return security.get_activity_report()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/rules")
async def api_security_rules():
    try:
        return {"rules": security.list_rules()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/audit")
async def api_security_audit(limit: int = 20):
    try:
        return {"audit": security.db.get_audit_log(limit)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/security/check")
async def api_security_check(body: SecurityCheck):
    if not body.command:
        raise HTTPException(400, "Command required")
    safe, reason, risk = security.check_command_safety(body.command)
    return {"safe": safe, "reason": reason, "risk": risk}

@app.post("/api/security/rule")
async def api_security_rule(body: SecurityRule):
    if body.action == "add":
        return {"result": security.add_permission_rule(body.pattern, body.level)}
    elif body.action == "remove":
        return {"result": security.remove_permission_rule(body.pattern)}
    raise HTTPException(400, "Invalid action")

# ── Pantheon ──

@app.get("/api/pantheon/agents")
async def api_pantheon_agents():
    try:
        return {"agents": pantheon.db.list_agents()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/pantheon/tasks")
async def api_pantheon_tasks(limit: int = 10):
    try:
        return {"tasks": pantheon.db.get_pending_tasks(limit=limit)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/pantheon/economy")
async def api_pantheon_economy():
    try:
        return {"economy": pantheon.economy_report()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/pantheon/register")
async def api_pantheon_register(body: PantheonRegister):
    if not body.name:
        raise HTTPException(400, "Name required")
    cl = [c.strip() for c in body.capabilities.split(",")] if body.capabilities else ["general"]
    return pantheon.register_agent(body.name, cl, body.endpoint)

@app.post("/api/pantheon/delegate")
async def api_pantheon_delegate(body: PantheonDelegate):
    if not body.description:
        raise HTTPException(400, "Description required")
    return pantheon.delegate(body.description, body.agent if body.agent else None)

@app.post("/api/pantheon/transfer")
async def api_pantheon_transfer(body: PantheonTransfer):
    if not body.from_agent or not body.to_agent:
        raise HTTPException(400, "from_agent and to_agent required")
    ok, msg = pantheon.db.transfer_credits(body.from_agent, body.to_agent, body.amount, body.reason)
    return {"success": ok, "message": msg}

@app.post("/api/pantheon/message")
async def api_pantheon_message(body: PantheonMessage):
    if not body.to_agent or not body.subject:
        raise HTTPException(400, "to_agent and subject required")
    return {"result": pantheon.send_message(body.to_agent, body.subject, body.body)}

@app.post("/api/pantheon/broadcast")
async def api_pantheon_broadcast(body: PantheonBroadcast):
    if not body.subject:
        raise HTTPException(400, "Subject required")
    return {"result": pantheon.broadcast(body.subject, body.body)}

@app.post("/api/pantheon/task/complete")
async def api_pantheon_task_complete(body: PantheonTaskComplete):
    if not body.task_id:
        raise HTTPException(400, "task_id required")
    return {"result": pantheon.complete_task(body.task_id, body.result, body.error)}

# ── Plugins ──

@app.get("/api/plugins/list")
async def api_plugins_list():
    try:
        return {"plugins": plugins.list_plugins()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/plugins/marketplace")
async def api_plugins_marketplace():
    try:
        return {"marketplace": plugins.marketplace_catalog()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/plugins/health")
async def api_plugins_health():
    try:
        return {"health": plugins.plugins_health()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/plugins/updates")
async def api_plugins_updates():
    try:
        return {"updates": plugins.check_updates()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/plugins/search")
async def api_plugins_search(q: str = ""):
    try:
        return {"results": plugins.search_marketplace(q)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/plugins/install")
async def api_plugins_install(body: PluginInstall):
    if not body.source:
        raise HTTPException(400, "Source required")
    return {"result": plugins.install(body.source, body.name)}

@app.post("/api/plugins/uninstall")
async def api_plugins_uninstall(body: PluginUninstall):
    if not body.name:
        raise HTTPException(400, "Name required")
    return {"result": plugins.uninstall(body.name)}

@app.post("/api/plugins/toggle")
async def api_plugins_toggle(body: PluginToggle):
    if not body.name:
        raise HTTPException(400, "Name required")
    if body.enable:
        return {"result": plugins.enable(body.name)}
    return {"result": plugins.disable(body.name)}

@app.post("/api/plugins/rate")
async def api_plugins_rate(body: PluginRate):
    if not body.name or not body.rating:
        raise HTTPException(400, "Name and rating required")
    return {"result": plugins.rate_plugin(body.name, body.rating, body.review)}

@app.post("/api/plugins/update_all")
async def api_plugins_update_all():
    return {"result": plugins.update_all()}

# ── Skills ──

@app.get("/api/skills/list")
async def api_skills_list():
    try:
        return {"skills": skills.list_skills()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/skills/stats")
async def api_skills_stats():
    try:
        return {"stats": skills.get_stats()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/skills/suggestions")
async def api_skills_suggestions():
    try:
        return {"suggestions": skills.get_suggestions()}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/skills/create")
async def api_skills_create(body: SkillCreate):
    if not body.name or not body.description:
        raise HTTPException(400, "Name and description required")
    result = skills.create_skill(body.name, body.description, body.category)
    return {"result": result}

@app.post("/api/skills/run")
async def api_skills_run(body: SkillRun):
    if not body.name:
        raise HTTPException(400, "Name required")
    return {"result": skills.run_skill(body.name, **body.args)}

@app.post("/api/skills/improve")
async def api_skills_improve(body: SkillImprove):
    if not body.name or not body.feedback:
        raise HTTPException(400, "Name and feedback required")
    return {"result": skills.improve_skill(body.name, body.feedback)}

@app.post("/api/skills/toggle")
async def api_skills_toggle(body: SkillName):
    if not body.name:
        raise HTTPException(400, "Name required")
    return {"result": skills.toggle_skill(body.name)}

@app.post("/api/skills/delete")
async def api_skills_delete(body: SkillName):
    if not body.name:
        raise HTTPException(400, "Name required")
    return {"result": skills.delete_skill(body.name)}

# ── Goals ──

@app.get("/api/goals")
async def api_goals():
    try:
        import jarvis_goals as g
        goals_data = g._load()
        return {"goals": goals_data}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/goals/create")
async def api_goals_create(body: GoalCreate):
    if not body.title:
        raise HTTPException(400, "Title required")
    import jarvis_goals as g
    return {"result": g.create_goal(body.title, body.description)}

@app.post("/api/goals/delete")
async def api_goals_delete(body: GoalDelete):
    import jarvis_goals as g
    return {"result": g.delete_goal(body.id)}

@app.post("/api/goals/add_kr")
async def api_goals_add_kr(body: GoalAddKR):
    import jarvis_goals as g
    return {"result": g.add_key_result(body.goal_id, body.title, body.target)}

@app.post("/api/goals/update_kr")
async def api_goals_update_kr(body: GoalUpdateKR):
    import jarvis_goals as g
    return {"result": g.update_key_result(body.goal_id, body.kr_id, body.current)}

# ── Providers ──

@app.get("/api/providers")
async def api_providers():
    try:
        import jarvis_providers as p
        raw = p.list_providers()
        data = {"providers": [], "current": ""}
        for line in raw.split("\n"):
            for name in ["groq", "ollama", "openai", "gemini", "anthropic"]:
                if line.startswith(name) or name in line:
                    if "OK" in line:
                        data["current"] = name
                    data["providers"].append(name)
                    break
        return data
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Presentation ──

@app.post("/api/presentation/create")
async def api_presentation_create(body: PresentationCreate):
    try:
        from jarvis_docs import docgen
        data = body.data if body.data else {}
        slides = body.slides
        if body.pptx:
            path, url = docgen.make_pptx(data, slides)
        elif body.presenton:
            path, url = docgen.make_presenton_html(data, slides, theme=body.theme)
        else:
            path, url = docgen.make_html_presentation(data, slides)
        return {"path": path, "url": url}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

@app.post("/api/presentation/auto")
async def api_presentation_auto(body: PresentationAuto):
    if not body.prompt:
        raise HTTPException(400, "Prompt mancante")
    try:
        from presenton_engine import generate_slides, get_vision_report_data
        import time

        vision_data = None
        if body.tone == "vision" or "vision" in body.prompt.lower() or "traffic" in body.prompt.lower() or "video analytics" in body.prompt.lower():
            vision_data = get_vision_report_data()

        slides_data = generate_slides(
            topic=body.prompt,
            n_slides=body.n_slides,
            language=body.language,
            tone=body.tone,
            instructions=body.instructions,
            vision_data=vision_data,
        )

        if not slides_data:
            words = [w for w in body.prompt.split() if len(w) > 3][:6]
            short = ', '.join(words) if words else body.prompt[:60]
            slides_data = [
                {"type": "title", "title": body.title or body.prompt[:80], "subtitle": f"Generata da J.A.R.V.I.S — {short}"},
                {"type": "content", "title": "Panoramica", "items": [
                    f"{body.title or body.prompt[:80]}: contesto e scenario di riferimento",
                    "Analisi dei fattori chiave", "Dati e statistiche del settore",
                    "Confronto con scenari alternativi", "Proiezioni e tendenze future",
                ]},
                {"type": "two_column", "title": "Aspetti Principali",
                 "col1_title": "Punti di Forza",
                 "columns": [["Innovazione", "Efficienza", "Scalabilit\u00e0"], ["Costi", "Rischi", "Complessita"]],
                 "col2_title": "Sfide"},
                {"type": "thank_you", "title": "Grazie!", "subtitle": "Domande?"},
            ]

        from jarvis_docs import docgen
        if body.format == "pptx":
            path, url = docgen.make_pptx({"title": body.title or body.prompt[:80], "theme": body.theme, "author": body.author}, slides_data)
        else:
            path, url = docgen.make_presenton_html({
                "title": body.title or body.prompt[:80], "theme": body.theme, "author": body.author,
                "language": body.language, "tone": body.tone, "n_slides": body.n_slides,
                "instructions": body.instructions,
            }, slides_data, theme=body.theme)

        return {"path": path, "url": url, "slides": slides_data}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

# ── Video Analytics ──

@app.get("/api/video/analytics/frame")
async def api_video_analytics_frame():
    from jarvis_video_analytics import get_analytics
    a = get_analytics()
    jpeg = a.get_jpeg()
    if jpeg:
        return Response(content=jpeg, media_type="image/jpeg")
    import cv2
    blank = cv2.imencode(".jpg", 255 * np.ones((480, 640, 3), dtype=np.uint8))[1].tobytes()
    return Response(content=blank, media_type="image/jpeg")

@app.get("/api/video/analytics/status")
async def api_video_analytics_status():
    from jarvis_video_analytics import get_status
    return get_status()

@app.get("/api/video/analytics/counts")
async def api_video_analytics_counts(hours: int = 1):
    from jarvis_video_analytics import get_counts
    return get_counts(hours)

@app.post("/api/video/analytics/reset")
async def api_video_analytics_reset():
    from jarvis_video_analytics import reset_history
    return {"result": reset_history()}

@app.post("/api/video/analytics/start")
async def api_video_analytics_start(body: VideoAnalyticsStart):
    from jarvis_video_analytics import start_analytics
    return {"result": start_analytics(body.stream_url)}

@app.post("/api/video/analytics/stop")
async def api_video_analytics_stop():
    from jarvis_video_analytics import stop_analytics
    return {"result": stop_analytics()}

@app.post("/api/video/analytics/calibrate")
async def api_video_analytics_calibrate(body: VideoAnalyticsCalibrate):
    from jarvis_video_analytics import set_calibration
    return {"result": set_calibration(body.value)}

# ── WhatsApp (OpenWA) ──

_wa_webhook_url = "http://127.0.0.1:9999/api/whatsapp/webhook"

def _ensure_wa_webhook():
    """Registra il webhook su OpenWA se non già presente (es. dopo restart sessione)"""
    try:
        st = _wa_status()
        if not isinstance(st, dict) or not st.get("openwa_available"):
            return
        sid = st.get("session_id", "")
        if not sid:
            return
        WA_KEY = None
        for _kp in [
            os.path.expanduser("~/OpenWA/data/.api-key"),
            "/Users/daniele/OpenWA/data/.api-key",
        ]:
            if os.path.exists(_kp):
                WA_KEY = Path(_kp).read_text().strip()
                break
        if not WA_KEY:
            return
        import urllib.request, json as _json
        h = {"X-API-Key": WA_KEY, "Content-Type": "application/json"}
        req = urllib.request.Request(
            f"{OPENWA_URL}/api/sessions/{sid}/webhooks",
            headers=h,
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            existing = _json.loads(resp.read())
            if isinstance(existing, list) and any(w.get("url") == _wa_webhook_url for w in existing):
                return
        body = _json.dumps({"url": _wa_webhook_url, "events": ["message.received"]}).encode()
        req2 = urllib.request.Request(
            f"{OPENWA_URL}/api/sessions/{sid}/webhooks",
            data=body,
            headers=h,
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5):
            pass
    except Exception as e:
        logger.warning(f"[WA] Webhook auto-registration skipped: {e}")

@app.get("/api/whatsapp/status")
async def api_whatsapp_status():
    return _wa_status()

@app.post("/api/whatsapp/ensure")
async def api_whatsapp_ensure():
    result = _wa_ensure()
    if result.get("status") == "ready":
        _ensure_wa_webhook()
    return result

@app.post("/api/whatsapp/send")
async def api_whatsapp_send(body: WhatsAppSendRequest):
    global _wa_recent_ids
    result = _wa_send(body.to, body.text)
    if isinstance(result, dict) and result.get("ok") and isinstance(result.get("data"), dict):
        sent_id = result["data"].get("messageId")
        if sent_id:
            _wa_recent_ids[sent_id] = time.time()
    return result

@app.post("/api/whatsapp/send-image")
async def api_whatsapp_send_image(body: WhatsAppSendImageRequest):
    global _wa_recent_ids
    result = _wa_send_img(body.to, body.url, body.caption or "")
    if isinstance(result, dict) and result.get("ok") and isinstance(result.get("data"), dict):
        sent_id = result["data"].get("messageId")
        if sent_id:
            _wa_recent_ids[sent_id] = time.time()
    return result

_wa_recent_ids: dict[str, float] = {}  # msg_id -> timestamp, per evitare loop

def _process_wa_message(chat_id: str, msg_text: str, is_voice: bool = False):
    """Processa messaggio WhatsApp in background (thread separato)"""
    global _wa_recent_ids
    try:
        # Diamo contesto WhatsApp all'agente così sa di dover usare i tool WhatsApp
        wa_context = f"[WhatsApp - Gruppo Jarvis] {msg_text}"
        reply = agent.chat(wa_context)
        if isinstance(reply, tuple):
            reply = reply[0]
        reply_text = f"🤖 {reply.strip()}" if isinstance(reply, str) else f"🤖 {str(reply)}"

        if is_voice:
            try:
                import edge_tts, tempfile, base64 as b64, subprocess as _sp
                tts = edge_tts.Communicate(reply_text[:500], voice="it-IT-ElsaNeural")
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp.close()
                    tts.save(tmp.name)
                    mp3_path = tmp.name
                # Converti MP3 → OGG/Opus per compatibilità WhatsApp
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp2:
                    tmp2.close()
                    ogg_path = tmp2.name
                try:
                    _sp.run(["ffmpeg", "-y", "-i", mp3_path, "-c:a", "libopus", "-b:a", "24k", ogg_path],
                            capture_output=True, timeout=30, check=True)
                    with open(ogg_path, "rb") as f:
                        audio_b64 = b64.b64encode(f.read()).decode()
                except Exception as cv:
                    logger.warning(f"[WA] Conversione OGG fallita, uso MP3: {cv}")
                    with open(mp3_path, "rb") as f:
                        audio_b64 = b64.b64encode(f.read()).decode()
                finally:
                    os.unlink(mp3_path)
                    try:
                        os.unlink(ogg_path)
                    except:
                        pass
                result = _wa_send_audio(chat_id, audio_b64, "audio/ogg")
                if isinstance(result, dict):
                    if result.get("ok"):
                        sent_id = result.get("data", {}).get("messageId") if isinstance(result.get("data"), dict) else None
                        if sent_id:
                            _wa_recent_ids[sent_id] = time.time()
                        logger.info(f"[WA] Audio risposta inviata a {chat_id}: {reply_text[:60]}...")
                    else:
                        err_detail = result.get("error") or ""
                        if not err_detail and isinstance(result.get("data"), dict):
                            err_detail = str(result["data"].get("error", result["data"]))
                        elif not err_detail:
                            err_detail = str(result.get("data", ""))[:200]
                        logger.warning(f"[WA] Audio fallito: {err_detail or 'errore sconosciuto'} — fallback testo")
                        _wa_send(chat_id, reply_text[:4096])
                return
            except Exception as ae:
                logger.error(f"[WA] Audio fallito, testo fallback: {ae}")

        result = _wa_send(chat_id, reply_text[:4096])
        if isinstance(result, dict) and result.get("ok") and isinstance(result.get("data"), dict):
            sent_id = result["data"].get("messageId")
            if sent_id:
                _wa_recent_ids[sent_id] = time.time()
        logger.info(f"[WA] Risposta inviata a {chat_id}: {reply_text[:80]}...")
    except Exception as e:
        logger.error(f"[WA] Errore processamento messaggio: {e}")

@app.post("/api/whatsapp/webhook")
async def api_whatsapp_webhook(body: dict):
    """Riceve webhook da OpenWA quando arriva un messaggio WhatsApp (fire-and-forget)"""
    global _wa_recent_ids
    try:
        event = body.get("event", "")
        logger.info(f"[WA] Webhook received: event={event} body_keys={list(body.keys())}")
        if event == "message.received":
            data = body.get("data", {})
            msg_id = data.get("id", "")
            msg_text = (data.get("body") or "").strip()
            chat_id = data.get("chatId") or data.get("from", "")
            from_me = data.get("fromMe", False)
            is_group = data.get("isGroup", False)

            # Workaround: OpenWA a volte manda @lid come chatId invece del group ID
            jarvis_group_id = "120363407071302556@g.us"
            if msg_id.startswith(f"true_{jarvis_group_id}_"):
                chat_id = jarvis_group_id
                is_group = True

            sender_name = chat_id.split("@")[0]
            logger.info(f"[WA] msg_id={msg_id[:30]} chat={chat_id} from_me={from_me} is_group={is_group} text='{msg_text[:50]}'")

            # Dedup: salta messaggi inviati da noi (exact match su waMessageId)
            now = time.time()
            _wa_recent_ids = {k: v for k, v in _wa_recent_ids.items() if now - v < 30}
            if msg_id in _wa_recent_ids:
                logger.info(f"[WA] Dedup: {msg_id[:30]} saltato")
                return {"ok": True, "action": "dedup"}

            # Salta messaggi inviati dal bot che contengono media (immagini/audio/video)
            if from_me:
                media = data.get("media")
                if media and isinstance(media, dict) and media.get("data"):
                    logger.info(f"[WA] Ignorato from_me con media: {sender_name}")
                    return {"ok": True, "action": "ignored_from_me_media"}
                # Fuori dal gruppo, ignora anche i from_me senza media (testo del bot)
                if chat_id != jarvis_group_id:
                    logger.info(f"[WA] Ignorato from_me fuori dal gruppo: {sender_name}")
                    return {"ok": True, "action": "ignored_from_me"}

            # ── Voice message transcription ──
            was_voice = False
            media = data.get("media")
            if media and isinstance(media, dict):
                logger.info(f"[WA] Media keys: {list(media.keys())}, mimetype={media.get('mimetype','?')}, has_data={'data' in media}, has_url={'url' in media}")
                media_data = media.get("data") or ""
                media_url = media.get("url", "")
                mimetype = media.get("mimetype", "")
                msg_type = data.get("type", "")
                if msg_type == "ptt" or "audio" in mimetype:
                    import tempfile, urllib.request
                    ext = ".ogg"
                    if "mp4" in mimetype or "aac" in mimetype:
                        ext = ".m4a"
                    audio_bytes = b""
                    if media_data:
                        try:
                            audio_bytes = base64.b64decode(media_data)
                        except Exception as de:
                            logger.error(f"[WA] Errore decode base64: {de}")
                    elif media_url:
                        try:
                            with urllib.request.urlopen(media_url, timeout=15) as ru:
                                audio_bytes = ru.read()
                            logger.info(f"[WA] Audio scaricato da URL: {len(audio_bytes)} bytes")
                        except Exception as ue:
                            logger.error(f"[WA] Errore download audio da URL: {ue}")
                    if audio_bytes:
                        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                            tmp.write(audio_bytes)
                            audio_path = tmp.name
                        try:
                            from faster_whisper import WhisperModel
                            _whisper_model = getattr(api_whatsapp_webhook, "_whisper", None)
                            if _whisper_model is None:
                                _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
                                api_whatsapp_webhook._whisper = _whisper_model
                            segs, _ = _whisper_model.transcribe(audio_path, language="it", beam_size=1)
                            transcribed = " ".join(s.text.strip() for s in segs).strip()
                            logger.info(f"[WA] Trascrizione: {transcribed[:150]}")
                            if transcribed:
                                msg_text = transcribed
                                was_voice = True
                        except Exception as xe:
                            logger.error(f"[WA] Errore trascrizione: {xe}")
                        finally:
                            try:
                                os.unlink(audio_path)
                            except:
                                pass

            if not msg_text:
                logger.info(f"[WA] Messaggio vuoto ignorato")
                return {"ok": True, "action": "ignored_empty"}

            # Solo risposte automatiche a: gruppo Jarvis OPPURE Marco
            _marco_number = "393935434384"
            _sender_digits = re.sub(r"\D", "", sender_name)
            if _sender_digits != _marco_number and not is_group and chat_id != jarvis_group_id:
                logger.info(f"[WA] Ignorato: {sender_name} (non gruppo Jarvis né Marco)")
                return {"ok": True, "action": "ignored_not_authorized"}

            # Blocklist: numeri bloccati (in formato @c.us o @lid)
            _wa_blocked = {"65803361755387"}
            if _sender_digits in _wa_blocked:
                logger.info(f"[WA] Bloccato: {sender_name} (digits={_sender_digits})")
                return {"ok": True, "action": "blocked"}

            # Salta messaggi che iniziano con 🤖 (sono risposte del bot)
            if msg_text.startswith("🤖"):
                logger.info(f"[WA] Risposta del bot ignorata (🤖)")
                return {"ok": True, "action": "ignored_bot_reply"}

            logger.info(f"[WA] Da {sender_name} chat={chat_id} {'[GRUPPO]' if is_group else ''}: {msg_text[:100]}")

            # Processo in background: return immediato, evita timeout OpenWA
            import threading
            t = threading.Thread(target=_process_wa_message, args=(chat_id, msg_text), kwargs={"is_voice": was_voice}, daemon=True)
            t.start()
            return {"ok": True, "action": "accepted", "message": "Processing in background"}
        return {"ok": True, "action": f"event_{event}"}
    except Exception as e:
        logger.error(f"[WA] Webhook error: {e}")
        return {"ok": False, "error": str(e)}

# ── Export ──

@app.post("/api/export")
async def api_export(body: ExportRequest):
    convos = memory.get_recent_conversations(100)
    if body.format == "markdown":
        md = "# J.A.R.V.I.S Conversation Export\n\n"
        for c in convos:
            role = "Tu" if c["role"] == "user" else "JARVIS"
            md += f"### {role} — {c['timestamp']}\n\n{c['content']}\n\n---\n\n"
        return Response(content=md, media_type="text/markdown",
                        headers={"Content-Disposition": 'attachment; filename="jarvis_export.md"'})
    return {"conversations": convos}

# ── Static file routes (legacy support) ──

@app.get("/")
@app.get("/index.html")
async def serve_index():
    # Try new frontend build first
    new_p = FRONTEND_DIST / "index.html"
    if FRONTEND_DIST.exists() and new_p.exists():
        html = new_p.read_text("utf-8")
        # Inject legacy scripts that Vite can't bundle (worldnews.js)
        if '<script src="/assets/app.js"></script>' in html and '<script type="module" src="/assets/worldnews.js"></script>' not in html:
            html = html.replace('</body>', '  <script type="module" src="/assets/worldnews.js"></script>\n</body>')
        return HTMLResponse(html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    # Fallback to legacy
    p = STATIC_DIR / "index.html"
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(404, "index.html non trovato")

@app.get("/holographic_avatar.png")
async def serve_avatar():
    p = Path(__file__).parent / "holographic_avatar.png"
    if p.exists():
        return FileResponse(p, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(404, "avatar not found")

@app.get("/holographic_avatar_animated.mp4")
async def serve_avatar_animated():
    p = Path(__file__).parent / "holographic_avatar_animated.mp4"
    if p.exists():
        return FileResponse(p, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(404, "animated avatar not found")

@app.get("/waiting_neurons.mp4")
async def serve_waiting():
    p = Path(__file__).parent / "waiting_neurons.mp4"
    if p.exists():
        return FileResponse(p, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(404, "waiting video not found")

@app.get("/assets/avatar.glb")
async def serve_glb():
    p = Path(__file__).parent / "assets" / "avatar.glb"
    if p.exists():
        return FileResponse(p, media_type="model/gltf-binary",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(404, "avatar.glb not found")

@app.get("/api/image")
async def serve_image(file: str = Query("")):
    if not file:
        raise HTTPException(400, "Parametro 'file' mancante")
    import posixpath
    file_param = posixpath.basename(file)
    ALLOWED_DIRS = [Path("/tmp"), Path(__file__).parent / "output"]
    ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    for d in ALLOWED_DIRS:
        candidate = d / file_param
        if candidate.exists() and candidate.suffix.lower() in ALLOWED_EXT:
            ext_mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".gif": "image/gif", ".webp": "image/webp"}
            return FileResponse(candidate, media_type=ext_mime.get(candidate.suffix.lower(), "image/png"))
    raise HTTPException(404, f"Immagine non trovata: {file_param}")

# ── Video Analytics Stream (MJPEG) ──

@app.get("/api/video/analytics/stream")
async def api_video_analytics_stream():
    from jarvis_video_analytics import get_analytics
    import cv2

    async def generate():
        a = get_analytics()
        try:
            while True:
                jpeg = a.get_jpeg()
                if not jpeg:
                    blank = cv2.imencode(".jpg", 255 * np.ones((480, 640, 3), dtype=np.uint8))[1].tobytes()
                    jpeg = blank
                yield b"--frame\r\n"
                yield b"Content-Type: image/jpeg\r\n"
                yield f"Content-Length: {len(jpeg)}\r\n".encode()
                yield b"\r\n"
                yield jpeg
                yield b"\r\n"
                await asyncio.sleep(0.033)
        except:
            pass

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

# ── Main ──

if __name__ == "__main__":
    PORT = int(os.environ.get("JARVIS_PORT", 9999))
    HOST = os.environ.get("JARVIS_HOST", "0.0.0.0")
    print()
    print("=" * 52)
    print("  J.A.R.V.I.S  FASTAPI  v11.0 — CYBERPUNK EDITION")
    print("=" * 52)
    print(f"  URL   -> http://localhost:{PORT}")
    print(f"  DOCS  -> http://localhost:{PORT}/api/docs")
    print(f"  LLM   -> {cfg['groq']['model']}")
    print(f"  TTS   -> Qwen3-TTS (MLX) + Edge")
    print(f"  Voce  -> {cfg['tts'].get('qwen3_voice', 'vivian')}")
    print(f"  Tool  -> {len(TOOLS_SCHEMA)} disponibili")
    print("-" * 52)
    if cfg["groq"]["api_key"] == "YOUR_GROQ_API_KEY_HERE":
        print("  W  Groq API key mancante in config.json!")
        print()
    print("  Ctrl+C per fermare")
    print("-" * 52)
    print()
    sys.stdout.flush()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
