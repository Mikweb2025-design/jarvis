#!/usr/bin/env python3
"""smart_reply.py — Plugin per risposte email smart con AI"""
import subprocess, json, os
from pathlib import Path

def smart_reply(email_text="", tone="professional", **_):
    """Genera una risposta email intelligente basata sul testo ricevuto.
    
    Args:
        email_text: Testo dell'email ricevuta
        tone: Tono della risposta (professional, friendly, concise)
    """
    try:
        groq_key = json.loads((Path(__file__).parent.parent / "config.json").read_text()).get("groq", {}).get("api_key", "")
        if not groq_key:
            return "⚠ API key Groq non configurata"
        import requests
        tone_map = {"professional": "professionale e formale", "friendly": "amichevole e caloroso", "concise": "breve e diretto"}
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": f"Sei un assistente che scrive email in tono {tone_map.get(tone, 'professionale')}. Rispondi SOLO con il testo dell'email, niente spiegazioni."},
                    {"role": "user", "content": f"Scrivi una risposta a questa email:\n\n{email_text}"}
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            timeout=30
        )
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return f"⚠ Errore API: {resp.status_code}"
    except ImportError:
        return "⚠ Serve requests: pip install requests"
    except Exception as e:
        return f"⚠ Errore: {e}"

if __name__ == "__main__":
    print(smart_reply("Ciao, possiamo fissare una call per domani?", "friendly"))
