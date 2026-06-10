"""jarvis_telegram.py — Telegram bot module for Jarvis (polling-based, zero new deps)"""
import os, sys, json, time, threading, logging, base64, tempfile

ENABLED = False
BOT_TOKEN = None
ALLOWED_CHAT_IDS = []
_agent_instance = None
_bot_thread = None
_running = False
_last_update_id = 0
_whisper_model = None

def _load_config():
    """Carica config.json per le impostazioni Telegram."""
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        return cfg.get("telegram", {})
    except Exception:
        return {}

def _get_agent():
    """Crea o restituisce l'istanza JarvisAgent (thread-safe, lazy)."""
    global _agent_instance
    if _agent_instance is None:
        sys.path.insert(0, os.path.dirname(__file__))
        from jarvis_agent import JarvisAgent
        from jarvis import load_config
        cfg = load_config()
        _agent_instance = JarvisAgent(cfg)
    return _agent_instance

def _download_telegram_file(file_id):
    """Scarica un file da Telegram dato il file_id, restituisce bytes."""
    import requests as _req
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    try:
        resp = _req.get(f"{base_url}/getFile", params={"file_id": file_id}, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            logging.error(f"Telegram: getFile fallito: {data.get('description', '?')}")
            return None
        file_path = data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        resp = _req.get(file_url, timeout=30)
        return resp.content
    except Exception as e:
        logging.error(f"Telegram: download file error: {e}")
        return None

def _transcribe_audio(audio_bytes, ext=".ogg"):
    """Trascrive audio tramite Whisper, restituisce testo."""
    global _whisper_model
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.write(audio_bytes)
    audio_path = tmp.name
    tmp.close()
    try:
        from faster_whisper import WhisperModel
        global _whisper_model
        if _whisper_model is None:
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segs, _ = _whisper_model.transcribe(audio_path, language="it", beam_size=1)
        return " ".join(s.text.strip() for s in segs).strip()
    except Exception as e:
        logging.error(f"Telegram: trascrizione fallita: {e}")
        return ""
    finally:
        try:
            os.unlink(audio_path)
        except:
            pass

def _send_voice_reply(chat_id, text):
    """Genera TTS audio e lo invia come messaggio audio su Telegram."""
    import requests as _req
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    try:
        import edge_tts as etts
        tts = etts.Communicate(text[:500], voice="it-IT-ElsaNeural")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.close()
            tts.save(tmp.name)
        with open(tmp.name, "rb") as f:
            audio_data = f.read()
        os.unlink(tmp.name)
        resp = _req.post(
            f"{base_url}/sendAudio",
            data={"chat_id": chat_id},
            files={"audio": ("reply.mp3", audio_data, "audio/mpeg")},
            timeout=30
        )
        result = resp.json()
        if result.get("ok"):
            logging.info(f"Telegram: audio inviato a chat {chat_id}")
            return True
        logging.error(f"Telegram: sendAudio fallito: {result.get('description', '?')}")
        return False
    except Exception as e:
        logging.error(f"Telegram: TTS reply error: {e}")
        return False

def _poll():
    """Polling loop per messaggi Telegram (eseguito in thread separato)."""
    global _last_update_id, _running
    import requests as _req
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    # Verifica token all'avvio
    try:
        me = _req.get(f"{base_url}/getMe", timeout=10).json()
        if not me.get("ok"):
            logging.error(f"Telegram: token non valido (getMe fallito)")
            _running = False
            return
        logging.info(f"Telegram bot @{me.get('result', {}).get('username', '?')} avviato")
    except Exception as e:
        logging.error(f"Telegram: impossibile verificare token: {e}")
        _running = False
        return
    
    while _running:
        try:
            params = {"offset": _last_update_id + 1, "timeout": 30}
            resp = _req.get(f"{base_url}/getUpdates", params=params, timeout=35)
            data = resp.json()
            if not data.get("ok"):
                time.sleep(2)
                continue
            
            for update in data.get("result", []):
                _last_update_id = update["update_id"]
                if "message" not in update:
                    continue
                msg = update["message"]
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "").strip()
                is_voice = False
                
                # ── Rilevamento messaggi vocali ──
                voice_info = msg.get("voice") or msg.get("audio")
                if voice_info:
                    file_id = voice_info.get("file_id")
                    if file_id:
                        audio_bytes = _download_telegram_file(file_id)
                        if audio_bytes:
                            ext = ".oga" if msg.get("voice") else ".mp3"
                            transcribed = _transcribe_audio(audio_bytes, ext)
                            if transcribed:
                                text = transcribed
                                is_voice = True
                                logging.info(f"Telegram: vocale trascritto: {text[:100]}")
                
                # Filtra chat non autorizzate
                if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
                    _req.post(f"{base_url}/sendMessage", json={
                        "chat_id": chat_id, "text": "⛔ Non autorizzato."
                    }, timeout=10)
                    continue
                
                if not text:
                    continue
                
                # Processa con JarvisAgent
                try:
                    agent = _get_agent()
                    reply, actions = agent.chat(text)
                    if not reply:
                        reply = "✅ Fatto."
                    
                    if is_voice:
                        # Risposta audio per messaggi vocali
                        audio_ok = _send_voice_reply(chat_id, reply)
                        if not audio_ok:
                            # Fallback a testo se TTS fallisce
                            _req.post(f"{base_url}/sendMessage", json={
                                "chat_id": chat_id, "text": reply
                            }, timeout=10)
                    else:
                        # Risposta testo (split se > 4096 chars)
                        if len(reply) > 4000:
                            for i in range(0, len(reply), 4000):
                                _req.post(f"{base_url}/sendMessage", json={
                                    "chat_id": chat_id, "text": reply[i:i+4000]
                                }, timeout=10)
                        else:
                            _req.post(f"{base_url}/sendMessage", json={
                                "chat_id": chat_id, "text": reply
                            }, timeout=10)
                except Exception as e:
                    logging.error(f"Telegram: errore elaborazione: {e}")
                    try:
                        _req.post(f"{base_url}/sendMessage", json={
                            "chat_id": chat_id, "text": f"⚠ Errore: {str(e)[:200]}"
                        }, timeout=10)
                    except Exception:
                        pass
        except Exception as e:
            if _running:
                logging.error(f"Telegram poll error: {e}")
                time.sleep(2)

def start(token=None, allowed_ids=None):
    """Avvia il bot Telegram in un thread separato."""
    global BOT_TOKEN, ALLOWED_CHAT_IDS, ENABLED, _running, _bot_thread
    
    cfg = _load_config()
    BOT_TOKEN = token or cfg.get("bot_token", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    ALLOWED_CHAT_IDS = allowed_ids or cfg.get("allowed_chat_ids", [])
    
    if not BOT_TOKEN:
        logging.warning("Telegram: TELEGRAM_BOT_TOKEN non configurato. "
                        "Imposta in config.json o variabile ambiente TELEGRAM_BOT_TOKEN")
        return False
    
    if _running:
        logging.info("Telegram: bot già in esecuzione")
        return True
    
    _running = True
    _bot_thread = threading.Thread(target=_poll, daemon=True, name="telegram-bot")
    _bot_thread.start()
    ENABLED = True
    logging.info("Telegram: bot avviato in background")
    return True

def stop():
    """Ferma il bot Telegram."""
    global _running, ENABLED
    _running = False
    ENABLED = False
    logging.info("Telegram: bot fermato")

def send(chat_id, text):
    """Invia un messaggio Telegram (usa direttamente l'API)."""
    if not BOT_TOKEN:
        return "⚠ Telegram: bot non configurato"
    import requests as _req
    try:
        resp = _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": int(chat_id), "text": text},
            timeout=15
        )
        data = resp.json()
        if data.get("ok"):
            return f"✅ Messaggio inviato a chat {chat_id}"
        return f"⚠ Telegram: {data.get('description', 'errore sconosciuto')}"
    except Exception as e:
        return f"⚠ Telegram errore: {e}"

def status():
    """Stato del bot Telegram."""
    return {
        "enabled": ENABLED and bool(BOT_TOKEN),
        "configured": bool(BOT_TOKEN),
        "allowed_chats": len(ALLOWED_CHAT_IDS),
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[Telegram] %(message)s")
    print("Avvio Telegram bot standalone...")
    ok = start()
    if ok:
        print("✅ Bot in esecuzione. Premi Ctrl+C per fermare.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop()
            print("Bot fermato.")
    else:
        print("❌ Impossibile avviare il bot. Configura TELEGRAM_BOT_TOKEN.")
