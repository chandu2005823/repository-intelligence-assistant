export interface RepositorySummary {
  repository_id: string;
  repository_name: string;
  file_count: number;
  total_size_bytes: number;
  languages: Record<string, number>;
  directories: string[];
  important_files: string[];
  indexed_chunk_count: number;
  indexing_status: "indexed" | "missing";
  created_at?: number;
}

export interface RepositoryDetail extends RepositorySummary {
  analysis?: {
    python_file_count?: number;
    total_functions?: number;
    total_classes?: number;
    total_lines?: number;
    files_with_syntax_errors?: number;
    files?: Array<{
      path: string;
      functions: Array<{ name: string; line: number; async?: boolean }>;
      classes: Array<{ name: string; line: number }>;
      imports: Array<string | { module: string | null; names: string[]; level: number }>;
      total_lines: number;
      syntax_error?: { message: string; line: number | null } | null;
    }>;
  };
}

export interface SearchResult {
  file_path: string;
  chunk_type: string;
  symbol_name?: string | null;
  start_line: number;
  end_line: number;
  content: string;
  distance?: number;
  hybrid_score?: number;
}

export interface SearchResponse {
  repository_id: string;
  query: string;
  result_count: number;
  results: SearchResult[];
}

export interface DependencyNode {
  id: string;
  path: string;
  label: string;
  language: string;
}

export interface DependencyEdge {
  source: string;
  target: string;
  kind: string;
  line?: number;
  module?: string;
}

export interface UnresolvedDependency {
  file_path: string;
  module: string;
}

export interface DependencyGraph {
  repository_id: string;
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  unresolved: UnresolvedDependency[];
}

export interface CodeDefinition {
  name: string;
  kind: string;
  file_path: string;
  line: number;
  end_line?: number;
}

export interface CodeCall {
  caller: string;
  callee: string;
  file_path: string;
  line: number;
  resolved: boolean;
}

export interface CodeIntelligenceResult {
  repository_id: string;
  definitions: CodeDefinition[];
  calls: CodeCall[];
  impact: {
    files: string[];
    functions: string[];
  };
  unresolved: Array<Record<string, unknown>>;
}

export interface CodeReviewFinding {
  severity: 'Critical' | 'High' | 'Medium' | 'Low' | string;
  confidence?: string | number;
  file_path: string;
  start_line: number;
  end_line: number;
  title: string;
  description: string;
  suggestion: string;
  status?: string;
}

export interface CodeReviewResult {
  repository_id: string;
  findings: CodeReviewFinding[];
  summary?: string;
  ai_status?: string;
  ai_explanation?: string | null;
  ai_error?: string | null;
  ai_sources?: ConversationSource[];
}

export interface AskResponse {
  repository_id: string;
  question: string;
  answer: string;
  source_count: number;
  sources: Array<{
    file_path: string;
    chunk_type: string;
    symbol_name?: string | null;
    start_line?: number | null;
    end_line?: number | null;
    distance?: number;
  }>;
}

export interface UploadResponse {
  repository_id: string;
  status: string;
  summary: { repository_name: string; file_count: number; total_size_bytes: number; languages: Record<string, number> };
  code_analysis: { python_file_count?: number; total_functions?: number; total_classes?: number; total_lines?: number; files_with_syntax_errors?: number };
  chunking: {
    python_files_processed: number;
    chunk_count: number;
    chunks: Array<Record<string, unknown>>;
  };
  indexing: {
    repository_id: string;
    indexed_chunks: number;
  };
}

export interface ConversationSummary {
  id: string;
  repository_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationSource {
  file_path: string;
  chunk_type?: string;
  symbol_name?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  distance?: number | null;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  metadata: {
    repository_id?: string;
    resolved_question?: string;
    source_count?: number;
    sources?: ConversationSource[];
  };
}

export interface Conversation extends ConversationSummary {
  messages: ConversationMessage[];
}

export interface SendMessageResponse {
  repository_id: string;
  conversation_id: string;
  user_message: ConversationMessage;
  assistant_message: ConversationMessage;
  resolved_question: string;
}
