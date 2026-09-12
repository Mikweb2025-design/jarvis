/* worldnews.js — J.A.R.V.I.S World News Globe v8.0 — TOP5 ITALIANO CINEMATIC EDITION */
import * as THREE from 'three';

let wnData = [];
let wnGlobe = null;
let wnGlobeScene = null;
let wnGlobeCamera = null;
let wnGlobeRenderer = null;
let _wnAnimFrame = null;
let _wnAutoRotate = true;
let _wnSelected = null;
let _wnBeam = null;
let _wnParticles = [];
let _wnEntranceDone = false;
let _wnAutoPilot = false;
let _wnAutoPilotInterval = null;
let _wnHoveredMarker = null;
let _wnDragTimeout = null;
let _wnZooming = false;
let _wnCloudMesh = null;
let _wnArcs = [];
let _wnArcParticles = [];
let _wnGlobeAngle = 0;
let _wnDragVelocity = 0;
let _wnDragHistory = [];
let _wnDragDecay = 0.97;
let _wnClusters = [];
/* ── nuovo stato: filtri, sentiment, trending, stats, reel ── */
let _wnTrending = [];
let _wnStats = {};
let _wnCatFilter = 'all';
let _wnSentimentMode = false;
let _wnStatsOpen = false;
let _wnReelOpen = false;
let _wnReelAutoplay = false;
let _wnReelObserver = null;
let _wnReelCurrent = 0;
let _wnReelItems = [];

const CAT_COLORS = {
  conflict: '#ff4444', disaster: '#ff8800', politics: '#4488ff',
  economy: '#44dd88', climate: '#00ff88', tech: '#aa66ff', general: '#888899'
};
const CAT_ICONS = {
  conflict: '⚔', disaster: '🌊', politics: '🏛',
  economy: '💰', climate: '🌿', tech: '🔬', general: '📰'
};
const CAT_EMISSIVE = {
  conflict: 0xff2222, disaster: 0xff6600, politics: 0x2266ff,
  economy: 0x22dd66, climate: 0x00ff66, tech: 0x8844ff, general: 0x666688
};

/* ── TRADUTTORE ── */
const _transCache = {};
const _ITA_RE = /[àèéìòù]/i;
function wnTranslate(text, lang) {
  if (!text || text.length < 3) return Promise.resolve(text);
  if (lang === 'it' || _ITA_RE.test(text)) return Promise.resolve(text);
  const key = text.slice(0, 80);
  if (_transCache[key]) return Promise.resolve(_transCache[key]);
  return fetch('/api/translate', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: text.slice(0, 2000), target: 'italian', source: 'auto'})
  }).then(r => r.json()).then(d => {
    if (d.translated && d.translated !== text) {
      _transCache[key] = d.translated;
      return d.translated;
    }
    return text;
  }).catch(() => text);
}

function wnTranslateBatch(items) {
  return Promise.all(items.map(item => {
    if (item._translated) return item;
    const lang = item.lang || 'en';
    return wnTranslate(item.title, lang).then(tTitle => {
      return wnTranslate(item.snippet, lang).then(tSnippet => {
        item._tTitle = tTitle;
        item._tSnippet = tSnippet;
        item._translated = true;
        return item;
      });
    });
  }));
}

/* ── CITY IMAGE FETCH (Wikipedia → Wikimedia → Gradient fallback) ── */
const _imgCache = {};
function wnFetchCityImage(location, country) {
  const name = (location || country || '').split(',')[0].trim();
  const key = name + '|' + (country || '');
  if (_imgCache[key] === 'LOADING') return Promise.resolve(null);
  if (_imgCache[key]) return Promise.resolve(_imgCache[key]);

  const tryWikipedia = (q) => {
    return fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(q)}`, { mode: 'cors' })
      .then(r => r.ok ? r.json() : Promise.reject('no page'))
      .then(d => d.thumbnail?.source || d.originalimage?.source || null)
      .catch(() => null);
  };

  const tryCommons = (q) => {
    const url = `https://commons.wikimedia.org/w/api.php?action=query&generator=images&titles=${encodeURIComponent(q)}&prop=imageinfo&iiprop=url&format=json&origin=*&gimlimit=3`;
    return fetch(url, { mode: 'cors' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => {
        const pages = d.query?.pages;
        if (pages) {
          for (const p of Object.values(pages)) {
            const url = p?.imageinfo?.[0]?.url;
            if (url && (url.includes('.jpg') || url.includes('.png') || url.includes('.jpeg'))) return url;
          }
        }
        return null;
      })
      .catch(() => null);
  };

  _imgCache[key] = 'LOADING';
  return tryWikipedia(name).then(url => {
    if (url) { _imgCache[key] = url; return url; }
    return tryWikipedia(name + ', ' + (country || '')).then(url2 => {
      if (url2) { _imgCache[key] = url2; return url2; }
      return tryCommons(name).then(url3 => {
        if (url3) { _imgCache[key] = url3; return url3; }
        _imgCache[key] = null;
        return null;
      });
    });
  });
}

function wnInit() {
  console.log('[WN] init');
  const container = document.getElementById('wn-map');
  if (!container) { setTimeout(wnInit, 500); return; }
  if (container._wnInited) return;
  if (container.clientWidth < 10 || container.clientHeight < 10) {
    setTimeout(wnInit, 300); return;
  }
  container._wnInited = true;
  wnRefresh();
}

function wnLoadData(data) {
  wnData = data.news || [];
  window.wnData = wnData;
  _wnTrending = data.trending || [];
  _wnStats = data.stats || {};
  const el = document.getElementById('wn-count');
  if (el) el.textContent = `${wnData.length} notizie`;
  const geo = wnData.filter(n => n.lat).length;
  const badge = document.getElementById('wn-geo-badge');
  if (badge) badge.textContent = `${geo} localizzate`;
  /* Nuovi pannelli */
  wnRenderCategoryChips();
  wnRenderTrending();
  wnRenderStats();
  if (!wnGlobeRenderer) {
    setTimeout(wnInitGlobe, 200);
  } else {
    wnReinitGlobeMarkers();
  }
  /* Render SUBITO con testi originali, traduzione in background poi re-render */
  try { wnRenderList(document.getElementById('wn-search')?.value || ''); } catch (e) {}
  const geoLoc2 = wnData.filter(n => n.lat != null);
  if (geoLoc2.length >= 1 && !_wnAutoBusy) {
    setTimeout(wnStartAutoNews, 4000);
  }
  wnTranslateBatch(wnData.filter(n => !n._translated)).then(() => {
    try { wnRenderList(document.getElementById('wn-search')?.value || ''); } catch (e) {}
  }).catch(() => {});
}

/* ════════════════════════════════════════════════════════════════
   NUOVE FUNZIONI: filtri categoria, sentiment, trending, stats, reel
   ════════════════════════════════════════════════════════════════ */

const CAT_LABELS = {
  all: 'Tutte', conflict: 'Conflitti', disaster: 'Disastri', politics: 'Politica',
  economy: 'Economia', climate: 'Clima', tech: 'Tech', general: 'Generale'
};

function wnSentColor(s) {
  /* sentiment [-1,1] → rosso(neg) → grigio(neutro) → verde(pos) */
  if (s == null) return '#888899';
  if (s < -0.05) { const t = Math.min(1, -s); return `rgb(${Math.round(180+75*t)},${Math.round(80-40*t)},${Math.round(80-40*t)})`; }
  if (s > 0.05)  { const t = Math.min(1, s);  return `rgb(${Math.round(60-20*t)},${Math.round(180+40*t)},${Math.round(120+20*t)})`; }
  return '#888899';
}
function wnSentLabel(s) {
  if (s == null) return '';
  if (s < -0.3) return '😟 negativa';
  if (s < -0.05) return '🙁 neg.';
  if (s > 0.3) return '😀 positiva';
  if (s > 0.05) return '🙂 pos.';
  return '😐 neutra';
}
function wnMarkerColor(n) {
  return _wnSentimentMode ? wnSentColor(n.sentiment) : (CAT_COLORS[n.category] || '#888899');
}

/* ── CATEGORY CHIPS ── */
function wnRenderCategoryChips() {
  const el = document.getElementById('wn-cat-chips');
  if (!el) return;
  const counts = {};
  wnData.forEach(n => { const c = n.category || 'general'; counts[c] = (counts[c]||0)+1; });
  const cats = ['all', 'conflict', 'disaster', 'politics', 'economy', 'climate', 'tech', 'general'];
  el.innerHTML = cats.map(cat => {
    const active = _wnCatFilter === cat;
    const c = cat === 'all' ? '#00f0ff' : (CAT_COLORS[cat] || '#888');
    const icon = cat === 'all' ? '🌐' : (CAT_ICONS[cat] || '📰');
    const n = cat === 'all' ? wnData.length : (counts[cat] || 0);
    if (cat !== 'all' && n === 0) return '';
    return `<button onclick="wnSetCategoryFilter('${cat}')" style="
      background:${active ? c+'22' : 'rgba(0,0,0,0.25)'};
      border:1px solid ${active ? c : '#1a1a2e'};
      color:${active ? c : '#888'};
      padding:3px 10px;border-radius:12px;cursor:pointer;
      font:10px monospace;font-weight:${active?'700':'400'};letter-spacing:0.5px;
      transition:all .2s;display:inline-flex;align-items:center;gap:4px;white-space:nowrap;
      box-shadow:${active ? '0 0 12px '+c+'33' : 'none'}">
      <span>${icon}</span>${CAT_LABELS[cat]||cat}<span style="opacity:0.5;font-size:9px">${n}</span>
    </button>`;
  }).join('');
}

function wnSetCategoryFilter(cat) {
  _wnCatFilter = (_wnCatFilter === cat && cat !== 'all') ? 'all' : cat;
  wnRenderCategoryChips();
  wnRenderList(document.getElementById('wn-search')?.value || '');
  if (typeof wnReinitGlobeMarkers === 'function' && wnGlobeRenderer) wnReinitGlobeMarkers();
}

/* ── TRENDING TICKER ── */
function wnRenderTrending() {
  const track = document.getElementById('wn-trending-track');
  if (!track) return;
  if (!_wnTrending || !_wnTrending.length) { track.innerHTML = ''; return; }
  const maxC = Math.max(..._wnTrending.map(t => t.count), 1);
  const make = () => _wnTrending.map(t => {
    const heat = t.count / maxC;
    const col = heat > 0.66 ? '#ff66cc' : heat > 0.33 ? '#ffaa44' : '#4488ff';
    return `<span onclick="wnRenderList('${t.word.replace(/'/g,'')}');document.getElementById('wn-search')&&(document.getElementById('wn-search').value='${t.word.replace(/'/g,'')}')" style="cursor:pointer;color:${col};font:11px monospace;letter-spacing:0.5px;display:inline-flex;align-items:center;gap:5px">
      <span style="opacity:0.6">#</span>${t.word}<span style="opacity:0.4;font-size:9px">${t.count}</span>
    </span>`;
  }).join('<span style="color:#333;margin:0 14px">•</span>');
  /* duplica per scroll continuo */
  track.innerHTML = make() + '<span style="color:#333;margin:0 14px">•</span>' + make();
  track.style.animation = 'none';
  void track.offsetWidth;
  const dur = Math.max(20, _wnTrending.length * 3);
  track.style.animation = `wnTickerScroll ${dur}s linear infinite`;
}

/* ── STATS PANEL ── */
function wnToggleStats() {
  _wnStatsOpen = !_wnStatsOpen;
  const p = document.getElementById('wn-stats-panel');
  const btn = document.getElementById('wn-stats-btn');
  if (p) p.style.display = _wnStatsOpen ? 'block' : 'none';
  if (btn) { btn.style.color = _wnStatsOpen ? '#00f0ff' : '#666'; }
  if (_wnStatsOpen) wnRenderStats();
}
function wnRenderStats() {
  const p = document.getElementById('wn-stats-panel');
  if (!p || !_wnStatsOpen) return;
  const s = _wnStats || {};
  const cats = s.by_category || {};
  const countries = s.by_country || {};
  const totalCat = Object.values(cats).reduce((a,b)=>a+b,0) || 1;
  const catBars = Object.entries(cats).map(([cat,n]) => {
    const c = CAT_COLORS[cat] || '#888';
    const pct = Math.round(n/totalCat*100);
    return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
      <span style="width:60px;font:9px monospace;color:${c}">${CAT_ICONS[cat]||''} ${(CAT_LABELS[cat]||cat).slice(0,7)}</span>
      <div style="flex:1;height:5px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden">
        <div style="width:${pct}%;height:100%;background:${c};box-shadow:0 0 6px ${c}66"></div></div>
      <span style="width:18px;text-align:right;font:9px monospace;color:#888">${n}</span>
    </div>`;
  }).join('');
  const moodColor = wnSentColor(s.sentiment_avg);
  const moodPct = Math.round(((s.sentiment_avg||0)+1)/2*100);
  const topCountries = Object.entries(countries).slice(0,6).map(([c,n]) =>
    `<span style="font:9px monospace;color:#aaa;background:rgba(0,240,255,0.06);border:1px solid rgba(0,240,255,0.1);border-radius:8px;padding:1px 7px">${c} <b style="color:#00f0ff">${n}</b></span>`
  ).join('');
  p.innerHTML = `
    <div style="background:rgba(0,0,0,0.25);border:1px solid rgba(0,240,255,0.08);border-radius:8px;padding:10px;margin-bottom:6px">
      <div style="font:9px monospace;letter-spacing:2px;color:#00f0ff;margin-bottom:8px;text-transform:uppercase">📊 Per categoria</div>
      ${catBars}
      <div style="font:9px monospace;letter-spacing:2px;color:#ff66cc;margin:10px 0 6px;text-transform:uppercase">◐ Umore globale</div>
      <div style="display:flex;align-items:center;gap:8px">
        <div style="flex:1;height:6px;border-radius:3px;background:linear-gradient(90deg,#cc4444,#888,#44cc88);position:relative">
          <div style="position:absolute;left:${moodPct}%;top:-2px;width:3px;height:10px;background:#fff;border-radius:2px;box-shadow:0 0 6px #fff;transform:translateX(-50%)"></div>
        </div>
        <span style="font:9px monospace;color:${moodColor}">${(s.sentiment_avg>=0?'+':'')}${(s.sentiment_avg||0).toFixed(2)}</span>
      </div>
      <div style="display:flex;gap:8px;margin-top:4px;font:8px monospace;color:#666">
        <span style="color:#cc6666">▼ ${s.sentiment_neg||0} neg</span>
        <span style="color:#66cc88">▲ ${s.sentiment_pos||0} pos</span>
      </div>
      <div style="font:9px monospace;letter-spacing:2px;color:#4488ff;margin:10px 0 6px;text-transform:uppercase">🌍 Hotspot</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px">${topCountries||'<span style="color:#555;font:9px monospace">—</span>'}</div>
    </div>`;
}

/* ── SENTIMENT MODE TOGGLE ── */
function wnToggleSentimentMode() {
  _wnSentimentMode = !_wnSentimentMode;
  const btn = document.getElementById('wn-sentiment-btn');
  if (btn) { btn.style.color = _wnSentimentMode ? '#ff66cc' : '#666'; btn.textContent = _wnSentimentMode ? '◉ MOOD' : '◐ MOOD'; }
  if (wnGlobeRenderer) wnReinitGlobeMarkers();
  wnRenderList(document.getElementById('wn-search')?.value || '');
}

function wnRenderList(filter) {
  const el = document.getElementById('wn-news-list');
  let items = wnData;
  if (_wnCatFilter && _wnCatFilter !== 'all') items = items.filter(n => (n.category||'general') === _wnCatFilter);
  if (filter) items = items.filter(n => (n.title+' '+(n.location||'')+' '+(n.country||'')).toLowerCase().includes(filter.toLowerCase()));
  const limit = (_wnCatFilter !== 'all' || filter) ? 15 : 5;
  let withGeo = items.filter(n => n.lat).slice(0, limit);
  items = withGeo.length ? withGeo : items.slice(0, limit);
  if (items.length === 0) items = wnData.slice(0, 5);
  el.innerHTML = items.map((n, idx) => {
    const loc = n.location || n.country || '';
    const c = CAT_COLORS[n.category] || '#888';
    const icon = CAT_ICONS[n.category] || '📰';
    const t = n._tTitle || n.title || '';
    const rank = idx + 1;
    const delay = idx * 80;
    return `<div class="wn-card" onclick="wnSelectNews(wnData[${wnData.indexOf(n)}])" style="position:relative;background:linear-gradient(135deg,rgba(20,20,40,0.6),rgba(15,15,30,0.8));border:1px solid rgba(255,255,255,0.04);border-left:2px solid ${c};border-radius:6px;padding:10px 30px 10px 10px;margin-bottom:4px;cursor:pointer;animation:wnCardIn .35s ease-out ${delay}ms both;transition:all .25s cubic-bezier(0.175,0.885,0.32,1.275);backdrop-filter:blur(4px);overflow:hidden"
      onmouseenter="this.style.borderColor='${c}88';this.style.transform='translateX(4px)';this.style.boxShadow='0 0 20px ${c}22'"
      onmouseleave="this.style.borderColor='rgba(255,255,255,0.04)';this.style.transform='none';this.style.boxShadow='none'">
      <div style="position:absolute;top:0;right:0;width:60px;height:100%;background:linear-gradient(270deg,rgba(0,240,255,0.02),transparent);pointer-events:none"></div>
      <div style="position:absolute;top:-8px;right:-8px;width:32px;height:32px;border-radius:50%;background:radial-gradient(circle at center,${c}22,transparent 70%);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:800;color:${c};text-shadow:0 0 8px ${c}44">${rank}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
        <span style="display:inline-flex;align-items:center;gap:3px;color:${c};font-size:9px;font-weight:600;letter-spacing:1px;text-transform:uppercase">${icon} ${n.source}</span>
        <span style="color:#444;font-size:8px;font-family:monospace">${(n.published||'').slice(0,10)}</span>
      </div>
      <div style="font-size:11.5px;line-height:1.35;color:#ccc;margin-bottom:3px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${t}</div>
      ${loc ? `<div style="display:flex;align-items:center;gap:5px;margin-top:4px;padding:3px 6px;background:rgba(0,240,255,0.06);border:1px solid rgba(0,240,255,0.1);border-radius:4px">
        <span style="font-size:11px">📍</span>
        <span style="font-size:10px;color:#00f0ff;font-weight:600;letter-spacing:0.5px">${loc}</span>
        ${n.country ? `<span style="font-size:8px;color:rgba(0,240,255,0.4)">· ${n.country}</span>` : ''}
        <span style="flex:1"></span>
        <span style="font-size:7px;color:rgba(0,240,255,0.3);font-family:monospace">${n.lat ? n.lat.toFixed(1) + ',' + n.lon.toFixed(1) : ''}</span>
      </div>` : '<div style="margin-top:4px"></div>'}
      <div style="position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,${c}44,transparent);transform:scaleX(0);transition:transform .3s" onmouseenter="this.style.transform='scaleX(1)'" onmouseleave="this.style.transform='scaleX(0)'"></div>
    </div>`;
  }).join('');
  const untranslated = wnData.filter(n => !n._translated);
  if (untranslated.length > 0) {
    wnTranslateBatch(untranslated).then(() => {
      wnRenderList(filter);
    });
  }
}

function wnSelectNews(n) {
  _wnSelected = n;
  _wnZooming = true;
  _wnAutoRotate = false;

  /* Breaking news bar */
  const breakBar = document.getElementById('wn-breaking-bar');
  const breakText = document.getElementById('wn-breaking-text');
  if (breakBar && breakText) {
    breakText.textContent = (n._tTitle || n.title).slice(0, 80);
    breakBar.style.display = 'flex';
    breakBar.style.animation = 'none';
    void breakBar.offsetWidth;
    breakBar.style.animation = 'wnSlideDown .4s ease-out';
    setTimeout(() => { if (breakBar) breakBar.style.display = 'none'; }, 5000);
  }

  /* SCREEN SHAKE + flash */
  wnScreenShake(6, 400);
  const flash = document.getElementById('wn-flash');
  if (flash) { flash.style.opacity = '0.25'; setTimeout(() => { flash.style.opacity = '0'; }, 600); }

  /* HUD burst */
  wnHUDDataBurst(n);

  /* Globe pulse ring effect */
  if (n.lat && wnGlobeRenderer) {
    const pulseRing = document.createElement('div');
    pulseRing.style.cssText = `
      position:absolute;left:50%;top:50%;width:20px;height:20px;
      border:1px solid ${CAT_COLORS[n.category] || '#00f0ff'};
      border-radius:50%;transform:translate(-50%,-50%) scale(1);
      pointer-events:none;z-index:3;opacity:0.8;
      box-shadow:0 0 20px ${CAT_COLORS[n.category] || '#00f0ff'}44,inset 0 0 20px ${CAT_COLORS[n.category] || '#00f0ff'}22;
      animation:wnRadarPulse 1.2s ease-out forwards
    `;
    const map = document.getElementById('wn-map');
    if (map) map.appendChild(pulseRing);
    setTimeout(() => { if (pulseRing.parentNode) pulseRing.parentNode.removeChild(pulseRing); }, 1500);
  }

  const doShow = (imgUrl) => {
    if (!n._translated) {
      wnTranslate(n.title, n.lang).then(tTitle => {
        n._tTitle = tTitle;
        return wnTranslate(n.snippet, n.lang).then(tSnippet => {
          n._tSnippet = tSnippet;
          n._translated = true;
          wnShowDetail(n, imgUrl);
        });
      }).catch(() => wnShowDetail(n, imgUrl));
    } else {
      wnShowDetail(n, imgUrl);
    }
  };

  if (n.lat && (n.location || n.country)) {
    wnFetchCityImage(n.location, n.country).then(imgUrl => {
      doShow(imgUrl);
    }).catch(() => doShow(null));
  } else {
    doShow(null);
  }

  if (n.lat && wnGlobeRenderer) {
    wnGlobeFlyTo(n);
  }

  if (_wnAutoPilot) wnToggleAutoPilot();
  setTimeout(() => wnSpeakNews(n), 1200);
}

/* ── SCREEN SHAKE ── */
let _wnShakeTimeout = null;
function wnScreenShake(intensity, duration) {
  const container = document.getElementById('wn-map');
  if (!container) return;
  if (_wnShakeTimeout) clearInterval(_wnShakeTimeout);
  const start = performance.now();
  const origTransform = container.style.transform || '';
  function shake() {
    const elapsed = performance.now() - start;
    if (elapsed > duration) {
      container.style.transform = origTransform;
      return;
    }
    const decay = 1 - elapsed / duration;
    const x = (Math.random() - 0.5) * intensity * decay;
    const y = (Math.random() - 0.5) * intensity * decay;
    container.style.transform = `${origTransform} translate(${x}px, ${y}px)`;
    requestAnimationFrame(shake);
  }
  shake();
}

/* ── HUD DATA BURST ── */
let _wnHUDEl = null;
function wnHUDDataBurst(n) {
  let hud = document.getElementById('wn-hud-overlay');
  if (!hud) {
    hud = document.createElement('div');
    hud.id = 'wn-hud-overlay';
    hud.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:5;overflow:hidden';
    const map = document.getElementById('wn-map');
    if (map) map.appendChild(hud);
  }
  /* Scrolling data lines */
  const lines = [];
  const sources = ['SATLINK','GEOINT','NEWSFEED','DEEPSCAN','CYPHER','DATARIFT'];
  for (let i = 0; i < 6; i++) {
    const src = sources[i % sources.length];
    const val = Math.floor(Math.random() * 9999);
    lines.push(`[${src}] ${'>'.repeat(Math.min(Math.floor(Math.random()*20), 12))} PKT_${val}`);
  }
  hud.innerHTML = lines.map((l, i) => {
    const delay = i * 60;
    return `<div style="font:10px/1.4 'Rajdhani',monospace;color:#00f0ff;opacity:0;animation:wnHUDLine .6s ease-out ${delay}ms forwards;text-shadow:0 0 6px rgba(0,240,255,0.3)">${l}</div>`;
  }).join('');
  setTimeout(() => { if (hud) hud.innerHTML = ''; }, 3000);
}

/* ── TTS ── */
let _wnCurrentAudio = null;
let _wnLastAudioUrl = null;

/* Sblocca l'audio al primo gesto utente (autoplay policy dei browser) */
(function wnAudioUnlock() {
  const unlock = () => {
    try {
      window._wnAudioCtx = window._wnAudioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (window._wnAudioCtx.state === 'suspended') window._wnAudioCtx.resume();
    } catch (e) {}
    if (_wnLastAudioUrl && !_wnCurrentAudio) {
      /* c'era un audio bloccato in attesa: riproducilo ora */
      const a = new Audio(_wnLastAudioUrl);
      _wnCurrentAudio = a;
      a.play().catch(() => { _wnCurrentAudio = null; });
    }
  };
  document.addEventListener('pointerdown', unlock, true);
  document.addEventListener('keydown', unlock, true);
})();

function wnSpeakNews(n) {
  const tTitle = n._tTitle || n.title;
  const tSnippet = n._tSnippet || n.snippet;
  /* TTS locale veloce: max ~480 caratteri (oltre scatta il fallback cloud lento) */
  const txt = `Ecco la notizia. ${tTitle}. ${tSnippet}`.slice(0, 480);
  const voice = 'vivian';
  const btn = document.getElementById('wn-listen-btn');
  if (btn) { btn.textContent = '🔊 ● LIVE'; btn.style.animation = 'wnPulseCrit 0.8s infinite'; }
  wnStartVoiceWave();

  if (_wnCurrentAudio) { _wnCurrentAudio.pause(); _wnCurrentAudio = null; }
  _wnSpeakSeq = (_wnSpeakSeq || 0) + 1;
  const mySeq = _wnSpeakSeq;
  _wnLastAudioUrl = null;

  const doneFn = () => {
    if (btn) { btn.textContent = '🔊 Ascolta'; btn.style.animation = ''; }
    wnStopVoiceWave();
    _wnCurrentAudio = null;
    wnAutoZoomOut(wnOnNewsComplete);
  };
  const errFn = (msg) => {
    if (btn) { btn.textContent = '⚠ Voce non disponibile'; btn.style.animation = ''; }
    wnStopVoiceWave();
    _wnCurrentAudio = null;
    console.error('[WN] TTS:', msg);
    setTimeout(() => { if (btn) btn.textContent = '🔊 Ascolta'; }, 3000);
  };

  fetch('/api/tts', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:txt, voice, language:'italian'}) })
    .then(r => {
      if (!r.ok) throw new Error('TTS failed');
      const ct = r.headers.get('content-type') || '';
      if (ct.includes('json')) return r.json().then(j => { throw new Error(j.error || 'TTS JSON response'); });
      return r.blob();
    }).then(blob => {
      if (mySeq !== _wnSpeakSeq) return; /* notizia cambiata nel frattempo: scarta */
      try {
        window._wnAudioCtx = window._wnAudioCtx || new (window.AudioContext || window.webkitAudioContext)();
        if (window._wnAudioCtx.state === 'suspended') window._wnAudioCtx.resume();
      } catch (e) {}
      _wnLastAudioUrl = URL.createObjectURL(blob);
      const a = new Audio(_wnLastAudioUrl);
      _wnCurrentAudio = a;
      a.onended = () => { _wnLastAudioUrl = null; doneFn(); };
      a.onerror = () => errFn('audio error');
      a.play().then(() => {}).catch((e) => {
        /* Browser blocca l'autoplay senza gesto: conserva l'audio, parte al primo click */
        _wnCurrentAudio = null;
        if (btn) { btn.textContent = '🔇 Clicca per ascoltare'; btn.style.animation = 'wnPulseCrit 0.8s infinite'; }
        wnStopVoiceWave();
        console.warn('[WN] autoplay bloccato, in attesa di gesto utente');
        setTimeout(() => { if (btn && btn.textContent.includes('Clicca')) { btn.textContent = '🔊 Ascolta'; btn.style.animation = ''; } }, 8000);
      });
    }).catch((e) => errFn(e && e.message || 'fetch failed'));
}

let _wnAutoBusy = false;
let _wnAutoTop5 = [];
let _wnAutoIndex = 0;

function wnNextAutoNews() {
  if (!_wnAutoTop5.length || _wnAutoIndex >= _wnAutoTop5.length) {
    wnStopAutoNews();
    return;
  }
  _wnAutoBusy = true;
  const n = _wnAutoTop5[_wnAutoIndex];
  _wnAutoIndex++;
  wnSelectNews(n);
}

function wnOnNewsComplete() {
  if (!_wnAutoBusy) return;
  if (_wnAutoIndex >= _wnAutoTop5.length) {
    wnStopAutoNews();
    return;
  }
  setTimeout(wnNextAutoNews, 800);
}

function wnStartAutoNews() {
  if (_wnAutoBusy) return;
  const geo = wnData.filter(n => n.lat != null);
  if (geo.length < 1 && wnData.length < 1) return;
  let pool = geo.length >= 2 ? geo : wnData;
  _wnAutoTop5 = pool.slice(0, 5);
  while (_wnAutoTop5.length < 5 && wnData.length > _wnAutoTop5.length) {
    const extra = wnData.find(n => !_wnAutoTop5.includes(n));
    if (extra) _wnAutoTop5.push(extra);
    else break;
  }
  _wnAutoIndex = 0;
  _wnAutoBusy = true;
  const btn = document.getElementById('wn-autonews-btn');
  if (btn) {
    btn.textContent = '🤖 Auto News: ● ON';
    btn.style.borderColor = '#00f0ff';
    btn.style.color = '#00f0ff';
  }
  wnTranslateBatch(_wnAutoTop5.filter(n => !n._translated)).then(() => {
    setTimeout(wnNextAutoNews, 1000);
  });
}

function wnStopAutoNews() {
  _wnAutoTop5 = [];
  _wnAutoIndex = 0;
  _wnAutoBusy = false;
  const btn = document.getElementById('wn-autonews-btn');
  if (btn) {
    btn.textContent = '🤖 Auto News: OFF';
    btn.style.borderColor = '#2a2a3e';
    btn.style.color = '#888899';
  }
}

function wnToggleAutoNews() {
  if (_wnAutoBusy) {
    wnStopAutoNews();
    wnAutoZoomOut();
  } else {
    wnStartAutoNews();
  }
}

window.wnNextAutoNews = wnNextAutoNews;
window.wnOnNewsComplete = wnOnNewsComplete;
window.wnStartAutoNews = wnStartAutoNews;
window.wnStopAutoNews = wnStopAutoNews;
window.wnToggleAutoNews = wnToggleAutoNews;

function wnStartVoiceWave() {
  const c = document.getElementById('wn-voice-wave');
  if (!c) return;
  c.innerHTML = '';
  c.style.display = 'flex';
  for (let i = 0; i < 5; i++) {
    const bar = document.createElement('div');
    bar.style.cssText = `width:4px;height:${14 + Math.random()*22}px;background:#00f0ff;border-radius:2px;animation:wnVoiceBar ${0.35+Math.random()*0.5}s ease-in-out infinite;animation-delay:${i*0.1}s;opacity:0.9;box-shadow:0 0 8px rgba(0,240,255,0.4)`;
    c.appendChild(bar);
  }
}

function wnStopVoiceWave() {
  const c = document.getElementById('wn-voice-wave');
  if (c) { c.style.display = 'none'; c.innerHTML = ''; }
}

/* ── HOLOGRAPHIC FULL-SCREEN PAGE ── */
function wnShowDetail(n, imgUrl) {
  const c = CAT_COLORS[n.category] || '#4488ff';
  const loc = n.location || n.country || '';
  const tTitle = n._tTitle || n.title;
  const tSnippet = n._tSnippet || n.snippet;
  const source = n.source || 'JARVIS';
  const cat = n.category || 'news';
  const published = (n.published || '').slice(0, 10);

  const container = document.getElementById('worldnews-panel');
  if (!container) return;

  const existing = document.getElementById('wn-holo-page');
  if (existing) existing.remove();

  const page = document.createElement('div');
  page.id = 'wn-holo-page';
  page.style.cssText = `
    position:absolute;inset:0;z-index:100;
    background:#060a14;
    overflow-y:auto;overflow-x:hidden;
    animation:wnHoloIn .5s cubic-bezier(0.175,0.885,0.32,1.275) both;
    color:#fff;font-family:'Rajdhani','Courier New',monospace
  `;

  /* Procedural noise canvas background */
  const noiseCanvas = document.createElement('canvas');
  noiseCanvas.width = 256; noiseCanvas.height = 256;
  const nctx = noiseCanvas.getContext('2d');
  const nimg = nctx.createImageData(256, 256);
  for (let i = 0; i < nimg.data.length; i += 4) {
    const v = Math.floor(Math.random() * 60);
    nimg.data[i] = v * 0.15;
    nimg.data[i+1] = v * 0.2;
    nimg.data[i+2] = v * 0.35;
    nimg.data[i+3] = 25;
  }
  nctx.putImageData(nimg, 0, 0);
  noiseCanvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;opacity:0.15';
  page.appendChild(noiseCanvas);

  /* Holographic scanline overlay */
  const scanlines = document.createElement('div');
  scanlines.style.cssText = `
    position:fixed;inset:0;pointer-events:none;z-index:101;
    background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,240,255,0.03) 2px,rgba(0,240,255,0.03) 4px);
    animation:wnScanline 8s linear infinite
  `;
  page.appendChild(scanlines);

  /* Hero section with city photo */
  const hero = document.createElement('div');
  hero.style.cssText = `
    position:relative;width:100%;height:45vh;min-height:280px;
    overflow:hidden;border-bottom:1px solid ${c}33
  `;

  if (imgUrl) {
    const img = document.createElement('img');
    img.src = imgUrl;
    img.style.cssText = 'width:100%;height:100%;object-fit:cover;filter:brightness(0.35) saturate(1.3) contrast(1.1)';
    img.onerror = () => { img.style.display = 'none'; };
    hero.appendChild(img);
  } else {
    /* Generate procedural gradient + city name canvas */
    const fallbackCanvas = document.createElement('canvas');
    fallbackCanvas.width = 800; fallbackCanvas.height = 400;
    const fctx = fallbackCanvas.getContext('2d');
    const grad = fctx.createLinearGradient(0, 0, 800, 400);
    const baseColor = new THREE.Color(c);
    const hsl = { h: 0, s: 0, l: 0 };
    baseColor.getHSL(hsl);
    grad.addColorStop(0, `hsl(${hsl.h * 360}, 60%, 8%)`);
    grad.addColorStop(0.5, `hsl(${hsl.h * 360 + 20}, 50%, 12%)`);
    grad.addColorStop(1, `hsl(${hsl.h * 360 + 40}, 40%, 6%)`);
    fctx.fillStyle = grad; fctx.fillRect(0, 0, 800, 400);
    for (let i = 0; i < 40; i++) {
      const x = Math.random() * 800, y = Math.random() * 400;
      const r = 2 + Math.random() * 8;
      const g2 = fctx.createRadialGradient(x, y, 0, x, y, r);
      g2.addColorStop(0, `hsla(${hsl.h * 360 + Math.random() * 40}, 70%, 50%, ${0.05 + Math.random() * 0.1})`);
      g2.addColorStop(1, 'transparent');
      fctx.fillStyle = g2; fctx.beginPath(); fctx.arc(x, y, r, 0, Math.PI * 2); fctx.fill();
    }
    const locName = loc || 'Mondo';
    fctx.textAlign = 'center'; fctx.textBaseline = 'middle';
    fctx.shadowColor = `hsla(${hsl.h * 360}, 80%, 50%, 0.5)`;
    fctx.shadowBlur = 30;
    fctx.font = `bold 48px 'Rajdhani', 'Courier New', monospace`;
    fctx.fillStyle = `hsla(${hsl.h * 360}, 60%, 70%, 0.6)`;
    fctx.fillText(locName.toUpperCase(), 400, 200);
    fctx.shadowBlur = 0;
    fctx.font = `14px 'Rajdhani', monospace`;
    fctx.fillStyle = `hsla(0, 0%, 100%, 0.15)`;
    fctx.fillText((n.lat ? n.lat.toFixed(2) + ', ' + n.lon.toFixed(2) : ''), 400, 260);
    hero.style.backgroundImage = `url(${fallbackCanvas.toDataURL()})`;
    hero.style.backgroundSize = 'cover';
    hero.style.backgroundPosition = 'center';
  }

  /* Gradient overlay */
  const gradOverlay = document.createElement('div');
  gradOverlay.style.cssText = `
    position:absolute;inset:0;
    background:linear-gradient(0deg,#060a14 0%,transparent 50%,rgba(6,10,20,0.3) 100%)
  `;
  hero.appendChild(gradOverlay);

  /* Holographic grid lines overlay on hero */
  const holoGrid = document.createElement('div');
  holoGrid.style.cssText = `
    position:absolute;inset:0;pointer-events:none;opacity:0.15;
    background-image:
      linear-gradient(rgba(0,240,255,0.3) 1px,transparent 1px),
      linear-gradient(90deg,rgba(0,240,255,0.3) 1px,transparent 1px);
    background-size:40px 40px;
    animation:wnGridPulse 4s ease-in-out infinite
  `;
  hero.appendChild(holoGrid);

  /* Category badge */
  const badge = document.createElement('div');
  badge.style.cssText = `
    position:absolute;top:20px;right:20px;
    background:${c};color:#000;padding:4px 16px;
    border-radius:4px;font-size:11px;font-weight:700;
    letter-spacing:2px;text-transform:uppercase;
    box-shadow:0 0 20px ${c}66
  `;
  badge.textContent = cat;
  hero.appendChild(badge);

  /* Italian flag badge */
  const itBadge = document.createElement('div');
  itBadge.style.cssText = `
    position:absolute;top:20px;right:110px;
    background:rgba(0,0,0,0.5);backdrop-filter:blur(4px);
    color:#fff;padding:4px 10px;border-radius:4px;
    font-size:10px;font-weight:600;letter-spacing:1px;
    border:1px solid rgba(255,255,255,0.1);
    display:flex;align-items:center;gap:4px
  `;
  itBadge.innerHTML = `<span style="font-size:14px">🇮🇹</span> ITALIANO`;
  hero.appendChild(itBadge);

  /* Location + live indicator */
  const locBadge = document.createElement('div');
  locBadge.style.cssText = `
    position:absolute;bottom:30px;left:30px;
    display:flex;align-items:center;gap:12px
  `;
  locBadge.innerHTML = `
    <span style="font-size:22px;font-weight:600;color:#fff;text-shadow:0 2px 20px rgba(0,0,0,0.8)">📍 ${loc}</span>
    <span style="display:flex;align-items:center;gap:4px;font-size:11px;color:#00ff88;letter-spacing:1px">
      <span style="width:6px;height:6px;border-radius:50%;background:#00ff88;animation:wnPulse 1.2s infinite"></span>
      LIVE
    </span>
  `;
  hero.appendChild(locBadge);

  page.appendChild(hero);

  /* Content section */
  const content = document.createElement('div');
  content.style.cssText = `
    padding:30px 30px 100px;max-width:800px;margin:0 auto;position:relative
  `;

  /* Source + date bar */
  const bar = document.createElement('div');
  bar.style.cssText = `
    display:flex;justify-content:space-between;align-items:center;
    margin-bottom:20px;padding-bottom:16px;
    border-bottom:1px solid ${c}22;
    color:${c};font-size:12px;letter-spacing:1px;
    text-transform:uppercase
  `;
  bar.innerHTML = `
    <span>${CAT_ICONS[n.category]||'📰'} ${source} <span style="color:#555;font-weight:400">// SATELLITE FEED</span></span>
    <span style="color:#555">${published}</span>
  `;
  content.appendChild(bar);

  /* Title with typewriter effect */
  const titleEl = document.createElement('h1');
  titleEl.style.cssText = `
    font-size:28px;font-weight:700;line-height:1.3;margin-bottom:20px;
    color:#fff;text-shadow:0 0 30px ${c}44;
    overflow:hidden;border-right:2px solid ${c};
    white-space:nowrap;animation:wnTypewriter 2s steps(${tTitle.length}) forwards, wnBlinkCursor .8s step-end 3
  `;
  titleEl.textContent = tTitle;
  content.appendChild(titleEl);

  /* Snippet with glassmorphism card */
  const snippetCard = document.createElement('div');
  snippetCard.style.cssText = `
    background:rgba(6,10,20,0.7);backdrop-filter:blur(10px);
    border:1px solid rgba(0,240,255,0.1);border-radius:12px;
    padding:24px;margin-bottom:24px;
    box-shadow:0 0 40px rgba(0,240,255,0.05)
  `;
  snippetCard.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:11px;color:#00f0ff;letter-spacing:2px;text-transform:uppercase">
      <span style="width:20px;height:1px;background:#00f0ff"></span>
      RIASSUNTO NOTIZIA
    </div>
    <div style="font-size:15px;line-height:1.7;color:#ccc">${tSnippet}</div>
  `;
  content.appendChild(snippetCard);

  /* Voice wave container */
  const vw = document.createElement('div');
  vw.id = 'wn-voice-wave';
  vw.style.cssText = 'display:none;align-items:center;gap:3px;height:36px;margin-bottom:20px;justify-content:center';
  content.appendChild(vw);

  /* Action buttons */
  const actions = document.createElement('div');
  actions.style.cssText = `
    display:flex;gap:12px;flex-wrap:wrap;align-items:center;
    margin-top:8px
  `;
  actions.innerHTML = `
    <button id="wn-listen-btn" onclick="wnSpeakNews(wnData[${wnData.indexOf(n)}])"
      style="background:${c};color:#000;padding:12px 28px;border:none;border-radius:8px;
        cursor:pointer;font-size:14px;font-weight:700;letter-spacing:1px;
        box-shadow:0 0 30px ${c}44;transition:all .2s;
        display:flex;align-items:center;gap:8px">
      🔊 ASCOLTA
    </button>
    <a href="${n.url}" target="_blank"
      style="background:transparent;color:${c};padding:12px 28px;
        border:1px solid ${c}66;border-radius:8px;text-decoration:none;
        font-size:14px;font-weight:600;letter-spacing:1px;transition:all .2s">
      LEGGI COMPLETO →
    </a>
    <button onclick="wnCloseDetail()"
      style="background:transparent;color:#555;padding:12px 20px;
        border:1px solid #222;border-radius:8px;cursor:pointer;font-size:13px;
        letter-spacing:1px;margin-left:auto;transition:all .2s">
      ✕ CHIUDI
    </button>
  `;
  content.appendChild(actions);

  /* Data stream footer */
  const dataFoot = document.createElement('div');
  dataFoot.style.cssText = `
    margin-top:40px;padding-top:20px;
    border-top:1px solid #111;
    font:10px/1.6 'Rajdhani',monospace;color:#333;
    display:flex;gap:30px;flex-wrap:wrap
  `;
  const now = new Date().toISOString().replace('T',' ').slice(0,19);
  const sources = ['SATLINK','GEOINT','NEWSFEED','CYPHER'];
  const randSrc = sources[Math.floor(Math.random()*sources.length)];
  dataFoot.innerHTML = `
    <span>[SYS] ${randSrc} // PKT_${Math.floor(Math.random()*9999)}</span>
    <span>[TS] ${now} UTC</span>
    <span>[NID] JARVIS-WN-${String(wnData.indexOf(n)).padStart(4,'0')}</span>
    <span>[SIG] ${(Math.random()*5+2).toFixed(1)} dBm</span>
  `;
  content.appendChild(dataFoot);

  page.appendChild(content);

  /* ── DATA TICKER BAR (fissa in basso) ── */
  const ticker = document.createElement('div');
  ticker.style.cssText = `
    position:sticky;bottom:0;left:0;right:0;z-index:102;
    background:rgba(6,10,20,0.9);backdrop-filter:blur(12px);
    border-top:1px solid rgba(0,240,255,0.1);
    padding:8px 24px;overflow:hidden;height:32px;
    display:flex;align-items:center
  `;
  const tickerInner = document.createElement('div');
  tickerInner.style.cssText = `
    display:flex;gap:48px;white-space:nowrap;
    font:10px/1 'Rajdhani',monospace;color:#444;
    animation:wnTickerScroll 30s linear infinite
  `;
  const tickerItems = [
    `[SYS] ONLINE // UPTIME ${Math.floor(Math.random()*99)+1}h ${Math.floor(Math.random()*60)}m`,
    `[SAT] ${Math.floor(Math.random()*10)+1} LINKS ACTIVE`,
    `[SIG] ${(Math.random()*3+2).toFixed(2)} GHz // ${(Math.random()*5+2).toFixed(1)} dBm`,
    `[NET] PKT_LOSS ${(Math.random()*0.5).toFixed(2)}% // LAT ${Math.floor(Math.random()*20+5)}ms`,
    `[GEO] ${Math.floor(Math.random()*999)} STATIONS TRACKED`,
    `[INT] ${Math.floor(Math.random()*99)+1} ACTIVE THREADS`,
    `[SEC] PROTOCOL v${Math.floor(Math.random()*9)}.${Math.floor(Math.random()*9)}.${Math.floor(Math.random()*9)}`,
    `[NID] ${n.source.toUpperCase()}-${String(wnData.indexOf(n)).padStart(4,'0')}`,
    `[TS] ${new Date().toISOString().replace('T',' ').slice(0,19)} UTC`,
    `[CAT] ${n.category?.toUpperCase()||'NEWS'} // ${n.location?.toUpperCase()||n.country?.toUpperCase()||'GLOBAL'}`
  ];
  /* Duplicate for seamless scroll */
  tickerInner.innerHTML = tickerItems.map(t => `<span style="color:#00f0ff55;letter-spacing:0.5px">${t}</span>`).join('')
    + '<span style="width:48px"></span>'
    + tickerItems.map(t => `<span style="color:#00f0ff55;letter-spacing:0.5px">${t}</span>`).join('');
  ticker.appendChild(tickerInner);
  page.appendChild(ticker);

  container.appendChild(page);
}

function wnCloseDetail() {
  const page = document.getElementById('wn-holo-page');
  if (page) {
    page.style.animation = 'wnHoloOut .35s ease-in both';
    setTimeout(() => { if (page.parentNode) page.parentNode.removeChild(page); }, 400);
  }
  document.getElementById('wn-detail')?.classList.add('hidden');
  wnAutoZoomOut();
}

let _wnLoadingTimer = null;
function wnRefresh() {
  /* Feedback immediato: la lista non resta mai vuota/bianca */
  const list = document.getElementById('wn-news-list');
  if (list && (!window.wnData || !window.wnData.length)) {
    list.innerHTML = '<div style="padding:24px;text-align:center;color:#00f0ff;font:11px monospace;animation:wnPulse 1.2s infinite">⏳ Caricamento notizie...</div>';
  }
  const cnt = document.getElementById('wn-count');
  if (cnt) cnt.textContent = 'caricamento...';
  if (_wnLoadingTimer) clearTimeout(_wnLoadingTimer);
  _wnLoadingTimer = setTimeout(() => {
    const c = document.getElementById('wn-count');
    if (c && c.textContent === 'caricamento...') c.textContent = 'ancora in caricamento...';
  }, 8000);
  fetch('/api/worldnews?max=60')
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(d => { if (_wnLoadingTimer) clearTimeout(_wnLoadingTimer); wnLoadData(d); })
    .catch(() => {
      if (_wnLoadingTimer) clearTimeout(_wnLoadingTimer);
      const c2 = document.getElementById('wn-count');
      if (c2) c2.textContent = 'errore di rete';
      if (list) list.innerHTML = '<div style="padding:24px;text-align:center;color:#ff6666;font:11px monospace">⚠ Caricamento fallito. <a href="#" onclick="wnRefresh();return false" style="color:#00f0ff">Riprova</a></div>';
    });
}

function wnToggleAutoPilot() {
  if (_wnAutoPilotInterval) {
    clearInterval(_wnAutoPilotInterval);
    _wnAutoPilotInterval = null;
    _wnAutoPilot = false;
    _wnAutoRotate = true;
    const btn = document.getElementById('wn-autopilot-btn');
    if (btn) { btn.textContent = '🤖 Autopilota'; btn.style.borderColor = '#2a2a3e'; btn.style.color = '#888'; }
    return;
  }
  const geo = wnData.filter(n => n.lat);
  if (geo.length < 2) return;
  _wnAutoPilot = true;
  _wnAutoRotate = false;
  const btn = document.getElementById('wn-autopilot-btn');
  if (btn) { btn.textContent = '🤖 ● ON'; btn.style.borderColor = '#00f0ff'; btn.style.color = '#00f0ff'; }
  let idx = 0;
  _wnPilotInterval = setInterval(() => {
    const n = geo[idx % geo.length];
    if (n) wnSelectNews(n);
    idx++;
  }, 10000);
}

let _wnDefaultCameraPos = null;
let _wnWarpParticles = [];
/* ── WARP SPEED PARTICLES during zoom ── */
function wnSpawnWarpParticles() {
  if (!wnGlobeScene || !wnGlobeCamera) return;
  _wnWarpParticles.forEach(p => { if (p.parent) p.parent.remove(p); });
  _wnWarpParticles = [];
  const camDir = new THREE.Vector3();
  wnGlobeCamera.getWorldDirection(camDir);
  const perp = new THREE.Vector3(-camDir.y, camDir.x, 0).normalize();
  if (perp.length() < 0.1) perp.set(0, 0, 1);
  const up = new THREE.Vector3(0, 1, 0);
  const colors = [0x00f0ff, 0x4488ff, 0x8844ff, 0x00ff88];
  for (let i = 0; i < 120; i++) {
    const spread = 0.2 + Math.random() * 0.8;
    const angle = Math.random() * Math.PI * 2;
    const radial = new THREE.Vector3(
      Math.cos(angle) * spread,
      Math.sin(angle) * spread,
      0
    );
    const depth = -0.3 - Math.random() * 2.0;
    const offset = radial.clone().multiplyScalar(0.5);
    offset.z = depth;
    const sz = 0.003 + Math.random() * 0.012;
    const p = new THREE.Mesh(
      new THREE.SphereGeometry(sz, 3, 3),
      new THREE.MeshBasicMaterial({
        color: colors[Math.floor(Math.random() * colors.length)],
        transparent: true, opacity: 0.7,
        blending: THREE.AdditiveBlending, depthWrite: false
      })
    );
    p.position.copy(wnGlobeCamera.position).add(offset);
    const speed = 0.02 + Math.random() * 0.06;
    p.userData.vel = camDir.clone().multiplyScalar(-speed);
    p.userData.vel.add(radial.clone().multiplyScalar(0.002));
    p.userData.life = 0.8 + Math.random() * 0.4;
    p.userData.decay = 0.005 + Math.random() * 0.01;
    p.userData.maxScale = 1 + Math.random() * 4;
    _wnWarpParticles.push(p);
    wnGlobeScene.add(p);
  }
}
function wnCleanWarpParticles() {
  _wnWarpParticles.forEach(p => { if (p.parent) p.parent.remove(p); });
  _wnWarpParticles = [];
  if (_wnWarpRing) { wnGlobeScene.remove(_wnWarpRing); _wnWarpRing = null; }
}

function wnAutoZoomOut(cb) {
  if (!wnGlobeCamera || !wnGlobeRenderer) return;
  _wnAutoRotate = true;
  const target = _wnDefaultCameraPos || new THREE.Vector3(3.2, 0.8, 3.2);
  const start = wnGlobeCamera.position.clone();
  const t0 = performance.now();
  const dur = 1200;
  wnSpawnWarpParticles();
  function anim(now) {
    const t = Math.min((now - t0) / dur, 1);
    const e = 1 - Math.pow(1 - t, 3.5);
    wnGlobeCamera.position.lerpVectors(start, target, e);
    wnGlobeCamera.lookAt(0, 0, 0);
    if (t < 1) requestAnimationFrame(anim);
    else {
      wnCleanWarpParticles();
      if (cb) setTimeout(cb, 300);
    }
  }
  requestAnimationFrame(anim);
}

window.wnAutoZoomOut = wnAutoZoomOut;

function wnLatLonToPos(lat, lon, r) {
  const phi = (90 - lat) * Math.PI / 180;
  const theta = (lon + 180) * Math.PI / 180;
  return new THREE.Vector3(-r*Math.sin(phi)*Math.cos(theta), r*Math.cos(phi), r*Math.sin(phi)*Math.sin(theta));
}

/* ── BUILD ARCS BETWEEN CITIES ── */
function wnBuildArcs() {
  if (!wnGlobeScene || !wnGlobe) return;
  const geo = wnData.filter(n => n.lat);
  if (geo.length < 2) return;
  /* Clean old arcs */
  _wnArcs.forEach(a => { if (a.parent) a.parent.remove(a); });
  _wnArcs = [];
  _wnArcParticles.forEach(p => { if (p.parent) p.parent.remove(p); });
  _wnArcParticles = [];

  const r = wnGlobe.radius;
  const arcGroup = new THREE.Group();
  const numArcs = Math.min(geo.length * 2, 30); /* max 30 arcs */
  const enhanced = geo.length >= 3;

  for (let i = 0; i < numArcs; i++) {
    const a = geo[Math.floor(Math.random() * geo.length)];
    const b = geo[Math.floor(Math.random() * geo.length)];
    if (a === b) continue;
    if (Math.abs(a.lat - b.lat) < 5 && Math.abs(a.lon - b.lon) < 5) continue;

    const p1 = wnLatLonToPos(a.lat, a.lon, r);
    const p2 = wnLatLonToPos(b.lat, b.lon, r);
    const mid = p1.clone().add(p2).multiplyScalar(0.5);
    const dist = p1.distanceTo(p2);
    const arcHeight = 0.3 + dist * 0.25;
    mid.normalize().multiplyScalar(r + arcHeight);

    const curve = new THREE.QuadraticBezierCurve3(p1, mid, p2);
    const points = curve.getPoints(40);
    const color = new THREE.Color(CAT_COLORS[b.category] || '#00f0ff');

    const geom = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.25 + Math.random() * 0.2, blending: THREE.AdditiveBlending });
    const line = new THREE.Line(geom, mat);
    line.userData = { curve, points, p1, p2, phase: Math.random() * Math.PI * 2, color };
    arcGroup.add(line);
    _wnArcs.push(line);

    /* Glow arc underneath (wider, more transparent) */
    const glowGeom = new THREE.BufferGeometry().setFromPoints(points);
    const glowMat2 = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, linewidth: 2 });
    const glowLine = new THREE.Line(glowGeom, glowMat2);
    glowLine.userData = { curve, points, p1, p2, phase: Math.random() * Math.PI * 2, color, glow: true };
    arcGroup.add(glowLine);
    _wnArcs.push(glowLine);

    if (enhanced) {
      for (let j = 0; j < 5; j++) {
        const pColor = new THREE.Color(color).multiplyScalar(0.8 + Math.random() * 0.4);
        const p = new THREE.Mesh(
          new THREE.SphereGeometry(0.035, 8, 8),
          new THREE.MeshBasicMaterial({ color: pColor, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending })
        );
        const trails = [];
        for (let t = 0; t < 3; t++) {
          const trail = new THREE.Mesh(
            new THREE.SphereGeometry(0.015, 6, 6),
            new THREE.MeshBasicMaterial({ color: pColor, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending })
          );
          trail.position.copy(p.position);
          trail.userData.offset = (t + 1) * 0.04;
          trail.userData.baseAlpha = 0.25 - t * 0.07;
          arcGroup.add(trail);
          trails.push(trail);
          _wnArcParticles.push(trail);
        }
        p.userData = {
          curve, t: j / 3,
          speed: 0.003 + Math.random() * 0.008,
          phase: Math.random() * 1000,
          enhanced: true,
          source: p1, target: p2,
          color: pColor,
          glow: new THREE.Color(CAT_COLORS[b.category] || '#00f0ff'),
          pulseSpeed: 0.01 + Math.random() * 0.02,
          pulseOffset: Math.random() * 1000,
          streamOffset: Math.random() * 1000,
          streamSpeed: 0.005 + Math.random() * 0.02,
          trails,
        };
        arcGroup.add(p);
        _wnArcParticles.push(p);
      }
    }
  }

  wnGlobeScene.add(arcGroup);
}

/* ── TIKTOK-STYLE FLY-TO WITH SPRING OVERSHOOT ── */
/* ── WARP RING (hyperspace ring effect during zoom) ── */
let _wnWarpRing = null;
function wnSpawnWarpRing() {
  if (!wnGlobeScene) return;
  if (_wnWarpRing) { wnGlobeScene.remove(_wnWarpRing); _wnWarpRing = null; }
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.01, 0.05, 64),
    new THREE.MeshBasicMaterial({
      color: 0x00f0ff, transparent: true, opacity: 0.6,
      side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
      depthWrite: false
    })
  );
  ring.position.set(0, 0, 0);
  ring.lookAt(wnGlobeCamera.position);
  ring.scale.setScalar(0.1);
  ring.userData = { start: performance.now(), dur: 800 };
  wnGlobeScene.add(ring);
  _wnWarpRing = ring;
}

function wnGlobeFlyTo(n) {
  if (!wnGlobeCamera || !wnGlobe) return;
  const r = wnGlobe.radius;
  const pos = wnLatLonToPos(n.lat, n.lon, r);

  const startPos = wnGlobeCamera.position.clone();
  const targetDir = pos.clone().normalize();
  const targetPos = targetDir.multiplyScalar(1.35 / r);
  const overshootPos = targetDir.clone().multiplyScalar(0.95 / r);
  const pullBackPos = startPos.clone().normalize().multiplyScalar(5);

  if (_wnBeam) { wnGlobeScene.remove(_wnBeam); _wnBeam = null; }

  const t0 = performance.now();
  const pullDur = 350;
  const zoomDur = 700;
  const overshootDur = 300;
  const settleDur = 400;

  /* Spawn warp particles */
  wnSpawnWarpParticles();
  wnSpawnWarpRing();

  function phasePull(now) {
    const t = Math.min((now - t0) / pullDur, 1);
    const e = 1 - Math.pow(1 - t, 4);
    wnGlobeCamera.position.lerpVectors(startPos, pullBackPos, e);
    wnGlobeCamera.lookAt(0, 0, 0);
    /* Animate warp ring */
    if (_wnWarpRing) {
      const ringT = Math.min((now - _wnWarpRing.userData.start) / _wnWarpRing.userData.dur, 1);
      const s = 0.1 + ringT * 8;
      _wnWarpRing.scale.setScalar(s);
      _wnWarpRing.material.opacity = 0.6 * (1 - ringT);
      _wnWarpRing.position.copy(wnGlobeCamera.position).multiplyScalar(0.5);
      _wnWarpRing.lookAt(wnGlobeCamera.position);
    }
    if (t < 1) requestAnimationFrame(phasePull);
    else phaseZoom(performance.now());
  }

  function phaseZoom(t1) {
    wnAddBeamEffect(n, pos);
    const zoomStart = wnGlobeCamera.position.clone();
    function zoom(now) {
      const t = Math.min((now - t1) / zoomDur, 1);
      const e = 1 - Math.pow(1 - t, 3.5);
      wnGlobeCamera.position.lerpVectors(zoomStart, targetPos, e);
      wnGlobeCamera.lookAt(0, 0, 0);
      if (t < 1) requestAnimationFrame(zoom);
      else phaseOvershoot(performance.now());
    }
    requestAnimationFrame(zoom);
  }

  function phaseOvershoot(t2) {
    const osStart = wnGlobeCamera.position.clone();
    function os(now) {
      const t = Math.min((now - t2) / overshootDur, 1);
      const e = 1 - Math.pow(1 - t, 2);
      wnGlobeCamera.position.lerpVectors(osStart, overshootPos, e);
      wnGlobeCamera.lookAt(0, 0, 0);
      if (t < 1) requestAnimationFrame(os);
      else phaseSettle(performance.now());
    }
    requestAnimationFrame(os);
  }

  function phaseSettle(t3) {
    const stStart = wnGlobeCamera.position.clone();
    function st(now) {
      const t = Math.min((now - t3) / settleDur, 1);
      const e = 1 - Math.pow(1 - t, 3);
      wnGlobeCamera.position.lerpVectors(stStart, targetPos, e);
      wnGlobeCamera.lookAt(0, 0, 0);
      if (t < 1) requestAnimationFrame(st);
      else {
        _wnZooming = false;
        wnCleanWarpParticles();
        if (_wnWarpRing) { wnGlobeScene.remove(_wnWarpRing); _wnWarpRing = null; }
        if (_wnDragTimeout) clearTimeout(_wnDragTimeout);
        _wnDragTimeout = setTimeout(() => { if (!_wnAutoPilot) _wnAutoRotate = true; }, 5000);
      }
    }
    requestAnimationFrame(st);
  }

  requestAnimationFrame(phasePull);
}

function wnAddBeamEffect(n, pos) {
  const color = new THREE.Color(CAT_COLORS[n.category] || '#00f0ff');
  const hsl = { h: 0, s: 0, l: 0 };
  color.getHSL(hsl);
  const group = new THREE.Group();
  group.position.copy(pos);

  /* ── MAIN BEAM CONE (double-sided with glow) ── */
  const cone = new THREE.Mesh(
    new THREE.CylinderGeometry(0.003, 0.25, 1.5, 24, 1, true),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, side: THREE.DoubleSide, blending: THREE.AdditiveBlending })
  );
  cone.position.set(0, 0, 0);
  cone.lookAt(0, 0, 0);
  cone.rotateX(Math.PI / 2);
  group.add(cone);

  /* ── PULSING CORE ── */
  const pulse = new THREE.Mesh(
    new THREE.SphereGeometry(0.08, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 1 })
  );
  group.add(pulse);

  /* ── RING WAVE 1 ── */
  const ring1 = new THREE.Mesh(
    new THREE.RingGeometry(0.04, 0.2, 32),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending })
  );
  ring1.lookAt(0, 0, 0);
  group.add(ring1);

  /* ── RING WAVE 2 (larger, inverted) ── */
  const ring2 = new THREE.Mesh(
    new THREE.RingGeometry(0.15, 0.35, 32),
    new THREE.MeshBasicMaterial({ color: 0x4488ff, transparent: true, opacity: 0.4, side: THREE.DoubleSide, blending: THREE.AdditiveBlending })
  );
  ring2.lookAt(0, 0, 0);
  group.add(ring2);

  /* ── GLOW SPHERE ── */
  const glow = new THREE.Mesh(
    new THREE.SphereGeometry(0.35, 16, 16),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.15, blending: THREE.AdditiveBlending })
  );
  group.add(glow);

  /* ── CORONA RAYS (8 spikes) ── */
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2;
    const ray = new THREE.Mesh(
      new THREE.ConeGeometry(0.008, 0.4, 4),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending })
    );
    ray.position.set(Math.cos(angle) * 0.15, Math.sin(angle) * 0.15, 0);
    ray.lookAt(0, 0, 0);
    ray.rotateX(Math.PI / 2);
    group.add(ray);
  }

  /* ── EXPANDING SHOCKWAVE RING ── */
  const expandRing = new THREE.Mesh(
    new THREE.RingGeometry(0.05, 0.15, 48),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending })
  );
  expandRing.position.copy(pos);
  expandRing.lookAt(0, 0, 0);
  expandRing.userData = { expandStart: performance.now(), expandDur: 2500 };
  group.add(expandRing);

  /* ── EXPANDING RING 2 (offset delay) ── */
  const expandRing2 = new THREE.Mesh(
    new THREE.RingGeometry(0.03, 0.1, 48),
    new THREE.MeshBasicMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.6, side: THREE.DoubleSide, blending: THREE.AdditiveBlending })
  );
  expandRing2.position.copy(pos);
  expandRing2.lookAt(0, 0, 0);
  expandRing2.userData = { expandStart: performance.now(), expandDur: 2500, delay: 400 };
  group.add(expandRing2);

  wnGlobeScene.add(group);
  _wnBeam = group;

  /* ── CINEMATIC PARTICLE BURST (200 particles) ── */
  for (let i = 0; i < 200; i++) {
    const sz = 0.005 + Math.random() * 0.015;
    const pMat = new THREE.MeshBasicMaterial({
      color: Math.random() > 0.5 ? color : 0x88ccff,
      transparent: true, opacity: 1, blending: THREE.AdditiveBlending
    });
    const p = new THREE.Mesh(new THREE.SphereGeometry(sz, 4, 4), pMat);
    const dir = new THREE.Vector3(Math.random()-0.5, Math.random()-0.5, Math.random()-0.5).normalize();
    const dist = 0.02 + Math.random() * 0.15;
    p.position.copy(pos).add(dir.clone().multiplyScalar(dist));
    const speed = 0.008 + Math.random() * 0.025;
    p.userData.vel = dir.multiplyScalar(speed);
    p.userData.life = 0.6 + Math.random() * 0.4;
    p.userData.decay = 0.006 + Math.random() * 0.015;
    p.userData.phase = Math.random() * Math.PI * 2;
    _wnParticles.push(p);
    wnGlobeScene.add(p);
  }

  /* ── SECONDARY RING PARTICLES (ring burst) ── */
  for (let i = 0; i < 60; i++) {
    const theta = (i / 60) * Math.PI * 2 + Math.random() * 0.1;
    const radius2 = 0.08 + Math.random() * 0.06;
    const p = new THREE.Mesh(
      new THREE.SphereGeometry(0.006, 4, 4),
      new THREE.MeshBasicMaterial({ color: 0x88ddff, transparent: true, opacity: 1, blending: THREE.AdditiveBlending })
    );
    p.position.copy(pos).add(new THREE.Vector3(Math.cos(theta)*radius2, Math.sin(theta)*radius2, 0));
    p.userData.vel = new THREE.Vector3(Math.cos(theta)*0.015, Math.sin(theta)*0.015, (Math.random()-0.5)*0.01);
    p.userData.life = 0.4 + Math.random() * 0.3;
    p.userData.decay = 0.008 + Math.random() * 0.01;
    _wnParticles.push(p);
    wnGlobeScene.add(p);
  }

  let angle = 0;
  function beamAnim() {
    if (!_wnBeam || !wnGlobeScene) return;
    angle += 0.05;
    cone.material.opacity = 0.15 + Math.sin(angle * 0.8) * 0.3;
    cone.scale.x = 1 + Math.sin(angle * 1.2) * 0.2;
    cone.scale.z = 1 + Math.sin(angle * 1.2) * 0.2;

    const s = 1 + Math.sin(angle * 2.5) * 0.4;
    pulse.scale.setScalar(s);
    pulse.material.opacity = 0.5 + Math.sin(angle * 3) * 0.5;

    ring1.scale.setScalar(1 + Math.sin(angle * 1.8) * 0.6);
    ring1.material.opacity = 0.3 + Math.sin(angle * 1.5) * 0.4;
    ring1.material.color.setHSL((hsl.h + Math.sin(angle * 0.3) * 0.05) % 1, 0.8, 0.5);

    ring2.scale.setScalar(1 + Math.sin(angle * 1.2 + 1) * 0.5);
    ring2.material.opacity = 0.15 + Math.sin(angle * 1.5 + 1) * 0.25;

    glow.scale.setScalar(1 + Math.sin(angle * 0.8) * 0.4);
    glow.material.color.setHSL((hsl.h + Math.sin(angle * 0.2) * 0.1) % 1, 0.7, 0.4);

    /* Expand shockwave ring 1 */
    const erNow = performance.now();
    const erElapsed = erNow - expandRing.userData.expandStart;
    if (erElapsed < expandRing.userData.expandDur) {
      const erT = erElapsed / expandRing.userData.expandDur;
      const rScale = 0.1 + erT * 10;
      expandRing.scale.setScalar(rScale);
      expandRing.material.opacity = 0.9 * (1 - erT);
      expandRing.material.color.setHSL((hsl.h + erT * 0.3) % 1, 0.9, 0.4 + erT * 0.4);
    } else {
      expandRing.scale.setScalar(0.1);
      expandRing.material.opacity = 0;
    }

    /* Expand shockwave ring 2 (delayed) */
    const er2Now = performance.now();
    const er2Elapsed = er2Now - expandRing2.userData.expandStart - expandRing2.userData.delay;
    if (er2Elapsed > 0 && er2Elapsed < expandRing2.userData.expandDur) {
      const er2T = er2Elapsed / expandRing2.userData.expandDur;
      const rScale2 = 0.1 + er2T * 10;
      expandRing2.scale.setScalar(rScale2);
      expandRing2.material.opacity = 0.6 * (1 - er2T);
    } else {
      expandRing2.scale.setScalar(0.1);
      expandRing2.material.opacity = 0;
    }

    requestAnimationFrame(beamAnim);
  }
  beamAnim();
}

/* ── CLOUD LAYER ── */
function wnCreateCloudLayer(radius) {
  const canvas = document.createElement('canvas');
  canvas.width = 1024; canvas.height = 512;
  const ctx = canvas.getContext('2d');
  /* Procedural cloud-like noise */
  for (let x = 0; x < 1024; x++) {
    for (let y = 0; y < 512; y++) {
      const nx = x / 1024, ny = y / 512;
      const v = Math.sin(nx * 40) * Math.cos(ny * 30) * 0.3
              + Math.sin(nx * 80 + ny * 60) * 0.15
              + Math.cos(nx * 20 - ny * 50) * 0.2;
      const a = Math.max(0, Math.min(1, v + 0.4));
      ctx.fillStyle = `rgba(255,255,255,${a * 0.35})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1, 1);

  const cloud = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 1.03, 48, 48),
    new THREE.MeshPhongMaterial({
      map: tex, transparent: true, opacity: 0.2,
      blending: THREE.AdditiveBlending, depthWrite: false,
      side: THREE.DoubleSide
    })
  );
  _wnCloudMesh = cloud;
  return cloud;
}

function wnInitGlobe() {
  console.log('[WN] init globe');
  if (wnGlobeRenderer) return;
  const container = document.getElementById('wn-map');
  const w = container.clientWidth, h = container.clientHeight;
  if (w < 10) return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, w/h, 0.1, 1000);
  camera.position.set(3.2, 0.8, 3.2);
  _wnDefaultCameraPos = camera.position.clone();

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x06060d, 1);
  container.appendChild(renderer.domElement);

  const radius = 1.5;

  /* ── Earth with procedural night city lights ── */
  const texDay = new THREE.TextureLoader().load('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg');

  /* Procedural city lights texture (always works, no CDN dependency) */
  const nightCanvas = document.createElement('canvas');
  nightCanvas.width = 1024; nightCanvas.height = 512;
  const nctx = nightCanvas.getContext('2d');
  nctx.fillStyle = '#000'; nctx.fillRect(0, 0, 1024, 512);
  /* Major cities as glowing dots */
  const cities = [
    [520,200],[530,195],[525,210],[510,190],[535,205], /* NA */
    [490,240],[485,250],[500,235],[480,245],[510,255], /* SA */
    [600,195],[610,200],[605,190],[620,210],[590,205], /* EU */
    [660,220],[680,230],[650,215],[700,240],[640,225], /* ASIA */
    [660,280],[670,290],[650,285],[680,295],[645,275], /* SE ASIA */
    [560,340],[570,345],[555,350],[575,355],[550,335], /* AFRICA */
    [750,270],[760,275],[745,280],[770,285],[740,265], /* OCEANIA */
    [480,175],[540,185],[560,190],[620,225],[720,250],
    [530,235],[500,260],[510,270],[490,280],[600,205],
    [640,215],[680,225],[700,235],[630,230],[650,310]
  ];
  cities.forEach(([x,y]) => {
    const rad = 5 + Math.random() * 8;
    const g = nctx.createRadialGradient(x, y, 0, x, y, rad);
    g.addColorStop(0, 'rgba(255,220,120,0.95)');
    g.addColorStop(0.3, 'rgba(255,180,60,0.5)');
    g.addColorStop(0.6, 'rgba(200,100,20,0.15)');
    g.addColorStop(1, 'rgba(255,200,80,0)');
    nctx.fillStyle = g;
    nctx.beginPath(); nctx.arc(x, y, rad, 0, Math.PI*2); nctx.fill();
  });
  /* Add scattered small dots for smaller cities */
  for (let i = 0; i < 300; i++) {
    const x = Math.random() * 1024, y = Math.random() * 512;
    const sz = 1 + Math.random() * 2;
    nctx.fillStyle = `rgba(255,200,100,${0.1 + Math.random() * 0.4})`;
    nctx.beginPath(); nctx.arc(x, y, sz, 0, Math.PI*2); nctx.fill();
  }
  const texNight = new THREE.CanvasTexture(nightCanvas);

  const earthMat = new THREE.MeshPhongMaterial({
    map: texDay, specular: 0x222244, shininess: 25
  });
  earthMat.emissiveMap = texNight;
  earthMat.emissive = new THREE.Color(0xff8844);
  earthMat.emissiveIntensity = 0.6;
  const earth = new THREE.Mesh(new THREE.SphereGeometry(radius, 64, 64), earthMat);
  earth.scale.set(0, 0, 0);
  scene.add(earth);

  /* ── AURORA ATMOSPHERE (multi-layer Fresnel + wave + sparkle) ── */
  const glowMat = new THREE.ShaderMaterial({
    vertexShader: `varying vec3 vN;varying vec3 vP;void main(){vN=normalize(normalMatrix*normal);vec4 wp=modelMatrix*vec4(position,1);vP=wp.xyz;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec3 vN;varying vec3 vP;uniform float uTime;uniform vec3 vp;void main(){vec3 vd=normalize(vp-vP);float f=1.0-max(0.0,dot(vd,vN));float i=pow(f,3.5);float pulse=0.85+0.15*sin(uTime*0.4);float wave=sin(f*25.0-uTime*1.8)*0.5+0.5;float aurora=sin(f*10.0+uTime*0.6)*0.3;vec3 col1=vec3(0.1,0.5,1.0);vec3 col2=vec3(0.3,0.1,0.9);vec3 col3=vec3(0.0,0.9,0.6);vec3 col=mix(mix(col1,col2,wave),col3,aurora*0.5);gl_FragColor=vec4(col,i*0.9*pulse);}`,
    uniforms: { uTime: { value: 0 }, vp: { value: camera.position } },
    side: THREE.BackSide, blending: THREE.AdditiveBlending, transparent: true
  });
  const glowMesh = new THREE.Mesh(new THREE.SphereGeometry(radius*1.15, 64, 64), glowMat);
  glowMesh.scale.set(0, 0, 0);
  scene.add(glowMesh);

  /* ── SUPER-NOVA CORONA (hot white core + cyan halo) ── */
  const coronaMat = new THREE.ShaderMaterial({
    vertexShader: `varying vec3 vN;void main(){vN=normalize(normalMatrix*normal);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec3 vN;uniform float uTime;void main(){float i=pow(0.65-dot(vN,vec3(0,0,1)),6.0);float flicker=0.9+0.1*sin(uTime*2.0)*sin(uTime*0.8);float chaos=sin(vN.x*20.0+uTime*1.5)*0.3+0.7;gl_FragColor=vec4(0.2,0.85,1.0,i*0.5*flicker*chaos);}`,
    uniforms: { uTime: { value: 0 } },
    side: THREE.FrontSide, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false
  });
  const coronaMesh = new THREE.Mesh(new THREE.SphereGeometry(radius*1.01, 48, 48), coronaMat);
  coronaMesh.scale.set(0, 0, 0);
  scene.add(coronaMesh);

  /* ── Outer aurora halo (purple/green shift) ── */
  const haloMat = new THREE.ShaderMaterial({
    vertexShader: `varying vec3 vN;varying vec3 vP;void main(){vN=normalize(normalMatrix*normal);vec4 wp=modelMatrix*vec4(position,1);vP=wp.xyz;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec3 vN;varying vec3 vP;uniform float uTime;uniform vec3 vp;void main(){vec3 vd=normalize(vp-vP);float f=1.0-max(0.0,dot(vd,vN));float i=pow(f,4.0);float hue=sin(uTime*0.12)*0.5+0.5;float aurora=sin(f*12.0-uTime*0.5)*0.2;vec3 col1=vec3(0.3,0.05,0.8);vec3 col2=vec3(0.05,0.5,0.9);vec3 col3=vec3(0.0,0.7,0.5);vec3 col=mix(mix(col1,col2,hue),col3,aurora+0.5);gl_FragColor=vec4(col,i*0.35);}`,
    uniforms: { uTime: { value: 0 }, vp: { value: camera.position } },
    side: THREE.BackSide, blending: THREE.AdditiveBlending, transparent: true
  });
  const haloMesh = new THREE.Mesh(new THREE.SphereGeometry(radius*1.35, 48, 48), haloMat);
  haloMesh.scale.set(0, 0, 0);
  scene.add(haloMesh);

  /* ── EDGE RIM (electric cyan + sparkle + scan) ── */
  const rimMat = new THREE.ShaderMaterial({
    vertexShader: `varying vec3 vN;varying vec3 vP;void main(){vN=normalize(normalMatrix*normal);vec4 wp=modelMatrix*vec4(position,1);vP=wp.xyz;gl_Position=projectionMatrix*viewMatrix*wp;}`,
    fragmentShader: `varying vec3 vN;varying vec3 vP;uniform vec3 vp;uniform float uTime;void main(){vec3 vd=normalize(vp-vP);float r=1.0-max(0.0,dot(vd,vN));r=pow(r,4.0);float sparkle=sin(vP.x*60.0+vP.y*40.0+uTime*3.0)*0.5+0.5;float scan=sin(vP.y*30.0+uTime*2.0)*0.5+0.5;float edge=step(0.9,r);float glow2=sparkle*edge*0.4+scan*edge*0.2;gl_FragColor=vec4(0.2,0.7,1.0,r*0.6+glow2);}`,
    uniforms: { vp: { value: camera.position }, uTime: { value: 0 } },
    side: THREE.FrontSide, blending: THREE.AdditiveBlending, transparent: true
  });
  const rimMesh = new THREE.Mesh(new THREE.SphereGeometry(radius*1.007, 64, 64), rimMat);
  rimMesh.scale.set(0, 0, 0);
  scene.add(rimMesh);

  /* ── Cloud layer ── */
  const cloud = wnCreateCloudLayer(radius);
  cloud.scale.set(0, 0, 0);
  scene.add(cloud);

  /* ── Lights (dramatic cinematic) ── */
  /* ── Glow radial background ── */
  const glowBgCanvas = document.createElement('canvas');
  glowBgCanvas.width = 512; glowBgCanvas.height = 512;
  const gbgCtx = glowBgCanvas.getContext('2d');
  const gbgGrad = gbgCtx.createRadialGradient(256, 256, 0, 256, 256, 256);
  gbgGrad.addColorStop(0, 'rgba(0,100,200,0.12)');
  gbgGrad.addColorStop(0.2, 'rgba(40,0,80,0.06)');
  gbgGrad.addColorStop(1, 'rgba(0,0,0,0)');
  gbgCtx.fillStyle = gbgGrad; gbgCtx.fillRect(0, 0, 512, 512);
  const glowBgTex = new THREE.CanvasTexture(glowBgCanvas);
  const glowBgMat = new THREE.SpriteMaterial({ map: glowBgTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
  const glowBg = new THREE.Sprite(glowBgMat);
  glowBg.position.set(0, 0, -0.5);
  glowBg.scale.set(8, 8, 1);
  scene.add(glowBg);

  scene.add(new THREE.AmbientLight(0x111122, 0.3));
  const sun = new THREE.DirectionalLight(0xffeedd, 2.0); sun.position.set(5, 3, 5); scene.add(sun);
  const rim1 = new THREE.DirectionalLight(0x4488ff, 0.8); rim1.position.set(-3, -1, -2); scene.add(rim1);
  const rim2 = new THREE.DirectionalLight(0x8844ff, 0.5); rim2.position.set(2, -2, -4); scene.add(rim2);
  const fill = new THREE.DirectionalLight(0x224488, 0.3); fill.position.set(-1, -2, -3); scene.add(fill);

  /* ── Stars with twinkle ── */
  const sv = [];
  const starColors = [];
  for (let i = 0; i < 8000; i++) {
    sv.push((Math.random()-0.5)*600, (Math.random()-0.5)*600, (Math.random()-0.5)*600);
    const temp = Math.random();
    if (temp < 0.1) starColors.push(1, 0.85, 0.6); /* warm */
    else if (temp < 0.2) starColors.push(0.7, 0.8, 1); /* cool */
    else starColors.push(1, 1, 1); /* white */
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.Float32BufferAttribute(sv, 3));
  sg.setAttribute('color', new THREE.Float32BufferAttribute(starColors, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({ 
    vertexColors: true, size: 0.12 + Math.random() * 0.08, 
    transparent: true, opacity: 0.8, sizeAttenuation: true 
  })));

  /* ── Orbital particles ── */
  const ap = [];
  const apC = 300;
  const apG = new THREE.BufferGeometry();
  const apP = new Float32Array(apC * 3);
  for (let i = 0; i < apC; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = radius + 0.4 + Math.random() * 2.5;
    apP[i*3] = r * Math.sin(phi) * Math.cos(theta);
    apP[i*3+1] = r * Math.cos(phi);
    apP[i*3+2] = r * Math.sin(phi) * Math.sin(theta);
    ap.push({ theta, phi, r, speed: 0.0002 + Math.random() * 0.0008, phase: Math.random() * Math.PI * 2 });
  }
  apG.setAttribute('position', new THREE.Float32BufferAttribute(apP, 3));
  const apM = new THREE.PointsMaterial({ color: 0x4488ff, size: 0.008, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  const apS = new THREE.Points(apG, apM);
  scene.add(apS);

  /* ── Markers ── */
  const hasGeo = wnData.filter(n => n.lat);
  const mg = new THREE.Group();
  const mm = [];

  hasGeo.forEach(n => {
    const pos = wnLatLonToPos(n.lat, n.lon, radius);
    const color = new THREE.Color(CAT_COLORS[n.category] || '#888899');
    const em = CAT_EMISSIVE[n.category] || 0x666688;

    /* Outer glow halo (big transparent sphere) */
    const glowHalo = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 12, 12),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    glowHalo.position.copy(pos);
    mg.add(glowHalo);

    /* Main marker */
    const m = new THREE.Mesh(
      new THREE.SphereGeometry(0.045, 10, 10),
      new THREE.MeshPhongMaterial({ color, emissive: em, emissiveIntensity: 0.8 })
    );
    m.position.copy(pos);
    m.userData.newsItem = n;
    m.userData.phase = Math.random() * Math.PI * 2;
    mg.add(m);
    mm.push(m);

    /* Bright core dot */
    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(0.025, 6, 6),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 })
    );
    dot.position.copy(pos.clone().multiplyScalar(1.01));
    mg.add(dot);

    /* Pulse ring */
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.04, 0.08, 16),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.2, side: THREE.DoubleSide })
    );
    ring.position.copy(pos);
    ring.lookAt(0, 0, 0);
    ring.userData.phase = Math.random() * Math.PI * 2;
    mg.add(ring);

    /* Floating location label */
    const locName = (n.location || n.country || '').split(',')[0].trim();
    if (locName) {
      const labelCanvas = document.createElement('canvas');
      labelCanvas.width = 256; labelCanvas.height = 64;
      const lctx = labelCanvas.getContext('2d');
      lctx.clearRect(0, 0, 256, 64);
      lctx.shadowColor = 'rgba(0,0,0,0.8)'; lctx.shadowBlur = 8;
      lctx.font = 'bold 28px "Rajdhani","Courier New",monospace';
      lctx.textAlign = 'center'; lctx.textBaseline = 'middle';
      lctx.fillStyle = '#fff';
      lctx.fillText(locName.toUpperCase(), 128, 30);
      lctx.shadowBlur = 0;
      lctx.font = '14px "Rajdhani",monospace';
      lctx.fillStyle = 'rgba(0,240,255,0.5)';
      lctx.fillText('⬤ LIVE', 128, 55);
      const labelTex = new THREE.CanvasTexture(labelCanvas);
      labelTex.needsUpdate = true;
      const labelMat = new THREE.SpriteMaterial({ map: labelTex, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
      const label = new THREE.Sprite(labelMat);
      label.position.copy(pos.clone().multiplyScalar(1.12));
      label.scale.set(0.4, 0.1, 1);
      label.userData.newsItem = n;
      label.userData.entered = false;
      mg.add(label);
    }
  });

  scene.add(mg);

  /* ── Connection lines between nearby markers ── */
  const connGroup = new THREE.Group();
  const maxConnDist = 1.2;
  for (let i = 0; i < mm.length; i++) {
    for (let j = i + 1; j < mm.length; j++) {
      const pi = mm[i].position, pj = mm[j].position;
      const d = pi.distanceTo(pj);
      if (d < maxConnDist) {
        const connMat = new THREE.LineBasicMaterial({
          color: 0x4488ff, transparent: true, opacity: 0.08,
          blending: THREE.AdditiveBlending, depthWrite: false
        });
        const connGeom = new THREE.BufferGeometry().setFromPoints([pi, pj]);
        const connLine = new THREE.Line(connGeom, connMat);
        connLine.userData.phase = Math.random() * Math.PI * 2;
        connGroup.add(connLine);
      }
    }
  }
  if (connGroup.children.length > 0) scene.add(connGroup);

  wnGlobeScene = scene;
  wnGlobeCamera = camera;
  wnGlobeRenderer = renderer;
  wnGlobe = { scene, camera, renderer, earth, glowMesh, coronaMesh, haloMesh, rimMesh, cloud, markerGroup: mg, markerMeshes: mm, hasGeo, radius, bgGlow: glowBg, connGroup };

  /* Build arcs */
  setTimeout(wnBuildArcs, 800);

  /* ── Entrance animation ── */
  const entStart = performance.now();
  const entDur = 1500;
  let _wnEntranceFlash = true;
  /* Hyperspace flash on entrance */
  setTimeout(() => {
    const flash = document.getElementById('wn-flash');
    if (flash) {
      flash.style.background = 'radial-gradient(ellipse at center, rgba(0,150,255,0.6), rgba(100,0,255,0.3), transparent 70%)';
      flash.style.opacity = '0.4';
      setTimeout(() => { flash.style.opacity = '0'; }, 400);
    }
  }, 100);
  setTimeout(() => { if (!_wnEntranceDone) { _wnEntranceDone = true; } }, 5000);

  function animate() {
    if (!wnGlobeRenderer) return;
    const now = performance.now();
    const elapsed = now - entStart;

    if (elapsed < entDur && !_wnEntranceDone) {
      const t = elapsed / entDur;
      const e = 1 - Math.pow(1 - t, 3);
      const sc = e < 0.3 ? Math.sin(e/0.3*Math.PI)*0.3 : 0.3 + (e-0.3)/0.7*0.7;
      earth.scale.setScalar(Math.min(sc*0.98, 1));
      glowMesh.scale.setScalar(Math.min(sc, 1));
      coronaMesh.scale.setScalar(Math.min(sc, 1));
      haloMesh.scale.setScalar(sc < 0.2 ? 0 : Math.min((sc-0.2)/0.8, 1));
      rimMesh.scale.setScalar(Math.min(sc, 1));
      cloud.scale.setScalar(sc < 0.3 ? 0 : Math.min((sc-0.3)/0.7, 1));
      mg.scale.setScalar(sc < 0.2 ? 0 : Math.min((sc-0.2)/0.8, 1));
      apM.opacity = Math.min(sc*0.4, 0.3);
      const ct = Math.min(t*1.5, 1);
      const ce = 1 - Math.pow(1-ct, 2);
      camera.position.lerpVectors(new THREE.Vector3(5, 2, 5), new THREE.Vector3(3.2, 0.8, 3.2), ce);
      camera.lookAt(0, 0, 0);
      _wnEntranceDone = t >= 1;
    } else {
      if (!_wnEntranceDone) { _wnEntranceDone = true; wnStartAutoSuggest(); }
      earth.scale.setScalar(1);
      glowMesh.scale.setScalar(1);
      coronaMesh.scale.setScalar(1);
      haloMesh.scale.setScalar(1);
      rimMesh.scale.setScalar(1);
      cloud.scale.setScalar(1);
      mg.scale.setScalar(1);
      apM.opacity = 0.3;

      /* Auto-rotate + drag inertia */
      if (Math.abs(_wnDragVelocity) > 0.0001) {
        _wnGlobeAngle += _wnDragVelocity;
        _wnDragVelocity *= _wnDragDecay;
        earth.rotation.y = _wnGlobeAngle;
        mg.rotation.y = _wnGlobeAngle;
        if (cloud) cloud.rotation.y = _wnGlobeAngle * 0.7;
      } else if (_wnAutoRotate) {
        _wnGlobeAngle += 0.002;
        earth.rotation.y = _wnGlobeAngle;
        mg.rotation.y = _wnGlobeAngle;
        if (cloud) cloud.rotation.y = _wnGlobeAngle * 0.7;
      }

      /* Cloud slow rotation */
      if (_wnCloudMesh && !_wnAutoRotate && Math.abs(_wnDragVelocity) < 0.0001) {
        _wnCloudMesh.rotation.y += 0.0003;
        _wnCloudMesh.rotation.x += 0.0001;
      }

      /* Pulse markers */
      const activeMM = wnGlobe?.markerMeshes || mm;
      activeMM.forEach(m => {
        if (!m.material) return;
        m.material.opacity = Math.sin(now/400 + m.userData.phase) * 0.15 + 0.85;
        const s = 1 + Math.sin(now/500 + m.userData.phase) * 0.1;
        m.scale.setScalar(s);
      });

      /* Connection lines pulse */
      const activeConn = (wnGlobe?.connGroup) || connGroup;
      activeConn.children.forEach(line => {
        if (!line.material) return;
        const pulse = 0.06 + 0.04 * Math.sin(now/2000 + (line.userData.phase || 0));
        line.material.opacity = pulse;
      });

      /* Fade in labels after entrance */
      const activeMG = (wnGlobe?.markerGroup) || mg;
      activeMG.children.forEach(ch => {
        if (ch.isSprite && ch.material) {
          if (_wnEntranceDone && !ch.userData.entered) {
            ch.material.opacity = Math.min(1, ch.material.opacity + 0.02);
            if (ch.material.opacity >= 1) ch.userData.entered = true;
          }
          if (ch.material.opacity > 0) {
            ch.position.y += Math.sin(now/2000 + (ch.userData.phase||0)) * 0.00005;
          }
        }
      });

      /* Pulse rings */
      mg.children.forEach(ch => {
        if (ch.isMesh && ch.geometry?.type === 'RingGeometry') {
          const s = 1 + Math.sin(now/600 + (ch.userData.phase||0)) * 0.35;
          ch.scale.setScalar(s);
          ch.material.opacity = 0.1 + Math.sin(now/600 + (ch.userData.phase||0)) * 0.12;
          ch.material.color.setHSL(((now/8000 + (ch.userData.phase||0)) % 1), 0.6, 0.5);
        }
      });

      /* Arc animations */
      _wnArcs.forEach((line, li) => {
        if (!line.material) return;
        const phase = line.userData.phase || 0;
        const base = line.userData.glow ? 0.04 : 0.15;
        const amp = line.userData.glow ? 0.04 : 0.12;
        line.material.opacity = base + Math.sin(now/1500 + phase) * amp + amp * 0.5;
        if (line.userData.color && !line.userData.glow) {
          const c = new THREE.Color(line.userData.color);
          c.offsetHSL(Math.sin(now/3000 + phase) * 0.01, 0, 0);
          line.material.color.copy(c);
        }
      });

      /* Arc flowing particles */
      _wnArcParticles.forEach(p => {
        const d = p.userData;
        if (!d || !d.curve) return;
        if (!d.enhanced) {
          d.t = (d.t + d.speed) % 1;
          const pt = d.curve.getPoint(d.t);
          p.position.copy(pt);
          p.scale.setScalar(1 + Math.sin(d.t * Math.PI) * 0.5);
          p.material.opacity = 0.3 + Math.sin(d.t * Math.PI) * 0.5;
          return;
        }

        d.t = (d.t + d.speed) % 1;
        const pt = d.curve.getPoint(d.t);
        p.position.copy(pt);

        /* Pulse color along path */
        const pulse = 0.5 + 0.5 * Math.sin(now * d.pulseSpeed + d.pulseOffset);
        p.material.color.lerpColors(d.color, d.glow, Math.min(1, pulse));
        p.scale.setScalar(1 + 0.3 * pulse);

        /* Trail particles follow behind */
        if (d.trails) {
          d.trails.forEach((trail, ti) => {
            const tt = (d.t - (ti + 1) * 0.04 + 1) % 1;
            const trailPt = d.curve.getPoint(tt);
            trail.position.copy(trailPt);
            const fade = Math.sin(tt * Math.PI) * trail.userData.baseAlpha;
            trail.material.opacity = Math.max(0, fade);
            trail.scale.setScalar(0.4 + 0.6 * (1 - ti / d.trails.length));
            trail.material.color.copy(p.material.color);
          });
        }

        /* Stream wiggle */
        const streamPulse = (Math.sin(now * d.streamSpeed + d.streamOffset) + 1) / 2;
        p.material.opacity = 0.8 + 0.2 * streamPulse;
      });

      /* Animate orbital particles */
      const pos = apS.geometry.attributes.position.array;
      ap.forEach((p, i) => {
        p.theta += p.speed;
        const r = p.r;
        pos[i*3] = r * Math.sin(p.phi) * Math.cos(p.theta);
        pos[i*3+1] = r * Math.cos(p.phi);
        pos[i*3+2] = r * Math.sin(p.phi) * Math.sin(p.theta);
      });
      apS.geometry.attributes.position.needsUpdate = true;

      /* Particle burst cleanup */
      for (let i = _wnParticles.length-1; i >= 0; i--) {
        const p = _wnParticles[i];
        p.userData.life -= 0.015;
        if (p.userData.life <= 0) { wnGlobeScene.remove(p); _wnParticles.splice(i, 1); continue; }
        p.position.add(p.userData.vel);
        p.material.opacity = p.userData.life;
        p.scale.setScalar(1 + (1-p.userData.life) * 4);
      }

      /* Warp particle animation */
      for (let i = _wnWarpParticles.length-1; i >= 0; i--) {
        const p = _wnWarpParticles[i];
        p.userData.life -= 0.008;
        if (p.userData.life <= 0) { wnGlobeScene.remove(p); _wnWarpParticles.splice(i, 1); continue; }
        p.position.add(p.userData.vel);
        p.position.add(p.userData.vel.clone().multiplyScalar(1 - p.userData.life));
        p.material.opacity = p.userData.life * 0.6;
        p.scale.setScalar(1 + (1-p.userData.life) * 8);
      }

      if (rimMat.uniforms) { rimMat.uniforms.vp.value.copy(camera.position); rimMat.uniforms.uTime.value = now * 0.001; }
      if (glowMat.uniforms) { glowMat.uniforms.uTime.value = now * 0.001; glowMat.uniforms.vp.value.copy(camera.position); }
      if (coronaMat.uniforms) coronaMat.uniforms.uTime.value = now * 0.001;
      if (haloMat.uniforms) { haloMat.uniforms.uTime.value = now * 0.001; haloMat.uniforms.vp.value.copy(camera.position); }
    }

    renderer.render(scene, camera);
    _wnAnimFrame = requestAnimationFrame(animate);
  }
  animate();

  /* ── Raycaster ── */
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  const clickables = mg.children.filter(c => c.userData.newsItem);

  renderer.domElement.addEventListener('click', (e) => {
    if (!_wnEntranceDone || _wnZooming) return;
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX-rect.left)/rect.width)*2-1;
    mouse.y = -((e.clientY-rect.top)/rect.height)*2+1;
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(clickables);
    if (hits.length > 0) { const n = hits[0].object.userData.newsItem; if (n) wnSelectNews(n); }
  });

  renderer.domElement.addEventListener('mousemove', (e) => {
    if (!_wnEntranceDone || _wnZooming) return;
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX-rect.left)/rect.width)*2-1;
    mouse.y = -((e.clientY-rect.top)/rect.height)*2+1;
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(clickables);
    if (hits.length > 0 && hits[0].object.userData.newsItem) {
      const n = hits[0].object.userData.newsItem;
      if (n !== _wnHoveredMarker) {
        _wnHoveredMarker = n;
        renderer.domElement.style.cursor = 'pointer';
        const tt = document.getElementById('wn-globe-tooltip');
        if (tt) { tt.textContent = n.title; tt.style.display = 'block'; tt.style.left = (e.clientX+14)+'px'; tt.style.top = (e.clientY-10)+'px'; }
      }
    } else if (_wnHoveredMarker) { _wnHoveredMarker = null; renderer.domElement.style.cursor = 'default';
        const tt = document.getElementById('wn-globe-tooltip'); if (tt) tt.style.display = 'none'; }
  });

  renderer.domElement.addEventListener('pointerdown', (e) => { _wnAutoRotate = false;
    _wnDragVelocity = 0; _wnDragHistory = [];
    const tt = document.getElementById('wn-globe-tooltip'); if (tt) tt.style.display = 'none';
  });
  renderer.domElement.addEventListener('pointermove', (e) => {
    if (e.buttons !== 1) return;
    const now = performance.now();
    _wnDragHistory.push({ x: e.clientX, t: now });
    if (_wnDragHistory.length > 5) _wnDragHistory.shift();
  });
  renderer.domElement.addEventListener('pointerup', () => {
    if (_wnDragHistory.length > 1) {
      const first = _wnDragHistory[0], last = _wnDragHistory[_wnDragHistory.length-1];
      const dt = last.t - first.t;
      if (dt > 20) {
        const dx = last.x - first.x;
        const v = dx / dt;
        _wnDragVelocity = Math.max(-0.08, Math.min(0.08, v * 0.3));
      }
    }
    _wnDragHistory = [];
    if (_wnDragTimeout) clearTimeout(_wnDragTimeout);
    _wnDragTimeout = setTimeout(() => { if (!_wnAutoPilot && Math.abs(_wnDragVelocity) < 0.001) _wnAutoRotate = true; }, 3000);
  });
  window.addEventListener('resize', () => {
    if (!wnGlobeRenderer) return;
    camera.aspect = container.clientWidth/container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  });
}

function wnReinitGlobeMarkers() {
  if (!wnGlobeRenderer || !wnGlobeScene) return;
  const g = wnGlobe;
  if (g.markerGroup?.parent) g.markerGroup.parent.remove(g.markerGroup);
  if (g.connGroup?.parent) g.connGroup.parent.remove(g.connGroup);
  let hasGeo = wnData.filter(n => n.lat);
  if (_wnCatFilter && _wnCatFilter !== 'all') hasGeo = hasGeo.filter(n => (n.category||'general') === _wnCatFilter);
  const mg = new THREE.Group();
  const mm = [];

  hasGeo.forEach(n => {
    const pos = wnLatLonToPos(n.lat, n.lon, g.radius);
    const color = new THREE.Color(wnMarkerColor(n));
    const em = _wnSentimentMode ? new THREE.Color(wnMarkerColor(n)).getHex() : (CAT_EMISSIVE[n.category] || 0x666688);
    const glowHalo = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 12), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, depthWrite: false }));
    glowHalo.position.copy(pos); mg.add(glowHalo);
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.045, 10, 10), new THREE.MeshPhongMaterial({ color, emissive: em, emissiveIntensity: 0.8 }));
    m.position.copy(pos); m.userData.newsItem = n; m.userData.phase = Math.random()*Math.PI*2;
    mg.add(m); mm.push(m);
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.025, 6, 6), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 }));
    dot.position.copy(pos.clone().multiplyScalar(1.01)); mg.add(dot);
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.04, 0.08, 16), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.2, side: THREE.DoubleSide }));
    ring.position.copy(pos); ring.lookAt(0, 0, 0); ring.userData.phase = Math.random()*Math.PI*2; mg.add(ring);

    /* Floating location label */
    const locName = (n.location || n.country || '').split(',')[0].trim();
    if (locName) {
      const lc = document.createElement('canvas'); lc.width = 256; lc.height = 64;
      const lctx = lc.getContext('2d');
      lctx.shadowColor = 'rgba(0,0,0,0.8)'; lctx.shadowBlur = 8;
      lctx.font = 'bold 28px "Rajdhani","Courier New",monospace';
      lctx.textAlign = 'center'; lctx.textBaseline = 'middle';
      lctx.fillStyle = '#fff'; lctx.fillText(locName.toUpperCase(), 128, 30);
      lctx.shadowBlur = 0; lctx.font = '14px "Rajdhani",monospace';
      lctx.fillStyle = 'rgba(0,240,255,0.5)'; lctx.fillText('⬤ LIVE', 128, 55);
      const lt = new THREE.CanvasTexture(lc); lt.needsUpdate = true;
      const lm = new THREE.SpriteMaterial({ map: lt, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
      const lb = new THREE.Sprite(lm);
      lb.position.copy(pos.clone().multiplyScalar(1.12));
      lb.scale.set(0.4, 0.1, 1);
      lb.userData.newsItem = n; lb.userData.entered = false;
      mg.add(lb);
    }
  });

  g.markerGroup = mg; g.markerMeshes = mm; g.hasGeo = hasGeo;
  wnGlobeScene.add(mg);

  /* Rebuild connections */
  if (g.connGroup?.parent) g.connGroup.parent.remove(g.connGroup);
  const connGroup2 = new THREE.Group();
  const maxConnDist2 = 1.2;
  for (let i = 0; i < mm.length; i++) {
    for (let j = i + 1; j < mm.length; j++) {
      const pi = mm[i].position, pj = mm[j].position;
      if (pi.distanceTo(pj) < maxConnDist2) {
        const cm = new THREE.LineBasicMaterial({ color: 0x4488ff, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, depthWrite: false });
        const cg = new THREE.BufferGeometry().setFromPoints([pi, pj]);
        const cl = new THREE.Line(cg, cm);
        cl.userData.phase = Math.random() * Math.PI * 2;
        connGroup2.add(cl);
      }
    }
  }
  if (connGroup2.children.length > 0) wnGlobeScene.add(connGroup2);
  g.connGroup = connGroup2;

  setTimeout(wnBuildArcs, 500);
}

function wnStartAutoSuggest() {
  const el = document.getElementById('wn-suggest');
  if (!el) return;
  const geo = wnData.filter(n => n.lat && n.location);
  if (geo.length < 3) return;
  const shuffled = [...geo].sort(() => Math.random()-0.5).slice(0, 5);
  el.innerHTML = shuffled.map(n => {
    const c = CAT_COLORS[n.category] || '#888';
    return `<span class="wn-suggest-chip" onclick="wnSelectNews(wnData[${wnData.indexOf(n)}])" style="background:#1a1a2e;border:1px solid ${c}44;color:${c};padding:4px 12px;border-radius:14px;cursor:pointer;font-size:11px;transition:all.15s">${CAT_ICONS[n.category]||'📰'} ${n.location||n.country}</span>`;
  }).join('');
}

/* ════════════════════════════════════════════════════════════════
   REEL MODE — schede verticali full-screen stile TikTok
   ════════════════════════════════════════════════════════════════ */
function wnToggleReel() {
  _wnReelOpen = !_wnReelOpen;
  const reel = document.getElementById('wn-reel');
  const btn = document.getElementById('wn-reel-btn');
  if (!reel) return;
  if (_wnReelOpen) {
    reel.style.display = 'block';
    if (btn) { btn.style.color = '#fff'; btn.style.background = 'linear-gradient(135deg,#ff66cc,#8844ff)'; }
    wnRenderReel();
  } else {
    reel.style.display = 'none';
    if (btn) { btn.style.color = '#ff66cc'; btn.style.background = 'linear-gradient(135deg,rgba(255,102,204,0.1),rgba(136,68,255,0.1))'; }
    if (_wnReelObserver) { _wnReelObserver.disconnect(); _wnReelObserver = null; }
    if (_wnCurrentAudio) { try { _wnCurrentAudio.pause(); } catch(e){} _wnCurrentAudio = null; }
    _wnReelAutoplay = false;
    const ab = document.getElementById('wn-reel-autoplay-btn');
    if (ab) ab.textContent = '▶ AUTO-PLAY: OFF';
  }
}

function wnRenderReel() {
  const scroll = document.getElementById('wn-reel-scroll');
  if (!scroll) return;
  /* usa filtro categoria attivo, prioritizza geo-localizzate */
  let items = wnData.slice();
  if (_wnCatFilter && _wnCatFilter !== 'all') items = items.filter(n => (n.category||'general') === _wnCatFilter);
  items.sort((a,b) => (a.lat?0:1)-(b.lat?0:1));
  items = items.slice(0, 20);
  _wnReelItems = items;

  scroll.innerHTML = items.map((n, i) => {
    const c = CAT_COLORS[n.category] || '#4488ff';
    const sc = wnSentColor(n.sentiment);
    const t = n._tTitle || n.title || '';
    const loc = n.location || n.country || 'Mondo';
    const img = n.image || '';
    const bg = img
      ? `background-image:linear-gradient(0deg,#04060c 2%,rgba(4,6,12,0.4) 45%,rgba(4,6,12,0.7) 100%),url('${img.replace(/'/g,'')}');background-size:cover;background-position:center`
      : `background:radial-gradient(circle at 50% 35%, ${c}22, #04060c 70%)`;
    return `<div class="wn-reel-card" data-idx="${i}" style="scroll-snap-align:start;height:100%;width:100%;position:relative;display:flex;flex-direction:column;justify-content:flex-end;${bg};overflow:hidden">
      <div style="position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,240,255,0.015) 3px,rgba(0,240,255,0.015) 4px)"></div>
      <div style="position:absolute;top:60px;left:20px;display:flex;gap:6px;align-items:center">
        <span style="background:${c};color:#000;padding:3px 12px;border-radius:4px;font:10px monospace;font-weight:700;letter-spacing:1px;text-transform:uppercase">${CAT_ICONS[n.category]||'📰'} ${n.category||'news'}</span>
        <span style="background:rgba(0,0,0,0.5);border:1px solid ${sc}66;color:${sc};padding:3px 10px;border-radius:4px;font:9px monospace">${wnSentLabel(n.sentiment)}</span>
      </div>
      <div style="position:relative;z-index:2;padding:24px 70px 90px 24px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
          <span style="color:${c};font:11px monospace;font-weight:700;letter-spacing:1px">📍 ${loc}</span>
          <span style="width:5px;height:5px;border-radius:50%;background:#00ff88;animation:wnPulse 1.2s infinite"></span>
          <span style="color:#00ff88;font:9px monospace;letter-spacing:1px">LIVE</span>
          <span style="color:#555;font:9px monospace">${n.source||''}</span>
        </div>
        <div style="font-size:26px;font-weight:700;line-height:1.25;color:#fff;text-shadow:0 2px 20px rgba(0,0,0,0.9);margin-bottom:12px">${t}</div>
        ${n._tSnippet||n.snippet ? `<div style="font-size:13px;line-height:1.5;color:#bbc;max-width:90%;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden">${n._tSnippet||n.snippet}</div>` : ''}
      </div>
      <!-- right action rail -->
      <div style="position:absolute;right:14px;bottom:120px;z-index:3;display:flex;flex-direction:column;gap:14px;align-items:center">
        <button onclick="wnReelSpeak(${i})" title="Ascolta" style="width:46px;height:46px;border-radius:50%;background:rgba(0,0,0,0.5);border:1px solid ${c}88;color:${c};cursor:pointer;font-size:18px;backdrop-filter:blur(6px)">🔊</button>
        <button onclick="wnReelFlyTo(${i})" title="Mostra sul globo" style="width:46px;height:46px;border-radius:50%;background:rgba(0,0,0,0.5);border:1px solid rgba(0,240,255,0.4);color:#00f0ff;cursor:pointer;font-size:18px;backdrop-filter:blur(6px)">🌍</button>
        <a href="${n.url}" target="_blank" title="Apri" style="width:46px;height:46px;border-radius:50%;background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.2);color:#fff;cursor:pointer;font-size:16px;backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;text-decoration:none">↗</a>
      </div>
      <div style="position:absolute;bottom:0;left:0;right:0;height:3px;background:linear-gradient(90deg,${c},transparent)"></div>
    </div>`;
  }).join('');

  /* progress dots */
  const dots = document.getElementById('wn-reel-dots');
  if (dots) dots.innerHTML = items.map((_, i) =>
    `<span class="wn-reel-dot" data-i="${i}" style="width:6px;height:6px;border-radius:50%;background:${i===0?'#ff66cc':'rgba(255,255,255,0.2)'};transition:all .3s"></span>`
  ).join('');

  const counter = document.getElementById('wn-reel-counter');
  if (counter) counter.textContent = `01 / ${String(items.length).padStart(2,'0')}`;

  /* IntersectionObserver per card attiva */
  if (_wnReelObserver) _wnReelObserver.disconnect();
  _wnReelObserver = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting && e.intersectionRatio > 0.6) {
        const idx = parseInt(e.target.dataset.idx);
        _wnReelCurrent = idx;
        /* update dots */
        document.querySelectorAll('.wn-reel-dot').forEach((d,di) => {
          d.style.background = di===idx ? '#ff66cc' : 'rgba(255,255,255,0.2)';
          d.style.transform = di===idx ? 'scale(1.6)' : 'scale(1)';
        });
        if (counter) counter.textContent = `${String(idx+1).padStart(2,'0')} / ${String(items.length).padStart(2,'0')}`;
        /* sync globe */
        const n = _wnReelItems[idx];
        if (n && n.lat && wnGlobeRenderer) wnGlobeFlyTo(n);
        /* autoplay TTS */
        if (_wnReelAutoplay) wnReelSpeak(idx, true);
      }
    });
  }, { root: scroll, threshold: [0.6] });
  scroll.querySelectorAll('.wn-reel-card').forEach(c => _wnReelObserver.observe(c));
  scroll.scrollTop = 0;
}

function wnReelSpeak(idx, auto) {
  const n = _wnReelItems[idx];
  if (!n) return;
  if (_wnCurrentAudio) { try { _wnCurrentAudio.pause(); } catch(e){} _wnCurrentAudio = null; }
  const tTitle = n._tTitle || n.title;
  const tSnippet = n._tSnippet || n.snippet || '';
  const txt = `${tTitle}. ${tSnippet}`.slice(0, 400);
  fetch('/api/tts', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:txt, voice:'vivian', language:'italian'}) })
    .then(r => r.ok ? r.blob() : Promise.reject())
    .then(blob => {
      const a = new Audio(URL.createObjectURL(blob));
      _wnCurrentAudio = a;
      a.onended = () => {
        if (_wnReelAutoplay && _wnReelOpen) wnReelNext();
      };
      a.play().catch(()=>{});
    }).catch(()=>{ if (_wnReelAutoplay && _wnReelOpen) setTimeout(wnReelNext, 3000); });
}

function wnReelNext() {
  const scroll = document.getElementById('wn-reel-scroll');
  if (!scroll) return;
  const next = Math.min(_wnReelCurrent + 1, _wnReelItems.length - 1);
  if (next === _wnReelCurrent) { _wnReelAutoplay = false; const ab=document.getElementById('wn-reel-autoplay-btn'); if(ab) ab.textContent='▶ AUTO-PLAY: OFF'; return; }
  const card = scroll.querySelector(`.wn-reel-card[data-idx="${next}"]`);
  if (card) card.scrollIntoView({ behavior:'smooth' });
}

function wnReelFlyTo(idx) {
  const n = _wnReelItems[idx];
  if (n && n.lat && wnGlobeRenderer) { wnToggleReel(); setTimeout(()=>wnSelectNews(n), 400); }
}

function wnReelToggleAutoplay() {
  _wnReelAutoplay = !_wnReelAutoplay;
  const ab = document.getElementById('wn-reel-autoplay-btn');
  if (ab) ab.textContent = _wnReelAutoplay ? '⏸ AUTO-PLAY: ON' : '▶ AUTO-PLAY: OFF';
  if (_wnReelAutoplay) wnReelSpeak(_wnReelCurrent, true);
  else if (_wnCurrentAudio) { try { _wnCurrentAudio.pause(); } catch(e){} }
}

/* ── CSS ── */
const style = document.createElement('style');
style.textContent = `
  @keyframes wnPulse{0%{transform:scale(1);opacity:1}50%{transform:scale(1.3);opacity:0.7}100%{transform:scale(1);opacity:1}}
  @keyframes wnPulseCrit{0%{transform:scale(1);opacity:1}50%{transform:scale(1.5);opacity:0.5}100%{transform:scale(1);opacity:1}}
  @keyframes wnVoiceBar{0%,100%{transform:scaleY(0.4);opacity:0.3}50%{transform:scaleY(1.3);opacity:1}}
  @keyframes wnHUDLine{0%{opacity:0;transform:translateX(20px)}100%{opacity:1;transform:translateX(0)}}
  @keyframes wnHoloIn{0%{opacity:0;transform:scale(0.92);filter:brightness(2) hue-rotate(30deg)}100%{opacity:1;transform:scale(1);filter:brightness(1) hue-rotate(0deg)}}
  @keyframes wnHoloOut{0%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(1.08);filter:brightness(3)}}
  @keyframes wnTypewriter{from{width:0}to{width:100%}}
  @keyframes wnBlinkCursor{50%{border-color:transparent}}
  @keyframes wnScanline{0%{background-position:0 0}100%{background-position:0 100px}}
  @keyframes wnGridPulse{0%,100%{opacity:0.12}50%{opacity:0.2}}
  @keyframes wnTickerScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
  @keyframes wnZoomWarp{0%{opacity:0;transform:translate(0,0) scale(1)}20%{opacity:0.8}80%{opacity:0.8}100%{opacity:0;transform:translate(var(--wx,100px),var(--wy,-100px)) scale(0)}}
  @keyframes wnScanFast{0%{transform:translateX(-100%) skewX(-20deg)}100%{transform:translateX(500%) skewX(-20deg)}}
  @keyframes wnGlitchRandom{0%{clip-path:inset(0 0 100% 0)}5%{clip-path:inset(0 0 90% 0)}10%{clip-path:inset(20% 0 70% 0)}30%{clip-path:inset(60% 0 30% 0)}50%{clip-path:inset(90% 0 0 0)}70%{clip-path:inset(30% 0 50% 0)}100%{clip-path:inset(0 0 0 0)}}
  @keyframes wnBeamExpand{0%{opacity:1;transform:scale(0.5)}100%{opacity:0;transform:scale(12)}}
  @keyframes wnZoomFlare{0%{opacity:0;filter:brightness(3) blur(4px)}50%{opacity:0.5;filter:brightness(1.5) blur(0)}100%{opacity:0;filter:brightness(1) blur(0)}}
  @keyframes wnShake{0%,100%{transform:translate(0,0)}20%{transform:translate(-4px,2px)}40%{transform:translate(3px,-3px)}60%{transform:translate(-2px,4px)}80%{transform:translate(5px,-2px)}}
  #wn-flash{position:fixed;inset:0;background:radial-gradient(ellipse at center,rgba(0,150,255,0.4),transparent 70%);z-index:9999;pointer-events:none;opacity:0;transition:opacity .3s}
  #wn-globe-tooltip{position:fixed;z-index:910;background:rgba(16,16,30,0.93);border:1px solid rgba(42,42,78,0.8);color:#ddd;padding:6px 12px;border-radius:6px;font:12px/1.3 'Rajdhani',monospace;pointer-events:none;max-width:280px;backdrop-filter:blur(8px);display:none}
  .wn-suggest-chip:hover{border-color:#00f0ff!important;box-shadow:0 0 16px rgba(0,240,255,0.25)!important}
  #wn-sidebar .wn-card{border-left:2px solid transparent}
  #wn-sidebar .wn-card:hover{border-left-color:#00f0ff;transform:translateX(3px)}
  #wn-detail-card img{animation:wnImgFadeIn .6s cubic-bezier(0.175,0.885,0.32,1.275) both}
  @keyframes wnImgFadeIn{0%{opacity:0;transform:scale(1.05)}100%{opacity:1;transform:scale(1)}}
  #wn-autonews-btn{border-color:#2a2a3e!important;color:#888!important;transition:all .2s}
  #wn-autonews-btn:hover{border-color:#4488ff!important;color:#4488ff!important;box-shadow:0 0 12px rgba(68,136,255,0.2)}
  @keyframes wnGlobeScan{0%{background-position:0 0,0 0}100%{background-position:0 100px,0 0}}
  @keyframes wnCardIn{0%{opacity:0;transform:translateX(-12px) scale(0.95);filter:blur(2px)}100%{opacity:1;transform:translateX(0) scale(1);filter:blur(0)}}
  @keyframes wnCardGlow{0%,100%{box-shadow:0 0 8px rgba(0,240,255,0.05)}50%{box-shadow:0 0 20px rgba(0,240,255,0.12)}}
  @keyframes wnSlideDown{0%{opacity:0;transform:translateX(-50%) translateY(-12px)}100%{opacity:1;transform:translateX(-50%) translateY(0)}}
  @keyframes wnGradientShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
  .wn-card:active{transform:scale(0.97)!important}
  @keyframes wnGlobePulse{0%,100%{opacity:0.8}50%{opacity:1}}
  @keyframes wnDataStream{0%{background-position:0 0}100%{background-position:0 40px}}
  @keyframes wnScanReveal{0%{clip-path:inset(0 100% 0 0)}100%{clip-path:inset(0 0 0 0)}}
  @keyframes wnCityGlow{0%,100%{opacity:0.6;filter:blur(0px)}50%{opacity:1;filter:blur(1px)}}
  @keyframes wnRadarPulse{0%{transform:translate(-50%,-50%) scale(1);opacity:0.8}100%{transform:translate(-50%,-50%) scale(40);opacity:0}}
`;
document.head.appendChild(style);

const flashDiv = document.createElement('div');
flashDiv.id = 'wn-flash';
document.body.appendChild(flashDiv);

const ttDiv = document.createElement('div');
ttDiv.id = 'wn-globe-tooltip';
document.body.appendChild(ttDiv);

/* ── SIDEBAR PARTICLE SPARKLE ── */
const sideParticleCanvas = document.createElement('canvas');
sideParticleCanvas.id = 'wn-side-particles';
sideParticleCanvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;opacity:0.3';
const sideBar = document.getElementById('wn-sidebar');
if (sideBar) sideBar.appendChild(sideParticleCanvas);
function wnSideParticles() {
  const c = sideParticleCanvas;
  if (!c || !c.parentNode) return;
  const w = c.parentNode.clientWidth || 320;
  const h = c.parentNode.clientHeight || 600;
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  const particles = [];
  for (let i = 0; i < 30; i++) {
    particles.push({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.2, vy: -0.1 - Math.random() * 0.2,
      sz: 1 + Math.random() * 2, o: 0.1 + Math.random() * 0.4,
      phase: Math.random() * Math.PI * 2
    });
  }
  function draw() {
    if (!c || !c.parentNode) return;
    ctx.clearRect(0, 0, w, h);
    particles.forEach(p => {
      p.x += p.vx + Math.sin(performance.now() / 2000 + p.phase) * 0.1;
      p.y += p.vy;
      if (p.y < -5) { p.y = h + 5; p.x = Math.random() * w; }
      if (p.x < -5 || p.x > w + 5) p.x = Math.random() * w;
      const alpha = p.o * (0.5 + 0.5 * Math.sin(performance.now() / 1000 + p.phase));
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.sz, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0,200,255,${alpha * 0.3})`;
      ctx.fill();
    });
    requestAnimationFrame(draw);
  }
  draw();
}
setTimeout(wnSideParticles, 500);

  /* ── CYBERPUNK OVERLAY (scanlines + grid on globe) ── */
  const overlayDiv = document.createElement('div');
  overlayDiv.id = 'wn-globe-overlay';
  overlayDiv.style.cssText = `
    position:absolute;inset:0;pointer-events:none;z-index:4;
    opacity:0.12;
    background:
      repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,240,255,0.04) 3px,rgba(0,240,255,0.04) 4px),
      repeating-linear-gradient(90deg,transparent,transparent 40px,rgba(0,240,255,0.03) 40px,rgba(0,240,255,0.03) 41px);
    animation:wnGlobeScan 6s linear infinite;
    mix-blend-mode:screen
  `;
  const mapDiv = document.getElementById('wn-map');
  if (mapDiv) mapDiv.appendChild(overlayDiv);

  /* ── CYBERPUNK HUD CORNER BRACKETS ── */
  for (const [pos, rot] of [['top:8px;left:8px',''], ['top:8px;right:8px','rotate(90deg)'], ['bottom:8px;right:8px','rotate(180deg)'], ['bottom:8px;left:8px','rotate(270deg)']]) {
    const bracket = document.createElement('div');
    bracket.style.cssText = `position:absolute;${pos};z-index:5;pointer-events:none;opacity:0.15;width:24px;height:24px;transform:${rot}`;
    bracket.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24"><path d="M0 0h16v2H2v14H0z" fill="#00f0ff"/><path d="M24 24H8v-2h14V8h2z" fill="#00f0ff"/></svg>`;
    mapDiv.appendChild(bracket);
  }

window.wnData = wnData;
window.wnInit = wnInit;
window.wnRefresh = wnRefresh;
window.wnShowDetail = wnShowDetail;
window.wnCloseDetail = wnCloseDetail;
window.wnSelectNews = wnSelectNews;
window.wnSpeakNews = wnSpeakNews;
window.wnToggleAutoNews = wnToggleAutoNews;
/* ── nuove funzioni ── */
window.wnSetCategoryFilter = wnSetCategoryFilter;
window.wnToggleSentimentMode = wnToggleSentimentMode;
window.wnToggleStats = wnToggleStats;
window.wnToggleReel = wnToggleReel;
window.wnReelSpeak = wnReelSpeak;
window.wnReelFlyTo = wnReelFlyTo;
window.wnReelToggleAutoplay = wnReelToggleAutoplay;
window.wnRenderList = wnRenderList;

console.log('[WN] v9.0 // GDELT + SENTIMENT + REEL + FILTRI ON');

setInterval(() => {
  console.log('[WN] Hourly refresh...');
  if (_wnReelOpen) return; /* non disturbare durante reel */
  fetch('/api/worldnews?max=60').then(r=>r.json()).then(d => wnLoadData(d)).catch(() => {});
}, 3600000);

(function tryAutoInit() {
  const panel = document.getElementById('worldnews-panel');
  if (!panel) return;
  function safeInit() {
    if (typeof wnInit !== 'function') { setTimeout(safeInit, 500); return; }
    try { wnInit(); } catch(e) { console.warn('[WN] safeInit ritenta:', e); setTimeout(safeInit, 1000); }
  }
  if (panel.classList.contains('open')) { setTimeout(safeInit, 300); }
  else {
    const obs = new MutationObserver(() => {
      if (panel.classList.contains('open')) { obs.disconnect(); setTimeout(safeInit, 300); }
    });
    obs.observe(panel, { attributes: true, attributeFilter: ['class'] });
  }
})();