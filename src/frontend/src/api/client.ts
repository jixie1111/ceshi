export type Chapter = {
  chapter_id: string;
  title: string;
  page_start: number;
  page_end: number;
  content: string;
  char_count: number;
};

export type Textbook = {
  textbook_id: string;
  filename: string;
  title: string;
  format: string;
  file_size: number;
  total_pages: number;
  total_chars: number;
  status: '解析中' | '已完成' | '失败';
  error?: string;
  chapters: Chapter[];
};

export type KnowledgeNode = {
  id: string;
  name: string;
  definition: string;
  category: string;
  chapter: string;
  page: number;
  textbook_id: string;
  textbook_title: string;
  source: string;
  frequency: number;
  aliases: string[];
  importance: number;
};

export type KnowledgeEdge = {
  source: string;
  target: string;
  relation_type: 'prerequisite' | 'parallel' | 'contains' | 'applies_to';
  description: string;
  weight: number;
};

export type KnowledgeGraph = { textbook_id: string; nodes: KnowledgeNode[]; edges: KnowledgeEdge[]; created_at?: string };
export type Decision = {
  decision_id: string;
  action: 'merge' | 'keep' | 'remove' | 'split';
  affected_nodes: string[];
  result_node?: string;
  reason: string;
  confidence: number;
  teacher_locked: boolean;
};
export type IntegratedGraph = { nodes: KnowledgeNode[]; edges: KnowledgeEdge[]; decisions: Decision[]; stats: Record<string, any> };
export type RagStatus = { indexed_books: number; chunk_count: number; embedding_backend: string; last_indexed_at?: string };
export type RagAnswer = {
  answer: string;
  citations: { textbook: string; chapter: string; page: number; relevance_score: number; chunk_id: string }[];
  source_chunks: { chunk_id: string; text: string; textbook: string; chapter: string; page: number; relevance_score: number }[];
  latency_ms: number;
};

const API_BASE = import.meta.env.VITE_API_BASE || '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listBooks: () => request<Textbook[]>('/api/textbooks'),
  uploadBooks: async (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    return request<Textbook[]>('/api/textbooks/upload', { method: 'POST', body: form });
  },
  deleteBook: (id: string) => request('/api/textbooks/' + id, { method: 'DELETE' }),
  buildGraph: (id: string) => request<KnowledgeGraph>(`/api/graph/${id}/build`, { method: 'POST' }),
  getGraph: (id: string) => request<KnowledgeGraph>(`/api/graph/${id}`),
  runIntegration: () => request<IntegratedGraph>('/api/integration/run', { method: 'POST' }),
  getIntegration: () => request<IntegratedGraph>('/api/integration'),
  ragIndex: () => request<RagStatus>('/api/rag/index', { method: 'POST' }),
  ragStatus: () => request<RagStatus>('/api/rag/status'),
  ragQuery: (question: string, topK = 5) => request<RagAnswer>('/api/rag/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, top_k: topK }) }),
  sendDialogue: (message: string) => request('/api/dialogue/message', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }) }),
  history: () => request<{ role: string; content: string }[]>('/api/dialogue/history'),
  generateReport: () => request<{ message: string; data: { markdown: string } }>('/api/report/generate', { method: 'POST' }),
  runBenchmark: () => request<any>('/api/benchmark/run', { method: 'POST' }),
  loadDemo: () => request<Textbook[]>('/api/demo/load', { method: 'POST' })
};
