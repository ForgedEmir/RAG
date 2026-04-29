import { useState, useEffect, useRef } from 'react';
import { getAuthHeader } from '../../auth.js';
import { findPassage } from '../../utils/highlight.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

const LANG_MAP = { json: 'json', xml: 'xml', csv: 'plaintext', txt: 'plaintext' };

export default function TextViewer({ filename, passage }) {
  const [content, setContent] = useState(null);
  const [error, setError] = useState(false);
  const [highlightedHtml, setHighlightedHtml] = useState(null);
  const markRef = useRef(null);

  const ext = filename.split('.').pop()?.toLowerCase();

  useEffect(() => {
    setContent(null);
    setError(false);
    setHighlightedHtml(null);
    getAuthHeader().then(headers =>
      fetch(`/api/file-text/${encodeFilePath(filename)}`, { headers })
        .then(r => r.ok ? r.text() : Promise.reject())
        .then(text => setContent(text))
        .catch(() => setError(true))
    );
  }, [filename]);

  useEffect(() => {
    if (content === null || passage) { setHighlightedHtml(null); return; }
    const lang = LANG_MAP[ext] || 'plaintext';
    if (lang === 'plaintext') { setHighlightedHtml(null); return; }
    import('highlight.js/lib/core').then(async ({ default: hljs }) => {
      if (lang === 'json') {
        const { default: json } = await import('highlight.js/lib/languages/json');
        hljs.registerLanguage('json', json);
      } else if (lang === 'xml') {
        const { default: xml } = await import('highlight.js/lib/languages/xml');
        hljs.registerLanguage('xml', xml);
      }
      try {
        const result = hljs.highlight(content, { language: lang });
        setHighlightedHtml(result.value);
      } catch (_) {
        setHighlightedHtml(null);
      }
    }).catch(() => setHighlightedHtml(null));
  }, [content, passage, ext]);

  useEffect(() => {
    if (markRef.current) {
      markRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [content, passage]);

  if (error) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Impossible de charger le file.</div>;
  if (content === null) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Loading...</div>;

  const preStyle = { whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'var(--font-mono)', lineHeight: 1.6, padding: 20 };

  if (passage) {
    const found = findPassage(content, passage);
    if (found) {
      return (
        <div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
          <pre style={preStyle}>
            {found.before}
            <mark ref={markRef} style={{ background: 'rgba(250,204,21,0.45)', borderRadius: 3, padding: '1px 0', color: 'inherit' }}>{found.match}</mark>
            {found.after}
          </pre>
        </div>
      );
    }
    return (
      <div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
        <div style={{ margin: '12px 20px 0', padding: '8px 12px', background: 'rgba(250,204,21,0.15)', border: '1px solid rgba(250,204,21,0.4)', borderRadius: 6, fontSize: 12, lineHeight: 1.5 }}>
          <span style={{ fontWeight: 600, color: '#b45309', marginRight: 6 }}>Cited passage:</span>{passage}
        </div>
        <pre style={preStyle}>{content}</pre>
      </div>
    );
  }

  if (highlightedHtml) {
    return (
      <div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
        <pre style={preStyle}>
          <code dangerouslySetInnerHTML={{ __html: highlightedHtml }} />
        </pre>
      </div>
    );
  }

  return (
    <div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
      <pre style={preStyle}>{content}</pre>
    </div>
  );
}
