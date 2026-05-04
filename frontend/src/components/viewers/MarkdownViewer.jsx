import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';
import { getAuthHeader } from '../../auth.js';
import { injectPassageMark, highlightPdfLayer } from '../../utils/highlight.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

// Strip Markdown syntax so a raw-md passage matches the rendered plain-text DOM.
function stripMarkdown(s) {
  return s
    .replace(/```[\s\S]*?```/g, m => m.replace(/```\w*\n?|```/g, ''))
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/(\*\*|__)(.+?)\1/gs, '$2')
    .replace(/(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)/g, '$1')
    .replace(/(?<!_)_(?!_)([^_\n]+?)_(?!_)/g, '$1')
    .replace(/~~(.+?)~~/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s{0,3}[-*+]\s+/gm, '')
    .replace(/^\s{0,3}\d+\.\s+/gm, '')
    .replace(/^\s{0,3}>\s?/gm, '')
    .replace(/^\s*[-*_]{3,}\s*$/gm, '');
}

export default function MarkdownViewer({ filename, passage }) {
  const [content, setContent] = useState(null);
  const [error, setError]     = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    setContent(null);
    setError(false);
    getAuthHeader().then(headers =>
      fetch(`/api/file-text/${encodeFilePath(filename)}`, { headers })
        .then(r => r.ok ? r.text() : Promise.reject())
        .then(text => setContent(text))
        .catch(() => setError(true))
    );
  }, [filename]);

  useEffect(() => {
    if (!containerRef.current || !content) return;
    if (!passage) {
      containerRef.current.querySelectorAll('mark[data-passage]').forEach(m => m.replaceWith(...m.childNodes));
      return;
    }
    const cleanPassage = stripMarkdown(passage);
    let attempt = 0, tid;
    const tryMark = () => {
      let el = injectPassageMark(containerRef.current, cleanPassage);
      if (!el) el = injectPassageMark(containerRef.current, passage);
      if (!el) el = highlightPdfLayer(containerRef.current, cleanPassage);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else if (attempt < 3) {
        attempt++;
        tid = setTimeout(tryMark, 80 * attempt);
      }
    };
    tid = setTimeout(tryMark, 60);
    return () => clearTimeout(tid);
  }, [content, passage]);

  if (error) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      Impossible de charger le fichier.
    </div>
  );
  if (content === null) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      Chargement…
    </div>
  );

  return (
    <div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
      <div
        ref={containerRef}
        className="docviewer-md"
        style={{ padding: '20px 24px', fontSize: 13, lineHeight: 1.7, color: 'var(--fg-primary)' }}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
