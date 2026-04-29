import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import { getAuthHeader } from '../../auth.js';
import { normalize, injectPassageMark } from '../../utils/highlight.js';

import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function PDFViewer({ filename, passage }) {
  const [pdfData, setPdfData] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [targetPage, setTargetPage] = useState(null);
  const [error, setError] = useState(false);
  const [containerWidth, setContainerWidth] = useState(460);
  const containerRef = useRef(null);
  const pageRefs = useRef({});

  // Track container width so PDF pages fit inside the panel
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width;
      if (w) setContainerWidth(Math.max(200, w - 24));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    setPdfData(null);
    setNumPages(0);
    setError(false);
    setTargetPage(null);
    pageRefs.current = {};
    (async () => {
      try {
        const headers = await getAuthHeader();
        const res = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        setPdfData(new Uint8Array(buf));
      } catch (_) {
        setError(true);
      }
    })();
  }, [filename]);

  const onLoadSuccess = useCallback(async (pdf) => {
    setNumPages(pdf.numPages);
    if (!passage) return;
    const normPassage = normalize(passage);
    for (let p = 1; p <= pdf.numPages; p++) {
      const page = await pdf.getPage(p);
      const tc = await page.getTextContent();
      const pageText = tc.items.map(it => it.str ?? '').join(' ');
      if (normalize(pageText).includes(normPassage)) {
        setTargetPage(p);
        break;
      }
    }
  }, [passage]);

  // Scroll to target page once it's in the DOM
  useEffect(() => {
    if (!targetPage) return;
    const el = pageRefs.current[targetPage];
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [targetPage]);

  // After a page renders, inject the passage mark into its text layer
  const onPageRenderSuccess = useCallback((pageNum) => {
    if (!passage || pageNum !== targetPage) return;
    const pageEl = pageRefs.current[pageNum];
    if (!pageEl) return;
    // react-pdf puts the text layer in a child with this class
    const textLayer = pageEl.querySelector('.react-pdf__Page__textContent');
    if (!textLayer) return;
    // Small delay to let react-pdf finish positioning the spans
    setTimeout(() => {
      const mark = injectPassageMark(textLayer, passage);
      if (mark) mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 80);
  }, [passage, targetPage]);

  // Stable object reference — prevents react-pdf from reloading on every render
  const pdfFile = useMemo(() => (pdfData ? { data: pdfData } : null), [pdfData]);

  if (error) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      Impossible de charger le PDF.
    </div>
  );
  if (!pdfData) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      Loading...
    </div>
  );

  return (
    <div
      ref={containerRef}
      className="rb-scroll"
      style={{ flex: 1, overflow: 'auto', background: 'var(--bg-subtle, #f5f5f5)' }}
    >
      <Document
        file={pdfFile}
        onLoadSuccess={onLoadSuccess}
        onLoadError={() => setError(true)}
        loading={null}
        error={null}
      >
        {Array.from({ length: numPages }, (_, i) => i + 1).map(pageNum => (
          <div
            key={pageNum}
            ref={el => { pageRefs.current[pageNum] = el; }}
            style={{
              display: 'flex', justifyContent: 'center',
              marginBottom: 12,
              paddingTop: pageNum === 1 ? 12 : 0,
            }}
          >
            <Page
              pageNumber={pageNum}
              width={containerWidth}
              onRenderSuccess={() => onPageRenderSuccess(pageNum)}
              renderAnnotationLayer={false}
            />
          </div>
        ))}
      </Document>
    </div>
  );
}
