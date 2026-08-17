// ------------------------------------------------------------
// Shared domain types for the AI OS Control Center
// ------------------------------------------------------------

export type ChatEvent =
  | { type: 'start'; session_id: string }
  | { type: 'message'; content: string }
  | { type: 'tool_call'; name: string; args: Record<string, unknown> }
  | { type: 'error'; message: string }
  | { type: 'end' };

export interface ChatSession {
  id: string;
  title: string;
  time: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: Array<{ name: string; args: Record<string, unknown> }>;
}

export interface SystemTelemetry {
  cpu_percent: number;
  memory_gb: number;
  vector_latency_ms: number;
  network_gbps: number;
  active_tasks: number;
  llm_model: string;
  llm_status: string;
  memory_core_status: string;
}

export interface MetalPrice {
  price: number;
  unit: string;
  change_24h?: number;
  change_7d?: number;
}

export interface MarketSummary {
  timestamp?: string;
  metals?: Partial<Record<string, MetalPrice>>;
  gemstones?: Partial<Record<string, MetalPrice>>;
  gold_silver_ratio?: number | null;
  alerts?: string[];
}

export interface MarketPricesResponse {
  prices?: unknown[];
  summary?: MarketSummary | null;
}

export interface GoldPriceResponse {
  gold?: MetalPrice;
  silver?: MetalPrice;
}

export interface Task {
  id: string;
  description: string;
  assignee?: string | null;
  status: 'pending' | 'running' | 'completed' | string;
  created_at?: string;
}

export interface TasksResponse {
  tasks: Task[];
}

export interface SessionsResponse {
  sessions: ChatSession[];
}

export interface HistoryResponse {
  messages: ChatMessage[];
}

export interface UploadResponse {
  status: string;
  filename: string;
  file_id: string;
  chars: number;
  text_preview: string;
  chunks_indexed: number;
}

export type ModuleId = 'chat' | 'intel' | 'finance' | 'tasks' | 'knowledge';

export interface KnowledgeDocument {
  doc_id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  title: string;
  description: string;
  tags: string[];
  category: string;
  content_text: string;
  content_summary: string;
  source: string;
  session_id: string;
  word_count: number;
  page_count: number;
  mining_relevance: number;
  created_at: string;
  updated_at: string;
  indexing_status: string;
}

export interface KnowledgeStats {
  total_documents: number;
  total_size_bytes: number;
  by_type: Record<string, number>;
  by_category: Record<string, number>;
  recent_uploads: KnowledgeDocument[];
  total_words: number;
}

export interface KnowledgeSummary {
  total_documents: number;
  total_size_mb: number;
  categories: Record<string, number>;
  file_types: Record<string, number>;
  recent_documents: KnowledgeDocument[];
  top_topics: string[];
  total_words: number;
}

export interface DocumentReadResult {
  doc_id: string;
  filename: string;
  file_type: string;
  content_text: string;
  word_count: number;
  page_count: number;
  sections: Array<{ heading: string; content: string; level: number }>;
  key_findings: string[];
  summary: string;
  key_terms: string[];
  mining_relevance: number;
  entities: {
    minerals: string[];
    equipment: string[];
    locations: string[];
    chemicals: string[];
    processes: string[];
  };
}

export interface SatelliteAnnotation {
  type: 'Feature';
  geometry: { type: string; coordinates: unknown };
  properties: {
    annotation_id: string;
    annotation_type: string;
    timestamp: string;
    author: string;
    style: Record<string, unknown>;
    [key: string]: unknown;
  };
}

export interface AnnotationCollection {
  type: 'FeatureCollection';
  features: SatelliteAnnotation[];
}
