import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';
import { getAuthHeader } from '../../auth.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function MarkdownViewer({ filename, passage }) {
  const [content, setContent] = useState(null);
  const [error, setError]         = useState(false);

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
      {/* Passage cité — toujours affiché au-dessus du document */}
      {passage && (
        <div style={{ margin: '12px 20px 0', padding: '8px 12px', background: 'rgba(250,204,21,0.15)', border: '1px solid rgba(250,204,21,0.4)', borderRadius: 6, fontSize: 12, lineHeight: 1.5 }}>
          <span style={{ fontWeight: 600, color: '#b45309', marginRight: 6 }}>Passage cité :</span>{passage}
        </div>
      )}
      <div className="docviewer-md" style={{ padding: '20px 24px', fontSize: 13, lineHeight: 1.7, color: 'var(--fg-primary)' }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
