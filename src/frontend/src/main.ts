import { api } from './api/client';
import { byId, byAll } from './utils/dom';
import { initChat, updateTopTime, sendMessage, setVoice } from './components/chat';
import { initTheme } from './components/theme';
import { initRouting } from './components/routing';

// ── Global state ──
let srvOnline = false;

// ── Boot Sequence ──
(function boot() {
  const bar = byId('boot-fill');
  if (!bar) return;
  const steps = [
    { p: 25, d: 300 }, { p: 50, d: 600 },
    { p: 75, d: 900 }, { p: 100, d: 1200 },
  ];
  steps.forEach((s) => setTimeout(() => { bar!.style.width = `${s.p}%`; }, s.d));
  setTimeout(() => byId('boot')?.classList.add('hidden'), 1500);
})();

// ── Legacy page loading (pages/*.html via XHR) — runs BEFORE DOMContentLoaded ──
loadPages();

// ── DOM refs exposed for legacy pages (available after loadPages) ──
(window as any).msgsEl = byId('msgs');
(window as any).spkbar = byId('spkbar');
(window as any).sendbtn = byId('sendbtn');
(window as any).micbtn = byId('micbtn');
(window as any).minput = byId('minput');
(window as any).msgCountEl = byId('msg-count');
(window as any).logBox = byId('log-box');

// ── System message (exposed for legacy pages) ──
function sysmsg(text: string) {
  const msgs = byId('msgs');
  if (!msgs) return;
  const d = document.createElement('div');
  d.className = 'msg sys-msg';
  const t = new Date().toLocaleTimeString('it', { hour: '2-digit', minute: '2-digit' });
  d.innerHTML = `<div class="msg-header"><div class="msg-avatar sys">S</div><span class="msg-name sys">SYSTEM</span><span class="msg-time">${t}</span></div><div class="msg-body sys-msg">${text}</div>`;
  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
}
(window as any).sysmsg = sysmsg;

// ── UI Button handlers ──
byId('webcam-close')?.addEventListener('click', () => byId('webcam-widget')?.classList.add('hidden'));
byId('webcam-grid-close')?.addEventListener('click', () => byId('webcam-grid-widget')?.classList.add('hidden'));
byId('ha-widget-close')?.addEventListener('click', () => byId('ha-widget')?.classList.add('hidden'));
byId('mob-actions-btn')?.addEventListener('click', () => byId('mob-backdrop')?.classList.toggle('hidden'));
byId('mob-backdrop')?.addEventListener('click', () => byId('mob-backdrop')?.classList.add('hidden'));
byId('mob-drawer-close')?.addEventListener('click', () => byId('mob-backdrop')?.classList.add('hidden'));

// ── Clock ──
function tick() {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  const days = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];
  const mo = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

  const td = byId('time-display');
  if (td) td.innerHTML = `${p(d.getHours())}:${p(d.getMinutes())}<span class="sec">${p(d.getSeconds())}</span>`;
  byId('day-name')!.textContent = days[d.getDay()];
  byId('day-num')!.textContent = p(d.getDate());
  byId('month-name')!.textContent = mo[d.getMonth()];
  byId('year-num')!.textContent = String(d.getFullYear());
  updateTopTime();
  renderClocks(d);
}

function renderClocks(now: Date) {
  const zones = [
    { city: 'BERLIN', tz: 'Europe/Berlin' },
    { city: 'NEW YORK', tz: 'America/New_York' },
    { city: 'TOKYO', tz: 'Asia/Tokyo' },
    { city: 'LONDON', tz: 'Europe/London' },
    { city: 'SYDNEY', tz: 'Australia/Sydney' },
  ];
  const el = byId('clocks-list');
  if (!el) return;
  el.innerHTML = zones
    .map((z) => {
      const t = now.toLocaleTimeString('en-US', { timeZone: z.tz, hour: '2-digit', minute: '2-digit', hour12: false });
      return `<div class="clock-item"><span class="clock-city">${z.city}</span><span class="clock-time">${t}</span></div>`;
    })
    .join('');
}

// ── Weather ──
async function loadWeather() {
  try {
    const r = await fetch(
      'https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,surface_pressure&timezone=Europe/Berlin'
    );
    const d = await r.json();
    const c = d.current;
    byId('w-temp')!.innerHTML = `${Math.round(c.temperature_2m)}<span class="unit">°</span>`;
    byId('w-hum')!.textContent = `${c.relative_humidity_2m}%`;
    byId('w-wind')!.textContent = `${Math.round(c.wind_speed_10m)} km/h`;
    byId('w-feels')!.textContent = `${Math.round(c.apparent_temperature)}°`;
    byId('w-press')!.textContent = `${Math.round(c.surface_pressure)} hPa`;
    byId('atmo-hum')!.textContent = `${c.relative_humidity_2m}%`;
    byId('atmo-hum-bar')!.style.width = `${c.relative_humidity_2m}%`;

    const descs: Record<number, string> = { 0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast', 45: 'Foggy', 48: 'Rime fog', 51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle', 61: 'Light rain', 63: 'Rain', 65: 'Heavy rain', 71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 80: 'Light showers', 81: 'Showers', 82: 'Heavy showers', 95: 'Thunderstorm', 96: 'Thunderstorm with hail', 99: 'Severe thunderstorm' };
    const icons: Record<number, string> = { 0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️', 45: '🌫️', 48: '🌫️', 51: '🌦️', 53: '🌧️', 55: '🌧️', 61: '🌧️', 63: '🌧️', 65: '🌧️', 71: '❄️', 73: '❄️', 75: '🌨️', 80: '🌦️', 81: '🌧️', 82: '🌧️', 95: '⛈️', 96: '⛈️', 99: '⛈️' };
    byId('w-desc')!.textContent = `${icons[c.weather_code] || '🌡️'} ${descs[c.weather_code] || ''}`;
  } catch {
    byId('w-desc')!.textContent = 'OFFLINE';
  }
}

// ── System Info ──
async function loadSysInfo() {
  if (!srvOnline) return;
  try {
    const d = await api.sysinfo();
    const diskPct = parseInt((d.disk_pct || '0%').replace('%', '')) || 0;
    const battPct = parseInt((d.battery || '0%').replace('%', '')) || 0;

    byId('disk-fill')!.style.width = `${diskPct}%`;
    byId('disk-used')!.textContent = d.disk_used || '--';
    byId('disk-total')!.textContent = d.disk_total || '--';
    byId('power-pct')!.textContent = `${battPct}%`;
    byId('power-status')!.textContent = battPct > 20 ? 'ACTIVE' : 'LOW';

    const powerRing = byId('power-ring') as HTMLElement & { getAttribute: (s: string) => string; setAttribute: (s: string, v: string) => void };
    if (powerRing) {
      const circumference = 2 * Math.PI * 18;
      powerRing.setAttribute('stroke-dashoffset', String(circumference * (1 - battPct / 100)));
    }

    byId('waste-info')!.textContent = `${d.processes || '--'} processes`;
    byId('uptime')!.textContent = `UPTIME: ${d.uptime || '--'}`;
    byId('visual-label')!.textContent = `CPU ${d.cpu_usage || '0%'} / RAM ${Math.round(100 - (parseInt(d.ram_free) || 70))}%`;
  } catch { /* ignore */ }
}

// ── Ping ──
async function ping() {
  try {
    const st = await api.status();
    srvOnline = true;
    byId('status-dot')!.className = 'dot online';
    byId('status-text')!.textContent = 'ONLINE';
    byId('top-model')!.textContent = st.model || 'unknown';
  } catch {
    srvOnline = false;
    byId('status-dot')!.className = 'dot offline';
    byId('status-text')!.textContent = 'OFFLINE';
  }
}

// ── Init all modules ──
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initRouting();
  initChat();
  initMobDrawer();

  setInterval(tick, 1000);
  setInterval(ping, 10000);
  setInterval(loadSysInfo, 5000);
  setInterval(loadWeather, 300000);

  setTimeout(ping, 500);
  setTimeout(loadSysInfo, 1000);
  setTimeout(loadWeather, 2000);

  tick();
});

function loadPages() {
  const _t = Date.now();

  function load(url: string): string {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, false);
    xhr.send();
    return xhr.responseText;
  }

  function injectWithScripts(el: HTMLElement, html: string) {
    const scripts: string[] = [];
    const cleaned = html.replace(/<script>([\s\S]*?)<\/script>/g, (_m: string, code: string) => { scripts.push(code); return ''; });
    el.innerHTML = cleaned;
    scripts.forEach((code) => {
      const s = document.createElement('script');
      s.textContent = code;
      document.body.appendChild(s);
      document.body.removeChild(s);
    });
  }

  const chatHtml = load(`pages/chat.html?_=${_t}`);
  const dashHtml = load(`pages/dashboard.html?_=${_t}`);
  const memHtml = load(`pages/memory.html?_=${_t}`);
  const ragHtml = load(`pages/rag.html?_=${_t}`);
  const trendsHtml = load(`pages/trends.html?_=${_t}`);
  const worldnewsHtml = load(`pages/worldnews.html?_=${_t}`);
  const gitHtml = load(`pages/git.html?_=${_t}`);
  const goalsHtml = load(`pages/goals.html?_=${_t}`);
  const settingsHtml = load(`pages/settings.html?_=${_t}`);
  const visionHtml = load(`pages/vision.html?_=${_t}`);
  const presHtml = load(`pages/presentation.html?_=${_t}`);
  const imgGenHtml = load(`pages/imagegen.html?_=${_t}`);
  const musicGenHtml = load(`pages/musicgen.html?_=${_t}`);
  const kgHtml = load(`pages/knowledgegraph.html?_=${_t}`);

  byId('center')!.innerHTML = chatHtml;
  const splitIdx = dashHtml.indexOf('<!--RIGHT-->');
  byId('left')!.innerHTML = dashHtml.substring(0, splitIdx);
  byId('right')!.innerHTML = dashHtml.substring(splitIdx + '<!--RIGHT-->'.length);

  const memPanel = byId('mem-panel');
  const ragPanel = byId('rag-panel');
  const trendsPanel = byId('trends-panel');
  const worldnewsPanel = byId('worldnews-panel');
  const gitPanel = byId('git-panel');
  const goalsPanel = byId('goals-panel');
  const settingsPanel = byId('settings-panel');
  const visionPanel = byId('vision-panel');
  const presPanel = byId('presentation-panel');
  const imgGenPanel = byId('imagegen-panel');
  const musicGenPanel = byId('musicgen-panel');
  const kgPanel = byId('knowledgegraph-panel');

  if (memPanel) injectWithScripts(memPanel, memHtml);
  if (ragPanel) injectWithScripts(ragPanel, ragHtml);
  if (trendsPanel) injectWithScripts(trendsPanel, trendsHtml);
  if (worldnewsPanel) injectWithScripts(worldnewsPanel, worldnewsHtml);
  if (gitPanel) injectWithScripts(gitPanel, gitHtml);
  if (goalsPanel) injectWithScripts(goalsPanel, goalsHtml);
  if (settingsPanel) injectWithScripts(settingsPanel, settingsHtml);
  if (visionPanel) injectWithScripts(visionPanel, visionHtml);
  if (presPanel) injectWithScripts(presPanel, presHtml);
  if (imgGenPanel) injectWithScripts(imgGenPanel, imgGenHtml);
  if (musicGenPanel) injectWithScripts(musicGenPanel, musicGenHtml);
  if (kgPanel) injectWithScripts(kgPanel, kgHtml);
}

// ── Voice selection ──
(window as any).selectVoice = function (el: HTMLElement) {
  byAll('.voice-btn').forEach((c) => c.classList.remove('active'));
  el.classList.add('active');
  const voice = el.dataset.voice || 'vivian';
  setVoice(voice);
  api.configUpdate({ qwen3_voice: voice }).catch(() => {});
};

// ── Theme selection (exposed for pages) ──
(window as any).selectTheme = function (el: HTMLElement) {
  const t = el.dataset.theme || 'cyberpunk';
  byAll('.theme-btn').forEach((c) => c.classList.remove('active'));
  el.classList.add('active');
  document.documentElement.className = `theme-${t}`;
  localStorage.setItem('jarvis-theme', t);
};

// ── Quick actions ──
(window as any).qa = async function (tool: string, args: Record<string, any>) {
  try {
    const r = await api.tool(tool, args);
    if (typeof (window as any).sysmsg === 'function') (window as any).sysmsg(r.result || r.result || 'ok');
  } catch (e: any) {
    if (typeof (window as any).sysmsg === 'function') (window as any).sysmsg(`error: ${e.message}`);
  }
};

(window as any).speakAction = async function (tool: string, args: Record<string, any>) {
  try {
    const r = await api.tool(tool, args);
    const result = r.result || 'ok';
    if (typeof (window as any).sysmsg === 'function') (window as any).sysmsg(result);
    sendMessage();
  } catch {}
};

(window as any).mailAction = async function () {
  try {
    const d: any = await api.mailUnread();
    const msg: string = d.unread || '📬 Nessuna email';
    if (typeof (window as any).sysmsg === 'function') (window as any).sysmsg(msg);
    if (msg.includes('Nessuna')) return;
  } catch {}
};

// ── Mobile drawer: page navigation ──
function initMobDrawer() {
  const body = byId('mob-drawer-body');
  if (!body) return;
  const pages = [
    { label: 'CONSOLE', hash: 'chat', icon: '💬' },
    { label: 'MEMORIA', hash: 'memory', icon: '🧠' },
    { label: 'RAG', hash: 'rag', icon: '📁' },
    { label: 'TRENDS', hash: 'trends', icon: '📈' },
    { label: 'MONDO', hash: 'worldnews', icon: '🌍' },
    { label: 'GIT', hash: 'git', icon: '⎇' },
    { label: 'OKR', hash: 'goals', icon: '🎯' },
    { label: 'VISION', hash: 'vision', icon: '📹' },
    { label: 'SLIDE', hash: 'presentation', icon: '📊' },
    { label: 'IMG', hash: 'imagegen', icon: '🎨' },
    { label: 'MUSIC', hash: 'musicgen', icon: '🎵' },
    { label: 'GRAPH', hash: 'knowledgegraph', icon: '🔗' },
    { label: '⚙', hash: 'settings', icon: '' },
  ];
  body.innerHTML = pages.map(p =>
    `<a class="mob-page-link" href="#${p.hash}" data-page-link="${p.hash}"
        style="display:flex;align-items:center;gap:6px;padding:10px 12px;
               color:var(--tx2);text-decoration:none;font-family:var(--fd);
               font-size:9px;letter-spacing:0.1em;border-bottom:1px solid rgba(255,255,255,0.04);
               -webkit-tap-highlight-color:transparent">
      ${p.icon} ${p.label}
    </a>`
  ).join('');
  // Highlight active page on click
  body.addEventListener('click', () => {
    byId('mob-backdrop')?.classList.add('hidden');
  });
}

// ── Panel open/close for new pages ──
(window as any).openImageGen = function () {
  byId('imagegen-panel')?.classList.add('open');
};
(window as any).openMusicGen = function () {
  byId('musicgen-panel')?.classList.add('open');
};
(window as any).openKG = function () {
  byId('knowledgegraph-panel')?.classList.add('open');
};

// ── Legacy exports for pages ──
(window as any).send = sendMessage;
