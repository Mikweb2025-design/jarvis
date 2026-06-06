#!/usr/bin/env python3
"""jarvis_providers.py — Multi-LLM Provider Switchboard v1.0
Ispirato a rishaadj/JARVIS (neural switchboard) e deepakrakshit/jarvis
Consente di switchare dinamicamente tra: Groq, Ollama, OpenAI, Gemini, Anthropic"""
import json, os, requests, time
from pathlib import Path

PROVIDERS_FILE = Path(__file__).parent / "data" / "providers.json"

DEFAULT_PROVIDERS = {
    "groq": {
        "enabled": True,
        "api_key": "",
        "model": "llama-3.3-70b-versatile",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "ollama": {
        "enabled": True,
        "endpoint": "http://localhost:11434/api/chat",
        "model": "llama3.2",
        "temperature": 0.7,
        "timeout": 60,
    },
    "openai": {
        "enabled": False,
        "api_key": "",
        "model": "gpt-4o-mini",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "gemini": {
        "enabled": False,
        "api_key": "",
        "model": "gemini-2.0-flash",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "temperature": 0.7,
    },
    "anthropic": {
        "enabled": False,
        "api_key": "",
        "model": "claude-3-5-haiku-latest",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
}

def _load():
    PROVIDERS_FILE.parent.mkdir(exist_ok=True)
    if PROVIDERS_FILE.exists():
        with open(PROVIDERS_FILE) as f:
            data = json.load(f)
        for k, v in DEFAULT_PROVIDERS.items():
            if k not in data:
                data[k] = v
            elif isinstance(v, dict):
                for kk, vv in v.items():
                    if kk not in data[k]:
                        data[k][kk] = vv
        return data
    with open(PROVIDERS_FILE, "w") as f:
        json.dump(DEFAULT_PROVIDERS, f, indent=2)
    return DEFAULT_PROVIDERS.copy()

def _save(data):
    PROVIDERS_FILE.parent.mkdir(exist_ok=True)
    with open(PROVIDERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_active_provider():
    data = _load()
    for name, cfg in data.items():
        if cfg.get("enabled") and cfg.get("api_key", "") and name != "ollama":
            return name, cfg
        if name == "ollama" and cfg.get("enabled"):
            return name, cfg
    return "groq", data.get("groq", DEFAULT_PROVIDERS["groq"])

def list_providers():
    data = _load()
    result = []
    for name, cfg in data.items():
        status = "✅ attivo" if cfg.get("enabled") else "⬇ disabilitato"
        has_key = "🔑" if cfg.get("api_key") else "❌"
        model = cfg.get("model", "N/A")
        result.append(f"{has_key} {name}: {model} — {status}")
    return "\n".join(result)

def set_provider(name, enabled=True):
    data = _load()
    if name not in data:
        return f"Provider '{name}' non trovato. Disponibili: {', '.join(data.keys())}"
    data[name]["enabled"] = enabled
    _save(data)
    return f"Provider '{name}' {'attivato' if enabled else 'disabilitato'}"

def set_provider_model(name, model):
    data = _load()
    if name not in data:
        return f"Provider '{name}' non trovato"
    data[name]["model"] = model
    _save(data)
    return f"Model '{name}' → {model}"

def chat_completion(messages, provider_name=None, stream=False):
    data = _load()
    if provider_name:
        cfg = data.get(provider_name)
        if not cfg:
            return f"Provider '{provider_name}' non trovato"
    else:
        provider_name, cfg = get_active_provider()
    if not cfg.get("enabled"):
        return f"Provider '{provider_name}' disabilitato"
    try:
        if provider_name == "groq":
            return _call_openai_compat(cfg, messages, stream)
        elif provider_name == "openai":
            return _call_openai_compat(cfg, messages, stream)
        elif provider_name == "ollama":
            return _call_ollama(cfg, messages, stream)
        elif provider_name == "gemini":
            return _call_gemini(cfg, messages, stream)
        elif provider_name == "anthropic":
            return _call_anthropic(cfg, messages, stream)
        return "Provider non supportato"
    except Exception as e:
        return f"Errore {provider_name}: {e}"

def _call_openai_compat(cfg, messages, stream):
    headers = {"Authorization": f"Bearer {cfg.get('api_key', '')}", "Content-Type": "application/json"}
    payload = {"model": cfg["model"], "messages": messages,
               "temperature": cfg.get("temperature", 0.7), "max_tokens": cfg.get("max_tokens", 2048)}
    resp = requests.post(cfg["endpoint"], json=payload, headers=headers, timeout=cfg.get("timeout", 60))
    if resp.ok:
        return resp.json()["choices"][0]["message"]["content"]
    return f"Errore API: {resp.status_code} {resp.text[:200]}"

def _call_ollama(cfg, messages, stream):
    payload = {"model": cfg["model"], "messages": messages,
               "temperature": cfg.get("temperature", 0.7), "stream": False}
    try:
        resp = requests.post(cfg["endpoint"], json=payload, timeout=cfg.get("timeout", 60))
        if resp.ok:
            return resp.json()["message"]["content"]
        return f"Errore Ollama: {resp.status_code}"
    except requests.ConnectionError:
        return "Ollama non raggiungibile (server in esecuzione?)"

def _call_gemini(cfg, messages, stream):
    api_key = cfg.get("api_key", "")
    model = cfg.get("model", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    system = ""
    contents = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {"contents": contents}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    resp = requests.post(url, json=payload, timeout=60)
    if resp.ok:
        candidates = resp.json().get("candidates", [])
        if candidates:
            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return f"Errore Gemini: {resp.status_code} {resp.text[:200]}"

def _call_anthropic(cfg, messages, stream):
    api_key = cfg.get("api_key", "")
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    system = ""
    msgs = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            msgs.append({"role": m["role"], "content": m["content"]})
    payload = {"model": cfg["model"], "messages": msgs,
               "max_tokens": cfg.get("max_tokens", 2048),
               "temperature": cfg.get("temperature", 0.7)}
    if system:
        payload["system"] = system
    resp = requests.post(cfg["endpoint"], json=payload, headers=headers, timeout=60)
    if resp.ok:
        return resp.json()["content"][0]["text"]
    return f"Errore Anthropic: {resp.status_code} {resp.text[:200]}"

def switch_active(provider_name):
    data = _load()
    if provider_name not in data:
        return f"Provider '{provider_name}' non trovato. Disponibili: {', '.join(data.keys())}"
    for name in data:
        data[name]["enabled"] = (name == provider_name)
    _save(data)
    return f"Provider attivo: {provider_name} ({data[provider_name]['model']})"

def estimate_cost(messages, response_text=""):
    """Stima approssimativa del costo API"""
    input_chars = sum(len(m.get("content", "")) for m in messages)
    output_chars = len(response_text)
    return {
        "input_chars": input_chars,
        "output_chars": output_chars,
        "provider": get_active_provider()[0],
        "note": "Stima approssimativa. Costo reale dipende dal provider."
    }
