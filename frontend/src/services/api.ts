import type {
  AnnotationCollection,
  ChatEvent,
  DocumentReadResult,
  HistoryResponse,
  KnowledgeDocument,
  KnowledgeStats,
  KnowledgeSummary,
  MarketPricesResponse,
  SessionsResponse,
  Task,
  TasksResponse,
  UploadResponse,
} from '../types';

// Singleton API client bound to VITE_API_URL (Cloudflare tunnel or local).
class ChatAPI {
  private static get baseUrl(): string {
    return import.meta.env.VITE_API_URL || 'http://localhost:8000';
  }

  private static getHeaders(withJson = true): Record<string, string> {
    const headers: Record<string, string> = {};
    if (withJson) headers['Content-Type'] = 'application/json';
    const apiKey = import.meta.env.VITE_API_KEY;
    if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;
    return headers;
  }

  private static async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, init);
    if (!res.ok) {
      if (res.status === 401) {
        throw new Error('Unauthorized — check VITE_API_KEY matches the backend API_KEY');
      }
      throw new Error(`Request failed (${res.status})`);
    }
    return res.json() as Promise<T>;
  }

  static async streamChat(
    message: string,
    sessionId: string,
    onEvent: (event: ChatEvent) => void,
    attachmentId?: string,
  ): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/api/chat/stream`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({
          message,
          session_id: sessionId,
          interaction_mode: 'web_chat',
          attachment_id: attachmentId ?? '',
        }),
      });

      if (!response.ok) {
        throw new Error(response.status === 401
          ? 'Unauthorized — check VITE_API_KEY'
          : `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error('No response body');

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6);
          if (dataStr === '[DONE]') {
            onEvent({ type: 'end' });
            continue;
          }
          try {
            onEvent(JSON.parse(dataStr) as ChatEvent);
          } catch {
            // Ignore malformed SSE frames.
          }
        }
      }
    } catch (error) {
      onEvent({ type: 'error', message: error instanceof Error ? error.message : 'Connection failed' });
    }
  }

  static fetchSessions(): Promise<SessionsResponse> {
    return this.request<SessionsResponse>('/api/chat/sessions', { headers: this.getHeaders() });
  }

  static fetchChatHistory(sessionId: string): Promise<HistoryResponse> {
    return this.request<HistoryResponse>(`/api/chat/history/${encodeURIComponent(sessionId)}`, {
      headers: this.getHeaders(),
    });
  }

  static fetchTelemetry(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/api/system/telemetry', { headers: this.getHeaders() });
  }

  static fetchMarketPrices(): Promise<MarketPricesResponse> {
    return this.request<MarketPricesResponse>('/api/research/market-prices', { headers: this.getHeaders() });
  }

  static fetchTasks(): Promise<TasksResponse> {
    return this.request<TasksResponse>('/tasks', { headers: this.getHeaders() });
  }

  static createTask(description: string, assignee?: string): Promise<Task> {
    return this.request<Task>('/tasks', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ description, assignee }),
    });
  }

  static submitProcurement(item: string, cost: number): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/procurement', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ item, cost }),
    });
  }

  static uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request<UploadResponse>('/api/documents/upload', {
      method: 'POST',
      headers: this.getHeaders(false),
      body: formData,
    });
  }

  // Knowledge Base
  static fetchKnowledgeDocuments(): Promise<{ status: string; documents: KnowledgeDocument[] }> {
    return this.request('/api/knowledge/documents', { headers: this.getHeaders() });
  }

  static fetchKnowledgeStats(): Promise<{ status: string; stats: KnowledgeStats }> {
    return this.request('/api/knowledge/statistics', { headers: this.getHeaders() });
  }

  static searchKnowledge(query: string, category?: string): Promise<{ status: string; results: Array<{ document: KnowledgeDocument; score: number }> }> {
    return this.request('/api/knowledge/search', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ query, category }),
    });
  }

  static fetchRecentDocuments(limit = 20): Promise<{ status: string; documents: KnowledgeDocument[] }> {
    return this.request(`/api/knowledge/recent?limit=${limit}`, { headers: this.getHeaders() });
  }

  static readDocument(docId: string): Promise<{ status: string; result: DocumentReadResult }> {
    return this.request('/api/knowledge/read', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ doc_id: docId }),
    });
  }

  static understandDocument(docId: string): Promise<{ status: string; result: DocumentReadResult }> {
    return this.request('/api/knowledge/understand', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ doc_id: docId }),
    });
  }

  static fetchKnowledgeSummary(): Promise<{ status: string; summary: KnowledgeSummary }> {
    return this.request('/api/knowledge/summary', { headers: this.getHeaders() });
  }

  // Document Preview
  static listDocuments(folder?: string): Promise<{ status: string; documents: Array<{ name: string; type: string; path: string; size?: number; mime?: string; children?: unknown[] }> }> {
    const params = folder ? `?folder=${encodeURIComponent(folder)}` : '';
    return this.request(`/api/documents/list${params}`, { headers: this.getHeaders() });
  }

  static getDocumentPreviewUrl(filePath: string): string {
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    return `${base}/api/documents/preview/${encodeURIComponent(filePath)}?api_key=${this.getApiKey()}`;
  }

  private static getApiKey(): string {
    try {
      const stored = localStorage.getItem('aios_api_key');
      return stored || '';
    } catch {
      return '';
    }
  }

  // Satellite
  static fetchAnnotations(imageId: string): Promise<{ status: string; annotations: AnnotationCollection }> {
    return this.request(`/api/satellite/annotations/${encodeURIComponent(imageId)}`, { headers: this.getHeaders() });
  }

  static analyzeSpectral(bands: Record<string, number[]>): Promise<{ status: string; results: unknown }> {
    return this.request('/api/satellite/spectral', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ exploration_assessment: true, bands }),
    });
  }

  static fullSatelliteAnalysis(bands: Record<string, number[]>, dem?: number[][]): Promise<{ status: string; results: unknown }> {
    return this.request('/api/satellite/full-analysis', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ bands, dem }),
    });
  }

  static generateReport(type: string, data: Record<string, unknown>): Promise<{ status: string; report: string }> {
    return this.request('/api/satellite/report', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ type, ...data }),
    });
  }
}

export { ChatAPI };
