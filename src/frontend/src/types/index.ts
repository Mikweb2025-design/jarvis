export interface ApiStatus {
  status: string;
  model: string;
  voice: string;
  version: string;
  rag: { docs: number; chunks: number; model: string };
  time: string;
}

export interface ChatResponse {
  reply: string;
  actions: string[];
  elapsed: number;
  model: string;
  fast: boolean;
}

export interface ToolResult {
  result: string;
  tool: string;
}

export interface MemoryItem {
  id: number;
  content: string;
  category: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface MemoriesResponse {
  memories: MemoryItem[];
  total: number;
}

export interface SystemInfo {
  cpu_usage: string;
  cpu_cores: string;
  ram_total: string;
  ram_free: string;
  disk_total: string;
  disk_used: string;
  disk_pct: string;
  battery: string;
  uptime: string;
  load_avg: string;
  processes: string;
}

export interface RagStats {
  documents: number;
  chunks: number;
  model: string;
}

export interface SSEMessage {
  type: 'reply' | 'actions' | 'audio_chunk' | 'error' | 'done' | 'progress' | 'complete';
  data?: string;
  format?: string;
  elapsed?: number;
  model?: string;
  current?: number;
  total?: number;
  percent?: number;
  file?: string;
  status?: string;
  result?: any;
}

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, any>;
}
