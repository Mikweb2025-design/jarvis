"""jarvis_musicgen.py — Music Generation via ACE-Step 1.5 (API locale o fallback)"""
import json, os, time, threading, subprocess, requests
from pathlib import Path
from typing import Optional

OUTPUT_DIR = Path(__file__).parent / "data" / "downloads" / "music"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_ACE_AVAILABLE = False
_ACE_LOCK = threading.Lock()

ACE_API_URL = "http://localhost:8001"

def _check_ace_api():
    global _ACE_AVAILABLE
    try:
        r = requests.get(f"{ACE_API_URL}/health", timeout=3)
        _ACE_AVAILABLE = r.status_code == 200
    except Exception:
        _ACE_AVAILABLE = False
    return _ACE_AVAILABLE

_check_ace_api()

GENRE_PRESETS = {
    "electronic": "Electronic dance music with synth pads, driving beats, arpeggiated leads",
    "ambient": "Ambient atmospheric soundscape with gentle pads, field recordings, slow evolution",
    "cinematic": "Cinematic orchestral piece with strings, brass, percussion, dramatic builds",
    "lo-fi": "Lo-fi hip hop with warm vinyl crackle, gentle piano, soft drums",
    "synthwave": "Synthwave/retrowave with analog synths, gated reverb, 80s drum machines",
    "jazz": "Smooth jazz with saxophone, piano trio, walking bass, brushed drums",
    "classical": "Classical chamber music with strings, woodwinds, formal structure",
}

def generate_music(prompt: str, duration: int = 30, genre: str = "electronic",
                   temperature: float = 1.0, steps: int = 50) -> dict:
    if not _ACE_AVAILABLE:
        return {
            "error": "ACE-Step API non disponibile su localhost:8001",
            "fallback": _generate_fallback(prompt, genre, duration),
        }
    try:
        import soundfile as sf
        import numpy as np

        t0 = time.time()
        genre_desc = GENRE_PRESETS.get(genre, prompt)
        full_prompt = f"{genre_desc}. {prompt}" if prompt else genre_desc

        with _ACE_LOCK:
            task_resp = requests.post(
                f"{ACE_API_URL}/release_task",
                json={"ai_token": "", "prompt": full_prompt},
                timeout=10,
            )
            if task_resp.status_code != 200:
                return {"error": f"ACE-Step API error: {task_resp.text}", "fallback": _generate_fallback(prompt, genre, duration)}

            task_data = task_resp.json()
            task_id = task_data.get("data", {}).get("task_id")
            if not task_id:
                return {"error": "Nessun task_id ricevuto", "fallback": _generate_fallback(prompt, genre, duration)}

            result = None
            for _ in range(120):
                time.sleep(2)
                qr = requests.post(
                    f"{ACE_API_URL}/query_result",
                    json={"task_ids": [task_id]},
                    timeout=10,
                )
                if qr.status_code == 200:
                    data = qr.json()
                    if isinstance(data, list) and len(data) > 0:
                        item = data[0]
                        if item.get("status") == "completed":
                            result = item
                            break
                        elif item.get("status") == "failed":
                            return {"error": f"ACE-Step generation failed: {item.get('error', 'unknown')}", "fallback": _generate_fallback(prompt, genre, duration)}

            if not result:
                return {"error": "ACE-Step generation timeout", "fallback": _generate_fallback(prompt, genre, duration)}

            audio_url = result.get("audio_url") or result.get("audio_file")
            sample_rate = result.get("sample_rate", 32000)
            if audio_url:
                audio_resp = requests.get(f"{ACE_API_URL}{audio_url}" if audio_url.startswith("/") else audio_url, timeout=30)
                audio_data = np.frombuffer(audio_resp.content, dtype=np.float32)
            else:
                audio_array = result.get("audio")
                if audio_array is None:
                    return {"error": "Nessun audio nel risultato", "fallback": _generate_fallback(prompt, genre, duration)}
                audio_data = np.array(audio_array, dtype=np.float32)

            peak = np.max(np.abs(audio_data))
            if peak > 0:
                audio_data = audio_data / peak

        elapsed = round(time.time() - t0, 2)
        filename = f"ace_{int(time.time())}.wav"
        filepath = str(OUTPUT_DIR / filename)
        sf.write(filepath, audio_data, sample_rate)
        return {
            "file": f"/data/downloads/music/{filename}",
            "local_path": filepath,
            "filename": filename,
            "duration": duration,
            "genre": genre,
            "elapsed": elapsed,
            "sample_rate": sample_rate,
        }

    except Exception as e:
        return {
            "error": str(e),
            "fallback": _generate_fallback(prompt, genre, duration),
        }

def _generate_fallback(prompt: str, genre: str, duration: int) -> dict:
    filename = f"fallback_{int(time.time())}.wav"
    filepath = str(OUTPUT_DIR / filename)
    sample_rate = 44100
    try:
        import numpy as np
        import soundfile as sf
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        freq_map = {
            "electronic": 220, "ambient": 110, "cinematic": 165,
            "lo-fi": 196, "synthwave": 130.81, "jazz": 293.66, "classical": 261.63,
        }
        base_freq = freq_map.get(genre, 220)
        audio = 0.3 * np.sin(2 * np.pi * base_freq * t)
        audio += 0.15 * np.sin(2 * np.pi * base_freq * 1.5 * t)
        audio += 0.1 * np.sin(2 * np.pi * base_freq * 2 * t)
        envelope = np.exp(-t / (duration * 0.6))
        audio *= envelope
        audio = np.clip(audio, -1.0, 1.0).astype(np.float32)
        sf.write(filepath, audio, sample_rate)
        return {
            "file": f"/data/downloads/music/{filename}",
            "local_path": filepath,
            "filename": filename,
            "duration": duration,
            "genre": genre,
            "note": "Fallback synthesis (ACE-Step API non disponibile su localhost:8001)",
            "sample_rate": sample_rate,
        }
    except Exception as e2:
        return {"error": f"Fallback failed: {e2}"}

def list_genres() -> list:
    return list(GENRE_PRESETS.keys())

def get_status() -> dict:
    return {
        "ace_step_available": _ACE_AVAILABLE,
        "ace_step_loaded": _ACE_AVAILABLE,
        "api_url": ACE_API_URL,
        "output_dir": str(OUTPUT_DIR),
        "genres": list(GENRE_PRESETS.keys()),
    }
