#!/usr/bin/env python3
"""jarvis_agent.py — Groq agent con memoria, context-aware, tool routing, streaming v5.1
Novità v5.1: smart LLM tier routing (fast 8b / deep 70b) basato sulla complessità del messaggio
"""
import json, requests, time, re
from pathlib import Path
from jarvis_tools import execute_tool, TOOLS_SCHEMA, memory
from jarvis_memory import KnowledgeGraph
from jarvis_rag import rag

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
- Goals/OKR: crea obiettivi con key results misurabili, traccia progressi
- Providers: switcha tra Groq, Ollama, OpenAI, Gemini, Anthropic
- Network diagnostics: IP pubblico, ping, DNS, speed test
- World Map: griglia webcam mondo (Milano, Venezia, Tokyo, Berlino, New York, Sydney)
- MCP (Model Context Protocol): connetti server esterni (GitHub, Slack, filesystem)
- Home Assistant: controlla smart home (luci, switch, sensori, termostato) su mikweb.info. ha_states per lista entità, ha_service per comandi
- Blender 3D: controlla Blender via MCP. Hai questi tool: blender_status,
  blender_scene, blender_execute (esegui QUALSIASI codice bpy), blender_create,
  blender_delete, blender_material, blender_render, blender_screenshot,
  blender_setup_avatar, blender_focus_view.
  REGOLA BLENDER IMPORTANTE: per creare/modellare QUALSIASI cosa (cane, casa,
  albero, ecc.) chiama UNA SOLA VOLTA blender_execute con TUTTO il codice bpy
  completo: crea le primitive, assegna i materiali colorati (mat.use_nodes=True,
  nodo BSDF_PRINCIPLED, Base Color) a OGNI parte SUBITO dopo averla creata
  riferendoti a bpy.context.active_object. NON fare più chiamate separate, NON
  usare blender_material come tool a parte, NON chiamare focus/screenshot
  (avvengono in automatico). Una chiamata sola, codice completo e autosufficiente.

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
13. Goals/OKR: goals_create per obiettivi, goals_list per vedere progressi, goals_update_kr per aggiornare key results
14. Providers: providers_switch per cambiare LLM (groq/ollama/openai/gemini/anthropic), providers_list per vedere stato
15. Network: network_connectivity per diagnostica internet, network_speedtest per velocità
16. MCP: mcp_list per vedere server, mcp_enable per attivare (github, slack, filesystem), mcp_call per usare tool
17. Home Assistant: ha_states per vedere lo stato di tutte le entità, ha_state per un'entità specifica, ha_service per controllare luci, switch, termostato, ecc. (domain=light, switch, climate, media_player...). Usa ha_config per info sulla versione HA. ha_dashboard per aprire la dashboard HA nel browser
"""

class JarvisAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.history = []
        # ── Knowledge Graph ──
        self.graph = KnowledgeGraph(memory.db)
        # ── Conversational Awareness ──
        self.conversation_summary = ""
        self.current_topic = "general"
        self.topic_history = []
        self.turn_count = 0

    # ── TOPIC DETECTION ────────────────────────────────────────────────────
    TOPIC_KEYWORDS = {
        "code": ["codice", "programma", "python", "script", "function", "bug", "debug",
                 "repo", "git", "commit", "branch", "api", "server", "database", "sql",
                 "algoritmo", "classe", "metodo", "variabile", "refactor", "test",
                 "coding", "sviluppo", "software", "deploy"],
        "business": ["riunione", "meeting", "progetto", "scadenza", "cliente", "fattura",
                     "budget", "obiettivo", "kpi", "report", "strategia", "business",
                     "lavoro", "ufficio", "team", "manager", "presentazione",
                     "fatturato", "crescita", "produttività"],
        "wellbeing": ["benessere", "salute", "relax", "pausa", "meditazione", "yoga",
                      "palestra", "corsa", "dieta", "sonno", "stress", "ansia",
                      "tranquillo", "calma", "respiro", "energia", "umore",
                      "riposo", "mindfulness", "benessere"],
        "casual": ["ciao", "come stai", "che fai", "raga", "amico", "bella",
                   "tutto bene", "che si dice", "novità", "weekend", "serata",
                   "grazie", "prego", "perfetto", "ok", "bello"],
    }

    TONE_INSTRUCTIONS = {
        "code": """
TONO: Chirurgico e tecnico. Vai dritto al punto.
- Usa terminologia tecnica precisa (nomi di funzioni, variabili, framework)
- Dai risposte concise con esempi di codice quando utile
- Evita fronzoli, superlativi, linguaggio emotivo
- Se c'è un bug, spiega causa ed effetto in modo logico""",

        "business": """
TONO: Professionale e pragmatico. Orientato ai risultati.
- Struttura la risposta in modo chiaro (fatti, implicazioni, azioni consigliate)
- Sii diretto ma educato, come un consulente senior
- Quantifica quando possibile (tempi, costi, impatti)
- Evita dettagli tecnici superflui""",

        "wellbeing": """
TONO: Incoraggiante e caloroso. Supportivo ma non invadente.
- Usa un linguaggio positivo e rassicurante
- Offri suggerimenti pratici, non solo teorie
- Riconosci lo sforzo dell'utente
- Mantieni un tono caldo ma professionale, come un coach""",

        "casual": """
TONO: Amichevole e rilassato. Come parlare con un amico.
- Risposte brevi e naturali, come in una conversazione tra amici
- Puoi usare un po' di ironia leggera quando appropriato
- Niente fronzoli, sii spontaneo
- Chiedi all'utente come procedere se la richiesta è vaga""",

        "general": """
TONO: Equilibrato e professionale. Come l'AI di Tony Stark.
- Sii conciso, competente, leggermente ironico quando appropriato
- Bilancia precisione tecnica e chiarezza espositiva
- Adatta il livello di dettaglio alla complessità della domanda""",
    }

    def _detect_topic(self, text):
        """Rileva il topic principale del messaggio."""
        low = text.lower().strip()
        if not low:
            return "general"
        scores = {}
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            scores[topic] = sum(k in low for k in keywords)
        # Penalizza casual se il messaggio è lungo (probabilmente non è solo un saluto)
        if len(low.split()) > 8:
            scores["casual"] = scores.get("casual", 0) * 0.3
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _get_tone_instructions(self, topic):
        """Restituisce le istruzioni di tono per il topic rilevato."""
        return self.TONE_INSTRUCTIONS.get(topic, self.TONE_INSTRUCTIONS["general"])

    # ── CONVERSATIONAL AWARENESS ───────────────────────────────────────────

    def _update_conversation_summary(self, user_msg, reply):
        """Aggiorna il riassunto della conversazione in corso."""
        self.turn_count += 1
        topic = self._detect_topic(user_msg)
        self.topic_history.append(topic)
        # Tieni solo gli ultimi 5 topic
        if len(self.topic_history) > 5:
            self.topic_history = self.topic_history[-5:]

        # Topic prevalente
        if self.topic_history:
            self.current_topic = max(set(self.topic_history), key=self.topic_history.count)

        # Aggiorna il riassunto ogni 2 turni per non appesantire
        if self.turn_count % 2 == 0 and reply:
            snippet_user = user_msg[:80].strip()
            snippet_reply = reply[:80].strip()
            old = self.conversation_summary
            new_entry = f"[{self.turn_count}] Utente: {snippet_user}… → Assistente: {snippet_reply}…"
            # Tieni solo le ultime 3 entry
            entries = [e for e in self.conversation_summary.split("\n") if e.strip()]
            entries.append(new_entry)
            if len(entries) > 3:
                entries = entries[-3:]
            self.conversation_summary = "\n".join(entries)

        # Estrai conoscenza dal grafo
        if reply:
            self.graph.extract_from_conversation(user_msg, reply)

    def _get_conversation_context(self):
        """Restituisce il contesto conversazionale da iniettare nel prompt."""
        parts = []
        if self.conversation_summary:
            parts.append(f"RIASSUNTO CONVERSAZIONE:\n{self.conversation_summary}")
        parts.append(f"TOPICO CORRENTE: {self.current_topic}")
        return "\n\n".join(parts)

    def _build_system_prompt(self, user_message):
        """Costruisce il system prompt completo con memoria, grafo, RAG, tono e contesto."""
        topic = self._detect_topic(user_message)
        tone = self._get_tone_instructions(topic)

        # Memoria classica
        memory_context = memory.get_context_for_prompt(user_message, max_items=3)

        # Grafo di conoscenza
        graph_context = self.graph.get_context_for_prompt(user_message)

        # RAG — contesto da documenti (solo per domande sostanziali)
        rag_context = ""
        if len(user_message.split()) >= 3:
            try:
                rag_context = rag.query_context(user_message, max_chunks=3)
            except Exception as e:
                print(f"[RAG] query_context error: {e}")

        # Contesto conversazionale
        conv_context = self._get_conversation_context()

        # Assemblea
        parts = [SYSTEM_PROMPT]
        if rag_context:
            parts.append(rag_context)
        if graph_context:
            parts.append(graph_context)
        if memory_context:
            parts.append(memory_context)
        if conv_context:
            parts.append(conv_context)
        parts.append(tone)

        return "\n\n".join(parts)

    def _blender_ai_code(self, request):
        """Usa l'LLM per generare codice Python bpy che realizza la richiesta 3D.
        Ritorna (codice, errore)."""
        sys_prompt = (
            "Sei un esperto di Blender Python API (bpy) per Blender 4.x e 5.x. "
            "Genera SOLO codice Python eseguibile che realizza la richiesta dell'utente nella scena 3D.\n"
            "REGOLE FERREE:\n"
            "1. Output SOLO codice Python puro. NIENTE spiegazioni, NIENTE markdown, NIENTE ```.\n"
            "2. Costruisci l'oggetto componendo primitive (cubi, sfere, cilindri, coni) con bpy.ops.mesh.primitive_*_add, posizionate e scalate.\n"
            "3. Raggruppa le parti: alla fine seleziona tutte le parti create e uniscile con bpy.ops.object.join(), poi rinomina l'oggetto risultante in modo sensato.\n"
            "4. Applica materiali colorati: crea bpy.data.materials.new(...), use_nodes=True, trova il nodo con node.type=='BSDF_PRINCIPLED' e imposta inputs['Base Color'].default_value=(r,g,b,1).\n"
            "5. Tutto attorno all'origine (0,0,0), dimensioni 1-2 unità Blender.\n"
            "6. NON cancellare oggetti esistenti (no select_all+delete) a meno che la richiesta lo chieda.\n"
            "7. Il codice deve essere autosufficiente, deterministico e senza errori di sintassi.\n"
            "8. Inizia sempre con 'import bpy' e 'import math' se servono.\n"
        )
        payload = {
            "model": self.cfg["groq"]["model"],
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Crea in Blender: {request}"},
            ],
            "temperature": 0.4,
            "max_tokens": 1500,
        }
        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=45)
            if not resp.ok:
                return None, f"Groq {resp.status_code}"
            code = resp.json()["choices"][0]["message"]["content"].strip()
            # Rimuovi eventuali fence markdown
            import re as _re
            code = _re.sub(r'^```[a-zA-Z]*\n?', '', code)
            code = _re.sub(r'\n?```$', '', code).strip()
            return code, None
        except Exception as e:
            return None, str(e)

    def _detect_direct_actions(self, user_message):
        """Rileva azioni dirette senza chiamare l'LLM"""
        from jarvis_tools import execute_tool
        import re
        from datetime import datetime, timedelta
        actions_done = []
        lower = user_message.lower().strip()

        # ── BLENDER: ora gestito dal LOOP AGENTICO (tool calling nativo) ───
        # Il blocco regex sotto è DISATTIVATO: le richieste Blender passano
        # all'LLM che sceglie i blender_* tools da solo (architettura agentica).
        _blender_kw = False  # era: any(w in lower for w in ['blender','renderizza',...])
        if _blender_kw:
            # stato / connessione
            if any(w in lower for w in ['status', 'stato', 'connesso', 'attivo', 'funziona', 'online', 'controlla']):
                result = execute_tool('blender_status', {})
                actions_done.append(result)

            # scena / oggetti
            elif any(w in lower for w in ['scena', 'oggetti', 'mostra', 'lista', 'elenca', 'info', "c'è", 'hai in', 'cosa ha']):
                result = execute_tool('blender_scene', {})
                actions_done.append(result)

            # importa/setup avatar
            elif any(w in lower for w in ['importa', 'carica', 'setup', 'prepara', 'avatar', 'personaggio', 'modello']):
                import os
                result = execute_tool('blender_setup_avatar', {})
                actions_done.append(result)
                # Mostra screenshot del viewport in chat
                execute_tool('blender_screenshot', {'save_path': '/tmp/blender_viewport.png'})
                if os.path.exists('/tmp/blender_viewport.png'):
                    actions_done.append('IMAGE:/api/image?file=blender_viewport.png')

            # inquadra / aggiorna vista
            elif any(w in lower for w in ['inquadra', 'aggiorna vista', 'aggiorna viewport', 'mostra avatar', 'focus', 'centra']):
                result = execute_tool('blender_focus_view', {})
                actions_done.append(result)

            # render
            elif any(w in lower for w in ['renderizza', 'render', 'esegui render', 'fai render', 'avvia render']):
                import os
                out = '/tmp/blender_render.png'
                result = execute_tool('blender_render', {'output_path': out})
                actions_done.append(result)
                if os.path.exists(out):
                    actions_done.append('IMAGE:/api/image?file=blender_render.png')

            # screenshot viewport
            elif any(w in lower for w in ['screenshot', 'schermata', 'viewport', 'anteprima']):
                import os
                out = '/tmp/blender_viewport.png'
                result = execute_tool('blender_screenshot', {'save_path': out})
                actions_done.append(result)
                if os.path.exists(out):
                    actions_done.append('IMAGE:/api/image?file=blender_viewport.png')

            # elimina oggetto
            elif any(w in lower for w in ['elimina', 'cancella', 'rimuovi', 'delete']):
                nm = re.search(r'(?:elimina|cancella|rimuovi|delete)\s+(?:l\'?|il\s+)?["\']?(\w[\w ]*?)["\']?$', user_message, re.IGNORECASE)
                name = nm.group(1).strip() if nm else 'Cube'
                result = execute_tool('blender_delete', {'name': name})
                actions_done.append(result)

            # crea / genera oggetto — LLM genera il codice bpy (qualsiasi cosa, non solo primitive)
            elif any(w in lower for w in ['crea', 'aggiungi', 'inserisci', 'metti', 'add', 'nuovo',
                                          'fai', 'fammi', 'genera', 'costruisci', 'disegna', 'modella',
                                          'build', 'make']):
                import os
                # Estrai la descrizione: tutto dopo il verbo, rimuovendo "in/su blender"
                req = re.sub(r'\b(in|su|con|usando)\s+blender\b', '', user_message, flags=re.IGNORECASE)
                req = re.sub(r'^\s*(crea(?:mi)?|aggiungi|inserisci|metti|fai|fammi|genera(?:mi)?|costruisci(?:mi)?|disegna(?:mi)?|modella|build|make|add)\s+', '', req, flags=re.IGNORECASE).strip()
                if not req:
                    req = user_message
                # Primitive semplici → via diretta veloce (nessun LLM)
                _types = {'cubo':'cube','cube':'cube','sfera':'sphere','sphere':'sphere',
                          'cilindro':'cylinder','piano':'plane','toro':'torus',
                          'monkey':'monkey','suzanne':'monkey','cono':'cone'}
                simple = next((v for k,v in _types.items() if k in lower and len(req.split())<=4), None)
                if simple:
                    execute_tool('blender_create', {'object_type': simple})
                    result = f"✅ {simple} creato"
                else:
                    # IBRIDO: prima prova Hyper3D (text-to-3D realistico),
                    # se fallisce ripiega sul codice LLM con primitive
                    result = None
                    # 1. Hyper3D Rodin (realistico, richiede credito API)
                    try:
                        from jarvis_blender import blender_generate_hyper3d
                        ok, msg = blender_generate_hyper3d(req)
                        if ok: result = msg
                        else: print(f"  [Blender] Hyper3D ND ({msg})")
                    except Exception as _e:
                        print(f"  [Blender] Hyper3D err: {_e}")
                    # 2. Fallback: LLM genera codice bpy con primitive
                    if result is None:
                        code, err = self._blender_ai_code(req)
                        if err or not code:
                            result = f"❌ Generazione fallita: {err or 'vuoto'}"
                        else:
                            execute_tool('blender_execute', {'code': code})
                            result = f"✅ Generato '{req}' (codice AI primitive)"
                actions_done.append(result)
                # Inquadra + screenshot in chat
                execute_tool('blender_focus_view', {})
                execute_tool('blender_screenshot', {'save_path': '/tmp/blender_viewport.png'})
                if os.path.exists('/tmp/blender_viewport.png'):
                    actions_done.append('IMAGE:/api/image?file=blender_viewport.png')

            # PolyHaven
            elif any(w in lower for w in ['polyhaven', 'poly haven', 'hdri']):
                qm = re.search(r'(?:cerca|trova|cerca)\s+(.+?)(?:\s+su|$)', lower)
                query = qm.group(1).strip() if qm else 'forest'
                atype = 'hdris' if 'hdri' in lower else 'textures'
                result = execute_tool('blender_polyhaven_search', {'query': query, 'asset_type': atype})
                actions_done.append(result)

            # codice Python in Blender
            elif any(w in lower for w in ['esegui', 'esegui codice', 'python blender', 'bpy']):
                cm = re.search(r'(?:esegui|run|codice)\s+(.+)', user_message, re.IGNORECASE)
                code = cm.group(1).strip() if cm else ''
                if code:
                    result = execute_tool('blender_execute', {'code': code})
                    actions_done.append(result)

            if not actions_done:
                # Fallback generico: mostra scena
                result = execute_tool('blender_scene', {})
                actions_done.append(result)

            return actions_done  # Blender ha priorità — esce subito
        # ── FINE BLENDER ───────────────────────────────────────────────────

        # world map: "aprimi il mondo" — griglia webcam
        if not actions_done and any(w in lower for w in ['aprimi il mondo', 'apri il mondo', 'mostra il mondo', 'mondo', 'world map', 'apri mappa']):
            wc_data = execute_tool('open_world_map', {})
            if isinstance(wc_data, list) and len(wc_data) > 0:
                actions_done.append(f'WEBCAM_GRID:{json.dumps(wc_data, ensure_ascii=False)}')
                speech = "Apro le webcam del mondo in griglia."
                actions_done.append(f'SPEECH:{speech}')
        # Home Assistant dashboard widget (PRIMA della webcam — evita conflitti)
        if not actions_done and ((
            any(w in lower for w in ['home assistant', 'homeassistant', 'homeassitetn', 'homeassiste'])
            or any(w.startswith('home') for w in lower.split())
            or ' ha ' in lower or lower.startswith('ha ') or lower.endswith(' ha') or lower == 'ha'
        ) and any(w in lower for w in ['dashboard', 'apri', 'widget', 'mostra', 'apre', 'mostrami', 'dasboard', 'fammi vedere', 'apre'])):
            actions_done.append('HA_DASHBOARD:')
            speech = "Apro la dashboard di Home Assistant."
            actions_done.append(f'SPEECH:{speech}')

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
            # Se il result contiene il percorso del file, mostralo in chat
            import re as _re2, os as _os
            _img_m = _re2.search(r'(/tmp/[\w\-\.]+\.png|/[\w/\-]+\.png)', str(result))
            if _img_m and _os.path.exists(_img_m.group(1)):
                _fn = _img_m.group(1).split('/')[-1]
                actions_done.append(f'IMAGE:/api/image?file={_fn}')

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

        # ── (blocco Blender rimosso — ora in cima con priorità assoluta) ──
        _is_blender = False  # disabilitato qui

        # stato / connessione Blender
        if not actions_done and _is_blender and any(w in lower for w in [
            'stato blender', 'blender attivo', 'blender connesso', 'controlla blender',
            'blender online', 'blender funziona', 'blender status'
        ]):
            result = execute_tool('blender_status', {})
            actions_done.append(result)
            actions_done.append(f'SPEECH:{result}')

        # scena / oggetti in Blender
        elif not actions_done and _is_blender and any(w in lower for w in [
            'scena', 'oggetti', 'cosa c\'è', 'cosa hai', 'mostra', 'lista', 'elenca', 'info'
        ]):
            result = execute_tool('blender_scene', {})
            actions_done.append(result)
            actions_done.append(f'SPEECH:Ecco la scena Blender attuale.')

        # importa avatar / setup avatar in Blender
        elif not actions_done and _is_blender and any(w in lower for w in [
            'importa avatar', 'carica avatar', 'metti avatar', 'setup avatar',
            'avatar in blender', 'prepara scena', 'setup scena', 'importa modello',
            'carica modello', 'importa personaggio'
        ]):
            result = execute_tool('blender_setup_avatar', {})
            actions_done.append(result)
            actions_done.append(f'SPEECH:Avatar importato in Blender con luci e camera. Usa "renderizza" per fare il render.')

        # render in Blender
        elif not actions_done and any(w in lower for w in [
            'renderizza', 'fai il render', 'fai un render', 'render blender',
            'render in blender', 'fai render', 'esegui render', 'avvia render'
        ]):
            import re as _re
            path_m = _re.search(r'(?:salva|salvo|in|su|a)\s+([\w/~\-]+\.png)', lower)
            out = path_m.group(1) if path_m else '/tmp/blender_render.png'
            result = execute_tool('blender_render', {'output_path': out})
            actions_done.append(result)
            actions_done.append(f'SPEECH:Render completato e salvato.')

        # screenshot viewport Blender
        elif not actions_done and _is_blender and any(w in lower for w in [
            'screenshot', 'schermata', 'viewport', 'mostra viewport'
        ]):
            result = execute_tool('blender_screenshot', {'save_path': '/tmp/blender_viewport.png'})
            actions_done.append(result)
            actions_done.append(f'SPEECH:Screenshot del viewport Blender salvato.')

        # crea oggetto in Blender
        elif not actions_done and _is_blender and any(w in lower for w in [
            'crea', 'aggiungi', 'inserisci', 'metti', 'add', 'nuovo'
        ]):
            obj_types = {
                'cubo': 'cube', 'cube': 'cube', 'sfera': 'sphere', 'sphere': 'sphere',
                'cilindro': 'cylinder', 'cylinder': 'cylinder', 'piano': 'plane',
                'toro': 'torus', 'torus': 'torus', 'monkey': 'monkey', 'suzanne': 'monkey',
                'luce': 'light', 'light': 'light', 'camera': 'camera', 'cono': 'cone',
            }
            found_type = 'cube'
            for k, v in obj_types.items():
                if k in lower:
                    found_type = v
                    break
            # Cerca nome tra virgolette
            name_m = re.search(r'(?:chiamalo?|nome|named?)\s+"?([^"]+)"?', lower)
            name = name_m.group(1).strip() if name_m else None
            # Cerca colore
            colors = {
                'rosso': [1,0,0], 'blu': [0,0.3,1], 'verde': [0,0.8,0],
                'giallo': [1,1,0], 'bianco': [1,1,1], 'nero': [0,0,0],
                'arancione': [1,0.4,0], 'viola': [0.6,0,1], 'ciano': [0,1,1],
                'rosa': [1,0.4,0.7], 'grigio': [0.5,0.5,0.5],
            }
            color = None
            for k, v in colors.items():
                if k in lower:
                    color = v
                    break
            result = execute_tool('blender_create', {'object_type': found_type, 'name': name})
            speech = f'{found_type} creato in Blender'
            if color and name:
                execute_tool('blender_material', {'object_name': name, 'color': color})
                speech += f' con colore applicato'
            elif color:
                speech += f'. Specifica un nome per applicare il colore.'
            actions_done.append(result)
            actions_done.append(f'SPEECH:{speech}.')

        # elimina oggetto da Blender
        elif not actions_done and _is_blender and any(w in lower for w in [
            'elimina', 'cancella', 'rimuovi', 'delete', 'remove'
        ]):
            name_m = re.search(r'(?:elimina|cancella|rimuovi|delete|remove)\s+(?:l\'?oggetto\s+|il\s+)?["\']?(\w[\w\s]*?)["\']?(?:\s|$)', user_message, re.IGNORECASE)
            name = name_m.group(1).strip() if name_m else 'Cube'
            result = execute_tool('blender_delete', {'name': name})
            actions_done.append(result)
            actions_done.append(f'SPEECH:Oggetto {name} eliminato da Blender.')

        # cerca PolyHaven
        elif not actions_done and any(w in lower for w in ['polyhaven', 'poly haven', 'hdri', 'texture polyhaven']):
            q_m = re.search(r'(?:cerca|trova|search|scarica)\s+(.+?)(?:\s+su\s+polyhaven|$)', lower)
            query = q_m.group(1).strip() if q_m else 'forest'
            asset_type = 'hdris' if 'hdri' in lower else ('models' if 'model' in lower else 'textures')
            result = execute_tool('blender_polyhaven_search', {'query': query, 'asset_type': asset_type})
            actions_done.append(result)
            actions_done.append(f'SPEECH:Ecco i risultati PolyHaven per {query}.')

        # ── FINE BLENDER ───────────────────────────────────────────────────

        return actions_done

    def chat(self, user_message):
        # 1. rileva azioni dirette
        actions_done = self._detect_direct_actions(user_message)

        memory.log_conversation("user", user_message)

        # Se azione diretta eseguita → rispondi subito senza chiamare LLM
        if actions_done:
            speech_msg = next((a[7:] for a in actions_done if a.startswith('SPEECH:')), None)
            filtered = [a for a in actions_done if not a.startswith('SPEECH:')]
            reply = speech_msg or ""
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": reply or "✅"})
            if len(self.history) > 40:
                self.history = self.history[-40:]
            memory.log_conversation("assistant", reply or "✅")
            self._update_conversation_summary(user_message, reply)
            return reply, filtered

        # 2. costruisci system prompt avanzato (memoria + grafo + tono + contesto)
        system_msg = self._build_system_prompt(user_message)
        self.history.append({"role": "user", "content": user_message})
        if len(self.history) > 40:
            self.history = self.history[-40:]

        messages = [{"role": "system", "content": system_msg}] + self.history

        if self._needs_tools(user_message):
            # ── LOOP AGENTICO: l'LLM sceglie i tool, esegue, vede i risultati, itera ──
            reply, tool_actions = self._agentic_loop(messages, user_message)
            self.history.append({"role": "assistant", "content": reply or "✅"})
            memory.log_conversation("assistant", reply or "✅")
            self._update_conversation_summary(user_message, reply)
            return reply, (actions_done + tool_actions)

        # ── Chat normale: completion semplice ──
        chosen_model = _detect_complexity(user_message) or self.cfg["groq"]["model"]
        topic = self._detect_topic(user_message)
        temp = float(self.cfg["groq"]["temperature"])
        if topic == "code":
            temp = min(temp, 0.3)  # più basso = più preciso
        elif topic == "wellbeing":
            temp = max(temp, 0.7)  # più alto = più creativo/caldo
        payload = {"model": chosen_model, "messages": messages,
                   "temperature": temp, "max_tokens": 2048}
        headers = {"Authorization": f"Bearer {self.cfg['groq']['api_key']}", "Content-Type": "application/json"}
        try:
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=45)
            reply = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            reply = f"[Errore connessione] {e}"
        self.history.append({"role": "assistant", "content": reply})
        memory.log_conversation("assistant", reply)
        self._update_conversation_summary(user_message, reply)
        return reply, actions_done

    def _needs_tools(self, msg):
        """True se il messaggio richiede strumenti (azioni), False per pura conversazione.
        Solo allora attiviamo il loop agentico con i tool."""
        low = msg.lower()
        return any(w in low for w in [
            # blender / 3d
            'blender', 'render', '3d', 'modell', 'avatar', 'scena', 'oggetto 3d', 'polyhaven', 'hdri',
            # azioni macOS / tool
            'crea', 'fai', 'fammi', 'genera', 'costruisci', 'disegna', 'apri', 'cerca', 'manda',
            'invia', 'scrivi', 'screenshot', 'volume', 'luminos', 'calendario', 'evento',
            'email', 'mail', 'nota', 'promemoria', 'musica', 'file', 'cartella', 'git',
        ])

    def _relevant_tools(self, user_message):
        """Seleziona un sottoinsieme rilevante di TOOLS_SCHEMA per non superare i
        limiti di token (lo schema completo da 100+ tool è troppo grande).
        I memory tool sono sempre inclusi perché il system prompt li richiama esplicitamente."""
        low = user_message.lower()
        is_blender = any(w in low for w in ['blender','render','3d','modell','oggetto 3d','scena 3d','avatar 3d','polyhaven','hdri'])
        memory_tools = []
        subset = []
        for t in TOOLS_SCHEMA:
            n = t["function"]["name"]
            if n.startswith("memory_"):
                memory_tools.append(t)
            elif is_blender:
                if n.startswith("blender_"):
                    subset.append(t)
            else:
                if not n.startswith("blender_"):
                    subset.append(t)
        # Groq ha un limite pratico: tieni max ~24 tool
        result = memory_tools + subset
        return result[:24] if result else TOOLS_SCHEMA[:24]

    def _agentic_loop(self, messages, user_message, max_iters=4):
        """Loop di tool-calling nativo Groq: il modello decide quali tool chiamare,
        i risultati gli vengono rimandati, finché non produce una risposta finale.
        Ritorna (testo_finale, lista_azioni_per_UI)."""
        import json as _json
        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json",
        }
        # Loop agentico → usa sempre il 70b (tool calling migliore, limiti più alti)
        chosen_model = self.cfg["groq"]["model"]
        tools = self._relevant_tools(user_message)
        # Tool che producono un'immagine da mostrare in chat
        IMG_TOOLS = {
            "blender_render": "/api/image?file=blender_render.png",
            "blender_screenshot": "/api/image?file=blender_viewport.png",
            "blender_setup_avatar": "/api/image?file=blender_viewport.png",
            "blender_create": "/api/image?file=blender_viewport.png",
            "blender_execute": "/api/image?file=blender_viewport.png",
        }
        _NEEDS_SHOT = {"blender_create", "blender_setup_avatar", "blender_execute"}
        msgs = list(messages)
        actions = []
        final_text = ""
        for it in range(max_iters):
            payload = {
                "model": chosen_model,
                "messages": msgs,
                "temperature": float(self.cfg["groq"]["temperature"]),
                "max_tokens": 2048,
                "tools": tools,
                "tool_choice": "auto",
            }
            # Chiamata con retry sul rate limit (429) — piano gratuito Groq
            msg = None
            for attempt in range(3):
                try:
                    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=60)
                    if resp.status_code == 429:
                        import time as _t
                        wait = 4 * (attempt + 1)
                        print(f"  [Agentic] rate limit, retry tra {wait}s...")
                        _t.sleep(wait)
                        continue
                    if not resp.ok:
                        err = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {}
                        return f"[Errore Groq {resp.status_code}] {err.get('error',{}).get('message','')}", actions
                    msg = resp.json()["choices"][0]["message"]
                    break
                except Exception as e:
                    return f"[Errore connessione] {e}", actions
            if msg is None:
                # esauriti i retry: se abbiamo già fatto azioni, chiudiamo con successo parziale
                return (final_text or "✅ Completato (rate limit Groq)"), actions

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                # Nessun tool → risposta finale
                final_text = (msg.get("content") or "").strip()
                break

            # Aggiungi il messaggio assistant con le tool_calls
            msgs.append({"role": "assistant", "content": msg.get("content"), "tool_calls": tool_calls})
            print(f"  [Agentic it{it+1}] {len(tool_calls)} tool: " + ", ".join(tc['function']['name'] for tc in tool_calls))

            for tc in tool_calls:
                fname = tc["function"]["name"]
                try:
                    fargs = _json.loads(tc["function"].get("arguments") or "{}")
                except Exception:
                    fargs = {}
                tool_result = execute_tool(fname, fargs)
                result_str = str(tool_result)
                actions.append(f"{fname}: {result_str[:80]}")
                # Se il tool produce un'immagine, mostrala + auto-focus per Blender
                if fname in IMG_TOOLS:
                    if fname in _NEEDS_SHOT:
                        execute_tool("blender_focus_view", {})
                        execute_tool("blender_screenshot", {"save_path": "/tmp/blender_viewport.png"})
                    actions.append(f"IMAGE:{IMG_TOOLS[fname]}")
                # Home Assistant dashboard → widget
                if fname == "ha_dashboard":
                    actions.append("HA_DASHBOARD:")
                # Rimanda il risultato al modello
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", fname),
                    "content": result_str[:2000],
                })
        else:
            final_text = final_text or "✅ Completato (limite iterazioni raggiunto)"
        return final_text, actions

    def _legacy_complete(self, messages, payload, actions_done):
        """[non usato] completion semplice senza tool — mantenuto per riferimento."""
        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json"
        }
        try:
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=45)
            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            return reply, actions_done
        except Exception as e:
            return f"[Errore] {e}", actions_done

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

        if actions_done:
            speech_msg = next((a[7:] for a in actions_done if a.startswith('SPEECH:')), None)
            filtered = [a for a in actions_done if not a.startswith('SPEECH:')]
            reply = speech_msg or ""
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": reply or "✅"})
            if len(self.history) > 40:
                self.history = self.history[-40:]
            memory.log_conversation("assistant", reply or "✅")
            self._update_conversation_summary(user_message, reply)
            return reply, 0.0

        system_msg = self._build_system_prompt(user_message)
        self.history.append({"role": "user", "content": user_message})
        if len(self.history) > 40:
            self.history = self.history[-40:]

        messages = [{"role": "system", "content": system_msg}] + self.history

        headers = {
            "Authorization": f"Bearer {self.cfg['groq']['api_key']}",
            "Content-Type": "application/json"
        }

        chosen_model = _detect_complexity(user_message) or self.cfg["groq"]["model"]
        topic = self._detect_topic(user_message)
        temp = float(self.cfg["groq"]["temperature"])
        if topic == "code":
            temp = min(temp, 0.3)
        elif topic == "wellbeing":
            temp = max(temp, 0.7)
        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temp,
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
                if self.cfg.get("ollama", {}).get("enabled", False):
                    print("[INFO] Groq stream fallito, provo Ollama...")
                    reply = self._ollama_chat(messages, payload)
                    self._update_conversation_summary(user_message, reply)
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
            self._update_conversation_summary(user_message, full_reply)
            return full_reply, elapsed

        except Exception as e:
            print(f"[Groq stream exception] {e}")
            if self.cfg.get("ollama", {}).get("enabled", False):
                print("[INFO] Groq stream fallito, provo Ollama...")
                reply = self._ollama_chat(messages, payload)
                self._update_conversation_summary(user_message, reply)
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
