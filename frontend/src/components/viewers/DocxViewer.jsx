import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { getAuthHeader } from '../../auth.js';
import { injectPassageMark, highlightPdfLayer } from '../../utils/highlight.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function DocxViewer({ filename, passage }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState('loading'); // 'loading' | 'ok' | 'error'
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    setStatus('loading');
    let cancelled = false;
    (async () => {
      try {
        const headers = await getAuthHeader();
        const res     = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        if (cancelled) return;
        containerRef.current.innerHTML = '';
        const { renderAsync } = await import('docx-preview');
        await renderAsync(buf, containerRef.current, null, {
          className: 'docx-preview', inWrapper: true, ignoreWidth: true,
          ignoreHeight: true, renderHeaders: true, renderFooters: true,
          renderFootnotes: true, useBase64URL: true,
        });
        if (cancelled) return;
        setStatus('ok');
      } catch (_) {
        if (!cancelled) setStatus('error');
      }
    })();
    return () => { cancelled = true; };
  }, [filename]);

  useEffect(() => {
    if (status !== 'ok' || !passage || !containerRef.current) return;
    let attempt = 0, tid;
    const tryMark = () => {
      let el = injectPassageMark(containerRef.current, passage);
      if (!el) el = highlightPdfLayer(containerRef.current, passage);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
      {t('viewer.error_load_doc')}
    </div>
  );

  return (
    <div className="rb-scroll" style={{ flex: 1, overflow: 'auto', background: '#f5f5f5' }}>
      {status === 'loading' && (
        <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
          {t('viewer.loading')}
        </div>
      )}
      <div ref={containerRef} style={{ display: status === 'loading' ? 'none' : 'block' }} />
    </div>
  );
}
