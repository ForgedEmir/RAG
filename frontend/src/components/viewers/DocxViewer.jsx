import { useState, useEffect, useRef } from 'react';
import { getAuthHeader } from '../../auth.js';
import { injectPassageMark } from '../../utils/highlight.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function DocxViewer({ filename, passage }) {
  const [html, setHtml] = useState(null);
  const [error, setError] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    setHtml(null);
    setError(false);
    (async () => {
      try {
        const headers = await getAuthHeader();
        const res = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error('fetch failed');
        const buf = await res.arrayBuffer();
        const mammoth = await import('mammoth');
        const result = await mammoth.convertToHtml({ arrayBuffer: buf });
        setHtml(result.value);
      } catch (_) {
        // Fallback: plain text
        try {
          const headers = await getAuthHeader();
          const res = await fetch(`/api/file-text/${encodeFilePath(filename)}`, { headers });
          if (res.ok) {
            const text = await res.text();
            setHtml(`<pre style="white-space:pre-wrap;font-size:12px;line-height:1.6">${text.replace(/</g, '&lt;')}</pre>`);
          } else {
            setError(true);
          }
        } catch (_2) {
          setError(true);
        }
      }
    })();
  }, [filename]);

  useEffect(() => {
    if (!containerRef.current || !html || !passage) return;
    const id = setTimeout(() => {
      const mark = injectPassageMark(containerRef.current, passage);
      if (mark) mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 50);
    return () => clearTimeout(id);
  }, [html, passage]);

  if (error) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Impossible de charger le fichier.</div>;
  if (html === null) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Chargement…</div>;

  return (
    <div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
      <div
        ref={containerRef}
        className="docviewer-docx"
        style={{ padding: '24px 32px', fontSize: 13, lineHeight: 1.8, color: 'var(--fg-primary)', maxWidth: 800, margin: '0 auto' }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
