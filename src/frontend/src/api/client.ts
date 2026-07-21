import type {
  ApiStatus,
  ChatResponse,
  ToolResult,
  MemoriesResponse,
  SystemInfo,
  RagStats,
  SSEMessage,
} from '../types';

const BASE = window.location.origin;

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers as Record<string, string> },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Status
  status: () => request<ApiStatus>('/api/status'),
  sysinfo: () => request<SystemInfo>('/api/sysinfo/detailed'),

  // Chat
  chat: (message: string, model?: string, temperature?: number) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, model, temperature }),
    }),

  chatStreamFetch: async function* (message: string, voice?: string, language?: string, speed?: number): AsyncGenerator<SSEMessage> {
    const body = voice
      ? JSON.stringify({ message, voice, language: language || 'italian', speed: speed || 1.0 })
      : JSON.stringify({ message });

    const res = await fetch(`${BASE}/${voice ? 'api/chat/voice' : 'api/chat/stream'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });

    if (!res.ok) throw new Error(`SSE error: ${res.status}`);

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6)) as SSEMessage;
            yield data;
          } catch { /* skip malformed */ }
        }
      }
    }
  },

  // Tool
  tool: (name: string, args: Record<string, any> = {}) =>
    request<ToolResult>('/api/tool', {
      method: 'POST',
      body: JSON.stringify({ name, args }),
    }),

  // Memory
  memoryAll: () => request<MemoriesResponse>('/api/memory/all'),
  memoryRemember: (content: string, category = 'fact', tags: string[] = []) =>
    request('/api/memory/remember', {
      method: 'POST',
      body: JSON.stringify({ content, category, tags }),
    }),
  memoryDelete: (id: number) =>
    request('/api/memory/delete', {
      method: 'POST',
      body: JSON.stringify({ id }),
    }),
  memoryUpdate: (id: number, content: string) =>
    request('/api/memory/update', {
      method: 'POST',
      body: JSON.stringify({ id, content }),
    }),
  memorySearch: (query: string) =>
    request('/api/memory/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),

  // RAG
  ragStats: () => request<RagStats>('/api/rag/stats'),
  ragList: () => request('/api/rag/list'),
  ragSearch: (query: string, limit = 5) =>
    request('/api/rag/search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    }),

  // TTS
  tts: async (text: string, voice = 'vivian', language = 'italian'): Promise<Blob> => {
    const res = await fetch(`${BASE}/api/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice, language }),
    });
    if (!res.ok) throw new Error(`TTS error: ${res.status}`);
    return res.blob();
  },

  // Config
  configUpdate: (config: Record<string, any>) =>
    request('/api/config/update', {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  // Translate
  translate: (text: string, target = 'italian', source = 'english') =>
    request('/api/translate', {
      method: 'POST',
      body: JSON.stringify({ text, target, source }),
    }),

  // Web search
  webSearch: (query: string) =>
    request('/api/web/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),

  // Git
  gitStatus: () => request('/api/git/status'),
  gitLog: () => request('/api/git/log'),
  gitBranches: () => request('/api/git/branches'),

  // Calendar
  calendarToday: () => request('/api/calendar/today'),

  // Mail
  mailUnread: () => request('/api/mail/unread'),
  mailRecent: () => request('/api/mail/recent'),

  // World News
  worldNews: (max = 30) => request(`/api/worldnews?max=${max}`),

  // Trends
  trends: (category = 'technology', region = 'wt', maxResults = 10) =>
    request(`/api/trends?category=${category}&region=${region}&max_results=${maxResults}`),

  // Evolution
  evolutionStatus: () => request('/api/evolution/status'),
  evolutionHeal: () => request('/api/evolution/heal'),

  // Image Generation
  imageGen: (prompt: string, model = 'black-forest-labs/FLUX.1-schnell', size = '1024x1024', n = 1) =>
    request('/api/imagegen/generate', {
      method: 'POST',
      body: JSON.stringify({ prompt, model, size, n }),
    }),

  imageGenModels: () => request('/api/imagegen/models'),

  // Music Generation
  musicGen: (prompt = '', genre = 'electronic', duration = 30, temperature = 1.0) =>
    request('/api/musicgen/generate', {
      method: 'POST',
      body: JSON.stringify({ prompt, genre, duration, temperature }),
    }),

  musicGenGenres: () => request('/api/musicgen/genres'),

  // Knowledge Graph
  kgAnalyze: (path = '') =>
    request('/api/kg/analyze', {
      method: 'POST',
      body: JSON.stringify({ path }),
    }),

  kgSymbols: (path = '') =>
    request('/api/kg/symbols', {
      method: 'POST',
      body: JSON.stringify({ path }),
    }),

  kgGraph: (path = '') =>
    request('/api/kg/graph', {
      method: 'POST',
      body: JSON.stringify({ path }),
    }),

  kgSearch: (query: string, path = '') =>
    request('/api/kg/search', {
      method: 'POST',
      body: JSON.stringify({ query, path }),
    }),

  kgStatus: () => request('/api/kg/status'),

  // Reset
  reset: () => request('/api/reset', { method: 'POST' }),
};
