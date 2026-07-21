"""jarvis_imagegen.py — Image Generation via IONOS Hub (OpenAI-compatible API)"""
import json, os, time, base64, io
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent / "data"
PROVIDERS_PATH = DATA_DIR / "providers.json"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def _load_providers():
    if PROVIDERS_PATH.exists():
        return json.loads(PROVIDERS_PATH.read_text())
    return {}

IONOS_IMAGE_ENDPOINT = "https://openai.inference.de-txl.ionos.com/v1/images/generations"

AVAILABLE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "black-forest-labs/FLUX.1-dev",
    "stabilityai/stable-diffusion-3.5-large",
]

def generate_image(prompt: str, model: str = "black-forest-labs/FLUX.1-schnell",
                    size: str = "1024x1024", n: int = 1,
                    quality: str = "standard", style: str = "natural") -> dict:
    providers = _load_providers()
    ionos = providers.get("ionos", {})
    api_key = ionos.get("api_key", "")
    if not api_key:
        return {"error": "IONOS Hub API key not configured in data/providers.json"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": quality,
        "style": style,
    }

    try:
        import requests
        t0 = time.time()
        resp = requests.post(IONOS_IMAGE_ENDPOINT, json=payload, headers=headers, timeout=120)
        elapsed = round(time.time() - t0, 2)
        if resp.status_code != 200:
            return {"error": f"IONOS Hub error {resp.status_code}: {resp.text}", "elapsed": elapsed}
        data = resp.json()
        images = []
        def _detect_ext(data: bytes) -> str:
            if data[:4] == b'\x89PNG':
                return "png"
            if data[:2] in (b'\xff\xd8',):
                return "jpg"
            if data[:4] == b'RIFF':
                return "webp"
            if data[:6] in (b'GIF87a', b'GIF89a'):
                return "gif"
            return "png"

        for item in data.get("data", []):
            if "b64_json" in item:
                img_data = base64.b64decode(item["b64_json"])
                ext = _detect_ext(img_data)
                filename = f"ionos_{int(time.time())}_{len(images)}.{ext}"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(img_data)
                images.append({
                    "url": f"/api/image?file={filename}",
                    "local_path": str(filepath),
                    "filename": filename,
                })
            elif "url" in item:
                _remote_url = item["url"]
                _saved = False
                try:
                    _r = requests.get(_remote_url, timeout=30)
                    if _r.status_code == 200:
                        _img_data = _r.content
                        ext = _detect_ext(_img_data)
                        _filename = f"ionos_{int(time.time())}_{len(images)}.{ext}"
                        _filepath = OUTPUT_DIR / _filename
                        _filepath.write_bytes(_img_data)
                        images.append({
                            "url": f"/api/image?file={_filename}",
                            "local_path": str(_filepath),
                            "filename": _filename,
                        })
                        _saved = True
                except Exception as _e:
                    print(f"[ImageGen] download fallito: {_e}")
                if not _saved:
                    images.append({"url": _remote_url})
        return {
            "images": images,
            "model": model,
            "prompt": prompt,
            "elapsed": elapsed,
            "revised_prompt": data.get("data", [{}])[0].get("revised_prompt", prompt),
        }
    except ImportError:
        return {"error": "requests library not installed"}
    except Exception as e:
        return {"error": str(e)}

def list_models() -> list:
    return AVAILABLE_MODELS
