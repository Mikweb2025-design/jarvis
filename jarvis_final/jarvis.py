#!/usr/bin/env python3
"""
jarvis.py — core LLM + TTS
"""
import os, sys, json, time, re, subprocess, tempfile
import numpy as np
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

CONFIG_PATH = Path(__file__).parent / "config.json"

VOICE_LANG = {
    "af":"🇺🇸 EN female","am":"🇺🇸 EN male",
    "bf":"🇬🇧 UK female","bm":"🇬🇧 UK male",
    "ef":"🇪🇸 ES female","em":"🇪🇸 ES male",
    "ff":"🇫🇷 FR female",
    "hf":"🇮🇳 HI female","hm":"🇮🇳 HI male",
    "if":"🇮🇹 IT female","im":"🇮🇹 IT male",
    "jf":"🇯🇵 JP female","jm":"🇯🇵 JP male",
    "pf":"🇵🇹 PT female","pm":"🇵🇹 PT male",
    "zf":"🇨🇳 ZH female","zm":"🇨🇳 ZH male",
}

KNOWN_VOICES = [
    "af_alloy","af_aoede","af_bella","af_heart","af_jadzia","af_jessica",
    "af_kore","af_nicole","af_nova","af_river","af_sarah","af_sky",
    "am_adam","am_echo","am_eric","am_fenrir","am_liam","am_michael",
    "am_onyx","am_puck","am_santa",
    "bf_alice","bf_emma","bf_lily","bm_daniel","bm_fable","bm_george","bm_lewis",
    "ef_dora","em_alex","em_santa","ff_siwis",
    "hf_alpha","hf_beta","hm_omega","hm_psi",
    "if_sara","im_nicola",
    "jf_alpha","jf_gongitsune","jf_nezumi","jf_tebukuro","jm_kumo",
    "pf_dora","pm_alex","pm_santa",
    "zf_xiaobei","zf_xiaoni","zf_xiaoxiao","zf_xiaoyi",
    "zm_yunjian","zm_yunxi","zm_yunxia","zm_yunyang",
]

DEFAULT_CONFIG = {
    "groq": {
        "api_key": "YOUR_GROQ_API_KEY_HERE",
        "model": "llama-3.3-70b-versatile",
        "temperature": 0.7,
        "max_tokens": 1024,
        "system_prompt": "You are J.A.R.V.I.S. — Just A Rather Very Intelligent System. You are a sophisticated AI assistant, sharp, precise, and slightly witty. Keep responses concise and direct. Respond in the same language the user uses."
    },
    "ollama": {
        "enabled": False,
        "endpoint": "http://localhost:11434",
        "model": "llama3.2",
        "timeout": 60
    },
    "tts": {
        "endpoint": "https://meet.mikweb.info/v1/audio/speech",
        "model": "kokoro",
        "voice": "im_nicola",
        "speed": 1.0,
        "response_format": "mp3",
        "enabled": True,
        "qwen3_enabled": True,
        "qwen3_model": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
        "qwen3_voice": "serena",
        "qwen3_language": "Italian",
        "qwen3_instruct": "Chiara, professionale, leggermente calda, pronuncia italiana perfetta",
        "qwen3_available_voices": ["serena", "vivian", "uncle_fu", "ryan", "aiden", "ono_anna", "sohee", "eric", "dylan"],
        "qwen3_languages": {
            "italian": {"voice": "serena", "language": "Italian", "instruct": "Chiara, professionale, leggermente calda, pronuncia italiana perfetta"},
            "german": {"voice": "ryan", "language": "German", "instruct": "Clear, professional, slightly warm tone"}
        }
    },
    "wake_word": "jarvis",
    "history_max": 20,
    "debug": False
}

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
            elif isinstance(v, dict):
                for kk, vv in v.items():
                    if kk not in cfg[k]:
                        cfg[k][kk] = vv
        return cfg
    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"[INFO] config.json creato — inserisci la Groq API key!")
    return DEFAULT_CONFIG.copy()

class GroqClient:
    URL = "https://api.groq.com/openai/v1/chat/completions"
    def __init__(self, cfg):
        self.cfg = cfg
        self.history = []
    def chat(self, msg):
        self.history.append({"role":"user","content":msg})
        if len(self.history) > self.cfg["history_max"]*2:
            self.history = self.history[-self.cfg["history_max"]*2:]
        messages = [{"role":"system","content":self.cfg["groq"]["system_prompt"]}] + self.history
        headers = {"Authorization":f"Bearer {self.cfg['groq']['api_key']}","Content-Type":"application/json"}
        payload = {"model":self.cfg["groq"]["model"],"messages":messages,
                   "temperature":self.cfg["groq"]["temperature"],"max_tokens":self.cfg["groq"]["max_tokens"]}
        try:
            r = requests.post(self.URL, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            reply = r.json()["choices"][0]["message"]["content"].strip()
            self.history.append({"role":"assistant","content":reply})
            return reply
        except Exception as e:
            # Fallback a Ollama se Groq fallisce
            if self.cfg.get("ollama", {}).get("enabled", False):
                print(f"[INFO] Groq fallito, provo Ollama...")
                return self._ollama_chat(msg)
            return f"[Errore Groq] {e}"
    def _ollama_chat(self, msg):
        """Fallback locale con Ollama"""
        ollama_cfg = self.cfg.get("ollama", {})
        endpoint = ollama_cfg.get("endpoint", "http://localhost:11434")
        model = ollama_cfg.get("model", "llama3.2")
        timeout = ollama_cfg.get("timeout", 60)
        url = f"{endpoint}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role":"system","content":self.cfg["groq"]["system_prompt"]}] + self.history,
            "stream": False
        }
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            reply = r.json()["message"]["content"].strip()
            self.history.append({"role":"assistant","content":reply})
            return reply
        except Exception as e:
            return f"[Errore Ollama] {e}"
    def reset(self):
        self.history.clear()

class KokoroTTS:
    def __init__(self, cfg):
        self.cfg = cfg["tts"]
        self._qwen3_model = None
        self._qwen3_voice = self.cfg.get("qwen3_voice", "Vivian")
        self._qwen3_language = self.cfg.get("qwen3_language", "Italian")
        self._qwen3_instruct = self.cfg.get("qwen3_instruct", "Clear, professional, slightly warm tone")
    def _clean(self, text):
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'#{1,6}\s*', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        return text.strip()
    def _qwen3_tts(self, text, language=None, voice=None, instruct=None):
        """Qwen3-TTS via mlx-audio — modello principale, locale, offline, Apple Silicon
        Lingue supportate: Italian, German, English, French, Spanish, Portuguese, Russian, Japanese, Korean, Chinese
        Voci disponibili: serena, vivian, uncle_fu, ryan, aiden, ono_anna, sohee, eric, dylan
        """
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        from mlx_audio.tts.generate import generate_audio
        
        if self._qwen3_model is None:
            model_name = self.cfg.get("qwen3_model", "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit")
            print(f"[TTS] Caricamento modello Qwen3-TTS: {model_name}...")
            self._qwen3_model = load_model(model_name)
            print("[TTS] Modello Qwen3-TTS caricato ✅")
        
        # Rileva lingua dal testo o usa configurazione
        lang_config = self.cfg.get("qwen3_languages", {})
        if language and language.lower() in lang_config:
            lc = lang_config[language.lower()]
            spk = voice or lc.get("voice", self._qwen3_voice)
            lang = lc.get("language", self._qwen3_language)
            inst = instruct or lc.get("instruct", self._qwen3_instruct)
        else:
            spk = voice or self._qwen3_voice
            lang = language or self._qwen3_language
            inst = instruct or self._qwen3_instruct
        
        print(f"[TTS Qwen3] Lingua: {lang}, Voce: {spk}")
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = f.name
        
        results = list(self._qwen3_model.generate_custom_voice(
            text=text,
            speaker=spk,
            language=lang,
            instruct=inst
        ))
        
        audio = results[0].audio
        import soundfile as sf
        sf.write(output_path, np.array(audio), 24000)
        
        subprocess.run(["afplay", output_path], check=True, capture_output=True)
        os.unlink(output_path)
    def _kokoro(self, text):
        """TTS originale via endpoint remoto"""
        r = requests.post(self.cfg["endpoint"], json={
            "model": self.cfg.get("model","kokoro"),
            "input": text,
            "voice": self.cfg["voice"],
            "speed": self.cfg.get("speed",1.0),
            "response_format": self.cfg.get("response_format","mp3")
        }, timeout=15, stream=True)
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            for chunk in r.iter_content(4096):
                f.write(chunk)
            p = f.name
        subprocess.run(["afplay", p], check=True, capture_output=True)
        os.unlink(p)
    def _edge_tts(self, text):
        """Edge TTS — gratis, alta qualità, voci italiane"""
        import asyncio
        import edge_tts
        voice = "it-IT-DiegoNeural"
        if "female" in self.cfg.get("voice","").lower() or self.cfg.get("voice","").startswith("if"):
            voice = "it-IT-ElsaNeural"
        rate = f"+{int((self.cfg.get('speed',1.0)-1)*100)}%"
        async def _gen():
            comm = edge_tts.Communicate(text, voice, rate=rate)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                p = f.name
            await comm.save(p)
            return p
        p = asyncio.run(_gen())
        subprocess.run(["afplay", p], check=True, capture_output=True)
        os.unlink(p)
    def _say(self, text):
        """Fallback macOS say command"""
        subprocess.run(["say", "-v", "Alice", text], capture_output=True)
    def speak(self, text, language=None):
        if not self.cfg.get("enabled", True): return True
        text = self._clean(text)
        if not text: return True
        # Try: Qwen3-TTS (MLX) → Kokoro → Edge TTS → macOS say
        if self.cfg.get("qwen3_enabled", True):
            try:
                self._qwen3_tts(text, language=language)
                return True
            except Exception as e:
                print(f"  [TTS Qwen3-MLX] fallito: {e}")
        try:
            self._kokoro(text)
            return True
        except Exception as e:
            print(f"  [TTS Kokoro] fallito: {e}")
        try:
            self._edge_tts(text)
            return True
        except Exception as e:
            print(f"  [TTS Edge] fallito: {e}")
        try:
            self._say(text[:200])
            return True
        except Exception as e:
            print(f"  [TTS Say] fallito: {e}")
            return False
