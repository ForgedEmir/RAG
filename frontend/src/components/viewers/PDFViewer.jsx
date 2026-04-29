import { useState, useEffect, useRef, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import { getAuthHeader } from '../../auth.js';
import { normalize } from '../../utils/highlight.js';

// Vite: inline worker URL so pdfjs doesn't try to fetch from CDN
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function PDFViewer({ filename, passage }) {
  const [pdfData, setPdfData] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [targetPage, setTargetPage] = useState(null);
  const [matchItems, setMatchItems] = useState(null); // Set of item indices on targetPage
  const [error, setError] = useState(false);
  const pdfRef = useRef(null);
  const pageRefs = useRef({});

  useEffect(() => {
    setPdfData(null);
    setError(false);
    setTargetPage(null);
    setMatchItems(null);
    (async () => {
      try {
        const headers = await getAuthHeader();
        const res = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error('fetch failed');
        const buf = await res.arrayBuffer();
        setPdfData(new Uint8Array(buf));
      } catch (_) {
        setError(true);
      }
    })();
  }, [filename]);

  const onLoadSuccess = useCallback(async (pdf) => {
    pdfRef.current = pdf;
    setNumPages(pdf.numPages);
    if (!passage) return;

    const normPassage = normalize(passage);
    for (let p = 1; p <= pdf.numPages; p++) {
      const page = await pdf.getPage(p);
      const tc = await page.getTextContent();
      const items = tc.items;
      const pageText = items.map(it => it.str).join(' ');
      const normPage = normalize(pageText);
      if (normPage.indexOf(normPassage) !== -1) {
        // Find which item indices are part of the match
        const matchSet = new Set();
        let accumulated = '';
        const itemStarts = [];
        for (let i = 0; i < items.length; i++) {
          itemStarts.push(accumulated.length);
          accumulated += (i > 0 ? ' ' : '') + items[i].str;
        }
        const normAccum = normalize(accumulated);
        const matchStart = normAccum.indexOf(normPassage);
        const matchEnd = matchStart + normPassage.length;
        if (matchStart !== -1) {
          for (let i = 0; i < items.length; i++) {
            const ns = itemStarts[i];
            const ne = ns + items[i].str.length;
            if (ne > matchStart && ns < matchEnd) matchSet.add(i);
          }
        }
        setTargetPage(p);
        setMatchItems(matchSet);
        break;
      }
    }
  }, [passage]);

  useEffect(() => {
    if (targetPage && pageRefs.current[targetPage]) {
      pageRefs.current[targetPage].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [targetPage]);

  const customTextRenderer = useCallback(({ str, itemIndex }) => {
    if (!matchItems || !matchItems.has(itemIndex)) return str;
    const escaped = str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<mark style="background:rgba(250,204,21,0.55);border-radius:2px;color:inherit;padding:0">${escaped}</mark>`;
  }, [matchItems]);

  if (error) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Impossible de charger le PDF.</div>;
  if (!pdfData) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Chargement…</div>;

  return (
    <div className="rb-scroll" style={{ flex: 1, overflow: 'auto', background: 'var(--bg-subtle, #f5f5f5)' }}>
      <Document
        file={{ data: pdfData }}
        onLoadSuccess={onLoadSuccess}
        onLoadError={() => setError(true)}
        loading={null}
      >
        {Array.from({ length: numPages }, (_, i) => i + 1).map(pageNum => (
          <div
            key={pageNum}
            ref={el => { pageRefs.current[pageNum] = el; }}
            style={{ display: 'flex', justifyContent: 'center', marginBottom: 12, paddingTop: pageNum === 1 ? 12 : 0 }}
          >
            <Page
              pageNumber={pageNum}
              width={Math.min(700, window.innerWidth - 60)}
              customTextRenderer={matchItems ? customTextRenderer : undefined}
              renderAnnotationLayer={false}
            />
          </div>
        ))}
      </Document>
    </div>
  );
}
