"""jarvis_whatsapp_openwa.py — WhatsApp integration via OpenWA (self-hosted API)"""
import json, os, time, threading, base64, re, requests, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OPENWA_URL = os.environ.get("OPENWA_URL", "http://localhost:2785")
OPENWA_SESSION = os.environ.get("OPENWA_SESSION", "jarvis")

# Auto-read API key from OpenWA data dir if not set via env
_api_key_env = os.environ.get("OPENWA_API_KEY", "")
if not _api_key_env:
    for _keypath in [
        os.path.expanduser("~/OpenWA/data/.api-key"),
        "/Users/daniele/OpenWA/data/.api-key",
    ]:
        if os.path.exists(_keypath):
            _api_key_env = Path(_keypath).read_text().strip()
            break
OPENWA_API_KEY = _api_key_env

_wa_available = False
_wa_session_ready = False
_wa_session_id = None
_wa_lock = threading.Lock()
_last_qr = None

def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if OPENWA_API_KEY:
        h["X-API-Key"] = OPENWA_API_KEY
    return h

def _api_get(path: str) -> dict:
    try:
        r = requests.get(f"{OPENWA_URL}{path}", headers=_headers(), timeout=10)
        return {"ok": r.ok, "status": r.status_code, "data": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _api_post(path: str, body: dict = None) -> dict:
    try:
        r = requests.post(f"{OPENWA_URL}{path}", headers=_headers(), json=body or {}, timeout=10)
        return {"ok": r.ok, "status": r.status_code, "data": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _api_delete(path: str) -> dict:
    try:
        r = requests.delete(f"{OPENWA_URL}{path}", headers=_headers(), timeout=10)
        return {"ok": r.ok, "status": r.status_code, "data": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _sid() -> str:
    global _wa_session_id
    if _wa_session_id:
        return _wa_session_id
    st = _api_get(f"/api/sessions")
    if st["ok"] and isinstance(st.get("data"), list):
        for s in st["data"]:
            if s.get("name") == OPENWA_SESSION:
                _wa_session_id = s["id"]
                return _wa_session_id
    return OPENWA_SESSION

def check_health() -> bool:
    global _wa_available
    try:
        r = requests.get(f"{OPENWA_URL}/api/health/live", timeout=5)
        _wa_available = r.status_code == 200
    except:
        _wa_available = False
    return _wa_available

def ensure_session() -> dict:
    global _wa_session_ready, _wa_session_id, _last_qr

    st = _api_get(f"/api/sessions")
    if st["ok"] and isinstance(st.get("data"), list):
        for s in st["data"]:
            if s.get("name") == OPENWA_SESSION:
                _wa_session_id = s["id"]
                status = s.get("status", "")
                if status == "ready":
                    _wa_session_ready = True
                    return {"ok": True, "status": "ready", "session_id": _wa_session_id}
                if status == "authenticating" or status == "initializing":
                    time.sleep(2)
                    st2 = _api_get(f"/api/sessions/{_wa_session_id}")
                    if st2["ok"] and isinstance(st2.get("data"), dict):
                        s2 = st2["data"]
                        if s2.get("status") == "ready":
                            _wa_session_ready = True
                            return {"ok": True, "status": "ready", "session_id": _wa_session_id}
                    return {"ok": True, "status": status, "session_id": _wa_session_id}
                break

    if not _wa_session_id:
        cr = _api_post("/api/sessions", {"name": OPENWA_SESSION})
        if cr["ok"] and isinstance(cr.get("data"), dict):
            _wa_session_id = cr["data"].get("id")
        else:
            return {"ok": False, "error": "Session creation failed"}

    st2 = _api_post(f"/api/sessions/{_wa_session_id}/start")
    if st2["ok"]:
        time.sleep(3)
        qr_resp = _api_get(f"/api/sessions/{_wa_session_id}/qr")
        if qr_resp["ok"] and isinstance(qr_resp.get("data"), dict) and "qrCode" in qr_resp["data"]:
            _last_qr = qr_resp["data"]["qrCode"]
            return {"ok": True, "status": "scan_qr", "qr": _last_qr, "session_id": _wa_session_id}
        st3 = _api_get(f"/api/sessions/{_wa_session_id}")
        if st3["ok"] and isinstance(st3.get("data"), dict) and st3["data"].get("status") == "ready":
            _wa_session_ready = True
            return {"ok": True, "status": "ready", "session_id": _wa_session_id}
        return {"ok": True, "status": "scan_qr", "session_id": _wa_session_id}

    return {"ok": False, "error": f"Failed to start session: {st2}"}

def send_message(to: str, text: str) -> dict:
    sid = _sid()
    if not _wa_session_ready:
        es = ensure_session()
        if not es["ok"]:
            return es
        if es.get("status") != "ready":
            return {"ok": False, "error": f"Session not ready: {es.get('status')}"}
        sid = es.get("session_id", sid)
    chat_id = to if "@" in to else f"{to}@c.us"
    return _api_post(f"/api/sessions/{sid}/messages/send-text", {
        "chatId": chat_id,
        "text": text,
    })

def send_image(to: str, image_url: str, caption: str = "") -> dict:
    sid = _sid()
    if not _wa_session_ready:
        es = ensure_session()
        if not es["ok"]:
            return es
        if es.get("status") != "ready":
            return {"ok": False, "error": f"Session not ready: {es.get('status')}"}
        sid = es.get("session_id", sid)
    chat_id = to if "@" in to else f"{to}@c.us"

    # OpenWA @IsUrl() rejects localhost — auto-convert to base64
    is_local = "localhost" in image_url or "127.0.0.1" in image_url or image_url.startswith("/api/image")
    if is_local:
        image_data = None
        ext = "png"
        m = re.search(r"/api/image\?file=([^&\s]+)", image_url)
        if m:
            fname = m.group(1)
            ext = fname.rsplit(".", 1)[-1] if "." in fname else "png"
            for base_dir in [
                Path(__file__).parent / "output",
                Path(__file__).parent / "data" / "downloads",
            ]:
                fp = base_dir / fname
                if fp.exists():
                    image_data = fp.read_bytes()
                    break
        if image_data is None:
            try:
                fetch_urls = [image_url]
                if image_url.startswith("/"):
                    for _base in ["http://localhost:9999", "http://127.0.0.1:9999"]:
                        fetch_urls.append(f"{_base}{image_url}")
                for _fu in fetch_urls:
                    resp = requests.get(_fu, timeout=15)
                    if resp.ok:
                        image_data = resp.content
                        break
            except Exception:
                pass
        if image_data:
            b64 = base64.b64encode(image_data).decode()
            if len(b64) > 80000:
                try:
                    from PIL import Image as _PIL
                    import io
                    img = _PIL.open(io.BytesIO(image_data))
                    mime_ext = "jpeg"
                    max_dim = 800
                    for _ in range(5):
                        w, h = img.size
                        if max(w, h) > max_dim:
                            scale = max_dim / max(w, h)
                            img = img.resize((int(w * scale), int(h * scale)), _PIL.LANCZOS)
                        buf = io.BytesIO()
                        img = img.convert("RGB")
                        img.save(buf, "JPEG", quality=75)
                        b64 = base64.b64encode(buf.getvalue()).decode()
                        if len(b64) <= 80000:
                            break
                        max_dim = int(max_dim * 0.7)
                except Exception as e:
                    logger.warning("[WA] Compression failed: %s", e)
            mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
            mime_type = f"image/{mime_map.get(ext, 'png')}"
            return _api_post(f"/api/sessions/{sid}/messages/send-image", {
                "chatId": chat_id,
                "base64": b64,
                "mimetype": mime_type,
                "caption": caption,
            })
        return {"ok": False, "error": f"Impossibile caricare l'immagine locale: {image_url[:100]}"}
    return _api_post(f"/api/sessions/{sid}/messages/send-image", {
        "chatId": chat_id,
        "url": image_url,
        "caption": caption,
    })

def send_audio(to: str, audio_base64: str, mimetype: str = "audio/ogg") -> dict:
    sid = _sid()
    if not _wa_session_ready:
        es = ensure_session()
        if not es["ok"]:
            return es
        if es.get("status") != "ready":
            return {"ok": False, "error": f"Session not ready: {es.get('status')}"}
        sid = es.get("session_id", sid)
    chat_id = to if "@" in to else f"{to}@c.us"
    ext = mimetype.split("/")[-1] if "/" in mimetype else "ogg"
    if ext == "mpeg": ext = "mp3"
    if ext == "x-wav": ext = "wav"
    return _api_post(f"/api/sessions/{sid}/messages/send-audio", {
        "chatId": chat_id,
        "base64": audio_base64,
        "mimetype": mimetype,
        "filename": f"voice.{ext}",
    })

def get_qr() -> Optional[str]:
    global _last_qr
    return _last_qr

def get_status() -> dict:
    global _wa_available, _wa_session_ready
    check_health()
    sid = _sid()
    st = _api_get(f"/api/sessions/{sid}")
    session_status = "unknown"
    if st["ok"] and isinstance(st.get("data"), dict):
        session_status = st["data"].get("status", "unknown")
        _wa_session_ready = session_status == "ready"
    return {
        "openwa_available": _wa_available,
        "session_ready": _wa_session_ready,
        "session_status": session_status,
        "session_name": OPENWA_SESSION,
        "session_id": sid,
        "api_url": OPENWA_URL,
    }
