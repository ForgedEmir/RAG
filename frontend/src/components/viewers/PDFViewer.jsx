import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import { getAuthHeader } from '../../auth.js';
import { normalize, highlightPdfLayer } from '../../utils/highlight.js';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function PDFViewer({ filename, passage }) {
  const { t } = useTranslation();
  const [blobUrl, setBlobUrl]       = useState(null);
  const [error, setError]           = useState(false);
  const [numPages, setNumPages]     = useState(null);
  const [pdfDoc, setPdfDoc]         = useState(null);
  const [targetPage, setTargetPage] = useState(null);
  const [pageWidth, setPageWidth]   = useState(480);

  const prevUrl        = useRef(null);
  const scrollRef      = useRef(null);
  const pageRefs       = useRef({});
  const highlightDone  = useRef(false);
  const pendingPages   = useRef(new Set());

  // ── Load PDF (authenticated) ────────────────────────────────────────────────
  useEffect(() => {
    setBlobUrl(null);
    setError(false);
    setNumPages(null);
    setPdfDoc(null);
    setTargetPage(null);
    highlightDone.current = false;
    pendingPages.current  = new Set();
    pageRefs.current      = {};

    let cancelled = false;
    (async () => {
      try {
        const headers = await getAuthHeader();
        const res = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
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

  // Track container width so pages fill the panel without overflowing
  useEffect(() => {
    if (!scrollRef.current) return;
    const ro = new ResizeObserver(entries => {
      const w = entries[0].contentRect.width;
      setPageWidth(Math.max(280, w - 32));
    });
    ro.observe(scrollRef.current);
    return () => ro.disconnect();
  }, []);

  // ── Document loaded — save proxy + page count ───────────────────────────────
  const onDocLoad = useCallback((pdf) => {
    setNumPages(pdf.numPages);
    setPdfDoc(pdf);
  }, []);

  // ── Find which page contains the passage ────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc || !numPages) return;
    if (!passage) { setTargetPage(null); return; }

    const needle = normalize(passage).toLowerCase().slice(0, 80);
    let cancelled = false;

    (async () => {
      for (let p = 1; p <= numPages; p++) {
        try {
          const page    = await pdfDoc.getPage(p);
          const content = await page.getTextContent();
          const text    = normalize(
            content.items.map(i => i.str || '').join(' ')
          ).toLowerCase();
          if (text.includes(needle.slice(0, 50))) {
            if (!cancelled) setTargetPage(p);
            return;
          }
        } catch (_) {}
      }
      // Passage not found in any page — stay on page 1
    })();
    return () => { cancelled = true; };
  }, [pdfDoc, passage, numPages]);

  // ── Apply highlight + scroll once targetPage is known ───────────────────────
  const tryHighlight = useCallback((pageNum) => {
    if (!passage || highlightDone.current) return;
    if (targetPage !== null && pageNum !== targetPage) return;

    const wrapper   = pageRefs.current[pageNum];
    if (!wrapper) return;
    const textLayer = wrapper.querySelector('.react-pdf__Page__textContent');
    if (!textLayer) return;

    // Text layer spans may not be fully laid out yet — small delay
    setTimeout(() => {
      const first = highlightPdfLayer(textLayer, passage);
      if (first) {
        highlightDone.current = true;
        first.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 60);
  }, [passage, targetPage]);

  // When targetPage changes, retry on any already-rendered pending pages
  useEffect(() => {
    if (targetPage === null) return;
    pendingPages.current.forEach(p => tryHighlight(p));
  }, [targetPage, tryHighlight]);

  // ── Per-page render callback ─────────────────────────────────────────────────
  const onPageRender = useCallback((pageNum) => {
    pendingPages.current.add(pageNum);
    tryHighlight(pageNum);
  }, [tryHighlight]);

  // ── UI ──────────────────────────────────────────────────────────────────────
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
          <div
            key={p}
            ref={el => { pageRefs.current[p] = el; }}
            style={{ marginBottom: 10, display: 'flex', justifyContent: 'center' }}
          >
            <Page
              pageNumber={p}
              renderTextLayer={true}
              renderAnnotationLayer={false}
              width={pageWidth}
              onRenderSuccess={() => onPageRender(p)}
            />
          </div>
        ))}
      </Document>
    </div>
  );
}
