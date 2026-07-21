# J.A.R.V.I.S — Agent Notes

## Struttura Progetto

```
jarvis/
├── jarvis_server.py              # Legacy server (http.server)
├── jarvis_server_fastapi.py      # Nuovo server FastAPI (moderno)
├── jarvis_agent.py               # LLM agent con tool routing
├── jarvis_tools.py               # 120+ tools unificati
├── jarvis_*.py                   # Moduli funzionali
├── src/frontend/                 # Frontend Vite + TypeScript
│   ├── index.html                # Entry point
│   ├── src/
│   │   ├── main.ts               # Entry point TS
│   │   ├── api/client.ts         # API client
│   │   ├── components/           # Componenti UI
│   │   ├── utils/dom.ts          # Helper DOM
│   │   └── types/index.ts        # TypeScript types
│   ├── vite.config.ts
│   └── package.json
├── assets/                       # Static assets (legacy)
├── pages/                        # Page fragments HTML
├── data/                         # Dati runtime
└── run.sh                        # Script di avvio
```

## Comandi

```bash
# Avvio server (modalità predefinita: FastAPI)
JARVIS_MODE=fastapi bash run.sh
JARVIS_MODE=legacy  bash run.sh    # Server legacy
JARVIS_MODE=dev     bash run.sh    # Frontend dev + backend

# Build frontend
cd src/frontend && npm run build

# Dev frontend (con proxy API su localhost:9999)
cd src/frontend && npm run dev

# Verifica TypeScript
cd src/frontend && npx tsc --noEmit
```

## API Endpoints

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/chat` | POST | Chat completamento |
| `/api/chat/stream` | POST | Chat streaming SSE |
| `/api/chat/voice` | POST | Chat + TTS streaming |
| `/api/tts` | POST | Text-to-speech |
| `/api/status` | GET | Stato server |
| `/api/sysinfo` | GET | Info sistema |
| `/api/memory/*` | GET/POST | Memoria persistente |
| `/api/rag/*` | GET/POST | RAG documenti |
| `/api/tool` | POST | Esecuzione tool |
| `/api/docs` | GET | Documentazione OpenAPI (FastAPI) |
| `/api/redoc` | GET | Documentazione ReDoc (FastAPI) |

## Regole per Agenti

1. **Non rompere il server legacy** — `jarvis_server.py` deve rimanere funzionante
2. **TypeScript strict** — Usa tipi, evita `any` dove possibile
3. **Python concurrency** — Usa `state_lock` per stato condiviso, thread separati per modelli ML
4. **Error handling** — Tutti gli endpoint FastAPI usano try/except + HTTPException
5. **Frontend pages** — Le pagine HTML legacy in `pages/` sono caricate via XHR sincrono

## Workflow: Foto → WhatsApp

Quando l'utente chiede di mandare una foto su WhatsApp ("manda una foto di X sul gruppo Y"):

1. **Genera immagine** via `POST /api/imagegen/generate` con `{prompt, model, size}`
   → Ottieni URL tipo `/api/image?file=ionos_xxx.png`
2. **Scarica e converti in base64** l'immagine dall'URL completo `http://localhost:9999/api/image?file=...`
3. **Invia su WhatsApp** via `POST /api/whatsapp/send-image` con:
   - `to`: `"<group_id>@g.us"` (per gruppi, cerca con GET `/api/whatsapp/contacts`)
   - `base64`: base64 dell'immagine
   - `mimetype`: `"image/png"`
   - `caption`: didascalia

⚠ `localhost` non funziona come URL per OpenWA (validazione `@IsUrl()` richiede TLD). Usa sempre **base64**. I gruppi WhatsApp hanno ID tipo `120363...@g.us`.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **jarvis** (4269 symbols, 39328 relationships, 291 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/jarvis/context` | Codebase overview, check index freshness |
| `gitnexus://repo/jarvis/clusters` | All functional areas |
| `gitnexus://repo/jarvis/processes` | All execution flows |
| `gitnexus://repo/jarvis/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
