export interface DocumentItem {
  id: string
  filename: string
  original_filename?: string
  file_type: string
  file_size_bytes: number
  status: string
  chunk_count: number
  token_count: number
  page_count?: number | null
  error_message?: string | null
  created_at: string
}

export interface SourceChunk {
  content: string
  chunk_index: number
  page_number?: number | null
  similarity_score: number
}

export interface MultiSourceChunk extends SourceChunk {
  document_id: string
  document_name: string
  rerank_score?: number | null
}

export interface QueryAnswer {
  question: string
  answer: string
  sources: SourceChunk[]
  model_used: string
  tokens_used: number
  latency_ms: number
  from_cache: boolean
  reranked: boolean
  query_id: string
}

export interface MultiQueryAnswer extends Omit<QueryAnswer, 'sources'> {
  sources: MultiSourceChunk[]
  documents_queried: Array<{ id: string; name: string }>
}

export interface SentimentAnalysis {
  label: string
  score: number
  confidence: number
  tone: string
  explanation: string
}

export interface DocumentAnalysis {
  summary?: string | null
  keywords?: string[] | null
  sentiment?: SentimentAnalysis | null
  entities?: Record<string, string[]> | null
}

export interface QueryHistoryItem {
  id: string
  question: string
  answer: string
  tokens_used: number
  latency_ms?: number | null
  from_cache: boolean
}

export interface BenchmarkMetric {
  name: string
  baseline: number
  reranked: number
  delta: number
  description: string
}

export interface BenchmarkCaseResult {
  case_id: string
  question: string
  category: string
  is_negative: boolean
  baseline: BenchmarkRunResult
  reranked: BenchmarkRunResult
}

interface BenchmarkRunResult {
  precision_at_k: number
  recall_at_k: number
  mrr: number
  groundedness: number
  latency_sec: number
  answer_preview: string
}

export interface BenchmarkReport {
  timestamp: string
  mode: string
  methodology_version: string
  results_validated: boolean
  evaluated_models: {
    chat_model: string
    embedding_model: string
  }
  parameters: {
    k: number
    candidates: number
    enable_rerank: boolean
    cases_evaluated: number
  }
  stats: {
    llm_calls_made: number
    baseline_avg_latency_sec: number
    reranked_avg_latency_sec: number
  }
  total_cases: number
  metrics: BenchmarkMetric[]
  details: BenchmarkCaseResult[]
}
