import { api } from '../api/client';
import { byId, esc, ts, bySel } from '../utils/dom';

let thinking = false;
let currentVoice = 'vivian';
let currentLang = 'italian';
let msgHistory: string[] = [];
let historyIdx = -1;
const CHAT_KEY = 'jarvis-chat';

export function getVoice() { return currentVoice; }
export function setVoice(v: string) { currentVoice = v; }

export function isThinking() { return thinking; }

export function initChat() {
  const minput = byId<HTMLInputElement>('minput');

  if (minput) {
    minput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
      if (e.key === 'ArrowUp') { e.preventDefault(); navHistory(-1); }
      if (e.key === 'ArrowDown') { e.preventDefault(); navHistory(1); }
    });
    minput.addEventListener('input', autoResize);
  }

  loadStatus();
  restoreChat();
  showWelcome();
}

function navHistory(dir: number) {
  const inp = byId<HTMLInputElement>('minput');
  if (!inp) return;
  if (msgHistory.length === 0) return;
  historyIdx = Math.max(-1, Math.min(msgHistory.length - 1, historyIdx + dir));
  inp.value = historyIdx >= 0 ? msgHistory[msgHistory.length - 1 - historyIdx] : '';
}

function autoResize() {
  const inp = byId<HTMLInputElement>('minput');
  if (!inp) return;
  inp.style.height = 'auto';
  inp.style.height = Math.min(inp.scrollHeight, 160) + 'px';
}

async function loadStatus() {
  try {
    const st = await api.status();
    const dot = byId('status-dot');
    const txt = byId('status-text');
    const model = byId('top-model');
    if (dot) dot.className = 'dot online';
    if (txt) txt.textContent = 'ONLINE';
    if (model) model.textContent = st.model || 'unknown';
  } catch {
    const dot = byId('status-dot');
    const txt = byId('status-text');
    if (dot) dot.className = 'dot offline';
    if (txt) txt.textContent = 'OFFLINE';
  }
}

export function sendMessage() {
  const minput = byId<HTMLInputElement>('minput');
  if (!minput) return;
  const text = minput.value.trim();
  if (!text || thinking) return;
  msgHistory.push(text);
  historyIdx = -1;
  minput.value = '';
  minput.style.height = '';
  minput.blur();
  doChat(text);
}

function showWelcome() {
  const msgs = byId('msgs');
  if (!msgs || msgs.children.length > 0) return;
  const suggestions = [
    { label: 'Cosa sai fare?', icon: '⚡', cmd: 'Cosa sai fare? Raccontami le tue capacità.' },
    { label: 'Che tempo fa?', icon: '🌤️', cmd: 'Che tempo fa oggi a Berlino?' },
    { label: 'Stato sistema', icon: '🖥️', cmd: 'Mostrami lo stato del sistema' },
    { label: 'Notizie tech', icon: '📰', cmd: 'Quali sono le ultime notizie tech?' },
    { label: 'Calendario', icon: '📅', cmd: 'Cosa ho in agenda oggi?' },
    { label: 'Cerca file', icon: '🔍', cmd: 'Cerca file con estensione .py' },
  ];
  const d = document.createElement('div');
  d.className = 'welcome-screen';
  d.innerHTML = `
    <div class="welcome-title">J.A.R.V.I.S</div>
    <div class="welcome-sub">SYSTEM READY — Inizia una conversazione</div>
    <div class="welcome-grid">
      ${suggestions.map(s => `
        <button class="welcome-chip" data-cmd="${esc(s.cmd)}">
          <span class="wc-icon">${s.icon}</span>
          <span class="wc-label">${s.label}</span>
        </button>
      `).join('')}
    </div>
  `;
  d.querySelectorAll('.welcome-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const cmd = (btn as HTMLElement).dataset.cmd || '';
      doChat(cmd);
    });
  });
  msgs.appendChild(d);
}

function hideWelcome() {
  const w = bySel('.welcome-screen');
  if (w) w.remove();
}

function saveChat() {
  const msgs = byId('msgs');
  if (!msgs) return;
  const items: { type: string; text: string; time: string }[] = [];
  msgs.querySelectorAll('.msg').forEach(el => {
    const isUser = !!el.querySelector('.msg-avatar.user');
    const body = el.querySelector('.msg-body');
    items.push({
      type: isUser ? 'user' : 'bot',
      text: body?.textContent || '',
      time: el.querySelector('.msg-time')?.textContent || '',
    });
  });
  try { localStorage.setItem(CHAT_KEY, JSON.stringify(items.slice(-50))); } catch {}
}

function restoreChat() {
  try {
    const raw = localStorage.getItem(CHAT_KEY);
    if (!raw) return;
    const items = JSON.parse(raw);
    if (!Array.isArray(items)) return;
    items.forEach((item: any) => {
      if (item.type === 'user') addUserMsg(item.text, item.time);
      else addBotMsg(item.text, [], item.time);
    });
  } catch {}
}

async function doChat(text: string) {
  if (thinking || !text) return;
  thinking = true;
  hideWelcome();
  addUserMsg(text);
  showThinking(true);
  setHoloState('thinking');
  saveChat();

  const t0 = Date.now();
  let fullReply = '';
  try {
    for await (const msg of api.chatStreamFetch(text)) {
      switch (msg.type) {
        case 'reply':
          hideThinking();
          fullReply = msg.data || '';
          if (fullReply) {
            addBotMsg(fullReply);
            updateLatency(((Date.now() - t0) / 1000).toFixed(2));
            if (msg.model) showTierBadge(msg.model);
            speak(fullReply);
          }
          break;
        case 'actions':
          if (msg.data) {
            let parsed: any[];
            if (Array.isArray(msg.data)) {
              parsed = msg.data;
            } else {
              try { parsed = JSON.parse(msg.data); } catch { parsed = []; }
            }
            if (Array.isArray(parsed)) handleActions(parsed);
          }
          break;
        case 'audio_chunk':
          if (msg.data) playAudioChunk(msg.data, msg.format || 'mp3');
          break;
        case 'error':
          hideThinking();
          fullReply = `error: ${msg.data}`;
          addBotMsg(fullReply);
          break;
        case 'done':
          thinking = false;
          saveChat();
          if (byId('minput')) byId('minput')!.focus();
          break;
      }
    }
  } catch (e: any) {
    hideThinking();
    const errMsg = `error: ${e.message}`;
    addBotMsg(errMsg, [], undefined, true);
    thinking = false;
    saveChat();
  }
  if (holoState !== 'speaking') setHoloState('idle');
}

function addUserMsg(text: string, timeOverride?: string) {
  const msgs = byId('msgs');
  if (!msgs) return;
  const d = document.createElement('div');
  d.className = 'msg user';
  const t = timeOverride || ts();
  d.innerHTML = `<div class="msg-header"><div class="msg-avatar user">U</div><span class="msg-name user">YOU</span><span class="msg-time">${t}</span></div><div class="msg-body user-msg">${esc(text)}</div>`;
  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
}

export function addBotMsg(text: string, _actions: string[] = [], timeOverride?: string, isError = false) {
  const msgs = byId('msgs');
  if (!msgs) return;
  const d = document.createElement('div');
  d.className = `msg${isError ? ' error' : ' jarvis'}`;
  const t = timeOverride || ts();
  let rendered = (typeof marked !== 'undefined' ? marked.parse(text || '') : (text || '').replace(/\n/g, '<br>'));
  rendered = enhanceCodeBlocks(rendered);
  d.innerHTML = `
    <div class="msg-header">
      <div class="msg-avatar jarvis">AI</div>
      <span class="msg-name jarvis">J.A.R.V.I.S</span>
      <span class="msg-time">${t}</span>
      <div class="msg-actions">
        <button class="msg-action copy-btn" title="Copia">📋</button>
        ${isError ? '<button class="msg-action retry-btn" title="Riprova">⟳</button>' : ''}
      </div>
    </div>
    <div class="msg-body jarvis-msg">${rendered}</div>`;
  
  const copyBtn = d.querySelector('.copy-btn');
  copyBtn?.addEventListener('click', () => {
    navigator.clipboard.writeText(text).then(() => {
      copyBtn.textContent = '✓';
      setTimeout(() => { copyBtn.textContent = '📋'; }, 1500);
    });
  });

  const retryBtn = d.querySelector('.retry-btn');
  retryBtn?.addEventListener('click', () => {
    const lastUserMsg = msgs.querySelector('.msg:has(.msg-avatar.user):last-child');
    if (lastUserMsg) {
      const textEl = lastUserMsg.querySelector('.msg-body');
      if (textEl?.textContent) doChat(textEl.textContent);
    }
  });

  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
  updateMsgCount();
}

function enhanceCodeBlocks(html: string): string {
  return html.replace(/<pre><code class="language-(\w+)">([\s\S]*?)<\/code><\/pre>/g, (_, lang, code) => {
    const escaped = esc(code);
    return `<div class="code-block"><div class="code-header"><span class="code-lang">${esc(lang)}</span><button class="code-copy" data-code="${esc(escaped)}">📋</button></div><pre><code class="language-${esc(lang)}">${escaped}</code></pre></div>`;
  }).replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    const escaped = esc(code);
    return `<div class="code-block"><div class="code-header"><span class="code-lang">CODE</span><button class="code-copy" data-code="${esc(escaped)}">📋</button></div><pre><code>${escaped}</code></pre></div>`;
  });
}

function handleActions(_actions: string[]) {
  for (const a of _actions) {
    if (a.startsWith('SPEECH:')) continue;
    if (a.startsWith('WEBCAM:')) {
      try { openWebcam(JSON.parse(a.slice(7))); } catch {}
    } else if (a.startsWith('WEBCAM_GRID:')) {
      try { openWebcamGrid(JSON.parse(a.slice(12))); } catch {}
    } else if (a.startsWith('WORLD_NEWS_GLOBE:')) {
      window.location.hash = '#worldnews';
    } else if (a.startsWith('WEATHER_CARD:')) {
      try { showWeatherCard(JSON.parse(a.slice(13))); } catch {}
    } else if (a.startsWith('HA_DASHBOARD:')) {
      openHAWidget();
    }
  }
}

function openWebcam(data: any) {
  const w = byId('webcam-widget');
  if (!w) return;
  w.classList.remove('hidden');
  const title = byId('webcam-title');
  const city = byId('webcam-city');
  if (title) title.textContent = `📡 ${data.city}`;
  if (city) city.textContent = data.city?.toUpperCase() || '--';
  const f = byId('webcam-iframe');
  if (f && data.video_id) {
    f.innerHTML = '';
    const ifr = document.createElement('iframe');
    ifr.src = `https://www.youtube.com/embed/${data.video_id}?autoplay=1&mute=1&loop=1&controls=0&rel=0`;
    ifr.allow = 'autoplay; encrypted-media; picture-in-picture';
    ifr.allowFullscreen = true;
    ifr.style.width = '100%';
    ifr.style.height = '100%';
    ifr.style.border = '0';
    f.appendChild(ifr);
  }
}

function openWebcamGrid(data: any) {
  const w = byId('webcam-grid-widget');
  const b = byId('webcam-grid-body');
  if (!w || !b) return;
  w.classList.remove('hidden');
  b.innerHTML = '';
  if (!Array.isArray(data)) return;
  data.forEach(function(c: any) {
    const card = document.createElement('div');
    card.className = 'wc-grid-card';
    const hdr = document.createElement('div');
    hdr.className = 'wc-grid-card-header';
    hdr.textContent = c.name;
    const body = document.createElement('div');
    body.className = 'wc-grid-card-body';
    if (c.video_id) {
      const ifr = document.createElement('iframe');
      ifr.src = `https://www.youtube.com/embed/${c.video_id}?autoplay=1&mute=1&loop=1&controls=0&rel=0`;
      ifr.allow = 'autoplay; encrypted-media; picture-in-picture';
      ifr.allowFullscreen = true;
      ifr.style.width = '100%';
      ifr.style.height = '100%';
      ifr.style.border = '0';
      body.appendChild(ifr);
    } else {
      body.innerHTML = `<div class="no-vid">📡 ${c.name}<br>Nessuna live trovata</div>`;
    }
    card.appendChild(hdr);
    card.appendChild(body);
    b.appendChild(card);
  });
}

function openHAWidget() {
  const w = byId('ha-widget');
  const f = byId<HTMLIFrameElement>('ha-widget-iframe');
  if (w) w.classList.remove('hidden');
  if (f) f.src = 'https://mikweb.info';
}

function showWeatherCard(_data: any) {}

function updateMsgCount() {
  const el = byId('msg-count');
  if (el) {
    const count = parseInt(el.textContent || '0') + 1;
    el.textContent = `${count} MSG`;
  }
}

function updateLatency(lat: string) {
  const el = byId('latbar');
  if (el) el.textContent = `LAT ${lat}s`;
}

function showThinking(on: boolean) {
  const el = byId('thinkEl');
  if (el) el.classList.toggle('active', on);
}

function hideThinking() {
  showThinking(false);
}

function showTierBadge(model: string) {
  const el = byId('tier-indicator');
  if (!el) return;
  const isFast = model.includes('8b') || model.includes('instant');
  el.className = isFast ? 'fast' : 'deep';
  el.textContent = isFast ? `⚡ FAST — ${model}` : `🧠 DEEP — ${model}`;
  setTimeout(() => { el.className = ''; }, 4000);
  triggerGlitch();
}

function triggerGlitch() {
  const bar = bySel('.glitch-bar');
  if (bar) {
    (bar as HTMLElement).style.top = `${Math.random() * 100}%`;
    (bar as HTMLElement).style.left = '0';
    (bar as HTMLElement).style.width = `${20 + Math.random() * 40}%`;
  }
}

async function speak(text: string) {
  if (!text) return;
  const wg = byId('avatar-widget');
  wg?.classList.add('speaking');

  try {
    const blob = await api.tts(text, currentVoice, currentLang);
    setHoloState('speaking');
    const done = () => {
      wg?.classList.remove('speaking');
      if (holoState === 'speaking') setHoloState('idle');
    };
    if ((window as any).Avatar3D?.speak) {
      (window as any).Avatar3D.speak(blob, done);
    } else {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => { URL.revokeObjectURL(url); done(); };
      audio.onerror = () => { URL.revokeObjectURL(url); done(); };
      audio.play().catch(done);
    }
  } catch {
    wg?.classList.remove('speaking');
    if (holoState === 'speaking') setHoloState('idle');
  }
}

function playAudioChunk(b64: string, _format: string) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes]);
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.onended = () => URL.revokeObjectURL(url);
  audio.play().catch(() => {});
}

let recognition: any = null;
let micActive = false;

function toggleMic() {
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!SR) return;
  if (micActive) { stopMic(); return; }
  recognition = new SR();
  recognition.lang = 'it-IT';
  recognition.continuous = false;
  recognition.onresult = (e: any) => {
    let t = '';
    for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
    const inp = byId<HTMLInputElement>('minput');
    if (inp) inp.value = t;
    if (e.results[e.results.length - 1].isFinal) {
      stopMic();
      setTimeout(() => doChat(t), 150);
    }
  };
  recognition.onerror = () => stopMic();
  recognition.onend = () => { if (micActive) stopMic(); };
  try { recognition.start(); micActive = true; } catch { stopMic(); }
}

function stopMic() {
  micActive = false;
  if (recognition) try { recognition.stop(); } catch {}
}

let holoState: 'idle' | 'thinking' | 'speaking' = 'idle';

function setHoloState(state: 'idle' | 'thinking' | 'speaking') {
  holoState = state;
  const reactor = byId('cyber-reactor');
  const core = reactor?.querySelector('.reactor-core');
  const status = byId('holo-status');
  const wg = byId('avatar-widget');

  if ((window as any).Avatar3D?.setState) {
    (window as any).Avatar3D.setState(state);
  }

  if (state === 'thinking') {
    if (reactor) (reactor as HTMLElement).style.opacity = '0.6';
    if (core) {
      (core as HTMLElement).style.background = 'var(--am)';
      (core as HTMLElement).style.boxShadow = '0 0 20px var(--amg),0 0 60px rgba(255,170,0,0.4)';
    }
    if (status) { status.textContent = '◉ PROCESSING...'; status.className = 'thinking'; }
    if (wg) {
      (wg as HTMLElement).style.borderColor = 'rgba(255,170,0,0.3)';
      (wg as HTMLElement).style.boxShadow = '0 0 20px rgba(255,170,0,0.12),inset 0 0 30px rgba(255,170,0,0.03)';
    }
  } else if (state === 'speaking') {
    if (reactor) (reactor as HTMLElement).style.opacity = '0.5';
    if (core) {
      (core as HTMLElement).style.background = 'var(--cy)';
      (core as HTMLElement).style.boxShadow = '0 0 20px var(--cyg),0 0 60px rgba(0,240,255,0.4)';
    }
    if (status) { status.textContent = '◉ SPEAKING...'; status.className = 'speaking'; }
    if (wg) {
      (wg as HTMLElement).style.borderColor = 'rgba(0,240,255,0.4)';
      (wg as HTMLElement).style.boxShadow = '0 0 30px rgba(0,240,255,0.15),inset 0 0 40px rgba(0,240,255,0.04)';
    }
  } else {
    if (reactor) (reactor as HTMLElement).style.opacity = 'var(--reactor-bg,0.35)';
    if (core) {
      (core as HTMLElement).style.background = 'var(--cy)';
      (core as HTMLElement).style.boxShadow = '0 0 20px var(--cyg),0 0 60px rgba(0,240,255,0.2)';
    }
    if (status) { status.textContent = '◆ SYSTEM STANDBY ◆'; status.className = 'idle'; }
    if (wg) {
      (wg as HTMLElement).style.borderColor = 'rgba(0,240,255,0.2)';
      (wg as HTMLElement).style.boxShadow = '0 0 20px rgba(0,240,255,0.08),inset 0 0 30px rgba(0,240,255,0.02)';
    }
  }
}

export function updateTopTime() {
  const el = byId('top-time');
  if (el) el.textContent = new Date().toLocaleTimeString('it', { hour: '2-digit', minute: '2-digit' });
}

(window as any).sendMessage = sendMessage;
(window as any).doChat = doChat;
(window as any).speak = speak;
(window as any).setHoloState = setHoloState;
(window as any).toggleMic = toggleMic;
(window as any).clearChat = () => {
  const msgs = byId('msgs');
  if (msgs) { msgs.innerHTML = ''; localStorage.removeItem(CHAT_KEY); showWelcome(); }
};
