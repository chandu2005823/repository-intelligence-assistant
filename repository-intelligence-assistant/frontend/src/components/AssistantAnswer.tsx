import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { visit } from 'unist-util-visit';
import type { Link, Root } from 'mdast';
import type { Plugin } from 'unified';

import type { ConversationSource } from '../types';

interface AssistantAnswerProps {
  content: string;
  sources?: ConversationSource[];
}

const remarkSourceCitations: Plugin<[], Root> = () => (tree) => {
  visit(tree, 'text', (node, index, parent) => {
    if (!parent || index === undefined) return;

    const matches = [...node.value.matchAll(/\[SOURCE (\d+)\]/g)];
    if (matches.length === 0) return;

    const replacements: Array<Link | { type: 'text'; value: string }> = [];
    let cursor = 0;
    for (const match of matches) {
      const start = match.index;
      if (start > cursor) {
        replacements.push({ type: 'text', value: node.value.slice(cursor, start) });
      }

      replacements.push({
        type: 'link',
        url: `#repo-source-${match[1]}`,
        children: [{ type: 'text', value: 'Source' }],
      });
      cursor = start + match[0].length;
    }

    if (cursor < node.value.length) {
      replacements.push({ type: 'text', value: node.value.slice(cursor) });
    }

    parent.children.splice(index, 1, ...replacements);
    return index + replacements.length;
  });
};

export default function AssistantAnswer({ content, sources = [] }: AssistantAnswerProps) {
  const components: Components = {
    a({ node: _node, href, children, ...props }) {
      void _node;
      const citation = href?.match(/^#repo-source-(\d+)$/);
      if (citation) {
        const source = sources[Number(citation[1]) - 1];
        if (!source?.file_path) {
          return <span className="source-citation">Source unavailable</span>;
        }

        const hasLines = source.start_line != null || source.end_line != null;
        const lineRange = hasLines
          ? `, Lines ${source.start_line ?? '?'}-${source.end_line ?? '?'}`
          : '';

        return (
          <span className="source-citation">
            Source: <code>{source.file_path}</code>{lineRange}
          </span>
        );
      }

      return <a href={href} {...props}>{children}</a>;
    },
    pre({ children }) {
      return <pre className="markdown-code-block">{children}</pre>;
    },
    table({ node: _node, children, ...props }) {
      void _node;
      return (
        <div className="markdown-table-wrap">
          <table {...props}>{children}</table>
        </div>
      );
    },
  };

  return (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkSourceCitations]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
