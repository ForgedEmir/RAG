import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import { getAuthHeader } from '../../auth.js';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function PptxViewer({ filename }) {
  const { t } = useTranslation();
  const [blobUrl, setBlobUrl] = useState(null);
  const [error, setError]     = useState(false);
  const [numPages, setNumPages] = useState(null);
  const [pageWidth, setPageWidth] = useState(480);

  const prevUrl   = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    setBlobUrl(null);
    setError(false);
    setNumPages(null);

    let cancelled = false;
    (async () => {
      try {
        const headers = await getAuthHeader();
        const res = await fetch(`/api/file-preview/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        if (cancelled) return;
        const url = URL.createObjectURL(new Blob([buf], { type: 'application/pdf' }));
        if (prevUrl.current) URL.revokeObjectURL(prevUrl.current);
        prevUrl.current = url;
        setBlobUrl(url);
      } catch (_) {
        if (!cancelled) setError(true);
      }
    })();
    return () => { cancelled = true; };
  }, [filename]);

  useEffect(() => () => {
    if (prevUrl.current) URL.revokeObjectURL(prevUrl.current);
  }, []);

  useEffect(() => {
    if (!scrollRef.current) return;
    const ro = new ResizeObserver(entries => {
      const w = entries[0].contentRect.width;
      setPageWidth(Math.max(280, w - 32));
    });
    ro.observe(scrollRef.current);
    return () => ro.disconnect();
  }, []);

  const onDocLoad = useCallback((pdf) => setNumPages(pdf.numPages), []);

  if (error) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      {t('viewer.error_load')}
    </div>
  );
  if (!blobUrl) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      {t('viewer.loading')}
    </div>
  );

  return (
    <div
      ref={scrollRef}
      className="rb-scroll"
      style={{ flex: 1, overflow: 'auto', background: '#525659', padding: '16px 0' }}
    >
      <Document
        file={blobUrl}
        onLoadSuccess={onDocLoad}
        loading={null}
        error={
          <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: '#f87171' }}>
            {t('viewer.error_load')}
          </div>
        }
      >
        {numPages && Array.from({ length: numPages }, (_, i) => i + 1).map(p => (
          <div key={p} style={{ marginBottom: 10, display: 'flex', justifyContent: 'center' }}>
            <Page
              pageNumber={p}
              renderTextLayer={true}
              renderAnnotationLayer={false}
              width={pageWidth}
            />
          </div>
        ))}
      </Document>
    </div>
  );
}
