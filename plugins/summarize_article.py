#!/usr/bin/env python3
"""summarize_article.py — Plugin per riassumere articoli web o testi lunghi"""
import json, requests, re
from pathlib import Path

def summarize_article(url="", text="", max_length=200, language="italian", **_):
    """Riassume un articolo web o un testo lungo.
    
    Args:
        url: URL dell'articolo (opzionale se text è fornito)
        text: Testo diretto (opzionale se url è fornito)
        max_length: Lunghezza massima del riassunto in parole
        language: Lingua del riassunto
    """
    try:
        groq_key = json.loads((Path(__file__).parent.parent / "config.json").read_text()).get("groq", {}).get("api_key", "")
        if not groq_key:
            return "⚠ API key Groq non configurata"
        content = text or ""
        if url and not text:
            try:
                resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if resp.ok:
                    from html.parser import HTMLParser
                    class TextExtractor(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.text = []
                            self.skip = False
                        def handle_starttag(self, tag, attrs):
                            if tag in ("script", "style", "nav", "footer", "header"):
                                self.skip = True
                        def handle_endtag(self, tag):
                            if tag in ("script", "style", "nav", "footer", "header"):
                                self.skip = False
                        def handle_data(self, data):
                            if not self.skip:
                                self.text.append(data.strip())
                    parser = TextExtractor()
                    parser.feed(resp.text)
                    content = " ".join(t for t in parser.text if t)[:5000]
            except:
                return "⚠ Impossibile scaricare l'URL"
        if not content:
            return "⚠ Fornisci un URL o del testo da riassumere"
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": f"Riassumi in {language} in max {max_length} parole. Sii conciso e cattura i punti chiave."},
                    {"role": "user", "content": content[:8000]}
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            timeout=30
        )
        if resp.ok:
            summary = resp.json()["choices"][0]["message"]["content"].strip()
            return f"📝 Riassunto:\n\n{summary}"
        return f"⚠ Errore API: {resp.status_code}"
    except ImportError:
        return "⚠ Serve requests: pip install requests"
    except Exception as e:
        return f"⚠ Errore: {e}"

if __name__ == "__main__":
    print(summarize_article(text="L'intelligenza artificiale sta trasformando il mondo. Ogni giorno emergono nuovi modelli e applicazioni.", max_length=50))
