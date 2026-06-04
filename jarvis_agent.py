#!/usr/bin/env python3
"""jarvis_agent.py — Groq agent con memoria, context-aware, tool routing, streaming v5.1
Novità v5.1: smart LLM tier routing (fast 8b / deep 70b) basato sulla complessità del messaggio
"""
import json, requests, time
from pathlib import Path
from jarvis_tools import execute_tool, TOOLS_SCHEMA, memory

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/chat"

# ── SMART TIER ROUTING ──
FAST_MODEL  = "llama-3.1-8b-instant"   # ~3-4× più veloce, ottimo per query semplici
DEEP_MODEL  = "llama-3.3-70b-versatile" # più potente, per analisi/coding/testo lungo

FAST_TRIGGERS = [
    # saluti e cortesie
    "ciao", "salve", "buongiorno", "buonasera", "grazie", "prego",
    "come stai", "che ora", "che giorno", "che tempo",
    # domande ultra brevi
    "ok", "si", "no", "sì", "dai", "perfetto",
]
DEEP_TRIGGERS = [
    # coding e analisi
    "codice", "programma", "scrivi", "analizza", "spiega dettagliatamente",
    "refactor", "debug", "errore nel codice", "implementa",
    # testi lunghi
    "riassumi", "traduci", "parafrasa", "ricerca",
    "progetta", "architettura", "strategia", "piano",
    # performance / tecnico
    "performance", "ottimizza", "produzione", "migliorare", "confronta",
    "differenza tra", "come funziona", "perché", "spiegami",
]

def _detect_complexity(msg: str) -> str:
    """Ritorna il modello Groq ottimale per questa query.
    Fast (8b) per query semplici/brevi, Deep (70b) per analisi/codice/testi lunghi."""
    low = msg.lower().strip()
    words = low.split()
    # Controlla deep PRIMA del short-check (4 parole ma "analizza il codice" è deep)
    if any(t in low for t in DEEP_TRIGGERS):
        return DEEP_MODEL
    # Messaggi molto brevi → fast
    if len(words) <= 5:
        return FAST_MODEL
    # Trigger espliciti fast
    if any(t in low for t in FAST_TRIGGERS) and len(words) <= 12:
        return FAST_MODEL
    # Messaggi lunghi (> 25 parole) o con punto interrogativo multiplo → deep
    if len(words) > 25 or low.count("?") >= 2:
        return DEEP_MODEL
    # Default: usa il modello configurato (normalmente il 70b)
    return None  # None = usa cfg["groq"]["model"] invariato

SYSTEM_PROMPT = """Sei J.A.R.V.I.S. — Just A Rather Very Intelligent System, l'assistente AI personale di Daniele sul Mac Mini M2 Pro.

CAPACITÀ:
- Controllo completo del Mac: app, file, sistema, volume, brightness, screenshot
- Calendar: leggi e crea eventi
- Mail: leggi email non lette, cerca e invia email con Apple Mail
- Notes: crea, cerca e leggi note
- Browser: apri URL, cerca, gestisci tab Chrome, automazione Playwright
- File management: crea, leggi, cerca, organizza, elimina file
- Memoria: ricordi fatti, preferenze, decisioni (persistono tra sessioni)
- Shortcuts: esegui Shortcuts macOS
- Planner: piani multi-step per compiti complessi
- Screen awareness: sai quali app sono aperte e in primo piano
- OCR: leggi testo dallo schermo con Apple Vision framework
- Computer Use: controlla mouse, tastiera, drag & drop
- RAG: database documenti con ricerca semantica vector embeddings
- Git: status, commit, branch, diff, log
- Web search: DuckDuckGo con risultati completi
- Approval flow: approvazione per azioni sensibili
- Blender 3D: controlla Blender via MCP — crea oggetti, imposta materiali, esegui render,
  scarica asset da PolyHaven e Sketchfab. Usa blender_* tools quando l'utente parla di
  3D, modellazione, render, oggetti 3D, scene Blender, HDRI, texture, ecc.
  (richiede Blender aperto con addon blender_addon.py attivo)

REGOLE:
1. Quando l'utente chiede di fare qualcosa, usa lo strumento appropriato
2. Quando l'utente chiede informazioni come meteo, notizie, sport, risultati, ORA APRI UNA FINESTRA DEL BROWSER con il sito appropriato invece di rispondere a voce
   - Meteo → apri ilmeteo.it o Google Weather
   - Notizie → apri Google News o repubblica.it
   - Sport → apri google.com/search?q=risultati+sport
   - Traduzioni → apri translate.google.it
   - YouTube → apri youtube.com
   - Mappe → apri maps.google.com
   - Amazon → apri amazon.it
3. Ricorda le preferenze dell'utente con memory_remember
4. Sii conciso e professionale come l'AI di Tony Stark
5. Rispondi sempre in italiano
6. Per compiti complessi, crea un piano con planner_create
7. Prima di rispondere, consulta la memoria per contesto personale
8. Usa markdown per formattare: code block, liste, grassetto
9. Per leggere testo dallo schermo usa screen_ocr
10. Per automazione browser avanzata usa browser_navigate e browser_extract
11. Per controllare mouse/tastiera usa computer_mouse_click, computer_keyboard_type
12. Per cercare documenti usa rag_search
"""

class JarvisAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.history = []

    def _detect_direct_actions(self, user_message):
        """Rileva azioni dirette senza chiamare l'LLM"""
        from jarvis_tools import execute_tool
        import re
        from datetime import datetime, timedelta
        actions_done = []
        lower = user_message.lower().strip()

        # invia email (PRIORITÀ — prima di calendario, per evitare falsi positivi)
        if not actions_done and any(w in lower for w in ['invia email', 'invia una email', 'manda email', 'manda una email', 'spedisci email']):
            import re as _re
            to = subject = body = ''
            # Extract "to" — stop at "con", "dicendo", "che", "oggetto", "corpo", end
            a_m = _re.search(r'(?:invia|manda|spedisci)\s+(?:una\s+)?email\s+a\s+([\w.@+\-_]+(?:\s+[\w.@+\-_]+)*?)(?:\s+con\s+|\s+dicendo\s+|\s+che\s+|\s+oggetto\s+|\s+corpo\s+|$)', user_message, _re.IGNORECASE)
            if a_m:
                to = a_m.group(1).strip().rstrip('.,!?')
            og_m = _re.search(r'(?:oggetto|subject)\s*:?\s*["""]?(.+?)["""]?(?:\s+corpo\s*:?\s*|["""]?\s*$)', user_message, _re.IGNORECASE)
            if og_m:
                subject = og_m.group(1).strip().rstrip('.,!?')
            co_m = _re.search(r'(?:corpo|body|contenuto|messaggio)\s*:?\s*["""]?(.+?)["""]?(?:\s*$)', user_message, _re.IGNORECASE)
            if co_m:
                body = co_m.group(1).strip().rstrip('.,!?')
            if not body:
                # Fallback: take everything after "dicendo che" / "dicendo" / "che"
                fb = _re.search(r'(?:dicendo\s+che|dicendo|che)\s+(.+)$', user_message, _re.IGNORECASE)
                if fb:
                    body = fb.group(1).strip().rstrip('.,!?')
            if to:
                result = execute_tool('mail_send', {'to': to, 'subject': subject or 'Inviata da JARVIS', 'body': body or ' '})
                actions_done.append(f'mail_send: {result}')
                actions_done.append(f'SPEECH:{"✅ " + result.strip("✅ ")}')
            else:
                actions_done.append(f'SPEECH:Per inviare email serve il destinatario. Dimmi "invia email a [indirizzo] con oggetto [oggetto] e corpo [testo]"')

        # crea evento calendario (PRIORITÀ — prima di "apri app")
        if not actions_done and any(w in lower for w in ['appuntamento', 'evento', 'riunione', 'meeting']):
            time_match = re.search(r'(\d{1,2}):(\d{2})', lower)
            hour = int(time_match.group(1)) if time_match else 12
            minute = int(time_match.group(2)) if time_match else 0
            day_offset = 0
            if 'domani' in lower: day_offset = 1
            elif 'dopodomani' in lower: day_offset = 2
            elif 'lun' in lower: day_offset = (0 - datetime.now().weekday()) % 7 or 7
            elif 'mar' in lower: day_offset = (1 - datetime.now().weekday()) % 7 or 7
            elif 'mer' in lower: day_offset = (2 - datetime.now().weekday()) % 7 or 7
            elif 'gio' in lower: day_offset = (3 - datetime.now().weekday()) % 7 or 7
            elif 'ven' in lower: day_offset = (4 - datetime.now().weekday()) % 7 or 7
            elif 'sab' in lower: day_offset = (5 - datetime.now().weekday()) % 7 or 7
            elif 'dom' in lower: day_offset = (6 - datetime.now().weekday()) % 7 or 7
            # Estrai titolo — cerca testo dopo "appuntamento"/"evento"
            title_match = re.search(r'(?:appuntamento|evento|riunione|meeting)\s+(?:per\s+|del\s+|di\s+)?(.+?)(?:\s+alle?\s+\d{1,2}:\d{2}|\s+domani|\s+dopodomani|\s+lunedì|\s+martedì|\s+mercoledì|\s+giovedì|\s+venerdì|\s+sabato|\s+domenica|\s+oggi|$)', user_message, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # Fallback: prendi tutto dopo la parola chiave
                kw_match = re.search(r'(?:appuntamento|evento|riunione|meeting)\s+(.*)', user_message, re.IGNORECASE)
                title = kw_match.group(1).strip() if kw_match else "Appuntamento"
            # Rimuovi parole temporali dal titolo
            title = re.sub(r'\b(domani|dopodomani|oggi|lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\b', '', title, flags=re.IGNORECASE).strip()
            # Pulisci articolo iniziale e parole comuni
            title = re.sub(r'^(nuovo|un|una|il|la|lo|gli|le|i|del|della|dei|degli|delle|dal|dall|con|per|tra|fra)\s+', '', title, flags=re.IGNORECASE).strip()
            title = re.sub(r'\d{1,2}:\d{2}', '', title).strip()
            title = re.sub(r'\s+', ' ', title).strip()
            if not title or len(title) < 2: title = "Appuntamento"
            event_date = datetime.now() + timedelta(days=day_offset)
            event_date = event_date.replace(hour=hour, minute=minute, second=0)
            start_str = event_date.isoformat()
            result = execute_tool('calendar_create', {'title': title, 'start_date': start_str, 'duration_minutes': 60})
            actions_done.append(f'calendar_create: {result}')

        # apri calendario
        if any(w in lower for w in ['apri calendario', 'mostra calendario', 'apri il calendario']):
            result = execute_tool('calendar_open', {})
            actions_done.append(f'calendar_open: {result}')

        # apri app (generico — solo se nessuna azione già fatta)
        if any(w in lower for w in ['apri ', 'lancia ', 'avvia ']) and not actions_done:
            for app in ['safari','chrome','spotify','terminal','finder','vs code','messages',
                        'calendar','notes','mail','music','whatsapp','discord','slack','preview',
                        'xcode','docker','figma','calcolatrice','impostazioni']:
                if app in lower:
                    result = execute_tool('open_app', {'app_name': app})
                    actions_done.append(f'open_app: {result}')
                    break

        # ── APRI SITI WEB (prima di "cerca") ──
        web_urls = {
            'meteo': 'https://www.ilmeteo.it/',
            'tempo': 'https://www.ilmeteo.it/',
            'previsioni': 'https://www.ilmeteo.it/',
            'weather': 'https://weather.com/it-IT/weather/today',
            'notizie': 'https://news.google.com/home?hl=it&gl=IT&ceid=IT:it',
            'news': 'https://news.google.com/home?hl=it&gl=IT&ceid=IT:it',
            'repubblica': 'https://www.repubblica.it/',
            'corriere': 'https://www.corriere.it/',
            'youtube': 'https://www.youtube.com/',
            'google': 'https://www.google.it/',
            'wikipedia': 'https://it.wikipedia.org/',
            'amazon': 'https://www.amazon.it/',
            'gmail': 'https://mail.google.com/',
            'drive': 'https://drive.google.com/',
            'maps': 'https://maps.google.com/',
            'traduttore': 'https://translate.google.it/',
            'translator': 'https://translate.google.it/',
        }
        for keyword, url in web_urls.items():
            if keyword in lower and any(w in lower for w in ['apri', 'mostra', 'vai su', 'vedi']):
                result = execute_tool('open_url', {'url': url})
                actions_done.append(f'open_url ({keyword}): {result}')
                break

        # meteo/tempo — usa Open-Meteo API per dati reali
        if not actions_done and any(w in lower for w in ['che tempo fa', 'com\'è il tempo', 'come sta il tempo', 'previsioni meteo', 'meteo', 'che tempo']):
            city_match = re.search(r'(?:a|per|del|della|di)\s+([A-ZÀ-Ö][a-zà-ö]+(?:\s+[A-ZÀ-Ö][a-zà-ö]+)*)', user_message)
            city = city_match.group(1).strip() if city_match else 'Berlino'
            from datetime import datetime, timedelta
            now = datetime.now()
            day_offset = 0; day_label = "oggi"
            if 'dopodomani' in lower: day_offset = 2; day_label = "dopodomani"
            elif 'domani' in lower: day_offset = 1; day_label = "domani"
            elif 'luned' in lower: day_offset = (0 - now.weekday()) % 7 or 7; day_label = "lunedì"
            elif 'marted' in lower: day_offset = (1 - now.weekday()) % 7 or 7; day_label = "martedì"
            elif 'mercoled' in lower: day_offset = (2 - now.weekday()) % 7 or 7; day_label = "mercoledì"
            elif 'gioved' in lower: day_offset = (3 - now.weekday()) % 7 or 7; day_label = "giovedì"
            elif 'venerd' in lower: day_offset = (4 - now.weekday()) % 7 or 7; day_label = "venerdì"
            elif 'sabato' in lower: day_offset = (5 - now.weekday()) % 7 or 7; day_label = "sabato"
            elif 'domenica' in lower: day_offset = (6 - now.weekday()) % 7 or 7; day_label = "domenica"
            elif 'settimana' in lower or 'prossimi giorni' in lower:
                day_offset = -1; day_label = "previsioni"
            import json as _json
            weather_card = None; speech = f"Ecco il meteo per {city} {day_label}."
            try:
                import requests as _req
                geo_r = _req.get(f'https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=it&format=json', timeout=8)
                if geo_r.ok and geo_r.json().get('results'):
                    r0 = geo_r.json()['results'][0]
                    lat, lon = r0['latitude'], r0['longitude']
                    city_name = r0.get('name', city)
                    if day_offset == -1:
                        fc_r = _req.get(f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max&timezone=auto&forecast_days=7', timeout=8)
                        if fc_r.ok:
                            d = fc_r.json().get('daily', {})
                            giorni_lista = ["lunedì","martedì","mercoledì","giovedì","venerdì","sabato","domenica"]
                            parts = []; forecast_data = []
                            for i, dt_str in enumerate(d.get('time', [])):
                                dt = datetime.strptime(dt_str, '%Y-%m-%d')
                                wc = d.get('weather_code', [0])[i]
                                desc = _weather_code_desc(wc)
                                parts.append(f"{giorni_lista[dt.weekday()]}: {desc}, max {d['temperature_2m_max'][i]}°, min {d['temperature_2m_min'][i]}°")
                                forecast_data.append({"day": giorni_lista[dt.weekday()], "desc": desc, "temp_max": d['temperature_2m_max'][i], "temp_min": d['temperature_2m_min'][i], "code": wc})
                            speech = f"Previsioni per {city_name}: " + ". ".join(parts) + "."
                            weather_card = {"city": city_name, "label": "Settimana", "forecast": forecast_data}
                    else:
                        fc_days = max(day_offset + 1, 1)
                        fc_r = _req.get(f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max&timezone=auto&forecast_days={fc_days}', timeout=8)
                        if fc_r.ok:
                            d = fc_r.json().get('daily', {})
                            idx = min(day_offset, len(d.get('time', [])) - 1)
                            if idx >= 0:
                                t_max = d['temperature_2m_max'][idx]; t_min = d['temperature_2m_min'][idx]
                                wc = d['weather_code'][idx] if idx < len(d.get('weather_code', [])) else 0
                                desc = _weather_code_desc(wc)
                                wind = d.get('wind_speed_10m_max', [0])[idx] if idx < len(d.get('wind_speed_10m_max', [])) else 0
                                speech = f"A {city_name} {day_label}: {desc}, massima {t_max}°, minima {t_min}°, vento {wind} km/h."
                                weather_card = {"city": city_name, "label": day_label, "today": {"desc": desc, "temp_max": t_max, "temp_min": t_min, "wind": wind, "code": wc}}
            except Exception as e:
                print(f"[Meteo] {e}")
            actions_done.append(f'meteo {city}: {speech}')
            actions_done.append(f'SPEECH:{speech}')
            if weather_card:
                actions_done.append(f'WEATHER_CARD:{_json.dumps(weather_card, ensure_ascii=False)}')

        # webcam / satellite — apre webcam widget nel dashboard
        if not actions_done and any(w in lower for w in ['fammi vedere', 'mostrami', 'webcam', 'satellite', 'mostra', 'telecamera', 'videocamera']):
            wc_city = None
            # 1) Try to extract city right after a trigger prefix
            for prefix in ['fammi vedere ', 'mostrami ', 'webcam ', 'satellite ', 'mostra ', 'telecamera ', 'videocamera ', 'apri satellite ']:
                if prefix in lower:
                    rest = user_message[lower.index(prefix)+len(prefix):].strip().rstrip('.,!?')
                    if rest:
                        # Take words that start with uppercase (city/proper names)
                        words = rest.split()
                        candidate = ''
                        for w in words:
                            w_clean = w.rstrip('.,!?')
                            if w_clean and w_clean[0].isupper():
                                candidate += (' ' + w_clean if candidate else w_clean)
                            else:
                                break
                        if candidate:
                            wc_city = candidate
                            break
                        # Fallback: capitalize all words (handles "milano" -> "Milano")
                        wc_city = ' '.join(w.rstrip('.,!?').capitalize() for w in words)
                        break
            # 2) Try preposition pattern
            if not wc_city:
                city_match = re.search(r'(?:a|di|del|della|per|su)\s+([A-ZÀ-Ö][a-zà-ö]+(?:\s+[A-ZÀ-Ö][a-zà-ö]+)*)', user_message)
                if city_match:
                    wc_city = city_match.group(1).strip()
            # 3) Try conversation history for last city mentioned
            if not wc_city:
                for msg in reversed(self.history):
                    text = msg.get('content', '') if isinstance(msg, dict) else ''
                    city_in = re.search(r'(?:fammi vedere|mostrami|webcam|mostra|satellite|apertura webcam per|per\s+mostrare|visualizzare|vista satellitare di)\s+([A-ZÀ-Ö][a-zà-ö]+(?:\s+[A-ZÀ-Ö][a-zà-ö]+)*)', text, re.IGNORECASE)
                    if city_in:
                        wc_city = city_in.group(1).strip()
                        break
            # 4) Default
            if not wc_city:
                wc_city = "Milano"
            if wc_city:
                wc_lat, wc_lon = None, None
                try:
                    import requests as _req
                    wc_r = _req.get(f'https://geocoding-api.open-meteo.com/v1/search?name={wc_city}&count=1&language=it&format=json', timeout=8)
                    if wc_r.ok and wc_r.json().get('results'):
                        wc_r0 = wc_r.json()['results'][0]
                        wc_lat, wc_lon = wc_r0['latitude'], wc_r0['longitude']
                        wc_city = wc_r0.get('name', wc_city)
                except Exception as e:
                    print(f"[Webcam geocode] {e}")
                # Dynamic YouTube search for latest working stream
                wc_video_id = None
                try:
                    import urllib.parse as _up
                    for q in [f'{wc_city} webcam diretta 4K', f'{wc_city} live webcam 4K', f'live webcam {wc_city}']:
                        yt_r = _req.get(
                            f'https://www.youtube.com/results?search_query={_up.quote(q)}',
                            timeout=8, headers={'User-Agent': 'Mozilla/5.0'}
                        )
                        import re as _re
                        ids = _re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', yt_r.text)
                        if ids:
                            wc_video_id = ids[0]
                            print(f"[Webcam] YouTube found: {wc_video_id} for {wc_city} (query: {q})")
                            break
                except Exception as e2:
                    print(f"[Webcam yt search] {e2}")
                wc_data = {"city": wc_city, "lat": wc_lat, "lon": wc_lon, "video_id": wc_video_id}
                actions_done.append(f'WEBCAM:{json.dumps(wc_data, ensure_ascii=False)}')
                speech = f"Apertura webcam per {wc_city}."
                actions_done.append(f'SPEECH:{speech}')
                actions_done.append(f'webcam {wc_city}: {speech}')

        # notizie senza "apri"
        if not actions_done and any(w in lower for w in ['ultime notizie', 'news di oggi', 'notizie oggi', 'cosa succede nel mondo']):
            result = execute_tool('open_url', {'url': 'https://news.google.com/home?hl=it&gl=IT&ceid=IT:it'})
            actions_done.append(f'news: {result}')

        # screenshot
        if not actions_done and ('screenshot' in lower or 'schermata' in lower or 'schermo' in lower):
            result = execute_tool('take_screenshot', {'mode': 'full'})
            actions_done.append(f'take_screenshot: {result}')

        # volume
        elif 'volume' in lower and ('muto' in lower or 'silenzi' in lower or 'mute' in lower):
            result = execute_tool('system_volume', {'action': 'mute'})
            actions_done.append(f'system_volume: {result}')
        elif 'volume' in lower and ('alto' in lower or 'su' in lower or 'max' in lower):
            result = execute_tool('system_volume', {'action': 'set', 'level': 80})
            actions_done.append(f'system_volume: {result}')
        elif 'volume' in lower and ('basso' in lower or 'giù' in lower or 'min' in lower):
            result = execute_tool('system_volume', {'action': 'set', 'level': 20})
            actions_done.append(f'system_volume: {result}')

        # cerca — apri Google con la query
        elif 'cerca ' in lower or 'googla ' in lower or 'cerca su ' in lower:
            query = user_message.lower().replace('cerca ','').replace('googla ','').replace('su internet','').replace('su google','').strip()
            url = f'https://www.google.com/search?q={query.replace(" ", "+")}'
            result = execute_tool('open_url', {'url': url})
            actions_done.append(f'google_search ({query}): {result}')

        # url
        elif lower.startswith('apri http') or lower.startswith('apri www'):
            url = user_message.split(' ', 1)[1] if ' ' in user_message else ''
            if url:
                result = execute_tool('open_url', {'url': url})
                actions_done.append(f'open_url: {result}')

        # blocca
        elif 'blocca' in lower and ('schermo' in lower or 'mac' in lower):
            result = execute_tool('lock_screen', {})
            actions_done.append(f'lock_screen: {result}')

        # clipboard
        elif 'clipboard' in lower or 'appunti' in lower:
            result = execute_tool('clipboard_action', {'action': 'read'})
            actions_done.append(f'clipboard: {result}')

        # sysinfo
        elif 'sysinfo' in lower or 'info sistema' in lower or 'stato mac' in lower:
            result = execute_tool('get_system_info', {'info_type': 'all'})
            actions_done.append(f'sysinfo: {result}')

        # calendario oggi
        if not actions_done and 'calendario' in lower and ('oggi' in lower or 'oggi?' in lower):
            result = execute_tool('calendar_today', {})
            actions_done.append(f'calendar: {result}')

        # email non lette / leggi email
        if not actions_done and 'email' in lower and ('non lette' in lower or 'nuove' in lower or 'leggi' in lower):
            result = execute_tool('mail_read_aloud', {})
            actions_done.append(f'mail: {result}')

        # organizza downloads
        if not actions_done and 'organizza' in lower and 'download' in lower:
            result = execute_tool('files_organize', {})
            actions_done.append(f'files: {result}')

        # musica
        if not actions_done and any(w in lower for w in ['metti in pausa', 'pausa musica', 'stop musica']):
            result = execute_tool('play_music', {'action': 'pause'})
            actions_done.append(f'music: {result}')
        if not actions_done and any(w in lower for w in ['riproduci musica', 'play musica', 'metti musica']):
            result = execute_tool('play_music', {'action': 'play'})
            actions_done.append(f'music: {result}')
        if not actions_done and ('prossima canzone' in lower or 'skip' in lower):
            result = execute_tool('play_music', {'action': 'next'})
            actions_done.append(f'music: {result}')

        return actions_done

    def chat(self, user_message):
        # 1. rileva azioni dirette
        actions_done = self._detect_direct_actions(user_message)

        memory.log_conversation("user", user_message)

        # Se azione diretta eseguita → rispondi subito senza chiamare LLM
        if actions_done:
            # Cerca messaggio vocale speciale (SPEECH:)
            speech_msg = None
            filtered = []
            for a in actions_done:
                if a.startswith('SPEECH:'):
                    speech_msg = a[7:]
                else:
                    filtered.append(a)
            if speech_msg:
                reply = speech_msg
            else:
                reply = "✅ " + "\n".join(filtered)
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": reply})
            if len(self.history) > 40:
                self.history = self.history[-40:]
            memory.log_conversation("assistant", reply)
            return reply, filtered

        # 2. carica contesto memoria
        memory_context = memory.get_context_for_prompt(user_message, max_items=3)

        # 3. costruisci messaggi
        self.history.append({"role": "user", "content": user_message})
        if len(self.history) > 40:
            self.history = self.history[-40:]

        system_msg = SYSTEM_PROMPT + "\n\n" + memory_context
        messages = [{"role": "system", "content": system_msg}] + self.history

        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json"
        }

        chosen_model = _detect_complexity(user_message) or self.cfg["groq"]["model"]
        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": float(self.cfg["groq"]["temperature"]),
            "max_tokens": 2048,
        }
        if chosen_model == FAST_MODEL:
            print(f"  [Tier] FAST ({FAST_MODEL})")
        else:
            print(f"  [Tier] DEEP ({chosen_model})")

        try:
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=45)
            if not resp.ok:
                err = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {}
                msg = err.get('error', {}).get('message', resp.text[:200])
                print(f"[Groq {resp.status_code}] {msg}")
                if self.cfg.get("ollama", {}).get("enabled", False):
                    print("[INFO] Groq fallito, provo Ollama...")
                    return self._ollama_chat(messages, payload), actions_done
                return f"[Errore Groq {resp.status_code}] {msg}", actions_done

            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            self.history.append({"role": "assistant", "content": reply})
            memory.log_conversation("assistant", reply)
            return reply, actions_done

        except Exception as e:
            print(f"[Groq exception] {e}")
            if self.cfg.get("ollama", {}).get("enabled", False):
                print("[INFO] Groq fallito, provo Ollama...")
                return self._ollama_chat(messages, payload), actions_done
            return f"[Errore connessione] {e}", actions_done

    def _ollama_chat(self, messages, payload):
        """Fallback locale con Ollama"""
        ollama_cfg = self.cfg.get("ollama", {})
        model = ollama_cfg.get("model", "llama3.2")
        timeout = ollama_cfg.get("timeout", 60)
        ollama_payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        try:
            resp = requests.post(OLLAMA_URL, json=ollama_payload, timeout=timeout)
            resp.raise_for_status()
            reply = resp.json()["message"]["content"].strip()
            self.history.append({"role": "assistant", "content": reply})
            memory.log_conversation("assistant", reply)
            return reply
        except Exception as e:
            return f"[Errore Ollama] {e}"

    def reset(self):
        self.history.clear()

    def chat_stream(self, user_message):
        """Chat con streaming SSE — ritorna (reply, elapsed)"""
        import time
        actions_done = self._detect_direct_actions(user_message)
        memory.log_conversation("user", user_message)

        # Se azione diretta eseguita → rispondi subito senza chiamare LLM
        if actions_done:
            speech_msg = None
            filtered = []
            for a in actions_done:
                if a.startswith('SPEECH:'):
                    speech_msg = a[7:]
                else:
                    filtered.append(a)
            reply = speech_msg if speech_msg else "✅ " + "\n".join(filtered)
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": reply})
            if len(self.history) > 40:
                self.history = self.history[-40:]
            memory.log_conversation("assistant", reply)
            return reply, 0.0

        memory_context = memory.get_context_for_prompt(user_message, max_items=3)
        self.history.append({"role": "user", "content": user_message})
        if len(self.history) > 40:
            self.history = self.history[-40:]

        system_msg = SYSTEM_PROMPT + "\n\n" + memory_context
        messages = [{"role": "system", "content": system_msg}] + self.history

        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json"
        }

        chosen_model = _detect_complexity(user_message) or self.cfg["groq"]["model"]
        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": float(self.cfg["groq"]["temperature"]),
            "max_tokens": 2048,
            "stream": True
        }
        if chosen_model == FAST_MODEL:
            print(f"  [Tier] FAST stream ({FAST_MODEL})")
        else:
            print(f"  [Tier] DEEP stream ({chosen_model})")

        t0 = time.time()
        full_reply = ""
        try:
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=60, stream=True)
            if not resp.ok:
                err = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {}
                msg = err.get('error', {}).get('message', resp.text[:200])
                # Fallback a Ollama (non-streaming)
                if self.cfg.get("ollama", {}).get("enabled", False):
                    print("[INFO] Groq stream fallito, provo Ollama...")
                    reply = self._ollama_chat(messages, payload)
                    return reply, round(time.time()-t0, 2)
                return f"[Errore Groq {resp.status_code}] {msg}", round(time.time()-t0, 2)

            for line in resp.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_reply += content
                        except:
                            pass

            elapsed = round(time.time() - t0, 2)
            self.history.append({"role": "assistant", "content": full_reply})
            memory.log_conversation("assistant", full_reply)
            return full_reply, elapsed

        except Exception as e:
            print(f"[Groq stream exception] {e}")
            # Fallback a Ollama (non-streaming)
            if self.cfg.get("ollama", {}).get("enabled", False):
                print("[INFO] Groq stream fallito, provo Ollama...")
                reply = self._ollama_chat(messages, payload)
                return reply, round(time.time()-t0, 2)
            return f"[Errore connessione] {e}", round(time.time()-t0, 2)

# ── UTILITY ──
def _weather_code_desc(code):
    """Converte WMO weather code in descrizione italiana"""
    codes = {
        0: "sereno", 1: "prevalentemente sereno", 2: "parzialmente nuvoloso", 3: "coperto",
        45: "nebbioso", 48: "nebbia con ghiaccio", 51: "pioggia leggera", 53: "pioggia moderata",
        55: "pioggia intensa", 56: "pioggia gelata leggera", 57: "pioggia gelata intensa",
        61: "pioggia debole", 63: "pioggia moderata", 65: "pioggia forte",
        66: "pioggia gelata debole", 67: "pioggia gelata forte",
        71: "neve debole", 73: "neve moderata", 75: "neve forte", 77: "granelli di neve",
        80: "rovesci deboli", 81: "rovesci moderati", 82: "rovesci violenti",
        85: "rovesci di neve deboli", 86: "rovesci di neve forti",
        95: "temporale", 96: "temporale con grandine", 99: "temporale violento con grandine"
    }
    return codes.get(code, f"codice {code}")
