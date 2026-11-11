import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent } from 'react';

import { api } from '../services/api';
import AssistantAnswer from './AssistantAnswer';
import type {
  CodeIntelligenceResult,
  CodeReviewFinding,
  CodeReviewResult,
  DependencyGraph,
} from '../types';

interface RepositoryFeatureProps {
  repositoryId: string;
}

const severityClass = (severity: string) => `severity-${severity.toLowerCase()}`;

export function DependencyExplorer({ repositoryId }: RepositoryFeatureProps) {
  const [graph, setGraph] = useState<DependencyGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ pointerX: number; pointerY: number; x: number; y: number } | null>(null);

  useEffect(() => {
    let active = true;
    setGraph(null);
    setSelectedId('');
    if (!repositoryId) {
      setLoading(false);
      setError(null);
      return () => {
        active = false;
      };
    }

    setLoading(true);
    setError(null);
    void api.getDependencies(repositoryId)
      .then((result) => {
        if (active) setGraph(result);
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Unable to load dependencies.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [repositoryId]);

  const visibleNodes = useMemo(() => {
    const normalizedFilter = filter.trim().toLowerCase();
    return (graph?.nodes ?? [])
      .filter((node) => !normalizedFilter
        || node.path.toLowerCase().includes(normalizedFilter)
        || node.label.toLowerCase().includes(normalizedFilter))
      .slice(0, 120);
  }, [filter, graph]);
  const visibleIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes]);
  const visibleEdges = (graph?.edges ?? []).filter(
    (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
  );
  const selectedNode = graph?.nodes.find((node) => node.id === selectedId);
  const incoming = (graph?.edges ?? []).filter((edge) => edge.target === selectedId);
  const outgoing = (graph?.edges ?? []).filter((edge) => edge.source === selectedId);
  const nodeById = useMemo(
    () => new Map((graph?.nodes ?? []).map((node) => [node.id, node])),
    [graph],
  );
  const positions = useMemo(() => new Map(visibleNodes.map((node, index) => [
    node.id,
    { x: 105 + (index % 5) * 190, y: 65 + Math.floor(index / 5) * 115 },
  ])), [visibleNodes]);
  const svgHeight = Math.max(270, Math.ceil(visibleNodes.length / 5) * 115 + 45);

  const startPan = (event: ReactPointerEvent<SVGSVGElement>) => {
    if ((event.target as Element).closest('[data-graph-node]')) return;
    drag.current = { pointerX: event.clientX, pointerY: event.clientY, ...pan };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const movePan = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!drag.current) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    drag.current && setPan({
      x: drag.current.x + ((event.clientX - drag.current.pointerX) / bounds.width) * 1000 / zoom,
      y: drag.current.y + ((event.clientY - drag.current.pointerY) / bounds.height) * svgHeight / zoom,
    });
  };

  const handleZoom = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    setZoom((current) => Math.min(2.5, Math.max(0.55, current * (event.deltaY < 0 ? 1.1 : 0.9))));
  };

  if (!repositoryId) return <p className="empty-state">Select a repository to explore its dependencies.</p>;

  return (
    <section className="panel feature-panel">
      <div className="section-heading">
        <div>
          <h2>Dependency Explorer</h2>
          <p className="muted-copy">Resolved static imports between repository files.</p>
        </div>
        {graph ? <span className="muted-copy">{graph.nodes.length} files · {graph.edges.length} links</span> : null}
      </div>
      <input
        aria-label="Filter dependency graph by file"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        placeholder="Filter files by name or path"
      />
      {loading ? <p className="empty-state">Building dependency graph...</p> : null}
      {error ? <p className="feature-error" role="alert">{error}</p> : null}
      {!loading && !error && graph?.nodes.length === 0 ? (
        <p className="empty-state">No supported source files were found for dependency analysis.</p>
      ) : null}
      {graph && graph.nodes.length > 0 ? (
        <>
          <div className="graph-toolbar">
            <span className="muted-copy">
              Showing {visibleNodes.length} of {graph.nodes.length} files · drag canvas to pan · scroll to zoom
            </span>
            <button type="button" className="compact-button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>
              Reset view
            </button>
          </div>
          <div className="dependency-graph">
            {visibleNodes.length === 0 ? (
              <p className="empty-state">No files match this filter.</p>
            ) : (
              <svg
                viewBox={`0 0 1000 ${svgHeight}`}
                role="img"
                aria-label="Interactive dependency graph"
                onPointerDown={startPan}
                onPointerMove={movePan}
                onPointerUp={() => { drag.current = null; }}
                onPointerCancel={() => { drag.current = null; }}
                onWheel={handleZoom}
              >
                <defs>
                  <marker id="dependency-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                  </marker>
                </defs>
                <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
                  {visibleEdges.map((edge, index) => {
                    const source = positions.get(edge.source);
                    const target = positions.get(edge.target);
                    if (!source || !target) return null;
                    const selected = selectedId === edge.source || selectedId === edge.target;
                    return (
                      <line
                        key={`${edge.source}-${edge.target}-${index}`}
                        x1={source.x}
                        y1={source.y}
                        x2={target.x}
                        y2={target.y}
                        className={selected ? 'dependency-edge selected' : 'dependency-edge'}
                        markerEnd="url(#dependency-arrow)"
                      />
                    );
                  })}
                  {visibleNodes.map((node) => {
                    const point = positions.get(node.id);
                    if (!point) return null;
                    const connected = selectedId && (incoming.some((edge) => edge.source === node.id)
                      || outgoing.some((edge) => edge.target === node.id));
                    return (
                      <g
                        key={node.id}
                        data-graph-node
                        className={`dependency-node${selectedId === node.id ? ' selected' : ''}${connected ? ' connected' : ''}`}
                        transform={`translate(${point.x - 78} ${point.y - 28})`}
                        role="button"
                        tabIndex={0}
                        aria-label={`Select ${node.path}`}
                        onClick={() => setSelectedId(node.id)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            setSelectedId(node.id);
                          }
                        }}
                      >
                        <rect width="156" height="56" rx="10" />
                        <text x="10" y="23">{node.label.length > 21 ? `${node.label.slice(0, 18)}...` : node.label}</text>
                        <text className="dependency-node-path" x="10" y="41">
                          {node.path.length > 24 ? `...${node.path.slice(-21)}` : node.path}
                        </text>
                        <title>{node.path}</title>
                      </g>
                    );
                  })}
                </g>
              </svg>
            )}
          </div>
          {selectedNode ? (
            <div className="dependency-details">
              <strong>{selectedNode.path}</strong>
              <div className="dependency-neighbors">
                <div>
                  <h3>Imported by</h3>
                  {incoming.length ? incoming.map((edge) => (
                    <button className="text-link" type="button" key={`${edge.source}-${edge.target}`} onClick={() => setSelectedId(edge.source)}>
                      {nodeById.get(edge.source)?.path ?? edge.source}
                    </button>
                  )) : <span className="muted-copy">No resolved importers</span>}
                </div>
                <div>
                  <h3>Imports</h3>
                  {outgoing.length ? outgoing.map((edge) => (
                    <button className="text-link" type="button" key={`${edge.source}-${edge.target}`} onClick={() => setSelectedId(edge.target)}>
                      {nodeById.get(edge.target)?.path ?? edge.target}
                    </button>
                  )) : <span className="muted-copy">No resolved dependencies</span>}
                </div>
              </div>
            </div>
          ) : null}
          {graph.unresolved.length ? (
            <details className="unresolved-list">
              <summary>{graph.unresolved.length} imports could not be resolved statically</summary>
              <ul>
                {graph.unresolved.map((item, index) => (
                  <li key={`${item.file_path}-${item.module}-${index}`}>
                    <code>{item.file_path}</code> imports <code>{item.module}</code>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

export function CodeIntelligencePanel({ repositoryId }: RepositoryFeatureProps) {
  const [query, setQuery] = useState('');
  const [filePath, setFilePath] = useState('');
  const [result, setResult] = useState<CodeIntelligenceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const repositoryIdRef = useRef(repositoryId);
  repositoryIdRef.current = repositoryId;

  useEffect(() => {
    setResult(null);
    setError(null);
    setLoading(false);
  }, [repositoryId]);

  const analyze = async () => {
    const requestRepositoryId = repositoryId;
    setLoading(true);
    setError(null);
    try {
      const response = await api.getCodeIntelligence(
        requestRepositoryId,
        { query: query.trim(), file_path: filePath.trim() },
      );
      if (repositoryIdRef.current === requestRepositoryId) setResult(response);
    } catch (requestError) {
      if (repositoryIdRef.current === requestRepositoryId) {
        setError(requestError instanceof Error ? requestError.message : 'Code intelligence request failed.');
      }
    } finally {
      if (repositoryIdRef.current === requestRepositoryId) setLoading(false);
    }
  };

  if (!repositoryId) return <p className="empty-state">Select a repository to inspect its code.</p>;

  return (
    <section className="panel feature-panel">
      <h2>Code Intelligence</h2>
      <p className="muted-copy">Look up definitions and statically resolved calls, and see which files may be affected.</p>
      <div className="feature-controls">
        <input aria-label="Function or symbol" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Function, method, or class name" />
        <input aria-label="File path for impact analysis" value={filePath} onChange={(event) => setFilePath(event.target.value)} placeholder="Optional file path for impact analysis" />
        <button type="button" disabled={loading || (!query.trim() && !filePath.trim())} onClick={() => void analyze()}>
          {loading ? 'Analyzing...' : 'Analyze code'}
        </button>
      </div>
      {error ? <p className="feature-error" role="alert">{error}</p> : null}
      {result ? (
        <div className="intelligence-results">
          <div>
            <h3>Definitions</h3>
            {result.definitions.length ? result.definitions.map((definition, index) => (
              <article className="analysis-item" key={`${definition.file_path}-${definition.line}-${index}`}>
                <strong>{definition.name}</strong> <span>{definition.kind}</span>
                <p><code>{definition.file_path}</code>: {definition.line}{definition.end_line ? `-${definition.end_line}` : ''}</p>
              </article>
            )) : <p className="empty-state">No matching definitions found.</p>}
          </div>
          <div>
            <h3>Call relationships</h3>
            {result.calls.length ? result.calls.map((call, index) => (
              <article className="analysis-item" key={`${call.file_path}-${call.line}-${index}`}>
                <strong>{call.caller}</strong> calls <strong>{call.callee}</strong>
                <p><code>{call.file_path}</code>: {call.line} · {call.resolved ? 'Resolved statically' : 'Unresolved statically'}</p>
              </article>
            )) : <p className="empty-state">No statically supported call relationships found.</p>}
          </div>
          <div>
            <h3>Potentially affected files</h3>
            {result.impact.files.length ? (
              <ul className="impact-list">{result.impact.files.map((file) => <li key={file}><code>{file}</code></li>)}</ul>
            ) : <p className="empty-state">No affected files identified from static relationships.</p>}
            <p className="muted-copy">Static analysis is conservative; dynamic dispatch and runtime relationships may not be visible.</p>
          </div>
          {result.unresolved.length ? (
            <details className="unresolved-list">
              <summary>{result.unresolved.length} relationships were not resolved</summary>
              <ul>{result.unresolved.map((item, index) => <li key={index}>{JSON.stringify(item)}</li>)}</ul>
            </details>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function CodeReviewPanel({ repositoryId }: RepositoryFeatureProps) {
  const [findings, setFindings] = useState<CodeReviewFinding[] | null>(null);
  const [summary, setSummary] = useState('');
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState('');
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiSources, setAiSources] = useState<CodeReviewResult['ai_sources']>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const repositoryIdRef = useRef(repositoryId);
  repositoryIdRef.current = repositoryId;

  useEffect(() => {
    setFindings(null);
    setSummary('');
    setAiExplanation(null);
    setAiStatus('');
    setAiError(null);
    setAiSources([]);
    setError(null);
    setLoading(false);
  }, [repositoryId]);

  const runReview = async () => {
    const requestRepositoryId = repositoryId;
    setLoading(true);
    setError(null);
    try {
      const result = await api.reviewRepository(requestRepositoryId);
      if (repositoryIdRef.current === requestRepositoryId) {
        setFindings(result.findings);
        setSummary(result.summary ?? '');
        setAiExplanation(result.ai_explanation ?? null);
        setAiStatus(result.ai_status ?? '');
        setAiError(result.ai_error ?? null);
        setAiSources(result.ai_sources ?? []);
      }
    } catch (requestError) {
      if (repositoryIdRef.current === requestRepositoryId) {
        setError(requestError instanceof Error ? requestError.message : 'Code review failed.');
      }
    } finally {
      if (repositoryIdRef.current === requestRepositoryId) setLoading(false);
    }
  };

  if (!repositoryId) return <p className="empty-state">Select a repository to review its code.</p>;

  return (
    <section className="panel feature-panel">
      <div className="section-heading">
        <div>
          <h2>Code Review</h2>
          <p className="muted-copy">Review findings are advisory. The assistant does not edit your source files.</p>
        </div>
        <button type="button" disabled={loading} onClick={() => void runReview()}>
          {loading ? 'Reviewing...' : findings ? 'Run review again' : 'Review repository'}
        </button>
      </div>
      {error ? <p className="feature-error" role="alert">{error}</p> : null}
      {summary ? <p className="review-summary">{summary}</p> : null}
      {aiStatus === 'missing_api_key' ? (
        <p className="feature-error" role="status">AI explanations are unavailable: configure the API key for the selected LLM provider.</p>
      ) : null}
      {aiStatus === 'failed' ? <p className="feature-error" role="status">{aiError ?? 'AI explanation failed; static findings remain available.'}</p> : null}
      {aiExplanation ? (
        <article className="analysis-item">
          <h3>AI explanation</h3>
          <AssistantAnswer content={aiExplanation} sources={aiSources} />
        </article>
      ) : null}
      {loading ? <p className="empty-state">Checking repository source for actionable findings...</p> : null}
      {findings ? findings.length ? (
        <div className="review-findings">
          {findings.map((finding, index) => (
            <article className="review-finding" key={`${finding.file_path}-${finding.start_line}-${finding.title}-${index}`}>
              <div className="finding-heading">
                <span className={`severity-badge ${severityClass(finding.severity)}`}>{finding.severity}</span>
                <strong>{finding.title}</strong>
                {finding.status ? <span className="muted-copy">{finding.status}</span> : null}
              </div>
              <p className="path-line"><code>{finding.file_path}</code>: {finding.start_line}-{finding.end_line}</p>
              <p>{finding.description}</p>
              {finding.suggestion ? <p><strong>Suggested action:</strong> {finding.suggestion}</p> : null}
              {finding.confidence !== undefined ? <p className="muted-copy">Confidence: {finding.confidence}</p> : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">No findings were reported by the available checks.</p>
      ) : (
        <p className="empty-state">Run a review to see potential issues found in this repository.</p>
      )}
    </section>
  );
}
