import type {
  AskResponse,
  CodeIntelligenceResult,
  CodeReviewResult,
  Conversation,
  ConversationSummary,
  DependencyGraph,
  RepositoryDetail,
  RepositorySummary,
  SearchResponse,
  SendMessageResponse,
  UploadResponse,
} from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

function getErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = payload.detail;
    if (typeof detail === 'string') return detail;
    if (typeof detail === 'object' && detail !== null && 'message' in detail && typeof detail.message === 'string') {
      return detail.message;
    }
  }
  return `Request failed with status ${status}.`;
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});

  if (!(options.body instanceof FormData) && options.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const payload = await response.text();
  let json: unknown = null;

  try {
    json = payload ? JSON.parse(payload) : null;
  } catch {
    json = null;
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(json, response.status));
  }

  if (payload.length === 0) {
    return undefined as T;
  }

  return json as T;
}

export const api = {
  async healthCheck(): Promise<{ status: string; service: string }> {
    return apiRequest('/health');
  },

  async listRepositories(): Promise<{ count: number; repositories: RepositorySummary[] }> {
    return apiRequest('/api/repositories');
  },

  async getRepository(repositoryId: string): Promise<RepositoryDetail> {
    return apiRequest(`/api/repositories/${encodeURIComponent(repositoryId)}`);
  },

  async uploadRepository(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return apiRequest('/api/repositories/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async searchRepository(repositoryId: string, query: string, topK = 5): Promise<SearchResponse> {
    return apiRequest('/api/repositories/search', {
      method: 'POST',
      body: JSON.stringify({ repository_id: repositoryId, query, top_k: topK }),
    });
  },

  async getDependencies(repositoryId: string): Promise<DependencyGraph> {
    return apiRequest(`/api/repositories/${encodeURIComponent(repositoryId)}/dependencies`);
  },

  async getCodeIntelligence(
    repositoryId: string,
    params: { query?: string; file_path?: string; symbol?: string },
  ): Promise<CodeIntelligenceResult> {
    const query = new URLSearchParams();
    if (params.query) query.set('query', params.query);
    if (params.file_path) query.set('file_path', params.file_path);
    if (params.symbol) query.set('symbol', params.symbol);
    const suffix = query.size > 0 ? `?${query.toString()}` : '';
    return apiRequest(
      `/api/repositories/${encodeURIComponent(repositoryId)}/intelligence${suffix}`,
    );
  },

  async reviewRepository(repositoryId: string): Promise<CodeReviewResult> {
    return apiRequest(`/api/repositories/${encodeURIComponent(repositoryId)}/review`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
  },

  async askQuestion(repositoryId: string, question: string, topK = 5): Promise<AskResponse> {
    return apiRequest('/api/repositories/ask', {
      method: 'POST',
      body: JSON.stringify({ repository_id: repositoryId, question, top_k: topK }),
    });
  },

  async listConversations(repositoryId: string): Promise<{ repository_id: string; conversations: ConversationSummary[] }> {
    return apiRequest(`/api/repositories/${encodeURIComponent(repositoryId)}/conversations`);
  },

  async createConversation(repositoryId: string, title?: string): Promise<ConversationSummary> {
    return apiRequest(`/api/repositories/${encodeURIComponent(repositoryId)}/conversations`, {
      method: 'POST',
      body: JSON.stringify(title ? { title } : {}),
    });
  },

  async getConversation(repositoryId: string, conversationId: string): Promise<Conversation> {
    return apiRequest(
      `/api/repositories/${encodeURIComponent(repositoryId)}/conversations/${encodeURIComponent(conversationId)}`,
    );
  },

  async sendConversationMessage(
    repositoryId: string,
    conversationId: string,
    message: string,
  ): Promise<SendMessageResponse> {
    return apiRequest(
      `/api/repositories/${encodeURIComponent(repositoryId)}/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ message }),
      },
    );
  },
};
