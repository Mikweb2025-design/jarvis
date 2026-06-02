#!/usr/bin/env python3
"""jarvis_agent.py — Groq agent con memoria, context-aware, tool routing, streaming v5.0"""
import json, requests, time
from pathlib import Path
from jarvis_tools import execute_tool, TOOLS_SCHEMA, memory

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT = """Sei J.A.R.V.I.S. — Just A Rather Very Intelligent System, l'assistente AI personale di Daniele sul Mac Mini M2 Pro.

CAPACITÀ:
- Controllo completo del Mac: app, file, sistema, volume, brightness, screenshot
- Calendar: leggi e crea eventi
- Mail: leggi email non lette e cerca (read-only)
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

        # crea evento calendario (PRIORITÀ — prima di "apri app")
        if any(w in lower for w in ['appuntamento', 'evento', 'riunione', 'meeting']):
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

        # meteo/tempo senza "apri" — cerca città e apri ilmeteo.it
        if not actions_done and any(w in lower for w in ['che tempo fa', 'com\'è il tempo', 'come sta il tempo', 'previsioni meteo', 'meteo oggi']):
            city_match = re.search(r'(?:a|per|del|della|di)\s+([A-ZÀ-Ö][a-zà-ö]+(?:\s+[A-ZÀ-Ö][a-zà-ö]+)*)', user_message)
            city = city_match.group(1) if city_match else 'Italia'
            url = f'https://www.google.com/search?q=meteo+{city.replace(" ", "+")}'
            result = execute_tool('open_url', {'url': url})
            actions_done.append(f'meto {city}: {result}')

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

        # email non lette
        if not actions_done and 'email' in lower and ('non lette' in lower or 'nuove' in lower):
            result = execute_tool('mail_unread', {})
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

        # 2. carica contesto memoria
        memory_context = memory.get_context_for_prompt(user_message, max_items=3)

        # 3. log conversazione
        memory.log_conversation("user", user_message)

        # 4. costruisci messaggi
        self.history.append({"role": "user", "content": user_message})
        if len(self.history) > 40:
            self.history = self.history[-40:]

        system_msg = SYSTEM_PROMPT + "\n\n" + memory_context
        messages = [{"role": "system", "content": system_msg}] + self.history

        if actions_done:
            messages.append({
                "role": "system",
                "content": "Azioni già eseguite: " + "; ".join(actions_done)
            })

        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.cfg["groq"]["model"],
            "messages": messages,
            "temperature": float(self.cfg["groq"]["temperature"]),
            "max_tokens": 2048,
        }

        try:
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=45)
            if not resp.ok:
                err = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {}
                msg = err.get('error', {}).get('message', resp.text[:200])
                print(f"[Groq {resp.status_code}] {msg}")
                # Fallback a Ollama
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
            # Fallback a Ollama
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
        memory_context = memory.get_context_for_prompt(user_message, max_items=3)
        memory.log_conversation("user", user_message)

        self.history.append({"role": "user", "content": user_message})
        if len(self.history) > 40:
            self.history = self.history[-40:]

        system_msg = SYSTEM_PROMPT + "\n\n" + memory_context
        messages = [{"role": "system", "content": system_msg}] + self.history

        if actions_done:
            messages.append({
                "role": "system",
                "content": "Azioni già eseguite: " + "; ".join(actions_done)
            })

        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.cfg["groq"]["model"],
            "messages": messages,
            "temperature": float(self.cfg["groq"]["temperature"]),
            "max_tokens": 2048,
            "stream": True
        }

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
