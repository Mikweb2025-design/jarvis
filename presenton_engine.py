#!/usr/bin/env python3
"""presenton_engine.py — AI Presentation Generator (Presenton-style)
Genera presentazioni spettacolari con dati reali, grafici, statistiche.
Usa IONOS Hub AI (o fallback Ollama) via API OpenAI-compatible.
Ispirato a github.com/presenton/presenton + Sentry design system."""
import json, re, time, sqlite3
from pathlib import Path
from datetime import datetime, timedelta

PROVIDERS_FILE = Path(__file__).parent / "data" / "providers.json"
DB_VIDEO = Path(__file__).parent / "data" / "video_analytics.db"

def get_vision_report_data():
    """Legge dati reali da video_analytics.db e restituisce statistiche strutturate.
    Usata per iniettare dati reali nelle presentazioni invece di generare fake."""
    if not DB_VIDEO.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_VIDEO))
        conn.row_factory = sqlite3.Row
        # Ultime 24h
        since_1h = (datetime.now() - timedelta(hours=1)).isoformat()
        since_6h = (datetime.now() - timedelta(hours=6)).isoformat()
        since_24h = (datetime.now() - timedelta(hours=24)).isoformat()
        since_7d = (datetime.now() - timedelta(days=7)).isoformat()

        def totals(hours, since):
            cur = conn.execute(
                "SELECT SUM(cars) as cars, SUM(people) as people, SUM(vehicles) as vehicles, "
                "COUNT(*) as samples FROM counts WHERE ts >= ?", (since,))
            r = cur.fetchone()
            return {
                "cars": int(r["cars"] or 0), "people": int(r["people"] or 0),
                "vehicles": int(r["vehicles"] or 0), "samples": int(r["samples"] or 0),
                "hours": hours
            }

        stats_1h = totals(1, since_1h)
        stats_6h = totals(6, since_6h)
        stats_24h = totals(24, since_24h)
        stats_7d = totals(168, since_7d)

        # Speed data (ultime 24h)
        cur = conn.execute(
            "SELECT AVG(speed) as avg_speed, COUNT(*) as sp_count FROM speed_samples WHERE ts >= ?",
            (since_24h,))
        sr = cur.fetchone()
        avg_speed_24h = round(float(sr["avg_speed"] or 0), 1)
        speed_count = int(sr["sp_count"] or 0)

        # Orari di punta (ultimi 7gg): ora con più traffico
        cur = conn.execute("""
            SELECT hour, SUM(cars+vehicles) as total FROM counts
            WHERE ts >= ? GROUP BY hour ORDER BY total DESC LIMIT 5
        """, (since_7d,))
        peak_hours = [{"hour": r["hour"], "total": int(r["total"] or 0)} for r in cur.fetchall()]

        # Trend per ora (ultime 24h) per chart
        cur = conn.execute("""
            SELECT hour, SUM(cars) as cars, SUM(people) as people, SUM(vehicles) as vehicles
            FROM counts WHERE ts >= ? GROUP BY hour ORDER BY hour
        """, (since_24h,))
        hourly_trend = [dict(r) for r in cur.fetchall()]

        conn.close()

        # Calcola medie e trend
        def avg_per_hour(stats):
            return round(stats["cars"] / max(stats["hours"], 1), 1)

        data = {
            "periods": {
                "1h": stats_1h,
                "6h": stats_6h,
                "24h": stats_24h,
                "7d": stats_7d,
            },
            "avg_speed_24h": avg_speed_24h,
            "speed_samples": speed_count,
            "peak_hours": peak_hours[:5],
            "hourly_trend": hourly_trend,
            "total_cars_24h": stats_24h["cars"],
            "total_people_24h": stats_24h["people"],
            "total_vehicles_24h": stats_24h["vehicles"],
            "avg_cars_per_hour": avg_per_hour(stats_24h),
            "avg_people_per_hour": round(stats_24h["people"] / max(stats_24h["hours"], 1), 1),
            "car_ratio": round(stats_24h["cars"] / max(stats_24h["vehicles"] + stats_24h["cars"], 1) * 100, 1),
            "peak_hour": peak_hours[0]["hour"] if peak_hours else "N/D",
            "peak_cars": peak_hours[0]["total"] if peak_hours else 0,
        }
        return data
    except Exception as e:
        return {"error": str(e)}

def _ionos_settings():
    """Legge le impostazioni IONOS Hub AI da providers.json.
    Restituisce (endpoint, model, temperature, timeout, api_key)."""
    try:
        with open(PROVIDERS_FILE) as f:
            data = json.load(f)
        io = data.get("ionos", {})
        if not io.get("enabled", False) or not io.get("api_key"):
            return None, None, 0.7, 120, None
        endpoint = io.get("endpoint", "https://openai.inference.de-txl.ionos.com/v1/chat/completions")
        model = io.get("model", "meta-llama/Llama-3.3-70B-Instruct")
        temperature = io.get("temperature", 0.7)
        timeout = io.get("timeout", 120)
        api_key = io.get("api_key", "")
        return endpoint, model, temperature, timeout, api_key
    except:
        return None, None, 0.7, 120, None

def _call_ionos(messages, temperature=None, max_tokens=8192):
    """Chiama IONOS Hub AI via API OpenAI-compatible"""
    endpoint, model, temp, timeout, api_key = _ionos_settings()
    if not endpoint or not api_key:
        return None
    import requests as _req
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature if temperature is not None else temp,
        "max_tokens": max_tokens
    }
    try:
        resp = _req.post(endpoint, json=payload,
                         headers={"Content-Type": "application/json",
                                  "Authorization": f"Bearer {api_key}"},
                         timeout=max(timeout, 180))
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"]
        return None
    except:
        return None

def _ollama_settings():
    """Legge le impostazioni Ollama da providers.json"""
    import requests as _req
    try:
        with open(PROVIDERS_FILE) as f:
            data = json.load(f)
        o = data.get("ollama", {})
        endpoint = o.get("endpoint", "http://localhost:11434/api/chat")
        model = o.get("model", "llama3.1:8b")
        temperature = o.get("temperature", 0.7)
        timeout = o.get("timeout", 60)
        try:
            tags = _req.get(endpoint.replace('/api/chat','/api/tags'), timeout=5)
            if tags.ok:
                models = [m['name'] for m in tags.json().get('models', [])]
                if model not in models and models:
                    model = models[0]
        except:
            pass
        return endpoint, model, temperature, timeout
    except:
        return "http://localhost:11434/api/chat", "llama3.1:8b", 0.7, 60

def _openai_compat_url():
    """Ritorna l'URL endpoint in formato OpenAI-compatible"""
    ep, _, _, _ = _ollama_settings()
    if "/v1/chat/completions" in ep:
        return ep
    base = ep.replace("/api/chat", "").rstrip("/")
    return f"{base}/v1/chat/completions"

def _call_ollama(messages, temperature=None, max_tokens=4096):
    """Chiama Ollama via API nativa"""
    endpoint, model, temp, timeout = _ollama_settings()
    import requests as _req
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature if temperature is not None else temp,
        "stream": False,
    }
    try:
        resp = _req.post(endpoint, json=payload, timeout=max(timeout, 180))
        if resp.ok:
            return resp.json()["message"]["content"]
        return None
    except:
        return None

def _call_ollama_openai(messages, temperature=None, max_tokens=4096):
    """Chiama Ollama via API OpenAI-compatible (come fa Presenton)"""
    url = _openai_compat_url()
    _, model, temp, timeout = _ollama_settings()
    import requests as _req
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature if temperature is not None else temp,
        "max_tokens": max_tokens
    }
    try:
        resp = _req.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=max(timeout, 180))
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"]
        return None
    except:
        return None

def _chat(messages, temperature=None, max_tokens=4096):
    """Prova: 1) IONOS Hub AI, 2) Ollama OpenAI-compatible, 3) Ollama nativa"""
    r = _call_ionos(messages, temperature, max_tokens)
    if r:
        return r
    r = _call_ollama_openai(messages, temperature, max_tokens)
    if r:
        return r
    return _call_ollama(messages, temperature, max_tokens)

def _extract_json(text):
    """Estrae JSON da risposta LLM"""
    jm = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if jm:
        text = jm.group(1).strip()
    for delim in ('[', '{'):
        start = text.find(delim)
        if start >= 0:
            try:
                return json.loads(text[start:])
            except:
                end = text.rfind(']' if delim == '[' else '}')
                if end > start:
                    try:
                        return json.loads(text[start:end+1])
                    except:
                        pass
    return None

def generate_slides(topic, n_slides=8, language="Italian", tone="default", instructions="", vision_data=None):
    """Genera slides strutturate RICCHE di DATI, GRAFICI e STATISTICHE.
    Se vision_data viene fornito (dati reali da video_analytics.db), li usa invece di inventare statistiche.
    Ogni presentazione include sempre:
    - Almeno 2 slide con grafici (chart)
    - Almeno 1 slide con tabella dati
    - Slide content con dati numerici e statistiche verificabili
    - Design professionale e spettacolare
    """
    tone_map = {
        "default": "professionale ed equilibrato",
        "casual": "informale e accessibile",
        "professional": "formale e autorevole, con dati precisi",
        "funny": "leggero e spiritoso ma con dati reali",
        "educational": "chiaro e didattico, ricco di esempi numerici",
        "sales_pitch": "persuasivo e convincente, dati a supporto",
    }
    tone_desc = tone_map.get(tone, tone_map["default"])
    extra = f"\nIstruzioni aggiuntive: {instructions}" if instructions else ""

    # Se abbiamo dati reali, costruisci un contesto dati conciso
    data_context = ""
    if vision_data and isinstance(vision_data, dict) and "error" not in vision_data:
        d = vision_data
        v24 = d.get("periods", {}).get("24h", {})
        v1h = d.get("periods", {}).get("1h", {})
        v6h = d.get("periods", {}).get("6h", {})
        v7d = d.get("periods", {}).get("7d", {})
        peak_hours_str = "; ".join(
            f"{p['hour']}: {p['total']} veicoli" for p in d.get("peak_hours", [])[:3]
        )
        hourly_rows = d.get("hourly_trend", [])
        # Prendere ultime 8 ore uniche
        seen = set()
        uniq = []
        for r in hourly_rows:
            h = r.get("hour", "")
            if h not in seen:
                seen.add(h)
                uniq.append(r)
        last8 = uniq[-8:]

        data_context = f"""
=== DATI REALI VIDEO ANALYTICS (usa questi) ===

RIEPILOGO:
- 1h: {v1h.get('cars',0)} auto, {v1h.get('people',0)} persone, {v1h.get('vehicles',0)} veicoli
- 6h: {v6h.get('cars',0)} auto, {v6h.get('people',0)} persone, {v6h.get('vehicles',0)} veicoli  
- 24h: {v24.get('cars',0)} auto, {v24.get('people',0)} persone, {v24.get('vehicles',0)} veicoli
- 7gg: {v7d.get('cars',0)} auto, {v7d.get('people',0)} persone, {v7d.get('vehicles',0)} veicoli
- Velocità media 24h: {d.get('avg_speed_24h',0)} km/h
- Punta: {d.get('peak_hour','N/D')} ({d.get('peak_cars',0)} veicoli)
- Auto %: {d.get('car_ratio',0)}% del traffico totale

DATI ORARI (ultime {len(last8)} ore):
{'; '.join(f"{r['hour']}: {r['cars']} auto/{r['people']} pers/{r['vehicles']} veic" for r in last8)}

TOP ORE PUNTA:
{peak_hours_str}

REGOLE PER CHART/TABLE:
- Chart: usa DATI ORARI sopra come chart_rows, headers=["Ora","Auto","Persone","Veicoli"], chart_type="line"
- Table: usa RIEPILOGO sopra come rows, headers=["Periodo","Auto","Persone","Veicoli"]
- Non inventare dati. Usa solo questi numeri.
=== FINE DATI REALI ===
"""

    sys_prompt = f"""Sei un creatore di presentazioni professionista di livello mondiale. Genera una presentazione strutturata in formato JSON RICCA DI DATI, GRAFICI E STATISTICHE.
{data_context}
REGOLE FONDAMENTALI:
1. Genera ESATTAMENTE {n_slides} slide
2. OGNI SLIDE DEVE CONTENERE DATI NUMERICI E STATISTICHE — mai solo testo qualitativo
3. INCLUDE ALMENO 2 slide di tipo "chart" con dati numerici realistici
4. INCLUDE ALMENO 1 slide di tipo "table" con dati strutturabili
5. Usa varietà di tipi: title, section, content, two_column, table, chart, thank_you
6. Prima slide: type="title" con title e subtitle
7. Ultima slide: type="thank_you" con title e subtitle
8. TONO: {tone_desc}
9. LINGUA: TUTTO in {language}

FORMATO PER type="chart":
- chart_type: "bar" | "line" | "pie" | "area" | "horizontal_bar"
- chart_headers: array di stringhe (primo elemento = etichette righe, resto = nomi serie)
- chart_rows: array di array di valori (primo valore per riga = etichetta, resto = numeri)
- ESEMPIO: {{"type":"chart","title":"Andamento Vendite","chart_type":"bar","chart_headers":["Trimestre","Nord","Sud","Centro"],"chart_rows":[["Q1",120,85,95],["Q2",145,92,110],["Q3",165,88,130],["Q4",200,120,150]]}}

FORMATO PER type="table":
- headers: array di stringhe (nomi colonne)
- rows: array di array di valori (stringhe o numeri)
- ESEMPIO: {{"type":"table","title":"Confronto Costi","headers":["Categoria","2024","2025","Variazione"],"rows":[["Affitto",12000,12500,"+4%"],["Trasporti",2400,2600,"+8%"],["Cibo",4800,5100,"+6%"]]}}

FORMATO PER type="two_column":
- col1_title, col2_title: stringhe
- columns: array di 2 array di stringhe (ognuna può includere dati numerici)

FORMATO PER type="content":
- items: array di stringhe — OGNI ITEM DEVE INIZIARE CON UN DATO NUMERICO

FORMATO PER type="section":
- title: stringa, subtitle: stringa descrittiva

CRITICO:
- OGNI slide DEVE avere un campo "title" non vuoto e pertinente
- chart_rows DEVE avere almeno 3 righe
- headers e chart_headers devono avere almeno 2 elementi
- items DEVE avere almeno 3 elementi (sempre! mai vuoto)
- columns deve avere 2 array con almeno 2 elementi ciascuno
- two_column DEVE sempre avere title, col1_title, col2_title non vuoti

⚠️ SE SONO STATI FORNITI DATI REALI (sopra nella sezione DATI REALI DA VIDEO ANALYTICS):
   Usa QUEI dati precisi per chart_rows, tabelle, e statistiche. Non modificarli.
   I chart devono riflettere i trend orari reali.
   Le tabelle devono mostrare i riepiloghi reali per periodo.

Rispondi SOLO con il JSON array, nient'altro. Nessun preambolo, nessuna spiegazione."""
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Genera una presentazione spettacolare e professionale su: {topic}. Esattamente {n_slides} slide. Ricca di dati, grafici, statistiche e tabelle.{extra}"}
    ]

    text = _chat(messages, temperature=0.3, max_tokens=12000)
    if not text:
        return None

    slides = _extract_json(text)
    if slides and isinstance(slides, list):
        return slides
    return None

def generate_slide_content(slide_title, slide_type, context, language="Italian"):
    """Genera contenuto dettagliato per una singola slide"""
    field_map = {
        "content": "items (array di 4-6 stringhe bullet point con DATI NUMERICI)",
        "section": "subtitle (stringa descrittiva)",
        "two_column": "col1_title, col2_title, columns (array di 2 array di 3-4 stringhe ciascuno con dati)",
        "table": "headers (array di 3-5 stringhe), rows (array di 3-5 array di valori con dati reali)",
        "chart": "chart_type (bar/line/pie/area/horizontal_bar), chart_headers, chart_rows (dati numerici realistici)",
    }
    fields = field_map.get(slide_type, "items (array di stringhe con dati numerici)")

    sys_prompt = f"""Sei un creatore di presentazioni. Genera contenuti per una slide specifica con DATI NUMERICI REALISTICI.
LINGUA: {language}
TIPO SLIDE: {slide_type}
TITOLO: {slide_title}
CAMPI DA COMPILARE: {fields}
CONTESTO: {context}

OGNI ELEMENTO DEVE CONTENERE DATI NUMERICI (percentuali, importi, quantità, anni).
Rispondi SOLO con un JSON object contenente i campi richiesti."""
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Genera il contenuto per la slide '{slide_title}' di tipo {slide_type} con dati numerici"}
    ]

    text = _chat(messages, temperature=0.5, max_tokens=2048)
    if text:
        return _extract_json(text)
    return None


def refine_description(prompt):
    """Migliora una descrizione breve in un topic più dettagliato per la presentazione"""
    messages = [
        {"role": "system", "content": "Sei un copywriter. Espandi questa breve descrizione in un topic dettagliato per una presentazione. Massimo 3 frasi. Diretto, nessun preambolo."},
        {"role": "user", "content": prompt}
    ]
    text = _chat(messages, temperature=0.5, max_tokens=512)
    return text.strip() if text else prompt


# ── TEMPLATE HTML SPETTACOLARE (Sentry + Premium Design) ──

HTML_TEMPLATES = {
    "corporate": {
        "bg": "#faf9fb", "fg": "#1c1028", "accent": "#6c5fc7", "accent2": "#b5aade",
        "light_bg": "#f3f1f5", "text": "#1c1028", "text_light": "#80708f",
        "border": "#dbd6e1", "card_bg": "#ffffff",
        "cat": ["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f","#edc948","#b07aa1","#ff9da7","#9c755f","#bab0ac"],
        "sem_green": "#2ba185", "sem_red": "#f55459", "sem_amber": "#d4953a",
        "font": "'Rubik','Inter','Segoe UI',sans-serif", "progress": "#6c5fc7"
    },
    "dark": {
        "bg": "#0d1117", "fg": "#e6edf3", "accent": "#58a6ff", "accent2": "#1f6feb",
        "light_bg": "#161b22", "text": "#c9d1d9", "text_light": "#8b949e",
        "border": "#30363d", "card_bg": "#161b22",
        "cat": ["#58a6ff","#f0883e","#ff7b72","#3fb950","#d2a8ff","#a5d6ff","#79c0ff","#ffa657","#bc8cff","#f778ba"],
        "sem_green": "#3fb950", "sem_red": "#ff7b72", "sem_amber": "#d4953a",
        "font": "'Rubik','Inter','Segoe UI',sans-serif", "progress": "#58a6ff"
    },
    "nature": {
        "bg": "#f5faf0", "fg": "#1a3a2a", "accent": "#2d8a4e", "accent2": "#4caf50",
        "light_bg": "#e8f5e9", "text": "#2e4534", "text_light": "#689f63",
        "border": "#c8e6c9", "card_bg": "#ffffff",
        "cat": ["#2d8a4e","#8bc34a","#ff9800","#4caf50","#009688","#795548","#ff5722","#607d8b","#3f51b5","#e91e63"],
        "sem_green": "#2ba185", "sem_red": "#e53935", "sem_amber": "#fdd835",
        "font": "'Rubik','Inter','Segoe UI',sans-serif", "progress": "#2d8a4e"
    },
    "sunset": {
        "bg": "#fef5ef", "fg": "#2d1b2e", "accent": "#ff6b35", "accent2": "#ff9f43",
        "light_bg": "#ffe8d6", "text": "#5a3a2a", "text_light": "#a08070",
        "border": "#ffccaa", "card_bg": "#ffffff",
        "cat": ["#ff6b35","#ffd93d","#ff9f43","#ee5a24","#f368e0","#54a0ff","#5f27cd","#01a3a4","#00d2d3","#ff9ff3"],
        "sem_green": "#2ba185", "sem_red": "#e17055", "sem_amber": "#fdcb6e",
        "font": "'Rubik','Inter','Segoe UI',sans-serif", "progress": "#ff6b35"
    },
    "ocean": {
        "bg": "#f0f8ff", "fg": "#0c2340", "accent": "#0077b6", "accent2": "#00b4d8",
        "light_bg": "#e0f0ff", "text": "#1a3a5c", "text_light": "#5a8aaa",
        "border": "#b0d4f0", "card_bg": "#ffffff",
        "cat": ["#0077b6","#00b4d8","#90e0ef","#023e8a","#48cae4","#0096c7","#ade8f4","#03045e","#0077b6","#00b4d8"],
        "sem_green": "#2ba185", "sem_red": "#e63946", "sem_amber": "#e9c46a",
        "font": "'Rubik','Inter','Segoe UI',sans-serif", "progress": "#0077b6"
    },
    "midnight": {
        "bg": "#0d1117", "fg": "#c9d1d9", "accent": "#58a6ff", "accent2": "#1f6feb",
        "light_bg": "#161b22", "text": "#c9d1d9", "text_light": "#8b949e",
        "border": "#30363d", "card_bg": "#161b22",
        "cat": ["#58a6ff","#3fb950","#f0883e","#d2a8ff","#ff7b72","#a5d6ff","#79c0ff","#ffa657","#bc8cff","#f778ba"],
        "sem_green": "#3fb950", "sem_red": "#ff7b72", "sem_amber": "#d4953a",
        "font": "'Rubik','Inter','Segoe UI',sans-serif", "progress": "#58a6ff"
    },
}

THEMES = list(HTML_TEMPLATES.keys())

def render_html(data, slides, theme="corporate", title=None, author=None):
    """Genera HTML presentazione SPETTACOLARE stile Sentry + Presenton"""
    t = HTML_TEMPLATES.get(theme, HTML_TEMPLATES["corporate"])
    title = title or data.get("title", "Presentazione")
    author = author or data.get("author", "J.A.R.V.I.S")
    slides = slides or []

    def esc(txt):
        return str(txt).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")

    def is_numeric(v):
        try:
            float(str(v).replace(',','.').replace('€','').replace('$','').replace('%','').strip())
            return True
        except:
            return float(v) if str(v).replace('.','',1).replace('-','',1).isdigit() else False

    def slide_html(sd, idx):
        st = sd.get("type", "content")
        stitle = esc(sd.get("title", ""))
        ssub = esc(sd.get("subtitle", ""))
        items = sd.get("items", [])
        if isinstance(items, str):
            items = [items]
        cols = sd.get("columns", sd.get("cols", [[], []]))
        col1_title = esc(sd.get("col1_title", sd.get("col1Title", "")))
        col2_title = esc(sd.get("col2_title", sd.get("col2Title", "")))
        headers = sd.get("headers", sd.get("chart_headers", []))
        rows = sd.get("rows", sd.get("chart_rows", []))
        chart_type = sd.get("chart_type", "bar")
        stag = sd.get("tag", "")
        if not stag:
            tag_map = {"title":"INTRODUZIONE","section":"SEZIONE","content":"APPROFONDIMENTO",
                       "two_column":"CONFRONTO","table":"DATI","chart":"ANALISI",
                       "thank_you":"CONCLUSIONE"}
            stag = tag_map.get(st, "")

        tag_html = f'<div class="tag tag-{st}">{esc(stag)}</div>' if stag else ''

        content_html = ""
        if st == "title":
            subtitle_block = f'<p class="subtitle">{ssub}</p>' if ssub else ''
            content_html = f'''<div class="slide-title">
              <div class="title-badge">{esc(author)}</div>
              <h1>{stitle}</h1>
              {subtitle_block}
            </div>'''
        elif st == "section":
            content_html = f'''<div class="slide-section">
              {tag_html}
              <h2>{stitle}</h2>
              {f'<p class="subtitle">{ssub}</p>' if ssub else ''}
            </div>'''
        elif st == "thank_you":
            content_html = f'''<div class="slide-thanks">
              <div class="thank-icon">✦</div>
              <h1>{stitle}</h1>
              {f'<p class="subtitle">{ssub}</p>' if ssub else ''}
              <div class="author-line">{esc(author)}</div>
            </div>'''
        elif st == "content" and items:
            bullets = "\n".join(f'<li><span class="bullet-marker"></span><span>{esc(i)}</span></li>' for i in items)
            content_html = f'''{tag_html}<h2>{stitle}</h2>
            <ul class="bullet-list">{bullets}</ul>'''
        elif st == "two_column":
            col1_items = "\n".join(f'<li>{esc(i)}</li>' for i in (cols[0] if cols else []))
            col2_items = "\n".join(f'<li>{esc(i)}</li>' for i in (cols[1] if len(cols) > 1 else []))
            content_html = f'''{tag_html}<h2>{stitle}</h2>
            <div class="two-col">
              <div class="col"><div class="col-head">{esc(col1_title or "")}</div><ul>{col1_items}</ul></div>
              <div class="col"><div class="col-head">{esc(col2_title or "")}</div><ul>{col2_items}</ul></div>
            </div>'''
        elif st == "table" and headers and rows:
            hdrs = "".join(f'<th>{esc(h)}</th>' for h in headers)
            rws = "".join(f'<tr>{"".join(f"<td>{esc(c)}</td>" for c in r[:len(headers)])}</tr>' for r in rows)
            content_html = f'''{tag_html}<h2>{stitle}</h2>
            <div class="table-wrap"><table><thead><tr>{hdrs}</tr></thead><tbody>{rws}</tbody></table></div>'''
        elif st == "chart":
            chart_id = f"chart-{idx}"
            # Build series data: first header element is label, rest are series names
            labels = [r[0] for r in rows] if rows else []
            series_list = []
            for j, h in enumerate(headers[1:]):
                vals = []
                for r in rows:
                    try:
                        v = str(r[j+1]).replace('€','').replace('$','').replace('%','').replace(',','.').strip()
                        vals.append(float(v))
                    except:
                        try:
                            vals.append(float(r[j+1]) if j+1 < len(r) else 0)
                        except:
                            vals.append(0)
                series_list.append({"name": h, "data": vals})
            has_data = any(any(v for v in s["data"]) for s in series_list)
            if not has_data:
                content_html = f'''{tag_html}<h2>{stitle}</h2>
                <div class="chart-wrap"><div class="chart-placeholder">📊 Dati in elaborazione</div></div>'''
            else:
                content_html = f'''{tag_html}<h2>{stitle}</h2>
                <div class="chart-wrap"><canvas id="{chart_id}"></canvas></div>
                <script>
                setTimeout(function(){{
                  renderChart({json.dumps(chart_id)},{json.dumps(chart_type)},
                    {json.dumps(labels)},{json.dumps(series_list)});
                }},100);
                </script>'''
        elif st == "image" and sd.get("image"):
            content_html = f'''{tag_html}<h2>{stitle}</h2>
            <div class="img-wrap"><img src="{esc(sd['image'])}" alt="{stitle}"></div>'''
        else:
            txt = esc(sd.get("content", ""))
            content_html = f'''{tag_html}<h2>{stitle}</h2>
            <p class="body-text">{txt}</p>''' if txt else f'{tag_html}<h2>{stitle}</h2>'

        return f'''<div class="slide" data-index="{idx}">
          <div class="slide-inner">{content_html}</div>
        </div>'''

    slides_html = "\n".join(slide_html(sd, i) for i, sd in enumerate(slides))
    cat_js = json.dumps(t["cat"])
    font_url = "https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;600;700&display=swap"

    full_html = f'''<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{font_url}" rel="stylesheet">
<style>
:root {{
  --bg: {t['bg']}; --fg: {t['fg']}; --accent: {t['accent']}; --accent2: {t['accent2']};
  --light-bg: {t['light_bg']}; --text: {t['text']}; --text-light: {t['text_light']};
  --border: {t['border']}; --card-bg: {t['card_bg']};
  --sem-green: {t['sem_green']}; --sem-red: {t['sem_red']}; --sem-amber: {t['sem_amber']};
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:{t['font']}; background:var(--bg); color:var(--text); overflow:hidden; height:100vh; font-size:0.9rem; line-height:1.7; }}
.progress {{ position:fixed; top:0; left:0; height:3px; background:{t['progress']}; transition:width 0.4s cubic-bezier(0.4,0,0.2,1); z-index:100; }}
.glyph-watermark {{ position:fixed; top:20px; left:24px; z-index:50; opacity:0.1; pointer-events:none; display:flex; align-items:center; gap:10px; }}
.glyph-watermark svg {{ width:28px; height:26px; }}
.watermark-title {{ font-size:0.8rem; font-weight:600; letter-spacing:-0.01em; color:var(--text-light); }}
.slides-container {{ position:relative; width:100vw; height:100vh; }}
.slide {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; opacity:0; transition:opacity 0.5s ease, transform 0.5s ease; pointer-events:none; padding:60px 80px; transform:scale(0.97); }}
.slide.active {{ opacity:1; pointer-events:auto; transform:scale(1); }}
.slide-inner {{ max-width:1000px; width:100%; }}
.anim h2, .anim .subtitle, .anim .bullet-list, .anim .two-col,
.anim .table-wrap, .anim .chart-wrap, .anim .tag, .anim .cards,
.anim .col, .anim p, .anim .img-wrap, .anim .thank-icon, .anim .author-line {{
  opacity:0; animation:fadeUp 0.6s ease both;
}}
.anim .d1 {{ animation-delay:0.1s; }}
.anim .d2 {{ animation-delay:0.2s; }}
.anim .d3 {{ animation-delay:0.35s; }}
@keyframes fadeUp {{ from{{opacity:0;transform:translateY(18px)}} to{{opacity:1;transform:translateY(0)}} }}
@keyframes fadeScale {{ from{{opacity:0;transform:scale(0.92)}} to{{opacity:1;transform:scale(1)}} }}
.anim .slide-title h1, .anim .slide-thanks h1 {{ animation:fadeScale 0.7s ease both; }}

h1 {{ font-size:3rem; font-weight:700; color:var(--accent); margin-bottom:0.3em; line-height:1.12; letter-spacing:-0.03em; }}
h2 {{ font-size:1.55rem; font-weight:600; color:var(--fg); margin-bottom:0.5em; line-height:1.25; letter-spacing:-0.02em; }}
.subtitle {{ font-size:1.05rem; color:var(--text-light); font-weight:400; line-height:1.6; max-width:700px; }}
.body-text {{ font-size:0.95rem; line-height:1.8; color:var(--text); max-width:860px; }}
.title-badge {{ display:inline-block; font-size:0.65rem; font-weight:600; text-transform:uppercase; letter-spacing:0.12em; padding:4px 12px; border:1px solid var(--border); border-radius:20px; color:var(--text-light); margin-bottom:20px; }}
.author-line {{ margin-top:30px; font-size:0.8rem; color:var(--text-light); letter-spacing:0.03em; }}
.slide-title, .slide-thanks {{ text-align:center; display:flex; flex-direction:column; align-items:center; }}
.slide-title h1, .slide-thanks h1 {{ font-size:3.2rem; }}
.slide-section {{ text-align:center; padding:40px 0; }}
.slide-thanks .thank-icon {{ font-size:3rem; color:var(--accent); margin-bottom:16px; opacity:0.6; }}
.tag {{ display:inline-block; font-size:0.66rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; padding:4px 10px; border-radius:4px; margin-bottom:10px; }}
.tag-title {{ background:var(--light-bg); color:var(--accent); }}
.tag-section {{ background:var(--light-bg); color:var(--accent); }}
.tag-content {{ background:rgba(108,95,199,0.1); color:var(--accent); }}
.tag-two_column {{ background:rgba(242,142,43,0.1); color:{t['cat'][1]}; }}
.tag-table {{ background:rgba(22,163,74,0.1); color:{t['cat'][4]}; }}
.tag-chart {{ background:rgba(225,87,89,0.1); color:{t['cat'][2]}; }}
.tag-thank_you {{ background:var(--light-bg); color:var(--text-light); }}

ul.bullet-list {{ list-style:none; padding:0; max-width:900px; }}
ul.bullet-list li {{ display:flex; gap:12px; padding:12px 0 12px 0; font-size:0.95rem; line-height:1.6; border-bottom:1px solid var(--border); align-items:flex-start; }}
ul.bullet-list li:last-child {{ border-bottom:none; }}
.bullet-marker {{ flex-shrink:0; width:8px; height:8px; border-radius:50%; background:var(--accent); margin-top:8px; opacity:0.7; }}

.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:28px; }}
.two-col .col {{ background:var(--card-bg); border-radius:10px; padding:24px; border:1px solid var(--border); }}
.col-head {{ font-weight:600; font-size:0.85rem; color:var(--accent); text-transform:uppercase; letter-spacing:0.05em; margin-bottom:12px; }}
.two-col .col ul {{ list-style:none; padding:0; }}
.two-col .col ul li {{ padding:6px 0; font-size:0.9rem; line-height:1.5; position:relative; padding-left:16px; }}
.two-col .col ul li::before {{ content:""; position:absolute; left:0; top:12px; width:5px; height:5px; border-radius:50%; background:var(--accent); opacity:0.5; }}

.table-wrap {{ overflow-x:auto; border-radius:8px; border:1px solid var(--border); }}
table {{ width:100%; border-collapse:collapse; font-size:0.9rem; }}
th {{ background:var(--accent); color:#fff; padding:12px 16px; text-align:left; font-weight:500; font-size:0.8rem; letter-spacing:0.03em; }}
th:first-child {{ border-radius:6px 0 0 0; }}
th:last-child {{ border-radius:0 6px 0 0; }}
td {{ padding:10px 16px; border-bottom:1px solid var(--border); }}
tr:last-child td {{ border-bottom:none; }}
tr:nth-child(even) td {{ background:var(--light-bg); }}

.chart-wrap {{ width:100%; max-width:920px; margin:0 auto; }}
.chart-wrap canvas {{ width:100% !important; height:380px !important; }}
.chart-placeholder {{ height:200px; display:flex; align-items:center; justify-content:center; color:var(--text-light); font-size:1.1rem; background:var(--light-bg); border-radius:8px; }}
.img-wrap {{ text-align:center; }}
.img-wrap img {{ max-width:80%; max-height:55vh; border-radius:10px; box-shadow:0 8px 30px rgba(0,0,0,0.08); }}
nav {{ position:fixed; bottom:0; left:0; right:0; display:flex; align-items:center; justify-content:center; gap:18px; padding:14px 20px; z-index:100; }}
nav button {{ background:none; border:none; color:var(--text-light); padding:4px 10px; border-radius:6px; cursor:pointer; font-size:0.85rem; transition:all 0.2s; font-family:inherit; }}
nav button:hover {{ color:var(--accent); background:var(--light-bg); }}
nav button:disabled {{ opacity:0.2; cursor:default; }}
nav button:disabled:hover {{ color:var(--text-light); background:none; }}
.dots {{ display:flex; gap:6px; align-items:center; }}
.dot {{ width:6px; height:6px; border-radius:50%; background:var(--border); cursor:pointer; transition:all 0.25s; }}
.dot.on {{ background:var(--accent); transform:scale(1.3); }}
.slide-number {{ font-size:0.75rem; color:var(--text-light); font-variant-numeric:tabular-nums; min-width:50px; text-align:center; }}
</style>
</head>
<body>
<div class="progress" id="progress" style="width:0%"></div>
<div class="glyph-watermark" id="watermark" style="display:none">
  <svg viewBox="0 0 72 66" aria-hidden="true"><path d="M29,2.26a4.67,4.67,0,0,0-8,0L14.42,13.53A32.21,32.21,0,0,1,32.17,40.19H27.55A27.68,27.68,0,0,0,12.09,17.47L6,28a15.92,15.92,0,0,1,9.23,12.17H4.62A.76.76,0,0,1,4,39.06l2.94-5a10.74,10.74,0,0,0-3.36-1.9l-2.91,5a4.54,4.54,0,0,0,1.69,6.24A4.66,4.66,0,0,0,4.62,44H19.15a19.4,19.4,0,0,0-8-17.31l2.31-4A23.87,23.87,0,0,1,23.76,44H36.07a35.88,35.88,0,0,0-16.41-31.8l4.67-8a.77.77,0,0,1,1.05-.27c.53.29,20.29,34.77,20.66,35.17a.76.76,0,0,1-.68,1.13H40.6q.09,1.91,0,3.81h4.78A4.59,4.59,0,0,0,50,39.43a4.49,4.49,0,0,0-.62-2.28Z" transform="translate(11, 11)" fill="{t['text_light']}"></path></svg>
  <span class="watermark-title">{esc(title)}</span>
</div>
<div class="slides-container">
  {slides_html}
</div>
<nav>
  <button id="prev-btn" onclick="go(-1)" disabled>←</button>
  <div class="dots" id="dots"></div>
  <span class="slide-number" id="slide-num">1 / {len(slides)}</span>
  <button id="next-btn" onclick="go(1)">→</button>
</nav>
<script>
var cur = 0, total = {len(slides)};
var slides = document.querySelectorAll('.slide');
var dotsEl = document.getElementById('dots');
for(var i=0;i<total;i++){{var d=document.createElement('div');d.className='dot'+(i===0?' on':'');d.onclick=(function(i){{return function(){{show(i)}}}})(i);dotsEl.appendChild(d);}}
function show(i){{
  if(i<0||i>=total)return;
  slides.forEach(function(s,j){{
    s.classList.toggle('active',j===i);
    if(j===i){{setTimeout(function(){{s.querySelector('.slide-inner').classList.add('anim');}},30);}}
    else{{s.querySelector('.slide-inner').classList.remove('anim');}}
  }});
  var ds=document.querySelectorAll('.dot');
  ds.forEach(function(d,j){{d.classList.toggle('on',j===i);}});
  document.getElementById('slide-num').textContent=(i+1)+' / '+total;
  document.getElementById('prev-btn').disabled=i===0;
  document.getElementById('next-btn').disabled=i===total-1;
  document.getElementById('progress').style.width=((i+1)/total*100)+'%';
  document.getElementById('watermark').style.display=i===0?'none':'flex';
  cur=i;
}}
function go(d){{show(cur+d);}}
document.addEventListener('keydown',function(e){{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;
  if(e.key==='ArrowRight'||e.key===' '||e.key==='ArrowDown'){{e.preventDefault();go(1);}}
  else if(e.key==='ArrowLeft'||e.key==='ArrowUp'){{e.preventDefault();go(-1);}}
}});
show(0);

function renderChart(id,type,labels,series){{
  var c=document.getElementById(id);
  if(!c)return;
  var W=c.parentElement.clientWidth||800;
  var ratio=window.devicePixelRatio||2;
  c.width=W*ratio;c.height=400*ratio;
  c.style.width=W+'px';c.style.height='400px';
  var ctx=c.getContext('2d');
  ctx.scale(ratio,ratio);
  var H=400,pad={{top:35,left:65,right:30,bottom:55}},cw=W-pad.left-pad.right,ch=H-pad.top-pad.bottom;
  var allVals=[];
  series.forEach(function(s){{s.data.forEach(function(v){{allVals.push(v);}});}});
  if(allVals.length===0)return;
  var maxVal=Math.max(1,...allVals)*1.12;
  var colors={cat_js};
  var borderColor='{t["border"]}';
  var textLight='{t["text_light"]}';
  var textColor='{t["text"]}';
  var bgColor='{t["bg"]}';
  function drawGrid(){{
    ctx.strokeStyle=borderColor;ctx.lineWidth=0.5;
    ctx.font='11px Rubik,Inter,sans-serif';ctx.fillStyle=textLight;ctx.textAlign='right';
    for(var i=0;i<=4;i++){{var y=pad.top+ch-(i/4)*ch;ctx.beginPath();ctx.moveTo(pad.left,y);ctx.lineTo(pad.left+cw,y);ctx.stroke();ctx.fillText(Math.round((i/4)*maxVal),pad.left-8,y+4);}}
  }}
  // Legend
  var lx=pad.left,ly=10;
  series.forEach(function(s,i){{
    ctx.fillStyle=colors[i%colors.length];ctx.fillRect(lx,ly,12,12);
    ctx.fillStyle=textColor;ctx.font='11px Rubik,Inter,sans-serif';ctx.textAlign='left';
    ctx.fillText(s.name,lx+16,ly+11);
    lx+=ctx.measureText(s.name).width+36;
    if(lx>W-100){{lx=pad.left;ly+=18;}}
  }});
  if(type==='bar'||type==='horizontal_bar'){{
    if(type==='bar'){{
      drawGrid();
      var groups=labels.length,serCount=series.length;
      if(groups===0)return;
      var gap=groups>1?cw*0.1:cw*0.3;
      var bw=(cw-gap)/(groups*serCount);
      series.forEach(function(s,si){{
        s.data.forEach(function(v,i){{
          var x=pad.left+i*((cw-gap)/groups)+(cw-gap)/groups*0.1+si*bw;
          if(groups>1)x=pad.left+(gap/2)+i*((cw-gap-gap/2)/groups)+si*bw;
          var barH=(v/maxVal)*ch;
          var grd=ctx.createLinearGradient(x,pad.top+ch,x,pad.top+ch-barH);
          grd.addColorStop(0,colors[(si+1)%colors.length]);
          grd.addColorStop(1,colors[si%colors.length]);
          ctx.fillStyle=grd;
          var r=Math.min(bw*0.35,4);
          var bw2=bw*0.65;
          ctx.beginPath();
          ctx.moveTo(x,pad.top+ch);
          ctx.lineTo(x,pad.top+ch-barH+r);
          ctx.quadraticCurveTo(x,pad.top+ch-barH,x+r,pad.top+ch-barH);
          ctx.lineTo(x+bw2-r,pad.top+ch-barH);
          ctx.quadraticCurveTo(x+bw2,pad.top+ch-barH,x+bw2,pad.top+ch-barH+r);
          ctx.lineTo(x+bw2,pad.top+ch);
          ctx.closePath();
          ctx.fill();
          // Value label
          ctx.fillStyle=textColor;ctx.font='10px Rubik,Inter,sans-serif';ctx.textAlign='center';
          ctx.fillText(v,x+bw2/2,pad.top+ch-barH-6);
        }});
      }});
      ctx.fillStyle=textLight;ctx.font='11px Rubik,Inter,sans-serif';ctx.textAlign='center';
      labels.forEach(function(l,i){{
        var x=pad.left+(gap/2)+i*((cw-gap-gap/2)/groups)+((cw-gap-gap/2)/groups)/2;
        ctx.fillText(l,x,H-12);
      }});
    }} else {{
      // horizontal_bar
      var barH=Math.min(30,(ch-20)/(labels.length*series.length));
      series.forEach(function(s,si){{
        s.data.forEach(function(v,i){{
          var y=pad.top+20+i*(series.length*barH+8)+si*barH;
          var barW=(v/maxVal)*cw;
          var grd=ctx.createLinearGradient(pad.left,y,pad.left+barW,y);
          grd.addColorStop(0,colors[si%colors.length]);
          grd.addColorStop(1,colors[(si+2)%colors.length]);
          ctx.fillStyle=grd;
          ctx.beginPath();
          ctx.roundRect(pad.left,y,barW,barH-2,barH/2);
          ctx.fill();
          ctx.fillStyle=textColor;ctx.font='10px Rubik,Inter,sans-serif';ctx.textAlign='left';
          ctx.fillText(v,pad.left+barW+6,y+barH/2+3);
        }});
      }});
      ctx.fillStyle=textLight;ctx.font='10px Rubik,Inter,sans-serif';ctx.textAlign='right';
      labels.forEach(function(l,i){{
        var y=pad.top+20+i*(series.length*barH+8)+(series.length*barH)/2+3;
        ctx.fillText(l,pad.left-8,y);
      }});
      // Draw vertical grid lines
      ctx.strokeStyle=borderColor;ctx.lineWidth=0.5;
      for(var i=0;i<=4;i++){{var x=pad.left+(i/4)*cw;ctx.beginPath();ctx.moveTo(x,pad.top);ctx.lineTo(x,pad.top+ch);ctx.stroke();}}
    }}
  }} else if(type==='pie'){{
    var cx=W/2,cy=H/2-10,r=Math.min(cw,ch)/2-20;
    var totalVal=allVals.reduce(function(a,b){{return a+b;}},0);
    if(totalVal===0)return;
    var startAngle=-Math.PI/2;
    series.forEach(function(s,i){{
      var val=s.data.reduce(function(a,b){{return a+b;}},0);
      var sliceAngle=(val/totalVal)*Math.PI*2;
      ctx.fillStyle=colors[i%colors.length];
      ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,r,startAngle,startAngle+sliceAngle);ctx.closePath();ctx.fill();
      ctx.strokeStyle=bgColor;ctx.lineWidth=2.5;ctx.stroke();
      var mid=startAngle+sliceAngle/2;
      var lx2=cx+Math.cos(mid)*r*0.55,ly2=cy+Math.sin(mid)*r*0.55;
      ctx.fillStyle='#fff';ctx.font='bold 13px Rubik,Inter,sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
      ctx.fillText(Math.round(val/totalVal*100)+'%',lx2,ly2);
      startAngle+=sliceAngle;
    }});
    // Labels
    var ly3=H-18*series.length-8;
    series.forEach(function(s,i){{
      ctx.fillStyle=colors[i%colors.length];ctx.fillRect(pad.left+20,ly3,12,12);
      ctx.fillStyle=textColor;ctx.font='11px Rubik,Inter,sans-serif';ctx.textAlign='left';
      ctx.fillText(s.name,pad.left+38,ly3+10);
      ly3+=18;
    }});
  }} else if(type==='area'){{
    drawGrid();
    var step=Math.max(1,cw/(labels.length-1||1));
    series.forEach(function(s,si){{
      ctx.beginPath();
      var pts=[];
      s.data.forEach(function(v,i){{
        var x=pad.left+i*step,y=pad.top+ch-(v/maxVal)*ch;
        pts.push({{x:x,y:y}});
        if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }});
      ctx.strokeStyle=colors[si%colors.length];ctx.lineWidth=2.5;ctx.stroke();
      // Fill area
      ctx.lineTo(pts[pts.length-1].x,pad.top+ch);
      ctx.lineTo(pts[0].x,pad.top+ch);
      ctx.closePath();
      var grd=ctx.createLinearGradient(0,pad.top,0,pad.top+ch);
      grd.addColorStop(0,colors[si%colors.length]+'40');
      grd.addColorStop(1,colors[si%colors.length]+'05');
      ctx.fillStyle=grd;ctx.fill();
      // Dots
      pts.forEach(function(p){{
        ctx.fillStyle=bgColor;ctx.beginPath();ctx.arc(p.x,p.y,4,0,Math.PI*2);ctx.fill();
        ctx.strokeStyle=colors[si%colors.length];ctx.lineWidth=2;ctx.stroke();
      }});
    }});
    ctx.fillStyle=textLight;ctx.font='11px Rubik,Inter,sans-serif';ctx.textAlign='center';
    labels.forEach(function(l,i){{ctx.fillText(l,pad.left+i*step,H-12);}});
  }} else {{
    // line (default)
    drawGrid();
    var step=Math.max(1,cw/(labels.length-1||1));
    series.forEach(function(s,si){{
      ctx.beginPath();
      s.data.forEach(function(v,i){{
        var x=pad.left+i*step,y=pad.top+ch-(v/maxVal)*ch;
        if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }});
      ctx.strokeStyle=colors[si%colors.length];ctx.lineWidth=2.5;ctx.stroke();
      // Dots
      s.data.forEach(function(v,i){{
        var x=pad.left+i*step,y=pad.top+ch-(v/maxVal)*ch;
        ctx.fillStyle=bgColor;ctx.beginPath();ctx.arc(x,y,4.5,0,Math.PI*2);ctx.fill();
        ctx.strokeStyle=colors[si%colors.length];ctx.lineWidth=2.5;ctx.stroke();
        // Value
        ctx.fillStyle=textLight;ctx.font='10px Rubik,Inter,sans-serif';ctx.textAlign='center';
        ctx.fillText(v,x,y-10);
      }});
    }});
    ctx.fillStyle=textLight;ctx.font='11px Rubik,Inter,sans-serif';ctx.textAlign='center';
    labels.forEach(function(l,i){{ctx.fillText(l,pad.left+i*step,H-12);}});
  }}
}}
</script>
</body>
</html>'''
    return full_html
