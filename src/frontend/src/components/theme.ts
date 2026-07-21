import { byId, byAll, bySel } from '../utils/dom';

const THEMES = ['cyberpunk', 'holo', 'sunset', 'matrix', 'crystal'] as const;
type Theme = typeof THEMES[number];

export function initTheme() {
  const saved = (localStorage.getItem('jarvis-theme') as Theme) || 'cyberpunk';
  applyTheme(saved);

  byAll('.theme-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const t = (btn as HTMLElement).dataset.theme as Theme;
      selectTheme(t);
    });
  });
}

function selectTheme(theme: Theme) {
  byAll('.theme-btn').forEach((c) => c.classList.remove('active'));
  const btn = bySel(`.theme-btn[data-theme="${theme}"]`);
  btn?.classList.add('active');
  applyTheme(theme);
  localStorage.setItem('jarvis-theme', theme);
  spawnParticles(theme);
  triggerGlitch();

  const hst = byId('holo-status');
  if (hst) {
    hst.textContent = `✦ TEMPLATE: ${theme.toUpperCase()} ✦`;
    hst.style.opacity = '1';
    setTimeout(() => { hst.style.opacity = '0.3'; }, 1500);
  }
}

function applyTheme(theme: Theme) {
  document.documentElement.className = `theme-${theme}`;
  const overlay = byId('holo-overlay');
  overlay?.classList.add('active');
}

function spawnParticles(theme: Theme) {
  const el = byId('particles');
  if (!el) return;
  el.innerHTML = '';
  const confs: Record<string, { count: number; colors: string[]; sz: number[]; dur: number[]; op: number[] }> = {
    cyberpunk: { count: 15, colors: ['var(--cy)', 'var(--pk)', 'var(--pp)'], sz: [1, 3], dur: [6, 12], op: [0.2, 0.4] },
    holo: { count: 20, colors: ['rgba(74,216,255,0.6)', 'rgba(126,200,255,0.4)', 'rgba(255,255,255,0.3)'], sz: [1, 4], dur: [8, 16], op: [0.15, 0.35] },
    sunset: { count: 18, colors: ['var(--cy)', 'var(--pk)', 'var(--am)'], sz: [1, 3], dur: [7, 14], op: [0.2, 0.4] },
    matrix: { count: 25, colors: ['rgba(0,255,65,0.5)'], sz: [1, 2], dur: [5, 10], op: [0.5, 0.8] },
    crystal: { count: 22, colors: ['rgba(136,221,255,0.5)', 'rgba(255,255,255,0.3)', 'rgba(200,136,255,0.4)'], sz: [1, 4], dur: [10, 20], op: [0.15, 0.3] },
  };
  const c = confs[theme] || confs.cyberpunk;
  for (let i = 0; i < c.count; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    const clr = c.colors[Math.floor(Math.random() * c.colors.length)];
    const sz = c.sz[0] + Math.random() * (c.sz[1] - c.sz[0]);
    const dur = c.dur[0] + Math.random() * (c.dur[1] - c.dur[0]);
    const op = c.op[0] + Math.random() * (c.op[1] - c.op[0]);
    const px1 = -50 + Math.random() * 100;
    const px2 = -30 + Math.random() * 60;
    p.style.cssText = `--sz:${sz}px;--dur:${dur}s;--del:${Math.random() * 5}s;--op:${op};--px:${px1}px;--px2:${px2}px;background:${clr};box-shadow:0 0 6px ${clr};left:${Math.random() * 100}%;bottom:-10px`;
    el.appendChild(p);
  }
}

function triggerGlitch() {
  let bar = bySel('.glitch-bar') as HTMLElement | null;
  if (!bar) {
    bar = document.createElement('div');
    bar.className = 'glitch-bar';
    bar.style.cssText = 'position:fixed;height:2px;background:var(--pk);opacity:0;z-index:9995;pointer-events:none';
    document.body.appendChild(bar);
  }
  bar.style.top = `${Math.random() * 100}%`;
  bar.style.left = '0';
  bar.style.width = `${20 + Math.random() * 40}%`;
  bar.style.animation = 'none';
  void bar.offsetWidth;
  bar.style.animation = 'glitchBar 0.3s ease forwards';
}
