import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from 'react';

import AssistantAnswer from './components/AssistantAnswer';
import { CodeIntelligencePanel, CodeReviewPanel, DependencyExplorer } from './components/FeaturePanels';
import { api } from './services/api';
import type {
  Conversation,
  ConversationSummary,
  RepositoryDetail,
  RepositorySummary,
  SearchResult,
  UploadResponse,
} from './types';

const formatBytes = (value: number) => {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
};

const formatLanguageSummary = (languages: Record<string, number>) => Object.entries(languages)
  .map(([language, count]) => `${language}: ${count}`)
  .join(' • ');

const formatTimestamp = (value?: string) => {
  if (!value) return 'Time unavailable';
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? 'Time unavailable' : timestamp.toLocaleString();
};

const conversationStorageKey = (repositoryId: string) => `selectedConversationId:${repositoryId}`;

const featureSections = [
  { id: 'search', label: 'Repository Search' },
  { id: 'assistant', label: 'AI Assistant' },
  { id: 'dependencies', label: 'Dependency Explorer' },
  { id: 'intelligence', label: 'Code Intelligence' },
  { id: 'review', label: 'Code Review' },
] as const;

function App() {
  const [activeFeature, setActiveFeature] = useState<(typeof featureSections)[number]['id']>('assistant');
  const [repositories, setRepositories] = useState<RepositorySummary[]>([]);
  const [repositoriesLoaded, setRepositoriesLoaded] = useState(false);
  const [selectedRepositoryId, setSelectedRepositoryId] = useState(
    () => window.localStorage.getItem('selectedRepositoryId') ?? '',
  );
  const selectedRepositoryIdRef = useRef(selectedRepositoryId);
  selectedRepositoryIdRef.current = selectedRepositoryId;
  const [repositoryDetail, setRepositoryDetail] = useState<RepositoryDetail | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('Find the function that analyzes a repository.');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [manualRepositoryId, setManualRepositoryId] = useState('');
  const [loadingManualRepository, setLoadingManualRepository] = useState(false);

  const [selectedConversationId, setSelectedConversationId] = useState('');
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      try {
        const payload = await api.listRepositories();
        if (!active) return;
        setRepositories(payload.repositories);
        setSelectedRepositoryId((currentId) => {
          if (payload.repositories.some((repo) => repo.repository_id === currentId)) return currentId;
          return payload.repositories[0]?.repository_id ?? '';
        });
        setRepositoriesLoaded(true);
      } catch (loadError) {
        if (active) {
          setSelectedRepositoryId('');
          setRepositoriesLoaded(true);
          setError(loadError instanceof Error ? loadError.message : 'Unable to load repositories.');
        }
      }
    };

    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!repositoriesLoaded) return;
    if (selectedRepositoryId) window.localStorage.setItem('selectedRepositoryId', selectedRepositoryId);
    else window.localStorage.removeItem('selectedRepositoryId');

    let active = true;
    setRepositoryDetail(null);
    setSearchResults([]);
    setSelectedConversationId('');
    setConversation(null);

    if (!selectedRepositoryId) return () => {
      active = false;
    };

    void api.getRepository(selectedRepositoryId)
      .then((detail) => {
        if (active) setRepositoryDetail(detail);
      })
      .catch((detailError: unknown) => {
        if (active) setError(detailError instanceof Error ? detailError.message : 'Unable to load repository details.');
      });

    void api.listConversations(selectedRepositoryId)
      .then((payload) => {
        if (active) {
          const savedId = window.localStorage.getItem(conversationStorageKey(selectedRepositoryId));
          const selectedId = savedId && payload.conversations.some((item) => item.id === savedId)
            ? savedId
            : payload.conversations[0]?.id ?? '';
          setSelectedConversationId(selectedId);
        }
      })
      .catch((listError: unknown) => {
        if (active) setError(listError instanceof Error ? listError.message : 'Unable to load conversations.');
      });

    return () => {
      active = false;
    };
  }, [repositoriesLoaded, selectedRepositoryId]);

  useEffect(() => {
    if (selectedRepositoryId && selectedConversationId) {
      window.localStorage.setItem(conversationStorageKey(selectedRepositoryId), selectedConversationId);
    }
  }, [selectedRepositoryId, selectedConversationId]);

  useEffect(() => {
    if (!selectedRepositoryId || !selectedConversationId) {
      setConversation(null);
      setConversationLoading(false);
      return;
    }

    let active = true;
    setConversation(null);
    setConversationLoading(true);
    void api.getConversation(selectedRepositoryId, selectedConversationId)
      .then((record) => {
        if (active) setConversation(record);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load this conversation.');
          setSelectedConversationId('');
        }
      })
      .finally(() => {
        if (active) setConversationLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRepositoryId, selectedConversationId]);

  const handleFileSelection = (event: ChangeEvent<HTMLInputElement>) => {
    setSelectedFile(event.target.files?.[0] ?? null);
    setError(null);
  };

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setError('Select a ZIP file before uploading.');
      return;
    }
    if (!selectedFile.name.toLowerCase().endsWith('.zip')) {
      setError('Only ZIP archives are supported.');
      return;
    }
    if (selectedFile.size > 1024 * 1024 * 1024) {
      setError('The uploaded ZIP exceeds the 1 GB backend limit.');
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const response = await api.uploadRepository(selectedFile);
      setUploadResult(response);
      setRepositories((current) => [
        {
          repository_id: response.repository_id,
          repository_name: response.summary.repository_name,
          file_count: response.summary.file_count,
          total_size_bytes: response.summary.total_size_bytes,
          languages: response.summary.languages,
          directories: [],
          important_files: [],
          indexed_chunk_count: response.indexing.indexed_chunks,
          indexing_status: 'indexed',
        },
        ...current,
      ]);
      setSelectedRepositoryId(response.repository_id);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed.');
    } finally {
      setUploading(false);
      setSelectedFile(null);
      const input = document.getElementById('zip-upload-input') as HTMLInputElement | null;
      if (input) input.value = '';
    }
  };

  const handleLoadManualRepository = async () => {
    const trimmedId = manualRepositoryId.trim();
    if (!trimmedId) {
      setError('Please enter a repository ID.');
      return;
    }

    setLoadingManualRepository(true);
    setError(null);
    try {
      const detail = await api.getRepository(trimmedId);
      if (detail) {
        setSelectedRepositoryId(trimmedId);
        setManualRepositoryId('');
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : `Repository ID "${trimmedId}" not found.`);
    } finally {
      setLoadingManualRepository(false);
    }
  };

  const handleSearch = async () => {
    if (!selectedRepositoryId) {
      setError('Select a repository before searching.');
      return;
    }
    if (!searchQuery.trim()) {
      setError('Enter a search query.');
      return;
    }

    const repositoryId = selectedRepositoryId;
    setSearching(true);
    setError(null);
    try {
      const results = await api.searchRepository(repositoryId, searchQuery, 5);
      if (selectedRepositoryIdRef.current === repositoryId) {
        setSearchResults(results.results ?? []);
      }
    } catch (searchError) {
      if (selectedRepositoryIdRef.current === repositoryId) {
        setError(searchError instanceof Error ? searchError.message : 'Search failed.');
      }
    } finally {
      setSearching(false);
    }
  };

  const handleSendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const submittedMessage = message.trim();
    if (!selectedRepositoryId || !submittedMessage || sendingMessage) return;

    setSendingMessage(true);
    setError(null);

    let activeConversationId = selectedConversationId;
    let newlyCreatedConversation: ConversationSummary | null = null;
    const previousMessageIds = new Set(conversation?.messages.map((entry) => entry.id) ?? []);

    try {
      // If the user starts typing before selecting/creating a conversation,
      // create one on submit instead of leaving the input permanently disabled.
      if (!activeConversationId) {
        const created = await api.createConversation(selectedRepositoryId, submittedMessage.slice(0, 60) || 'New conversation');
        newlyCreatedConversation = created;
        activeConversationId = created.id;
        setSelectedConversationId(created.id);
        window.localStorage.setItem(conversationStorageKey(selectedRepositoryId), created.id);
      }

      const response = await api.sendConversationMessage(
        selectedRepositoryId,
        activeConversationId,
        submittedMessage,
      );

      setConversation((current) => {
        const baseConversation = current?.id === activeConversationId
          ? current
          : newlyCreatedConversation;
        if (!baseConversation) return current;
        return {
          ...baseConversation,
          updated_at: response.assistant_message.created_at,
          messages: [
            ...(current?.id === activeConversationId ? current.messages : []),
            response.user_message,
            response.assistant_message,
          ],
        };
      });
      setMessage('');
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : 'Unable to send this message.');

      if (activeConversationId) {
        try {
          const persisted = await api.getConversation(selectedRepositoryId, activeConversationId);
          setConversation(persisted);
          const userMessage = persisted.messages[persisted.messages.length - 2];
          const assistantMessage = persisted.messages[persisted.messages.length - 1];
          const requestWasCommitted = userMessage?.role === 'user'
            && assistantMessage?.role === 'assistant'
            && userMessage.content === submittedMessage
            && !previousMessageIds.has(userMessage.id);
          if (requestWasCommitted) {
            setMessage('');
            setError(null);
          }
        } catch (reloadError) {
          setError(
            `${sendError instanceof Error ? sendError.message : 'Unable to send this message.'} `
            + `Conversation refresh failed: ${reloadError instanceof Error ? reloadError.message : 'unknown error'}`,
          );
        }
      }
    } finally {
      setSendingMessage(false);
    }
  };

  const selectedRepository = repositories.find((repo) => repo.repository_id === selectedRepositoryId) ?? null;
  const groupedSearchResults = searchResults.reduce<Record<string, SearchResult[]>>((groups, result) => {
    (groups[result.file_path] ??= []).push(result);
    return groups;
  }, {});

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>Repository Intelligence Assistant</h1>
        </div>
        <div className="repository-id-input-group">
          <div>
            <label htmlFor="manual-repo-id" className="repository-id-label">Repository ID</label>
            <div className="repository-id-row">
              <input
                id="manual-repo-id"
                type="text"
                value={manualRepositoryId}
                onChange={(event) => setManualRepositoryId(event.target.value)}
                placeholder="Enter repository ID"
                className="repository-id-input"
                disabled={loadingManualRepository}
                onKeyPress={(event) => {
                  if (event.key === 'Enter') {
                    void handleLoadManualRepository();
                  }
                }}
              />
              <button
                type="button"
                onClick={() => void handleLoadManualRepository()}
                disabled={loadingManualRepository || !manualRepositoryId.trim()}
                className="load-repo-button"
              >
                {loadingManualRepository ? 'Loading...' : 'Load'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="workspace-grid">
        <aside className="sidebar">
          <section className="panel">
            <h2>Upload repository</h2>
            <label className="repository-select-label" htmlFor="repository-select">Selected repository</label>
            <select
              id="repository-select"
              value={selectedRepositoryId}
              onChange={(event) => setSelectedRepositoryId(event.target.value)}
              disabled={sendingMessage || uploading || repositories.length === 0}
            >
              <option value="">Select a repository</option>
              {repositories.map((repository) => (
                <option key={repository.repository_id} value={repository.repository_id}>
                  {repository.repository_name}
                </option>
              ))}
            </select>
            <form onSubmit={handleUpload} className="upload-form">
              <label className="file-picker">
                <input id="zip-upload-input" type="file" accept=".zip" onChange={handleFileSelection} disabled={sendingMessage} />
                <span>{selectedFile ? selectedFile.name : 'Choose ZIP archive'}</span>
              </label>
              <button type="submit" disabled={uploading || sendingMessage || !selectedFile}>
                {uploading ? 'Uploading...' : 'Upload repository'}
              </button>
            </form>
            <p className="muted-copy">ZIP limit: 1 GB. Extracted contents are limited to 100 MB and 2,000 entries.</p>
            {uploadResult ? (
              <div className="card-success">
                <strong>Repository uploaded</strong>
                <p>ID: {uploadResult.repository_id}</p>
                <p>{uploadResult.summary.file_count} files • {uploadResult.chunking.chunk_count} indexed chunks</p>
              </div>
            ) : null}
          </section>
        </aside>

        <section className="content">
          <section className="panel metrics-panel">
            <h2>Repository overview</h2>
            {selectedRepository ? (
              <div className="metrics-grid">
                <div className="metric-card"><span>File count</span><strong>{selectedRepository.file_count}</strong></div>
                <div className="metric-card"><span>Storage</span><strong>{formatBytes(selectedRepository.total_size_bytes)}</strong></div>
                <div className="metric-card"><span>Indexed chunks</span><strong>{selectedRepository.indexed_chunk_count}</strong></div>
                <div className="metric-card"><span>Languages</span><strong>{Object.keys(selectedRepository.languages).length}</strong></div>
              </div>
            ) : (
              <p className="empty-state">Choose a repository to view its metadata.</p>
            )}
            {repositoryDetail ? (
              <div className="metadata-block">
                <p><strong>ID:</strong> {repositoryDetail.repository_id}</p>
                <p><strong>Languages:</strong> {formatLanguageSummary(repositoryDetail.languages)}</p>
                <p><strong>Important files:</strong> {repositoryDetail.important_files.length > 0 ? repositoryDetail.important_files.join(', ') : 'None found'}</p>
              </div>
            ) : null}
          </section>

          <nav className="feature-nav" aria-label="Repository features" role="tablist">
            {featureSections.map((feature) => (
              <button
                key={feature.id}
                type="button"
                role="tab"
                aria-selected={activeFeature === feature.id}
                className={activeFeature === feature.id ? 'feature-tab active' : 'feature-tab'}
                onClick={() => setActiveFeature(feature.id)}
              >
                {feature.label}
              </button>
            ))}
          </nav>

          {activeFeature === 'search' ? <section className="panel">
            <h2>Search repository</h2>
            <p className="muted-copy">Hybrid keyword and semantic search across indexed code, with source paths and line ranges.</p>
            <div className="search-row">
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search for code or concepts"
              />
              <button type="button" onClick={() => void handleSearch()} disabled={searching || !selectedRepositoryId}>
                {searching ? 'Searching...' : 'Search'}
              </button>
            </div>
            {searchResults.length > 0 ? (
              <div className="result-list">
                {Object.entries(groupedSearchResults).map(([filePath, results]) => (
                  <section className="search-file-group" key={filePath}>
                    <h3>{filePath}</h3>
                    {results.map((result, index) => (
                      <article key={`${result.file_path}-${result.start_line}-${index}`} className="result-card">
                        <div className="result-header"><strong>{result.symbol_name ?? 'Module'}</strong><span>{result.chunk_type}</span></div>
                        <p className="path-line">Lines {result.start_line}-{result.end_line}</p>
                        <pre>{result.content}</pre>
                      </article>
                    ))}
                  </section>
                ))}
              </div>
            ) : (
              <p className="empty-state">No search results yet for this repository.</p>
            )}
          </section> : null}

          {activeFeature === 'assistant' ? <section className="panel chat-panel">
            <div className="chat-heading">
              <div>
                <h2>{conversation?.title || 'Repository conversation'}</h2>
                <p className="muted-copy">
                  {selectedRepository ? `Grounded in ${selectedRepository.repository_name}` : 'Select a repository to begin'}
                </p>
              </div>
              {conversation ? <time dateTime={conversation.created_at}>Started {formatTimestamp(conversation.created_at)}</time> : null}
            </div>

            <div className="message-history" aria-live="polite">
              {conversationLoading ? (
                <p className="empty-state">Loading conversation...</p>
              ) : !selectedConversationId ? (
                <p className="empty-state">Choose a previous conversation or create a new one.</p>
              ) : conversation && conversation.messages.length > 0 ? (
                conversation.messages.map((entry) => (
                  <article key={entry.id} className={`chat-message ${entry.role}`}>
                    <div className="message-meta">
                      <strong>{entry.role === 'user' ? 'You' : 'Assistant'}</strong>
                      <time dateTime={entry.created_at}>{formatTimestamp(entry.created_at)}</time>
                    </div>
                    {entry.role === 'assistant' ? (
                      <div className="message-content">
                        <AssistantAnswer content={entry.content} sources={entry.metadata.sources} />
                      </div>
                    ) : (
                      <p className="message-content">{entry.content}</p>
                    )}
                    {entry.role === 'assistant' && entry.metadata.sources?.length ? (
                      <div className="message-sources">
                        <h3>Sources</h3>
                        {entry.metadata.sources.map((source, index) => (
                          <div className="message-source" key={`${source.file_path}-${source.start_line ?? index}-${index}`}>
                            <strong>{source.file_path}</strong>
                            {source.start_line != null || source.end_line != null ? (
                              <span>Lines {source.start_line ?? '?'}-{source.end_line ?? '?'}</span>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <p className="empty-state">Ask a question to start this conversation.</p>
              )}
              {sendingMessage ? <p className="typing-state">Searching repository and generating an answer...</p> : null}
            </div>

            <form className="message-form" onSubmit={(event) => void handleSendMessage(event)}>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder={selectedRepositoryId
                  ? 'Ask a question or follow up on the conversation'
                  : 'Select or upload a repository before asking a question'}
                rows={3}
                maxLength={2000}
                disabled={sendingMessage}
                aria-label="Your question"
              />
              <div className="message-form-footer">
                <span className="muted-copy">Follow-up questions use this conversation's context.</span>
                <button
                  type="submit"
                  disabled={!selectedRepositoryId || (Boolean(selectedConversationId) && conversationLoading) || !message.trim() || sendingMessage}
                >
                  {sendingMessage ? 'Answering...' : 'Send question'}
                </button>
              </div>
            </form>
          </section> : null}

          {activeFeature === 'dependencies' ? (
            <DependencyExplorer repositoryId={selectedRepositoryId} />
          ) : null}
          {activeFeature === 'intelligence' ? (
            <CodeIntelligencePanel repositoryId={selectedRepositoryId} />
          ) : null}
          {activeFeature === 'review' ? (
            <CodeReviewPanel repositoryId={selectedRepositoryId} />
          ) : null}
        </section>
      </main>

      {error ? (
        <div className="toast-error" role="alert">
          <span>{error}</span>
          <button type="button" aria-label="Dismiss error" onClick={() => setError(null)}>Dismiss</button>
        </div>
      ) : null}
    </div>
  );
}

export default App;
