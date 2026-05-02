import { useState, useEffect, useRef } from 'react';
import { getAuthHeader } from '../../auth.js';
import { injectPassageMark } from '../../utils/highlight.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function DocxViewer({ filename, passage }) {
  const [status, setStatus]       = useState('loading'); // 'loading' | 'ok' | 'error'
  const [markFound, setMarkFound] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    setStatus('loading');
    setMarkFound(false);

    let cancelled = false;
    (async () => {
      try {
        const headers = await getAuthHeader();
        const res     = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        if (cancelled) return;

        // Clear previous render
        containerRef.current.innerHTML = '';

        const { renderAsync } = await import('docx-preview');
        await renderAsync(buf, containerRef.current, null, {
          className:       'docx-preview',
          inWrapper:       true,
          ignoreWidth:     true,
          ignoreHeight:    true,
          renderHeaders:   true,
          renderFooters:   true,
          renderFootnotes: true,
          useBase64URL:    true,
        });
        if (cancelled) return;
        setStatus('ok');
      } catch (_) {
        if (!cancelled) setStatus('error');
      }
    })();

    return () => { cancelled = true; };
  }, [filename]);

  // Inject passage highlight after render
  useEffect(() => {
    if (status !== 'ok' || !passage || !containerRef.current) {
      setMarkFound(false);
      return;
    }
    setMarkFound(false);
    let attempt = 0;
    let tid;
    const tryMark = () => {
      const mark = injectPassageMark(containerRef.current, passage);
      if (mark) {
        setMarkFound(true);
        mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else if (attempt < 3) {
        attempt++;
        tid = setTimeout(tryMark, 80 * attempt);
      }
    };
    tid = setTimeout(tryMark, 80);
    return () => clearTimeout(tid);
  }, [status, passage]);

  if (status === 'error') return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      Impossible de charger le document.
    </div>
  );

  return (
    <div className="rb-scroll" style={{ flex: 1, overflow: 'auto', background: '#f5f5f5' }}>
      {status === 'loading' && (
        <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
          Chargement…
        </div>
      )}
      {/* Passage cité — toujours affiché au-dessus du document */}
      {passage && status === 'ok' && (
        <div style={{ margin: '12px 16px 0', padding: '8px 12px', background: 'rgba(250,204,21,0.15)', border: '1px solid rgba(250,204,21,0.4)', borderRadius: 6, fontSize: 12, lineHeight: 1.5 }}>
          <span style={{ fontWeight: 600, color: '#b45309', marginRight: 6 }}>Passage cité :</span>{passage}
        </div>
      )}
      <div
        ref={containerRef}
        style={{ display: status === 'loading' ? 'none' : 'block' }}
      />
    </div>
  );
}
