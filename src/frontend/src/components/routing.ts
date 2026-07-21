import { byAll } from '../utils/dom';

type PageHandler = () => void;

const pageHandlers: Record<string, PageHandler> = {};

export function registerPage(page: string, handler: PageHandler) {
  pageHandlers[page] = handler;
}

function handleRoute() {
  const hash = window.location.hash.slice(1) || 'chat';
  document.documentElement.setAttribute('data-page', hash);

  byAll('#top-nav .nav-link').forEach((a) => {
    a.classList.toggle('active', (a as HTMLElement).dataset.pageLink === hash);
  });

  // Close overlays when switching
  if (hash !== 'worldnews' && typeof (window as any).closeWorldNews === 'function') {
    (window as any).closeWorldNews();
  }
  if (hash !== 'chat') {
    ['closeRag', 'closeMem', 'closeTrends', 'closeGit', 'closeGoals', 'closeSettings', 'closeVision', 'closePresentation', 'closeImageGen', 'closeMusicGen', 'closeKG'].forEach((fn) => {
      if (typeof (window as any)[fn] === 'function') (window as any)[fn]();
    });
  }

  // Open page panels
  const pageMap: Record<string, string> = {
    memory: 'openMem',
    rag: 'openRag',
    trends: 'openTrends',
    worldnews: 'openWorldNews',
    git: 'openGit',
    goals: 'openGoals',
    settings: 'openSettings',
    vision: 'openVision',
    presentation: 'openPresentation',
    imagegen: 'openImageGen',
    musicgen: 'openMusicGen',
    knowledgegraph: 'openKG',
  };

  const fn = pageMap[hash];
  if (fn && typeof (window as any)[fn] === 'function') {
    setTimeout(() => (window as any)[fn](), 400);
  }

  if (pageHandlers[hash]) {
    setTimeout(pageHandlers[hash], 400);
  }
}

export function initRouting() {
  window.addEventListener('hashchange', handleRoute);
  if (!window.location.hash) history.replaceState(null, '', '#chat');
  setTimeout(handleRoute, 500);
}
