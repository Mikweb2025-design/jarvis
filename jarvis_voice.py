#!/usr/bin/env python3
"""jarvis_voice.py — Voice Engine: PlayAI TTS, STT, voice management, multi-voice synthesis"""
import json, os, requests, tempfile, time, subprocess, base64
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_PATH = Path(__file__).parent / "config.json"

def _load_config():
    try:
        return json.loads(CONFIG_PATH.read_text())
    except:
        return {}

class VoiceEngine:
    PLAYAI_VOICES = {
        "vivian": {"id": "vivian", "gender": "female", "lang": "it", "style": "natural"},
        "serena": {"id": "serena", "gender": "female", "lang": "it", "style": "warm"},
        "aiden": {"id": "aiden", "gender": "male", "lang": "it", "style": "professional"},
        "ryan": {"id": "ryan", "gender": "male", "lang": "de", "style": "deep"},
        "eric": {"id": "eric", "gender": "male", "lang": "de", "style": "calm"},
        "dylan": {"id": "dylan", "gender": "male", "lang": "de", "style": "energetic"},
        "aria": {"id": "aria", "gender": "female", "lang": "en", "style": "expressive"},
        "liam": {"id": "liam", "gender": "male", "lang": "en", "style": "conversational"},
        "olivia": {"id": "olivia", "gender": "female", "lang": "en", "style": "warm"},
        "noah": {"id": "noah", "gender": "male", "lang": "en", "style": "professional"},
        "emma": {"id": "emma", "gender": "female", "lang": "en", "style": "cheerful"},
        "lucas": {"id": "lucas", "gender": "male", "lang": "en", "style": "deep"},
        "sophia": {"id": "sophia", "gender": "female", "lang": "en", "style": "calm"},
        "mason": {"id": "mason", "gender": "male", "lang": "en", "style": "authoritative"},
    }

    def __init__(self):
        self.cfg = _load_config()
        playai_cfg = self.cfg.get("playai", {})
        self.api_key = playai_cfg.get("api_key", os.environ.get("PLAYAI_API_KEY", ""))
        self.user_id = playai_cfg.get("user_id", os.environ.get("PLAYAI_USER_ID", ""))
        self.current_voice = self.cfg.get("tts", {}).get("qwen3_voice", "vivian")

    def say(self, text, voice=None, speed=1.0, language="italian"):
        """Text-to-speech with PlayAI or fallback chain"""
        voice = voice or self.current_voice
        if self.api_key and self.user_id:
            try:
                data, fmt = self._playai_tts(text, voice, speed)
                if data:
                    path = f"/tmp/voice_playai_{int(time.time())}.{fmt}"
                    with open(path, "wb") as f:
                        f.write(data)
                    subprocess.run(["afplay", path], capture_output=True, timeout=30)
                    os.unlink(path)
                    return f"PlayAI: spoken {len(text)} chars in {voice}"
            except Exception as e:
                print(f"  [Voice] PlayAI fallito: {e}")
        # Fallback: macOS say
        try:
            voice_map = {"vivian":"Alice","serena":"Alice","aiden":"Luca",
                         "ryan":"Anna","eric":"Anna","dylan":"Anna"}
            mac_voice = voice_map.get(voice, "Alice")
            subprocess.run(["say", "-v", mac_voice, text[:500]], capture_output=True, timeout=30)
            return f"macOS say: spoken {len(text)} chars in {voice}"
        except Exception as e:
            return f"Voice synthesis failed: {e}"

    def listen(self, timeout=5, language="it-IT"):
        """Speech-to-text using macOS speech recognition"""
        path = f"/tmp/voice_input_{int(time.time())}.wav"
        try:
            subprocess.run([
                "rec", "-r", "16000", "-c", "1", "-b", "16", path,
                "trim", "0", str(timeout)
            ], capture_output=True, timeout=timeout + 5)
        except Exception:
            pass
        try:
            subprocess.run([
                "sox", "-d", "-r", "16000", "-c", "1", path,
                "trim", "0", str(timeout)
            ], capture_output=True, timeout=timeout + 5)
        except:
            return ""
        if not os.path.exists(path) or os.path.getsize(path) < 100:
            return ""
        text = self._stt_whisper(path, language)
        try:
            os.unlink(path)
        except:
            pass
        return text

    def _playai_tts(self, text, voice, speed):
        """PlayAI TTS API"""
        voice_id = self.PLAYAI_VOICES.get(voice, {}).get("id", "vivian")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-User-ID": self.user_id,
            "Content-Type": "application/json",
        }
        payload = {
            "model": "PlayDialog",
            "text": text[:2000],
            "voice": voice_id,
            "speed": speed,
            "output_format": "mp3",
        }
        resp = requests.post(
            "https://api.play.ai/v1/tts",
            json=payload, headers=headers, timeout=30
        )
        if resp.ok:
            data = resp.content
            ct = resp.headers.get("content-type", "audio/mpeg")
            fmt = "mp3"
            if "wav" in ct:
                fmt = "wav"
            return data, fmt
        # Try async endpoint
        resp = requests.post(
            "https://api.play.ai/v1/tts/async",
            json=payload, headers=headers, timeout=10
        )
        if resp.ok:
            task_id = resp.json().get("id")
            for _ in range(30):
                time.sleep(2)
                status = requests.get(
                    f"https://api.play.ai/v1/tts/status/{task_id}",
                    headers=headers, timeout=10
                )
                if status.ok:
                    data = status.json()
                    if data.get("status") == "completed":
                        audio_url = data.get("output", {}).get("url", "")
                        if audio_url:
                            audio_resp = requests.get(audio_url, timeout=30)
                            if audio_resp.ok:
                                return audio_resp.content, "mp3"
                    elif data.get("status") == "failed":
                        break
        return None, None

    def _stt_whisper(self, audio_path, language):
        """STT with Whisper (Ollama or local)"""
        try:
            import whisper
            model = whisper.load_model("tiny")
            result = model.transcribe(audio_path, language=language[:2])
            return result.get("text", "").strip()
        except:
            pass
        try:
            import requests
            with open(audio_path, "rb") as f:
                resp = requests.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "whisper", "file": base64.b64encode(f.read()).decode()},
                    timeout=30
                )
                if resp.ok:
                    return resp.json().get("response", "")
        except:
            pass
        return ""

    def set_voice(self, voice_name):
        """Change active voice"""
        if voice_name in self.PLAYAI_VOICES:
            self.current_voice = voice_name
            return f"Voice changed to {voice_name}"
        voices = [v for v in self.PLAYAI_VOICES.keys()]
        return f"Voice '{voice_name}' not found. Available: {', '.join(voices)}"

    def list_voices(self):
        """List all available voices sorted by language, gender"""
        lines = ["Available PlayAI voices:"]
        for lang in ["it", "en", "de"]:
            lang_voices = {k: v for k, v in self.PLAYAI_VOICES.items() if v["lang"] == lang}
            if lang_voices:
                lines.append(f"\n  {lang.upper()}:")
                for name, info in lang_voices.items():
                    active = " ★" if name == self.current_voice else ""
                    lines.append(f"    {name}: {info['gender']}, {info['style']}{active}")
        return "\n".join(lines)

    def speak_multilingual(self, segments):
        """Speak multiple segments with different voices per segment
        segments: list of {"text": str, "voice": str, "speed": float}"""
        audio_segments = []
        for seg in segments:
            text = seg.get("text", "")
            voice = seg.get("voice", self.current_voice)
            speed = seg.get("speed", 1.0)
            data, fmt = self._playai_tts(text, voice, speed)
            if data:
                audio_segments.append((data, fmt))
        if not audio_segments:
            for seg in segments:
                self.say(seg.get("text", ""), seg.get("voice", self.current_voice))
            return "Spoken sequentially (no PlayAI)"
        combined = b"".join(d for d, f in audio_segments)
        path = f"/tmp/voice_multilingual_{int(time.time())}.mp3"
        with open(path, "wb") as f:
            f.write(combined)
        subprocess.run(["afplay", path], capture_output=True, timeout=60)
        os.unlink(path)
        return f"Spoken {len(audio_segments)} multilingual segments"

voice = VoiceEngine()
