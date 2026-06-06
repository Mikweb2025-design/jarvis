/* worldnews.js — J.A.R.V.I.S World News Map v2.0 */
import * as THREE from 'three';

let wnData = [];
let wnMap = null;
let wnMarkers = [];
let wnGlobe = null;
let wnGlobeScene = null;
let wnGlobeCamera = null;
let wnGlobeRenderer = null;
let wnIs3D = true;
let _wnAnimFrame = null;

const CAT_COLORS = {
  conflict: '#ff4444', disaster: '#ff8800', politics: '#4488ff',
  economy: '#44dd88', climate: '#44dd88', tech: '#aa66ff', general: '#888899'
};
const CAT_ICONS = {
  conflict: '⚔', disaster: '🌊', politics: '🏛',
  economy: '💰', climate: '🌿', tech: '🔬', general: '📰'
};

function wnInit() {
  const container = document.getElementById('wn-map');
  if (!container) { console.error('WN: no #wn-map'); return; }
  if (container._wnInited) return;
  if (container.clientWidth < 10 || container.clientHeight < 10) {
    setTimeout(wnInit, 200);
    return;
  }
  container._wnInited = true;

  try {
    wnMap = L.map('wn-map', {
      center: [30, 20], zoom: 2,
      zoomControl: false, attributionControl: false,
      scrollWheelZoom: true
    });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png').addTo(wnMap);
    L.control.zoom({ position: 'bottomright' }).addTo(wnMap);
  } catch(e) { console.error('WN map init error:', e); return; }

  wnRefresh();

  wnMap.on('moveend', () => {
    document.getElementById('wn-3d-toggle').checked = false;
    wnIs3D = false;
  });
}

function wnLoadData(data) {
  wnData = data.news || [];
  window.wnData = wnData;
  document.getElementById('wn-count').textContent = `${wnData.length} news`;
  wnRenderMarkers();
  wnRenderList();
}

function wnRenderMarkers() {
  if (wnMap) {
    wnMarkers.forEach(m => wnMap.removeLayer(m));
    wnMarkers = [];
  }
  const hasGeo = wnData.filter(n => n.lat);
  hasGeo.forEach(n => {
    const color = CAT_COLORS[n.category] || '#888899';
    const icon = L.divIcon({
      className: '',
      html: `<div style="width:14px;height:14px;background:${color};border:2px solid #fff;border-radius:50%;box-shadow:0 0 12px ${color}44;cursor:pointer"></div>`,
      iconSize: [14, 14], iconAnchor: [7, 7]
    });
    const marker = L.marker([n.lat, n.lon], { icon }).addTo(wnMap);
    marker.on('click', () => wnSelectNews(n));
    marker.bindTooltip(n.title, { direction: 'top', offset: [0, -10],
      className: 'wn-tooltip' });
    wnMarkers.push(marker);
  });
}

function wnRenderList(filter) {
  const el = document.getElementById('wn-news-list');
  let items = wnData;
  if (filter) {
    const f = filter.toLowerCase();
    items = items.filter(n => n.title.toLowerCase().includes(f) || (n.location||'').toLowerCase().includes(f));
  }
  el.innerHTML = items.map((n, idx) => {
    const cat = CAT_ICONS[n.category] || '📰';
    const loc = n.location || n.country || '';
    const time = n.published ? n.published.slice(0, 10) : '';
    const hasGeo = n.lat ? 'style="cursor:pointer"' : '';
    return `<div class="wn-card" onclick="wnSelectNews(wnData[${idx}])" ${hasGeo}>
      <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:4px">
        <span style="color:${CAT_COLORS[n.category] || '#888'};font-size:11px">${cat} ${n.source}</span>
        <span style="color:#555;font-size:10px">${time}</span>
      </div>
      <div style="font-size:13px;line-height:1.3;color:#ddd;margin-bottom:4px">${n.title}</div>
      ${loc ? `<div style="font-size:11px;color:#00f0ff">📍 ${loc}${n.country ? ' · ' + n.country : ''}</div>` : ''}
    </div>`;
  }).join('');
}

function wnSelectNews(n) {
  wnShowDetail(n);
  // Fly to on 2D map or animate globe
  if (n.lat) {
    if (wnMap && wnMap._container && wnMap._container.parentNode) {
      wnMap.flyTo([n.lat, n.lon], 5, { duration: 1.5 });
    } else if (wnGlobeRenderer) {
      wnGlobeFlyTo(n.lat, n.lon, n);
    }
  }
  // Auto-read in Italian
  wnSpeakNews(n);
}

function wnSpeakNews(n) {
  const text = `Notizia da ${n.source}. ${n.title}. ${n.snippet}`;
  const voice = document.querySelector('.voice-btn.active')?.dataset?.voice || 'vivian';
  fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice, language: 'italian' })
  })
    .then(r => r.blob())
    .then(blob => {
      const audio = new Audio(URL.createObjectURL(blob));
      audio.play();
    })
    .catch(e => console.error('TTS error:', e));
}

function wnShowDetail(n) {
  const card = document.getElementById('wn-detail-card');
  const cat = CAT_ICONS[n.category] || '📰';
  const color = CAT_COLORS[n.category] || '#888';
  card.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <span style="color:${color};font-size:12px;letter-spacing:2px;text-transform:uppercase">${cat} ${n.category}</span>
      <span style="color:#555;font-size:11px">${n.source} · ${(n.published||'').slice(0,10)}</span>
    </div>
    <div style="font-size:18px;font-weight:600;color:#fff;margin-bottom:12px;line-height:1.3">${n.title}</div>
    ${n.location ? `<div style="color:#00f0ff;font-size:13px;margin-bottom:12px">📍 ${n.location}${n.country ? ' · ' + n.country : ''}</div>` : ''}
    <div style="color:#999;font-size:13px;line-height:1.5;margin-bottom:16px">${n.snippet}</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <button onclick="wnSpeakNews(wnData[${wnData.indexOf(n)}])" style="background:#1a1a2e;border:1px solid #2a2a4e;color:#00f0ff;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px">🔊 Ascolta</button>
      <a href="${n.url}" target="_blank" style="background:#00f0ff;color:#000;padding:8px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13px">Leggi →</a>
      ${n.lat ? `<button onclick="wnFlyTo(${n.lat},${n.lon})" style="background:#1a1a2e;border:1px solid #2a2a4e;color:#c0c0c0;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px">📍 Mappa</button>` : ''}
      <button onclick="wnCloseDetail()" style="background:transparent;border:1px solid #333;color:#888;padding:8px 16px;border-radius:6px;cursor:pointer;margin-left:auto;font-size:13px">✕ Chiudi</button>
    </div>
  `;
  document.getElementById('wn-detail').classList.remove('hidden');
}

function wnFlyTo(lat, lon) {
  if (wnMap && wnMap._container && wnMap._container.parentNode) {
    wnMap.flyTo([lat, lon], 5, { duration: 1.5 });
  } else if (wnGlobeRenderer) {
    const n = wnData.find(x => x.lat === lat && x.lon === lon);
    wnGlobeFlyTo(lat, lon, n);
  }
  wnCloseDetail();
}

function wnCloseDetail() {
  document.getElementById('wn-detail').classList.add('hidden');
}

function wnRefresh() {
  fetch('/api/worldnews?max=50')
    .then(r => r.json())
    .then(d => {
      wnLoadData(d);
      if (wnIs3D) wnInitGlobe();
    })
    .catch(e => console.error('WorldNews:', e));
}

/* 3D Globe (Three.js) */
function wnToggle3D() {
  wnIs3D = document.getElementById('wn-3d-toggle').checked;
  if (wnIs3D) {
    if (wnMap) { wnMap.remove(); wnMap = null; }
    document.getElementById('wn-map').innerHTML = '';
    document.getElementById('wn-map')._wnInited = false;
    wnInitGlobe();
  } else {
    if (wnGlobeRenderer) {
      wnGlobeRenderer.dispose();
      wnGlobeRenderer = null;
    }
    if (_wnAnimFrame) { cancelAnimationFrame(_wnAnimFrame); _wnAnimFrame = null; }
    wnGlobeScene = null;
    wnGlobeCamera = null;
    wnGlobeRenderer = null;
    document.getElementById('wn-map').innerHTML = '';
    wnInit();
  }
}

function wnGlobeFlyTo(lat, lon, newsItem) {
  if (!wnGlobeCamera || !wnGlobe) return;
  const phi = (90 - lat) * Math.PI / 180;
  const theta = (lon + 180) * Math.PI / 180;
  const r = 2.8;
  const target = new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  );

  // Stop auto-rotation
  const startRot = wnGlobe.earth.rotation.y;

  // Animate camera
  const startPos = wnGlobeCamera.position.clone();
  const duration = 1500;
  const startTime = performance.now();

  // Pause rotation
  const origAnimate = wnGlobe._animate;
  wnGlobe._paused = true;

  function flyStep(now) {
    const t = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    wnGlobeCamera.position.lerpVectors(startPos, target, ease);
    wnGlobeCamera.lookAt(0, 0, 0);
    if (t < 1) {
      requestAnimationFrame(flyStep);
    } else {
      wnGlobe._paused = false;
    }
  }
  requestAnimationFrame(flyStep);
}

function wnInitGlobe() {
  if (wnGlobeRenderer) return;
  const container = document.getElementById('wn-map');
  const w = container.clientWidth, h = container.clientHeight;
  if (w < 10) return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, w/h, 0.1, 1000);
  camera.position.set(0, 0, 4);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  const radius = 1.5;
  const geo = new THREE.SphereGeometry(radius, 64, 64);
  const tex = new THREE.TextureLoader().load('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg');
  const mat = new THREE.MeshPhongMaterial({ map: tex, specular: 0x222244, shininess: 15 });
  const earth = new THREE.Mesh(geo, mat);
  scene.add(earth);

  const ambient = new THREE.AmbientLight(0x222244, 0.5);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xffffff, 1.5);
  sun.position.set(5, 3, 5);
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0x4488ff, 0.5);
  rim.position.set(-3, -1, -2);
  scene.add(rim);

  /* Stars */
  const starGeo = new THREE.BufferGeometry();
  const starVerts = [];
  for (let i = 0; i < 2000; i++) {
    starVerts.push((Math.random() - 0.5) * 200);
    starVerts.push((Math.random() - 0.5) * 200);
    starVerts.push((Math.random() - 0.5) * 200);
  }
  starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starVerts, 3));
  const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.15 });
  scene.add(new THREE.Points(starGeo, starMat));

  /* Markers on globe — each mesh stores reference to its news item */
  const hasGeo = wnData.filter(n => n.lat);
  const markerGroup = new THREE.Group();
  const markerMeshes = [];
  hasGeo.forEach(n => {
    const phi = (90 - n.lat) * Math.PI / 180;
    const theta = (n.lon + 180) * Math.PI / 180;
    const x = -radius * Math.sin(phi) * Math.cos(theta);
    const y = radius * Math.cos(phi);
    const z = radius * Math.sin(phi) * Math.sin(theta);
    const color = new THREE.Color(CAT_COLORS[n.category] || '#888899');
    const pulse = new THREE.Mesh(
      new THREE.SphereGeometry(0.05, 10, 10),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 })
    );
    pulse.position.set(x, y, z);
    pulse.userData.newsItem = n;
    markerGroup.add(pulse);
    markerMeshes.push(pulse);
    /* glow ring */
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.06, 0.1, 16),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3, side: THREE.DoubleSide })
    );
    ring.position.set(x, y, z);
    ring.lookAt(0, 0, 0);
    ring.userData.newsItem = n;
    markerGroup.add(ring);
  });
  scene.add(markerGroup);

  wnGlobeScene = scene;
  wnGlobeCamera = camera;
  wnGlobeRenderer = renderer;
  wnGlobe = { scene, camera, renderer, earth, markerGroup, _paused: false, markerMeshes };

  /* Animation loop */
  let angle = 0;
  function animate() {
    if (!wnGlobeRenderer) return;
    if (!wnGlobe._paused) {
      angle += 0.002;
      earth.rotation.y = angle;
      markerGroup.rotation.y = angle;
      /* Pulse markers */
      const pulse = Math.sin(performance.now() / 300) * 0.15 + 0.85;
      markerMeshes.forEach(m => { m.material.opacity = pulse; });
    }
    renderer.render(scene, camera);
    _wnAnimFrame = requestAnimationFrame(animate);
  }
  animate();

  /* Click to pick news — improved with proper hit detection */
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  renderer.domElement.addEventListener('click', (e) => {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(markerGroup.children);
    if (intersects.length > 0) {
      const hit = intersects[0].object;
      const n = hit.userData.newsItem;
      if (n) wnSelectNews(n);
    }
  });

  window.addEventListener('resize', () => {
    if (!wnGlobeRenderer) return;
    const w2 = container.clientWidth, h2 = container.clientHeight;
    camera.aspect = w2 / h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2, h2);
  });
}

// Export to global scope
window.wnData = wnData;
window.wnInit = wnInit;
window.wnRefresh = wnRefresh;
window.wnIs3D = true;
window.wnShowDetail = wnShowDetail;
window.wnCloseDetail = wnCloseDetail;
window.wnFlyTo = wnFlyTo;
window.wnSelectNews = wnSelectNews;
window.wnSpeakNews = wnSpeakNews;

if (document.getElementById('worldnews-panel')?.classList.contains('open')) {
  setTimeout(wnInit, 200);
}