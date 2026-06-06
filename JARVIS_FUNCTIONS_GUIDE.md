# J.A.R.V.I.S. — Guida Completa a Tutte le Funzioni v9.0

> 120+ tools | 24 moduli | macOS | Multi-LLM | TTS | Computer Use | RAG | Blender

---

## Indice

1. [Sistema](#1-sistema)
2. [Calendario](#2-calendario)
3. [Mail](#3-mail)
4. [Note](#4-note)
5. [Schermo e OCR](#5-schermo-e-ocr)
6. [Browser (Chrome AppleScript)](#6-browser-chrome-applescript)
7. [Browser (Playwright)](#7-browser-playwright)
8. [File](#8-file)
9. [Memoria](#9-memoria)
10. [Shortcuts macOS](#10-shortcuts-macos)
11. [Planner](#11-planner)
12. [Ricerca Web](#12-ricerca-web)
13. [Git](#13-git)
14. [Computer Use (Mouse e Tastiera)](#14-computer-use-mouse-e-tastiera)
15. [RAG (Documenti)](#15-rag-documenti)
16. [Approval Flow](#16-approval-flow)
17. [Goals / OKR](#17-goals--okr)
18. [Multi-LLM Providers](#18-multi-llm-providers)
19. [Network Diagnostics](#19-network-diagnostics)
20. [World Map Webcam Grid](#20-world-map-webcam-grid)
21. [MCP (Model Context Protocol)](#21-mcp-model-context-protocol)
22. [Blender 3D](#22-blender-3d)

---

## 1. Sistema

### `open_app`
Apre qualsiasi app macOS.
- **Parametri:** `app_name` (es. "Safari", "Chrome", "VS Code", "Figma", "TeamViewer")
- **Alias supportati:** chrome→Google Chrome, vscode→VS Code, iterm→iTerm, calc→Calculator, whatsapp→WhatsApp, docker→Docker, figma→Figma, slack→Slack
- **Esempio:** `"Apri Chrome"` → Jarvis esegue `open_app(app_name="Google Chrome")`

### `web_search`
Apre Google Search nel browser.
- **Parametri:** `query`
- **Esempio:** `"Cerca su Google ricetta tiramisù"` → apre `google.com/search?q=ricetta+tiramisù`

### `system_volume`
Controlla il volume di sistema macOS.
- **Parametri:** `action` (set/mute/unmute/get), `level` (0-100, solo per set)
- **Esempio:** `"Volume al 50%"` → `system_volume(action="set", level=50)`

### `take_screenshot`
Cattura screenshot.
- **Parametri:** `mode` (full/window/selection, default: full)
- **Esempio:** `"Fai uno screenshot"` → cattura tutto lo schermo

### `get_system_info`
Info complete di sistema.
- **Parametri:** `info_type` (battery/cpu/ram/disk/ip/uptime/all)
- **Esempio:** `"Che batteria ho?"` → `get_system_info(info_type="battery")`

### `clipboard_action`
Legge o scrive la clipboard.
- **Parametri:** `action` (read/write), `text` (solo per write)
- **Esempio:** `"Copia negli appunti: Hello World"`

### `send_notification`
Mostra una notifica macOS.
- **Parametri:** `title`, `message`
- **Esempio:** `"Notifica: Promemoria bere acqua"`

### `set_reminder`
Crea un promemoria in Reminders.app.
- **Parametri:** `title`, `minutes_from_now` (default: 0 = senza promemoria)
- **Esempio:** `"Ricordami di chiamare Mario tra 30 minuti"`

### `play_music`
Controlla Music o Spotify.
- **Parametri:** `action` (play/pause/next/previous/stop), `app` (Music/Spotify)
- **Esempio:** `"Metti play su Spotify"` → `play_music(action="play", app="Spotify")`

### `quit_app`
Chiude un'app.
- **Parametri:** `app_name`
- **Esempio:** `"Chiudi Safari"`

### `lock_screen`
Blocca immediatamente lo schermo.
- **Parametri:** nessuno

### `show_desktop`
Mostra il desktop (cmd+F3).
- **Parametri:** nessuno

### `set_brightness`
Regola luminosità schermo 0-100.
- **Parametri:** `level` (0-100)
- **Esempio:** `"Luminosità al 40%"`

### `run_terminal_command`
Esegue comandi bash. Comandi pericolosi bloccati (rm -rf /, sudo rm -rf, fork bomb, ecc.).
- **Parametri:** `command`
- **Esempio:** `"Esegui ls -la ~/Desktop"`

---

## 2. Calendario

### `calendar_today`
Mostra eventi di oggi.
- **Parametri:** nessuno
- **Esempio:** `"Che eventi ho oggi?"`

### `calendar_upcoming`
Mostra i prossimi eventi.
- **Parametri:** `days` (default: 7)
- **Esempio:** `"Cosa ho in agenda questa settimana?"`

### `calendar_create`
Crea un evento sul calendario di sistema.
- **Parametri:** `title`, `start_date` (opzionale, default: ora), `duration_minutes` (default: 60)
- **Esempio:** `"Crea evento: Dentista domani alle 15 per 1 ora"`

### `calendar_list`
Mostra tutti i calendari configurati.
- **Parametri:** nessuno

### `calendar_open`
Apre l'app Calendario.
- **Parametri:** nessuno

---

## 3. Mail

### `mail_unread`
Mostra il numero di email non lette.
- **Parametri:** nessuno
- **Esempio:** `"Quante email non lette ho?"`

### `mail_recent`
Mostra le email recenti non lette.
- **Parametri:** `limit` (default: 5)
- **Esempio:** `"Mostra le ultime 3 email"`

### `mail_search`
Cerca tra le email.
- **Parametri:** `query`
- **Esempio:** `"Cerca email da Mario"`

### `mail_read_aloud`
Legge ad alta voce le email non lette (formattate per TTS).
- **Parametri:** nessuno

### `mail_send`
Invia email tramite Apple Mail.
- **Parametri:** `to`, `subject`, `body`, `cc` (opzionale), `bcc` (opzionale)
- **Esempio:** `"Invia email a mario@email.com con oggetto Ciao e corpo Come stai?"`

---

## 4. Note

### `notes_create`
Crea una nota in Notes.app.
- **Parametri:** `title`, `body` (opzionale)
- **Esempio:** `"Crea nota Idea progetto con corpo: ..."`

### `notes_search`
Cerca tra le note.
- **Parametri:** `query`
- **Esempio:** `"Cerca nelle note: ricette"`

### `notes_list`
Elenca le note recenti.
- **Parametri:** `limit` (default: 10)
- **Esempio:** `"Mostra le mie ultime note"`

---

## 5. Schermo e OCR

### `screen_info`
Mostra app visibili e informazioni schermo.
- **Parametri:** nessuno
- **Esempio:** `"Cosa c'è aperto sullo schermo?"`

### `screen_frontmost`
Mostra l'app e finestra in primo piano.
- **Parametri:** nessuno
- **Esempio:** `"Che app ho davanti?"`

### `screen_ocr`
Legge il testo dallo schermo usando OCR (Apple Vision + Tesseract).
- **Parametri:** `image_path` (opzionale, default: screenshot corrente)
- **Esempio:** `"Leggi il testo sullo schermo"`

### `screen_summary`
Riassunto completo dello stato dello schermo (app, finestre, contesto).
- **Parametri:** nessuno
- **Esempio:** `"Descrivi cosa vedi sullo schermo"`

### `screen_selected_text`
Estrae il testo selezionato nell'app attiva.
- **Parametri:** nessuno
- **Esempio:** `"Leggi cosa ho selezionato"`

---

## 6. Browser (Chrome AppleScript)

### `open_url`
Apre una URL nel browser predefinito.
- **Parametri:** `url`, `browser` (opzionale)
- **Esempio:** `"Apri youtube.com"`

### `browser_tabs`
Elenca tutte le tab aperte in Chrome.
- **Parametri:** nessuno
- **Esempio:** `"Che tab ho aperte in Chrome?"`

### `browser_current`
Mostra titolo e URL della tab attiva di Chrome.
- **Parametri:** nessuno
- **Esempio:** `"Che pagina sto visitando?"`

### `browser_scroll`
Scrolla la pagina Chrome in una direzione.
- **Parametri:** `direction` (up/down/top/bottom)
- **Esempio:** `"Scrolla giù"`

---

## 7. Browser (Playwright)

### `browser_navigate`
Apre una URL con Playwright e ne estrae il contenuto testuale.
- **Parametri:** `url`
- **Esempio:** `"Apri e leggi il contenuto di https://example.com"`

### `browser_extract`
Estrae contenuto da una pagina web con selettore CSS.
- **Parametri:** `url`, `selector` (default: "body")
- **Esempio:** `"Estrai il titolo da https://example.com"` con selettore `h1`

### `browser_playwright_click`
Clicca un elemento identificato da un selettore CSS.
- **Parametri:** `selector`, `url` (opzionale)
- **Esempio:** `"Clicca il pulsante #submit"`

### `browser_playwright_fill`
Compila un campo di un form.
- **Parametri:** `selector`, `text`, `url` (opzionale)
- **Esempio:** `"Scrivi 'ciao' nel campo #search"`

### `browser_screenshot`
Cattura screenshot di una pagina web con Playwright.
- **Parametri:** `url`, `save_path` (opzionale)
- **Esempio:** `"Screenshot di google.com"`

---

## 8. File

### `files_list`
Elenca il contenuto di una directory.
- **Parametri:** `path` (default: ~/Desktop)
- **Esempio:** `"Cosa c'è sul desktop?"`

### `files_read`
Legge il contenuto di un file.
- **Parametri:** `path`
- **Esempio:** `"Leggi il file ~/Desktop/note.txt"`

### `files_create`
Crea un nuovo file con contenuto.
- **Parametri:** `path`, `content` (opzionale)
- **Esempio:** `"Crea file ~/Desktop/hello.txt con contenuto Ciao mondo"`

### `files_search`
Cerca file per nome.
- **Parametri:** `query`, `path` (default: ~)
- **Esempio:** `"Cerca file con 'report' nella home"`

### `files_info`
Mostra informazioni su un file (dimensioni, tipo, permessi, date).
- **Parametri:** `path`
- **Esempio:** `"Info su ~/Desktop/photo.jpg"`

### `files_organize`
Organizza la cartella Downloads (sposta file in sottocartelle per tipo).
- **Parametri:** nessuno
- **Esempio:** `"Organizza i download"`

### `files_delete`
Elimina un file (attenzione: operazione definitiva).
- **Parametri:** `path`
- **Esempio:** `"Elimina ~/Desktop/temp.txt"`

---

## 9. Memoria

### `memory_remember`
Salva un fatto, preferenza o informazione nella memoria persistente.
- **Parametri:** `content`, `category` (fact/preference/decision, default: fact), `tags` (opzionale)
- **Esempio:** `"Ricorda che il mio colore preferito è il blu"`

### `memory_search`
Cerca nella memoria con full-text search (FTS5).
- **Parametri:** `query`
- **Esempio:** `"Cerca nella memoria: colore preferito"`

### `memory_preferences`
Mostra tutte le preferenze salvate.
- **Parametri:** nessuno
- **Esempio:** `"Quali preferenze hai su di me?"`

### `memory_stats`
Statistiche della memoria (totale memorie, categorie, conversazioni).
- **Parametri:** nessuno

---

## 10. Shortcuts macOS

### `shortcuts_run`
Esegue una Shortcut macOS.
- **Parametri:** `name`
- **Esempio:** `"Esegui shortcut Buongiorno"`

### `shortcuts_list`
Elenca tutte le Shortcut disponibili.
- **Parametri:** nessuno
- **Esempio:** `"Quali shortcut ho?"`

---

## 11. Planner

### `planner_create`
Crea un piano multi-step per compiti complessi.
- **Parametri:** `title`, `steps` (array di stringhe), `priority` (low/medium/high)
- **Esempio:** `"Crea piano Preparare viaggio con passi: Prendere volo, Prenotare hotel, Fare valigia"`

### `planner_list`
Elenca i piani attivi con progresso percentuale.
- **Parametri:** nessuno
- **Esempio:** `"Mostra i miei piani"`

### `planner_complete`
Segna uno step come completato.
- **Parametri:** `plan_id`, `step`
- **Esempio:** `"Completa step 1 del piano 1"`

### `planner_detail`
Mostra il dettaglio completo di un piano.
- **Parametri:** `plan_id`
- **Esempio:** `"Mostra dettaglio piano 1"`

---

## 12. Ricerca Web

### `web_search_ddg`
Cerca su DuckDuckGo e restituisce risultati completi (no API key necessaria).
- **Parametri:** `query`, `max_results` (default: 8)
- **Esempio:** `"Cerca su DuckDuckGo ultime notizie tecnologia"`

---

## 13. Git

### `git_status`
Mostra lo stato del repository git (file modificati, staged, untracked).
- **Parametri:** nessuno

### `git_log`
Mostra la cronologia dei commit.
- **Parametri:** `count` (default: 10)

### `git_branches`
Elenca tutti i branch git.
- **Parametri:** nessuno

### `git_diff`
Mostra le differenze non ancora committate.
- **Parametri:** nessuno

### `git_commit`
Crea un commit con auto-add dei file modificati.
- **Parametri:** `message`
- **Esempio:** `"Committa con messaggio Fix bug login"`

### `git_create_branch`
Crea un nuovo branch.
- **Parametri:** `name`
- **Esempio:** `"Crea branch feature/nuova-funzione"`

### `git_command`
Esegue un comando git arbitrario (con blocchi di sicurezza).
- **Parametri:** `command`
- **Esempio:** `"Esegui git pull origin main"`

---

## 14. Computer Use (Mouse e Tastiera)

### `computer_mouse_move`
Muove il mouse a coordinate specifiche.
- **Parametri:** `x` (pixel), `y` (pixel)
- **Esempio:** `"Muovi mouse a 500, 300"`

### `computer_mouse_click`
Click del mouse.
- **Parametri:** `x`, `y` (opzionali, posizione corrente se omessi), `button` (left/right), `clicks` (default: 1)
- **Esempio:** `"Click destro a 500, 300"`

### `computer_mouse_drag`
Trascina il mouse da una posizione all'altra.
- **Parametri:** `from_x`, `from_y`, `to_x`, `to_y`
- **Esempio:** `"Trascina da 100,100 a 300,300"`

### `computer_keyboard_type`
Digita testo come se fosse una tastiera.
- **Parametri:** `text`
- **Esempio:** `"Scrivi Ciao mondo"`

### `computer_keyboard_press`
Premi un tasto specifico (con modificatori opzionali).
- **Parametri:** `key`, `modifiers` (opzionale, es. "command,shift")
- **Esempio:** `"Premi F5"` o `"Premi cmd+c"`

### `computer_keyboard_shortcut`
Scorciatoia da tastiera (es. cmd+c, cmd+v).
- **Parametri:** `keys`
- **Esempio:** `"Esegui cmd+c"`

### `computer_mouse_position`
Mostra la posizione corrente del mouse.
- **Parametri:** nessuno

### `computer_resolution`
Mostra la risoluzione dello schermo.
- **Parametri:** nessuno

---

## 15. RAG (Documenti)

### `rag_add_document`
Aggiunge un documento al database RAG con embeddings vettoriali.
- **Parametri:** `title`, `content`, `source` (opzionale)
- **Esempio:** `"Aggiungi al RAG: Manuale utente con contenuto ..."`

### `rag_add_file`
Aggiunge un file al database RAG (legge e indicizza).
- **Parametri:** `file_path`
- **Esempio:** `"Indicizza ~/Desktop/documento.pdf"`

### `rag_search`
Cerca documenti nel database RAG con ricerca semantica.
- **Parametri:** `query`, `limit` (default: 5)
- **Esempio:** `"Cerca nel RAG: politica privacy"`

### `rag_list`
Elenca tutti i documenti nel database RAG.
- **Parametri:** nessuno

### `rag_stats`
Statistiche del database RAG (documenti, chunk).
- **Parametri:** nessuno

---

## 16. Approval Flow

### `approval_pending`
Mostra le richieste di approvazione in attesa.
- **Parametri:** nessuno

### `approval_approve`
Approva una richiesta in attesa.
- **Parametri:** `request_id`, `auto_future` (true = approva automaticamente in futuro)
- **Esempio:** `"Approva richiesta 5"`

### `approval_deny`
Nega una richiesta.
- **Parametri:** `request_id`
- **Esempio:** `"Nega richiesta 5"`

---

## 17. Goals / OKR

### `goals_create`
Crea un obiettivo con Key Results misurabili (sistema OKR).
- **Parametri:** `title`, `description`, `key_results` (array di stringhe), `priority` (low/medium/high)
- **Esempio:** `"Crea obiettivo Imparare Python con KR: Finire tutorial base, Fare 3 progetti, Superare esame"`

### `goals_list`
Elenca obiettivi filtrati per stato.
- **Parametri:** `status` (active/completed/archived — vuoto = tutti)
- **Esempio:** `"Mostra obiettivi attivi"`

### `goals_detail`
Mostra dettagli di un obiettivo con barre di progresso per ogni KR.
- **Parametri:** `goal_id`
- **Esempio:** `"Dettaglio obiettivo 1"`

### `goals_update_kr`
Aggiorna il progresso di un Key Result specifico.
- **Parametri:** `goal_id`, `kr_id`, `current` (valore corrente, 0-target)
- **Esempio:** `"Aggiorna KR 1 dell'obiettivo 1 a 75"`

### `goals_add_kr`
Aggiunge un nuovo Key Result a un obiettivo.
- **Parametri:** `goal_id`, `description`, `target` (default: 100)
- **Esempio:** `"Aggiungi KR all'obiettivo 1: Contribuire a progetto open source con target 1"`

### `goals_delete`
Elimina completamente un obiettivo.
- **Parametri:** `goal_id`

### `goals_archive`
Archivia un obiettivo (completato o non più attivo).
- **Parametri:** `goal_id`

---

## 18. Multi-LLM Providers

### `providers_list`
Elenca tutti i provider LLM configurati e il loro stato.
- **Provider supportati:** Groq, Ollama, OpenAI, Gemini, Anthropic
- **Parametri:** nessuno
- **Esempio:** `"Quali provider LLM hai?"`

### `providers_switch`
Cambia il provider LLM attivo al volo, senza riavviare.
- **Parametri:** `provider` (groq/ollama/openai/gemini/anthropic)
- **Esempio:** `"Passa a Ollama"` o `"Usa Gemini"`

### `providers_set_model`
Cambia il modello specifico per un provider.
- **Parametri:** `provider`, `model`
- **Esempio:** `"Imposta modello per groq: llama-3.3-70b-versatile"`

---

## 19. Network Diagnostics

### `network_public_ip`
Mostra l'IP pubblico e la geolocalizzazione approssimativa.
- **Parametri:** nessuno
- **Esempio:** `"Che IP pubblico ho?"`

### `network_ping`
Test ping verso un host per verificare la connettività.
- **Parametri:** `host` (default: 8.8.8.8)
- **Esempio:** `"Ping a github.com"`

### `network_dns`
Lookup DNS per un dominio.
- **Parametri:** `domain` (default: google.com)
- **Esempio:** `"DNS lookup di apple.com"`

### `network_speedtest`
Test della velocità di download (stima basata su download di un file di test).
- **Parametri:** nessuno
- **Esempio:** `"Testa la velocità di internet"`

### `network_connectivity`
Report completo dello stato della connessione (IP, geolocalizzazione, DNS, ping).
- **Parametri:** nessuno
- **Esempio:** `"Com'è la connessione?"`

---

## 20. World Map Webcam Grid

### `open_world_map`
Apre una griglia nel dashboard con webcam live YouTube per 6 città mondiali.
- **Città:** Milano, Venezia, Tokyo, Berlino, New York, Sydney
- **Parametri:** nessuno
- **Esempio:** `"Aprimi il mondo"` → mostra tutte le webcam in griglia a schermo intero

---

## 21. MCP (Model Context Protocol)

### `mcp_list`
Elenca tutti i server MCP configurati e il loro stato.
- **Server built-in:** github, slack, filesystem
- **Parametri:** nessuno
- **Esempio:** `"Quali server MCP hai?"`

### `mcp_enable`
Attiva un server MCP. Per GitHub serve il token in env.
- **Parametri:** `name`, `env` (opzionale, oggetto chiave-valore)
- **Esempio:** `"Attiva MCP github con env GITHUB_TOKEN=... "`

### `mcp_disable`
Disattiva un server MCP.
- **Parametri:** `name`
- **Esempio:** `"Disattiva MCP slack"`

### `mcp_tools`
Elenca i tools disponibili su un server MCP attivo.
- **Parametri:** `server`
- **Esempio:** `"Quali tools ha il server github?"`

### `mcp_call`
Chiama un tool specifico su un server MCP.
- **Parametri:** `server`, `tool`, `args` (oggetto opzionale)
- **Esempio:** `"Chiama tool github issues/list con args: ..."`

---

## 22. Blender 3D

*Richiede Blender aperto con il blender-mcp addon attivo.*

### `blender_status`
Verifica se Blender è connesso e gli addon sono attivi.
- **Parametri:** nessuno

### `blender_scene`
Mostra informazioni sulla scena (oggetti, frame, render engine).
- **Parametri:** nessuno

### `blender_object`
Mostra dettagli di un oggetto specifico.
- **Parametri:** `name`

### `blender_execute`
Esegue codice Python bpy arbitrario in Blender. Usato per creazioni complesse.
- **Parametri:** `code`
- **Esempio:** `"Esegui codice bpy per creare un cubo"`

### `blender_create`
Crea una primitiva 3D (cubo, sfera, cilindro, piano, toro, scimmia, cono, luce, camera).
- **Parametri:** `object_type`, `name` (opzionale), `location` (opzionale 3 numeri), `scale` (opzionale 3 numeri), `size` (default: 1.0)

### `blender_delete`
Elimina un oggetto per nome.
- **Parametri:** `name`

### `blender_material`
Applica un materiale PBR colorato a un oggetto.
- **Parametri:** `object_name`, `color` ([R,G,B] 0-1), `metallic` (default: 0.0), `roughness` (default: 0.5)

### `blender_move`
Muove, ruota o scala un oggetto.
- **Parametri:** `name`, `location` (opzionale), `rotation` (opzionale), `scale` (opzionale)

### `blender_screenshot`
Cattura screenshot del viewport 3D.
- **Parametri:** `save_path` (opzionale)

### `blender_render`
Renderizza la scena e salva come PNG.
- **Parametri:** `output_path` (default: /tmp/blender_render.png), `frame` (opzionale), `engine` (default: EEVEE)

### `blender_setup_avatar`
Importa avatar Ready Player Me (GLB) con luci e camera ritratto.
- **Parametri:** `glb_path` (opzionale)

### `blender_focus_view`
Forza material preview e inquadra tutti gli oggetti.
- **Parametri:** nessuno

### `blender_enable_hyper3d`
Abilita Hyper3D Rodin per text-to-3D realistico.
- **Parametri:** `api_key` (default: "vibecoding")

### `blender_generate_hyper3d`
Genera modello 3D realistico da descrizione testuale via Hyper3D Rodin.
- **Parametri:** `prompt`
- **Esempio:** `"Genera un albero di Natale realistico"`

### `blender_polyhaven_search`
Cerca asset PolyHaven (HDRI, texture, modelli).
- **Parametri:** `query`, `asset_type` (hdris/textures/models, default: hdris)

### `blender_polyhaven_download`
Scarica e importa asset PolyHaven.
- **Parametri:** `asset_id`, `asset_type` (default: textures), `resolution` (default: 2k)

### `blender_sketchfab_search`
Cerca modelli su Sketchfab.
- **Parametri:** `query`, `count` (default: 10)

### `blender_sketchfab_download`
Scarica e importa modello Sketchfab.
- **Parametri:** `model_id`

---

## Note Generali

- **Tutti i comandi possono essere dati in linguaggio naturale** — Jarvis sceglie automaticamente lo strumento giusto
- **Il server è su http://localhost:9999**
- **Configurazione in `config.json`** (API keys, modelli, TTS, preferenze)
- **Persistenza:** memoria SQLite, RAG vettoriale, planner JSON, goals JSON
- **TTS:** Usa Qwen3-TTS locale (MLX su Apple Silicon) con fallback Edge TTS
- **Smart LLM routing:** Query semplici → modello veloce (8b), complesse → modello potente (70b)
- **Security:** Blocchi per comandi pericolosi, approval flow per azioni sensibili
