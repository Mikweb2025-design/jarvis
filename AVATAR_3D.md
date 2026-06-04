# Avatar 3D — Sistema lip-sync real-time

Documentazione del sistema avatar 3D di J.A.R.V.I.S. Pensata per essere letta da
un **agente di codice** (o da uno sviluppatore) che debba modificare, debuggare o
estendere l'avatar parlante.

> **TL;DR** — L'avatar è un modello GLB (Ready Player Me) renderizzato con
> Three.js dentro un `<canvas>`. Il labiale è sincronizzato **in tempo reale**
> analizzando l'audio TTS con la Web Audio API (`AnalyserNode`): niente più
> generazione video lato server (Wav2Lip è stato rimosso dal flusso client).

---

## 1. Architettura in breve

```
utente scrive  ──▶  doChat()  ──▶  /api/chat  (risposta testo)
                                     │
                                     ▼
                                  speak(text)
                                     │
                                     ▼
                              POST /api/tts  ──▶  blob audio (mp3)
                                     │
                                     ▼
                        window.Avatar3D.speak(blob)
                                     │
                  ┌──────────────────┴───────────────────┐
                  ▼                                       ▼
       AudioBufferSource ──▶ AnalyserNode          render loop (tick)
       (riproduce audio)     (FFT + RMS)            legge analyser ogni frame
                                                    e muove i morph del volto
                                                    (jawOpen, viseme_aa/E/I/O/U)
```

Tutto il rendering e il lip-sync vivono **nel browser**, in un unico file:
`jarvis_app.html`. Il server (`jarvis_server.py`) serve solo l'HTML, il file
`.glb` e l'endpoint TTS.

---

## 2. File e punti di modifica

### `jarvis_app.html`

| Cosa | Dove (riferimento) | Note |
|------|--------------------|------|
| Import map Three.js | `<script type="importmap">` (head) | three@0.160.0 + addons via unpkg CDN |
| Canvas dell'avatar | `<canvas id="avatar3d-canvas">` dentro `#avatar-widget` | sopra al vecchio `#widget-canvas` 2D |
| Modulo 3D | `<script type="module">` in fondo al body | tutto il codice Three.js + lip-sync |
| API pubblica | `window.Avatar3D` | `setState(s)`, `speak(blob, onEnd)`, `stop()` |
| `initThree()` | modulo | crea renderer/scena/camera/luci, avvia loop |
| `loadAvatar()` | modulo | carica il GLB, framing camera sul bone "Head" |
| `applyHoloTint()` | modulo | tinta emissiva ciano sui material (tema holo) |
| `setMorph()` / `clearMouthMorphs()` | modulo | scrivono i morph su **tutte** le mesh del volto |
| `tick()` | modulo | render loop: blink, head-sway, lip-sync |
| `speakBlob()` / `stopCurrentAudio()` | modulo | Web Audio: decode → AnalyserNode → play |
| `speak(text)` | script classico (~riga 1616) | chiama solo `/api/tts` poi `Avatar3D.speak()` |
| `setHoloState()` | script classico (~riga 1366) | propaga `idle/thinking/speaking` ad `Avatar3D` |

### `jarvis_server.py`

| Cosa | Dove | Note |
|------|------|------|
| Route GLB | `elif self.path.startswith("/assets/avatar.glb")` | serve `assets/avatar.glb`, header `no-cache` |
| Route TTS | `/api/tts` | restituisce blob `audio/mpeg` (Edge TTS / Qwen3) |

### `assets/avatar.glb`

Il modello 3D. Attualmente: **avatar femminile** (`brunette.glb` da
[met4citizen/TalkingHead](https://github.com/met4citizen/TalkingHead)).
Vedi §4 per come sostituirlo.

---

## 3. Come funziona il lip-sync (dettaglio)

1. `speakBlob(blob)` decodifica l'mp3 in un `AudioBuffer`, crea un
   `AudioBufferSourceNode` e lo collega a un `AnalyserNode`
   (`fftSize = 1024`) → `destination` (così l'audio si sente).
2. Nel render loop `tick()`, ad ogni frame, quando `state === 'speaking'`:
   - **RMS** sul dominio del tempo (`getByteTimeDomainData`) → ampiezza voce →
     `smoothJaw` (smussata) → pilota `jawOpen` + `mouthOpen`.
   - **FFT** (`getByteFrequencyData`) divisa in 3 bande (lo/mid/hi):
     - banda bassa → `viseme_O` (vocali tonde)
     - banda media → `viseme_aa` (vocali aperte)
     - banda alta → `viseme_E` / `viseme_I` (vocali chiuse/sibilanti)
   - I valori sono smussati con interpolazione esponenziale per evirare scatti.
3. A fine audio (`onended`) → `clearMouthMorphs()` + `state='idle'` + callback
   che riporta la UI a idle.

> Non è un vero phoneme-to-viseme (servirebbe un forced-aligner). È un
> **amplitude+spectrum driven lip-sync**: visivamente convincente, costo zero,
> nessuna latenza, nessun modello server.

### Stati (`Avatar3D.setState`)
- `idle` — blink casuale + leggero head-sway, bocca chiusa.
- `thinking` — `mouthPucker` pulsante (sostituisce il vecchio video d'attesa).
- `speaking` — lip-sync attivo dall'analyser.

---

## 4. Come sostituire il modello 3D

**Requisito fondamentale:** il GLB deve avere i **morph targets ARKit + Oculus
Visemes** (almeno `jawOpen`, `viseme_aa`, `viseme_E`, `viseme_I`, `viseme_O`,
`viseme_U`). Senza questi, la bocca non si muove. Modelli Ready Player Me li
hanno se scaricati con `?morphTargets=ARKit,Oculus Visemes`.

Passi:
1. Procurati il `.glb` (vedi fonti sotto).
2. **Verifica i morph** prima di usarlo:
   ```bash
   python3 - <<'PY'
   import json, struct
   p = 'NUOVO.glb'
   with open(p,'rb') as f:
       f.read(12); cl=struct.unpack('<I',f.read(4))[0]; f.read(4)
       j=json.loads(f.read(cl).decode())
   for m in j.get('meshes',[]):
       tn=(m.get('extras') or {}).get('targetNames',[])
       if 'jawOpen' in tn: print(m.get('name'), '->', len(tn), 'morphs OK')
   PY
   ```
3. Copia il file: `cp NUOVO.glb assets/avatar.glb`
4. **Bust della cache:** l'URL nel loader è già `/assets/avatar.glb?v=<timestamp>`
   e l'header server è `no-cache`, quindi basta un **hard refresh** (Cmd+Shift+R).
   Non serve toccare il codice se il rig è Ready Player Me (mesh `Wolf3D_*`,
   bone `Head`): il codice trova automaticamente le mesh con `jawOpen` e fa il
   framing sul bone della testa.
5. Se il nuovo modello **non** è RPM, potresti dover regolare:
   - `headBone` matching (regex `/^head$|head/i` in `loadAvatar`)
   - framing camera (`target.y += 0.08`, distanza `target.z + 0.72`)

### Fonti modelli (testate, scaricabili via raw GitHub — il CDN
`models.readyplayer.me` NON risolve da questa rete)
- Femminile: `https://raw.githubusercontent.com/met4citizen/TalkingHead/main/avatars/brunette.glb` ← **in uso**
- Maschile: `https://raw.githubusercontent.com/readyplayerme/visage/main/public/half-body.glb`

### Nascondere accessori (es. occhiali)
Il `brunette.glb` ha una mesh `Wolf3D_Glasses`. Per nasconderla, in
`loadAvatar()` dentro il `traverse`:
```js
if (/glasses|headwear|hat|helmet/i.test(o.name||'')) o.visible = false;
```

---

## 5. Troubleshooting

| Sintomo | Causa probabile | Fix |
|---------|-----------------|-----|
| Si vede ancora il vecchio modello | Cache browser sul `.glb` | Già mitigato con `?v=timestamp` + header `no-cache`. Hard refresh; in DevTools → Network → "Disable cache". |
| Widget nero, nessun modello | Errore caricamento GLB | Il loading overlay mostra l'errore **in rosso a schermo**. Controlla console (`[Avatar3D]`). |
| Solo la sommità della testa visibile | Framing camera errato | Regola `target.y` / distanza in `loadAvatar()`. Il framing usa il bone "Head". |
| Modello visibile ma bocca ferma | GLB senza morph `jawOpen` | Usa un modello con ARKit/Oculus visemes (vedi §4). Overlay mostra "Modello senza morph targets jawOpen". |
| Nessun audio durante speaking | AudioContext sospeso | Richiede un gesto utente; `speakBlob` fa `audioCtx.resume()`. Se parte da autoplay, interagisci con la pagina. |
| `THREE is not defined` | Import map non caricata | Verifica connessione a unpkg.com; l'import map deve precedere il `<script type="module">`. |

### Diagnostica a schermo
Il modulo installa handler globali `error`/`unhandledrejection` che proiettano
il messaggio **in rosso** nel widget (funzione `showError`). Utile quando non si
ha accesso a DevTools.

---

## 6. Note / debito tecnico

- La route server `/api/wav2lip` esiste ancora ma **non è più chiamata dal
  client**. Si può rimuovere insieme alla cartella `Wav2Lip/` e agli asset
  `holographic_avatar*.{png,mp4}`, `waiting_neurons.mp4` se non servono altrove.
- `brunette.glb` non ha animazioni idle embedded (0 clip): blink e head-sway sono
  **procedurali** in `tick()`. Il modello precedente (`half-body.glb`) ne aveva 18.
- Three.js è caricato da CDN (unpkg). Per uso offline, scaricare i moduli in
  locale e aggiornare l'import map.
- Dipendenza di rete in fase di build: i `.glb` vanno scaricati da GitHub raw
  (il CDN ufficiale RPM non è raggiungibile da questo ambiente).
